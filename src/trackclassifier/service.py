import os
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from send2trash import send2trash
from threadpoolctl import threadpool_limits

from . import training_history
from .apply import FileVanishedError, move_to_folder, undo_move
from .audio_io import ANALYSIS_SR
from .cache import AnalysisCache
from .config import Config
from .extraction import extract_one
from .features import FeatureExtractor, HandcraftedExtractor, TrackAnalysis
from .key_detect import detect_key, detect_key_from_samples
from .keys import Key, is_harmonic_neighbor
from .labels import LABEL_ORDER, Label
from .library import Sha1Cache, TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel, weighted_f1
from .peaks import compute_bands
from .presentation import (
    KEY_SOURCE_AUDIO,
    KEY_SOURCE_NONE,
    KEY_SOURCE_TAG,
    VAZIO,
    PeaksStore,
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_key,
    read_tags,
)
from .profiles import nome_de
from .spectral import compute_spectra, track_bpm
from .training_history import TrainingEntry

_CACHE_SAVE_EVERY = 10

#: A cada quantas keys detectadas o lote salva o presentation.parquet.
#: `PresentationCache.save()` reescreve o parquet inteiro (e o ensure_key
#: o chama a cada track), entao salvar a cada key num acervo de milhares de
#: tracks gastaria mais I/O que o proprio chroma_cqt. 25 limita o prejuizo de
#: um kill -9 a ~25 tracks (alguns minutos de trabalho) sem pagar o parquet
#: a cada track. O cancelamento e o fim do lote salvam o resto.
_KEY_BATCH_SAVE_EVERY = 25


#: Threads nativas por worker, fixadas em 1 via ambiente.
#:
#: `extract_one` ja envolve a extracao em `threadpool_limits(limits=1)`, mas
#: no macOS isso e no-op: o BLAS do numpy aqui e o Accelerate da Apple, que o
#: threadpoolctl 3.x nao sabe controlar -- `threadpool_info()` devolve lista
#: vazia nesta plataforma. Isso NAO cura o segfault descrito em
#: `_empacotado()` abaixo -- foi medido reproduzindo com 2 threads e a mesma
#: stack. Fica porque a intencao original era essa, nao porque resolve algo.
_LIMITES_DE_THREAD = {
    "VECLIB_MAXIMUM_THREADS": "1",  # Accelerate (o BLAS do numpy no macOS)
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


#: Sobrescreve o teto de workers do scan. Adicionada para investigar o
#: segfault documentado em `_empacotado()` variando o teto sem pagar ~15 min
#: de rebuild do PyInstaller por tentativa. A causa raiz acabou sendo outra
#: (extracao rodando fora de subprocesso, nao o tamanho do pool) mas a
#: variavel continua util para limitar memoria numa biblioteca grande.
_ENV_MAX_WORKERS = "TRACKCLASSIFIER_MAX_WORKERS"


def _empacotado() -> bool:
    """True quando rodando de dentro do .app gerado pelo PyInstaller.

    Existe para uma unica decisao em `_analyze`: nunca chamar `extract_one`
    diretamente no processo principal quando empacotado.

    O gate `total > 1 and max_workers > 1` mais abaixo nasceu so para evitar
    o overhead de subir um subprocesso para 1 arquivo, e tem um efeito
    colateral que ninguem tinha testado: com `TRACKCLASSIFIER_MAX_WORKERS=1`,
    ou com qualquer teto quando so ha 1 pendente, `usa_pool` da False e
    `extract_one` roda direto na thread do CLI/janela. Numa sessao, esse
    caminho crashou 5/5 vezes no bundle (SIGSEGV em ~11s, uma track real de
    320kbps, sem pool nenhum) enquanto o pool rodava limpo no mesmo bundle.

    ISTO E CONTENCAO, NAO CURA -- a causa raiz continua ABERTA. Uma versao
    anterior desta docstring dizia que o crash era "deterministico, nao
    intermitente" e que o gatilho tinha sido isolado. Foi falsificado depois:
    um bundle reconstruido do mesmo commit pre-fix nao reproduz nada (240
    extracoes no processo principal, sequenciais e sem pinning, sob carga,
    zero crashes), e o binario do numpy e byte-identico entre o bundle que
    crashou e os que nao crasham (mesmo UUID no crash report e na venv), o
    que descarta build envenenado. Um bundle-sonda isolando cada camada
    (matmul, mel, STFT, HPSS, compute_spectra, decode, extract, extract_one,
    TrackService inteiro) tambem nunca crashou.

    Ou seja: intermitente, dependente de estado do ambiente, gatilho
    desconhecido. O unico invariante e a stack (chamada para o endereco 0 a
    partir de `generic_wrapped_legacy_loop`, sob
    `PyUFunc_GeneralizedFunctionInternal` -- um gufunc, provavelmente o
    matmul do banco de filtros mel) e que nao e OOM.

    O gate se justifica pelo mesmo motivo que a retentativa ja usava pool: um
    segfault num filho descartavel custa uma track, no processo principal
    custa a janela inteira. Nao o trate como prova de que a causa foi
    entendida -- se o crash voltar, pode voltar DENTRO de um worker.
    """
    return bool(getattr(sys, "frozen", False))


def _teto_de_workers() -> int:
    """Cap em 8: cada worker mantem simultaneamente um subprocesso ffmpeg mais
    copias em memoria do audio decodificado (buffer PCM, copia float32,
    intermediarios de STFT/HPSS/beat-tracking do librosa). Numa biblioteca
    real grande (centenas de tracks), deixar o default escalar sem limite com
    o numero de nucleos arrisca picos de memoria multi-GB. 8 ja satura o ganho
    pratico de paralelismo para essa carga.
    """
    bruto = os.environ.get(_ENV_MAX_WORKERS, "").strip()
    if bruto:
        try:
            pedido = int(bruto)
        except ValueError:
            pedido = 0
        if pedido > 0:
            return pedido
    return min(os.cpu_count() or 1, 8)


def _fixa_threads_dos_workers() -> None:
    """Pina as threads nativas dos workers. Ver _LIMITES_DE_THREAD.

    `setdefault` de proposito: quem exportou a variavel a mao antes de rodar
    o app esta depurando justamente isto, e sobrescrever esconderia o efeito.
    """
    for nome, valor in _LIMITES_DE_THREAD.items():
        os.environ.setdefault(nome, valor)


def _aquece_cache_numba() -> None:
    """Compila os gufuncs do numba de librosa ANTES de subir o pool.

    Esta e a causa raiz do segfault que `_empacotado()` so consegue conter:
    `librosa/util/utils.py` tem varios `@numba.guvectorize(cache=True)`
    (localmax, localmin, peak_pick) que `track_bpm` aciona via
    `librosa.beat.beat_track` a cada track. `cache=True` grava o codigo
    compilado em disco (dentro do bundle, em
    `Contents/Resources/librosa/util/__pycache__`) -- mas todo rebuild do
    .app apaga esse cache, e o primeiro scan depois de um build novo sobe ate
    8 workers ao mesmo tempo, todos com cache frio, todos tentando compilar E
    escrever no mesmo arquivo simultaneamente. Essa escrita concorrente
    corrompe o cache, e todo processo que depois LE o arquivo corrompido
    segfaulta executando o gufunc -- reproduzido 235/235 vezes contra 0/377
    rodando a mesma extracao com o cache ja aquecido por uma chamada serial
    antes. E por isso que o crash nunca aparece em `uv run dj`: sem rebuild
    de bundle apagando cache, a primeira execucao de sempre ja compila sem
    concorrencia nenhuma.

    Uma chamada, sem concorrencia, no processo PAI, resolve: compila e grava
    o cache uma unica vez antes de qualquer worker nascer, e todo spawn
    depois so LE um arquivo ja valido -- leitura concorrente e segura, so a
    escrita concorrente nao e. Roda sobre ruido sintetico, nao uma track
    real: o unico objetivo e acionar o compilador: o resultado numerico nao
    importa. Falha aqui nunca pode derrubar o scan -- sem aquecer, o
    comportamento so volta a ser o de hoje, nunca pior.
    """
    try:
        sr = 22050
        ruido = np.random.default_rng(0).standard_normal(sr * 2).astype(np.float32)
        track_bpm(compute_spectra(ruido, sr))
    except Exception:
        pass


def _aquece_cache_do_chroma() -> None:
    """Compila as funcoes numba do chroma_cqt ANTES de subir o pool do lote.

    `_aquece_cache_numba` NAO cobre isto: o beat-tracking nao passa por
    `librosa.core.constantq.__num_two_factors` (um `@jit(cache=True)`), que o
    primeiro `chroma_cqt` compila e grava. Medido com NUMBA_CACHE_DIR vazio:
    depois de `_aquece_cache_numba`, uma chamada de `chroma_cqt` ainda
    criava `constantq.__num_two_factors-*.nbi/.nbc`. Sem aquecer, os workers
    do lote cairiam na mesma corrida de escrita concorrente descrita em
    `_aquece_cache_numba`. Falha aqui nunca derruba o lote.
    """
    try:
        t = np.arange(ANALYSIS_SR * 3) / ANALYSIS_SR
        tom = (0.3 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        detect_key_from_samples(tom)
    except Exception:
        pass


def _detecta_key_no_worker(path: Path) -> tuple[Key | None, str | None]:
    """Roda `detect_key` dentro do worker do lote. Nunca levanta.

    Nivel de modulo para ser picklable (o ProcessPoolExecutor serializa a
    funcao por referencia). Devolve `(key, erro)`, no molde de `extract_one`:
    excecao de decode ou do librosa vira erro textual, e quem chama degrada
    a track para "none" -- uma track ilegivel nao pode parar o lote. Se o
    worker MORRER (segfault), o `_roda_em_blocos` isola e o lote degrada do
    mesmo jeito.
    """
    with threadpool_limits(limits=1):
        try:
            return detect_key(Path(path)), None
        except Exception as erro:
            return None, str(erro)


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]
#: Recebe "analisando" ou "processando" (ver analyze_all).
PhaseCallback = Callable[[str], None]


@dataclass(frozen=True)
class KeyBatchReport:
    """Resultado de `TrackService.detect_keys_batch`.

    `total` e o numero de ALVOS (tracks que o lote tentaria detectar), e nao do
    acervo: o que ja tinha key (de tag ou de deteccao anterior) ou ja foi
    tentado e deu "none" entra em `skipped`. `detected + none` pode ser menor
    que `total` quando o lote foi cancelado -- as que sobraram continuam
    pendentes para o proximo lote (cancelar nao e falhar).

    `none` inclui as falhas de decode e de worker: a track vira "none" e nao
    entra em `failures()`.

    Os campos de calibracao so valem com `calibrar=True`. Ali o alvo e a track
    COM tag, a tag e o gabarito, e nada e gravado: `com_tag` e o numero de
    comparacoes, `acerto_exato` conta key igual a da tag e `acerto_vizinho`
    conta o exato MAIS a relativa maior/menor e o +-1 na roda de Camelot
    (inclusivo de proposito: e a taxa de "serve para mixar", sempre >= exato).
    Track em que o detector devolveu None conta como erro nas duas.
    """

    total: int
    detected: int
    none: int
    skipped: int
    cancelled: bool
    calibrar: bool = False
    com_tag: int = 0
    acerto_exato: int = 0
    acerto_vizinho: int = 0

    @property
    def taxa_none(self) -> float:
        """Fracao das tentadas em que o detector nao achou key (0.0 a 1.0)."""
        tentadas = self.detected + self.none
        return self.none / tentadas if tentadas else 0.0


@dataclass(frozen=True)
class QueueItem:
    sha1: str
    filename: str
    path: Path
    label: Label
    score: float
    confidence: float
    bpm: float
    duration_s: float
    energy_curve: list[float]
    peak_offset_s: float


#: Inicio da mensagem -> categoria mostrada na aba Modelo. A primeira que
#: casar ganha. As mensagens vem de audio_io (via extract_one, que faz
#: str(erro)) e carregam o nome do arquivo e o stderr do ffmpeg -- casar so
#: o comeco e o que faz quarenta arquivos sem ffmpeg virarem UM problema
#: em vez de quarenta.
_CATEGORIAS = (
    ("ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("ffprobe nao encontrado", "ffmpeg nao encontrado"),
    ("Falha ao decodificar", "Falha ao decodificar"),
    ("Tempo esgotado ao decodificar", "Tempo esgotado"),
    ("Tempo esgotado ao medir duracao", "Tempo esgotado"),
    ("Falha ao medir duracao", "Falha ao medir duracao"),
    ("Duracao invalida", "Falha ao medir duracao"),
    ("Arquivo sem audio decodificavel", "Arquivo sem audio"),
    ("Arquivo nao encontrado", "Arquivo sumiu durante o scan"),
)


def _categoria(erro: str) -> str:
    """Categoria a partir do inicio da mensagem, nao da mensagem inteira.

    Desconhecido cai em "outros": inventar uma categoria por mensagem nova
    devolveria o agrupamento ao que ele era antes -- um grupo por arquivo.
    """
    for prefixo, categoria in _CATEGORIAS:
        if erro.startswith(prefixo):
            return categoria
    return "outros"


@dataclass(frozen=True)
class FailedItem:
    filename: str
    reason: str
    #: Tipo do erro, estavel entre arquivos. `reason` traz o nome do
    #: arquivo e o stderr do ffmpeg, entao varia sempre e nao serve para
    #: agrupar -- a aba Modelo agrupa por isto. Default "outros" para nao
    #: obrigar todo caminho de erro a classificar o que nao sabe.
    category: str = "outros"


@dataclass(frozen=True)
class _UltimaDecisao:
    sha1: str
    origem_dir: Path
    destino: Path
    label: Label
    posicao: int
    #: De onde a track saiu. None = da inbox (decide); um Label = da pasta
    #: daquele rotulo (reclassify). E o que undo_last usa para saber se
    #: devolve para a fila de revisao ou para a biblioteca.
    origem_label: Label | None = None
    #: Qual perfil a track pertence. Preservado por undo para que a track
    #: volte pro perfil certo -- decide so age sobre o perfil ativo, mas
    #: reclassify pode atuar sobre um rótulo de outro perfil (a Biblioteca
    #: mostra todos).
    profile: str | None = None


class TrackService:
    def __init__(
        self,
        config: Config,
        extractor: FeatureExtractor | None = None,
        max_workers: int | None = None,
        trash: Callable[[Path], None] | None = None,
    ):
        self.config = config
        self.extractor = extractor or HandcraftedExtractor()
        # A funcao de lixeira e injetavel para os testes nao dependerem da
        # lixeira real do SO (no CI ela pode nem existir). send2trash e puro
        # Python e cobre macOS (~/.Trash) e Windows (Lixeira), entao
        # empacota no PyInstaller sem hidden import.
        self._trash = trash if trash is not None else send2trash
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.sha1_cache = Sha1Cache(config.data_dir / "sha1.json")
        self.presentation = PresentationCache(
            config.data_dir / "presentation.parquet",
            config.data_dir / "covers",
        )
        self.peaks = PeaksStore(config.data_dir / "peaks")
        self.model_path = config.data_dir / "model.joblib"
        self.model = self._load_model()
        self.history_path = config.data_dir / "model_history.json"
        self._backfill_historico()
        self._labeled: list[TrackRef] = []
        self._inbox: list[TrackRef] = []
        self._failures: list[FailedItem] = []
        self._decisions_since_train = 0
        self._ultima_decisao: _UltimaDecisao | None = None
        # Cap em 8: cada worker mantem simultaneamente um subprocesso ffmpeg
        # mais copias em memoria do audio decodificado (buffer PCM, copia
        # float32, intermediarios de STFT/HPSS/beat-tracking do librosa).
        # Numa biblioteca real grande (centenas de tracks), deixar o default
        # escalar sem limite com o numero de nucleos de uma maquina com
        # muitos cores arrisca picos de memoria multi-GB. 8 workers ja
        # satura o ganho pratico de paralelismo para essa carga sem
        # depender do core count real da maquina.
        self._max_workers = max_workers or _teto_de_workers()
        #: Funcao que o lote de keys roda em cada worker. Atributo (e nao
        #: chamada direta) para os testes trocarem por uma que morre ou demora;
        #: precisa ser de nivel de modulo, ja que o pool a serializa.
        self._detector_de_key = _detecta_key_no_worker

    def set_config(self, config: Config) -> None:
        """Troca a config viva sem recriar o servico.

        Criar/renomear/excluir perfil nao muda cache, modelo nem os refs ja
        varridos (que guardam o ID do perfil); recriar o TrackService zeraria
        _inbox/_labeled e a fila ficaria vazia ate o proximo scan.
        """
        self.config = config

    def set_model_settings(self, retrain_every: int, min_examples: int) -> None:
        """Aplica retrain_every/min_examples no PERFIL ativo do config vivo.
        Gravar no toml nao e responsa daqui: cada cliente persiste com
        save_config (a rota /api/model/settings faz isso junto com a troca
        viva; o CLI retreino automatico usa o valor do config corrente).
        Config e frozen, entao vive por with_active_settings.
        """
        if retrain_every < 1 or min_examples < 1:
            raise ValueError("retrain_every e min_examples exigem valor >= 1")
        self.config = self.config.with_active_settings(
            retrain_every=retrain_every,
            min_examples=min_examples,
        )

    def _load_model(self) -> TrackModel:
        if not self.model_path.is_file():
            return TrackModel()
        try:
            return TrackModel.load(self.model_path)
        except Exception:
            # joblib/pickle e fragil a versao (bump de scikit-learn/numpy
            # pode quebrar o unpickling). Cai para um modelo novo em vez de
            # derrubar todo comando (scan/train/review) com traceback opaco.
            return TrackModel()

    def _backfill_historico(self) -> None:
        """Modelo antigo sem historico ganha UMA entrada de arranque.

        model.joblib salvo antes do historico existir nao tem de onde tirar
        timestamp: o mtime do artefato e quando o treino foi gravado, entao
        e o proxy honesto. Sem isso o dashboard comecaria "nunca treinado"
        ate o usuario retreinar, mentindo sobre um modelo que esta ativo.
        """
        historico = training_history.load(self.history_path)
        if not self.model.is_fitted or self.model.metrics_ is None or historico:
            return
        try:
            stamp = self.model_path.stat().st_mtime
        except OSError:
            return
        ts = datetime.fromtimestamp(stamp).strftime("%Y-%m-%dT%H:%M:%S")
        metrics = self.model.metrics_
        entrada = TrainingEntry(
            ts=ts,
            extractor=self.extractor.name,
            version=training_history.next_version(historico, self.extractor.name),
            n_examples=metrics.n_examples,
            accuracy=metrics.accuracy,
            ordinal_mae=metrics.ordinal_mae,
            weighted_f1=weighted_f1(metrics.confusion),
        )
        try:
            training_history.append(self.history_path, entrada)
        except OSError:
            # Disco cheio/permissoes: o treino em si nao depende do
            # historico; sem a entrada, o painel so degrada.
            print("falha ao gravar historico inicial", file=sys.stderr)

    def historico_treinos(self) -> list[TrainingEntry]:
        """Historico lido a cada chamada: barato (JSON pequeno) e fresco."""
        return training_history.load(self.history_path)

    def analyze_all(
        self,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
        on_phase: PhaseCallback | None = None,
    ) -> bool:
        """Varre, extrai o que falta e reconstroi _labeled/_inbox.

        should_cancel e consultado entre extracoes; devolve True se o scan foi
        interrompido. Interromper NAO e falhar: o que nao foi extraido
        simplesmente continua pendente para o proximo scan, sem entrar em
        failures(). O que ja foi extraido esta no cache e e preservado.

        on_phase anuncia as duas etapas: "analisando" (varredura + extracao,
        a unica com on_progress) e "processando" (tags, capa e tonalidade em
        _preenche_apresentacao, que nao emite progresso mas segura o scan por
        tanto tempo quanto a extracao numa biblioteca nova). Sem a segunda
        fase a UI nao tem como distinguir "terminou" de "ainda rodando". Um
        scan cancelado nunca chega em "processando".
        """
        if on_phase is not None:
            on_phase("analisando")
        self._failures = []
        if self.cache.load_error is not None:
            # Um parquet que nao abriu significa reanalisar o acervo inteiro
            # -- dezenas de minutos. Sem esta linha isso acontece calado: a
            # tela mostraria um scan longo e nenhuma explicacao, que e
            # exatamente como um cache perdido se disfarca de "o app nao
            # salva nada". Fica em failures() a cada scan da sessao de
            # proposito; o cache so volta a abrir num proximo processo.
            self._failures.append(
                FailedItem(
                    filename=self.cache.path.name,
                    reason=self.cache.load_error,
                    category="cache de analises ilegivel",
                )
            )
        for key, perfil in self.config.profiles.items():
            if not perfil.complete:
                # Perfil criado sem copiar pastas: nao e erro, so nao ha o
                # que varrer. Fica em failures() para a tela explicar por que
                # a fila dele esta vazia.
                self._failures.append(
                    FailedItem(
                        filename=nome_de(key, perfil),
                        reason="Perfil sem pastas configuradas.",
                        category="perfil incompleto",
                    )
                )
        candidatos = scan_labeled(self.config, self.sha1_cache) + scan_inbox(
            self.config, self.sha1_cache
        )
        # Salva antes de extrair: a varredura sozinha ja custou o I/O, e uma
        # interrupcao durante a extracao nao pode jogar esse trabalho fora.
        self.sha1_cache.save()
        aceitos, cancelado = self._analyze(candidatos, on_progress, should_cancel)
        self._labeled = [ref for ref in aceitos if ref.label is not None]
        self._inbox = [ref for ref in aceitos if ref.label is None]
        self.cache.save()

        if not cancelado:
            if on_phase is not None:
                on_phase("processando")
            cancelado = self._preenche_apresentacao(aceitos, should_cancel)
        self.presentation.save()
        return cancelado

    def _analyze(
        self,
        refs: list[TrackRef],
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> tuple[list[TrackRef], bool]:
        aceitos: list[TrackRef] = []
        pendentes: list[TrackRef] = []
        for ref in refs:
            if self.cache.get(ref.sha1, self.extractor.name) is not None:
                aceitos.append(ref)
            else:
                pendentes.append(ref)

        if not pendentes:
            return aceitos, False

        cancelou = should_cancel if should_cancel is not None else (lambda: False)
        cancelado = False
        total = len(pendentes)
        estado = {"concluidas": 0, "desde_o_ultimo_save": 0}

        def _processa_resultado(ref: TrackRef, analise, erro: str | None) -> None:
            estado["concluidas"] += 1
            if erro is not None:
                self._failures.append(
                    FailedItem(filename=ref.path.name, reason=erro, category=_categoria(erro))
                )
            else:
                self.cache.put(ref.sha1, ref.path.name, self.extractor.name, analise)
                aceitos.append(ref)
                estado["desde_o_ultimo_save"] += 1
                if estado["desde_o_ultimo_save"] >= _CACHE_SAVE_EVERY:
                    # Salva periodicamente durante o loop, alem do save final em
                    # analyze_all: um scan de ~100 tracks a 5-15s cada demora
                    # 10-25 minutos, e uma interrupcao no meio nao pode
                    # descartar toda extracao ja feita.
                    self.cache.save()
                    estado["desde_o_ultimo_save"] = 0
            if on_progress is not None:
                on_progress(estado["concluidas"], total, ref.path.name)

        # Empacotado, o pool e obrigatorio mesmo para 1 pendente e mesmo com
        # max_workers=1: ver `_empacotado()` para o SIGSEGV que isso evita.
        # Fora do bundle o atalho sequencial segue valendo -- e o que os
        # testes usam com ExtratorFalso, sem pagar overhead de subprocesso.
        usa_pool = _empacotado() or (self._max_workers > 1 and total > 1)

        if not usa_pool:
            for ref in pendentes:
                if cancelou():
                    cancelado = True
                    break
                analise, erro = extract_one(self.extractor, ref.path)
                _processa_resultado(ref, analise, erro)
        else:
            # Ver _roda_em_blocos: o pool em blocos, a retentativa isolada e o
            # cancelamento valem igual para o scan e para o lote de keys.
            #
            # Ver _aquece_cache_numba: sem isto, o primeiro scan depois de um
            # rebuild do .app corrompe o cache de compilacao do numba sob a
            # concorrencia dos workers, e todo processo que le esse cache
            # depois segfaulta.
            _aquece_cache_numba()
            cancelado = self._roda_em_blocos(
                pendentes,
                submete=lambda executor, ref: executor.submit(
                    extract_one, self.extractor, ref.path
                ),
                processa=lambda ref, resultado: _processa_resultado(ref, *resultado),
                resultado_de_worker_morto=lambda falha: (None, f"worker falhou: {falha}"),
                cancelou=cancelou,
            )

        # as_completed devolve em ordem de conclusao, nao de entrada. Reordena
        # pela ordem original de `refs` para que _labeled/_inbox fiquem
        # deterministicos entre execucoes -- library.py ja ordena de forma
        # estavel, e essa garantia nao pode se perder aqui.
        posicao = {ref.sha1: i for i, ref in enumerate(refs)}
        return sorted(aceitos, key=lambda ref: posicao[ref.sha1]), cancelado

    def _roda_em_blocos(
        self,
        itens: list[TrackRef],
        *,
        submete: Callable[[ProcessPoolExecutor, TrackRef], Future],
        processa: Callable[[TrackRef, Any], None],
        resultado_de_worker_morto: Callable[[Exception], Any],
        cancelou: CancelCheck,
    ) -> bool:
        """Roda `itens` em ProcessPoolExecutor, em blocos, e devolve se cancelou.

        Compartilhado pelo scan (`_analyze`) e pelo lote de keys
        (`detect_keys_batch`): o desenho abaixo nasceu de segfaults reais e
        nao pode divergir entre os dois. `submete` agenda UM item no executor,
        `processa` recebe o resultado do worker, e `resultado_de_worker_morto`
        fabrica o resultado de um item cujo worker morreu ate na retentativa
        isolada (cada chamador degrada do seu jeito: o scan vira falha, o lote
        vira "none"). O chamador aquece o cache do numba antes (o que aquecer
        depende do que o worker roda).
        """
        cancelado = False
        coletados: set[str] = set()

        # A morte de um worker NAO fica contida nele: quando um processo
        # filho cai (segfault em numpy/ffmpeg, OOM), o ProcessPoolExecutor
        # inteiro entra em estado quebrado e todo future pendente levanta
        # BrokenProcessPool -- inclusive os que nem tinham comecado. Numa
        # biblioteca de centenas de tracks, uma morte vira centenas de
        # falhas identicas: na biblioteca real foram 6 tracks analisadas e
        # ~370 falhas iguais, de um unico segfault.
        #
        # Por isso o lote vai em BLOCOS, cada um no proprio pool: a morte
        # de um worker so alcanca os futures do bloco em voo, nao o acervo
        # inteiro. O que sobrar do bloco e reprocessado item a item, cada
        # um num pool de um worker so, onde um segfault custa exatamente a
        # track que o causou.
        #
        # Nao vale reprocessar o lote inteiro num pool novo: a morte e rara
        # por track, mas basta uma para levar as outras junto, e o desfecho
        # vira binario -- em cinco execucoes da biblioteca real, ou ~todas
        # passaram ou ~todas falharam. Tambem nao vale mandar TUDO item a
        # item: medido, sao ~140 min contra ~10 min do pool cheio. O bloco
        # e o meio-termo -- mantem o paralelismo e limita o estrago.
        #
        # A retentativa usa pool de 1, e nao extracao direta nesta thread,
        # porque extract_one aqui dentro rodaria no processo da JANELA: um
        # segfault levaria o app inteiro em vez de um filho descartavel.

        def _processa_e_marca(ref: TrackRef, resultado: Any) -> None:
            processa(ref, resultado)
            coletados.add(ref.sha1)

        # Todo item do bloco sai marcado (sucesso ou falha) antes do bloco
        # seguinte, entao o laco termina sempre -- sem orcamento de
        # tentativas e sem risco de girar numa track ruim.
        _fixa_threads_dos_workers()
        tamanho_do_bloco = max(self._max_workers * 4, 1)

        for inicio in range(0, len(itens), tamanho_do_bloco):
            if cancelado:
                break
            bloco = itens[inicio : inicio + tamanho_do_bloco]
            try:
                with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
                    futuros = {submete(executor, ref): ref for ref in bloco}
                    for futuro in as_completed(futuros):
                        ref = futuros[futuro]
                        try:
                            resultado = futuro.result()
                        except Exception:
                            # A funcao do worker ja captura excecoes da propria
                            # extracao, entao chegar aqui significa que o
                            # worker morreu. Nao marca como falha: a
                            # retentativa isolada abaixo tenta de novo.
                            continue
                        _processa_e_marca(ref, resultado)

                        if cancelou():
                            cancelado = True
                            # O cancelamento descarta o bloco, mas nao e
                            # de graca: `wait=True` e obrigatorio porque o
                            # `__exit__` do `with` chamaria `shutdown(wait=True)`
                            # logo em seguida, e esse zera
                            # `_cancel_pending_futures` antes do manager thread
                            # ler o flag -- o descarte nunca chegaria a
                            # valer. Com `wait=False` (o que estava aqui
                            # ate 2026-10-20) medido em 3.11, 3.12 e 3.13:
                            # 12/12 tarefas do bloco continuavam extraindo
                            # depois do cancelamento, nenhuma ficava
                            # CANCELLED, e o resultado delas ia para o
                            # lixo. Ver
                            # docs/superpowers/specs/2026-10-20-grafo-como-impacto.md.
                            #
                            # O preco de `wait=True` e esperar o que ja
                            # estava rodando: no pior caso uma extracao
                            # (5-15s). Matar um processo no meio de um
                            # ffmpeg/librosa continua fora de questão --
                            # o que morre sao as faixas que NUNCA
                            # comecaram, e elas voltam a ser pendentes no
                            # proximo scan (cancelar nao e falhar).
                            #
                            # A latencia de DETECCAO e separada: o flag e
                            # lido no laco de `as_completed`, entao o
                            # cancelamento so entra em vigor quando o
                            # proximo resultado chega.
                            executor.shutdown(wait=True, cancel_futures=True)
                            break
            except Exception:
                # O PROPRIO pool falhou -- construcao (OSError por exaustao
                # de fd/semaforo) ou .submit() (BrokenProcessPool se um
                # worker morre durante o startup, antes de qualquer future
                # existir, ou RuntimeError se chamado apos shutdown).
                # Nenhum desses e capturado pelo try/except de
                # futuro.result(); o bloco inteiro cai na retentativa.
                pass

            for ref in bloco:
                if cancelado or cancelou():
                    cancelado = True
                    break
                if ref.sha1 in coletados:
                    continue
                try:
                    with ProcessPoolExecutor(max_workers=1) as solo:
                        resultado = submete(solo, ref).result()
                except Exception as falha:
                    resultado = resultado_de_worker_morto(falha)
                _processa_e_marca(ref, resultado)

        return cancelado

    def _preenche_apresentacao(
        self, refs: list[TrackRef], should_cancel: CancelCheck | None = None
    ) -> bool:
        """Le tags e capa de quem ainda nao tem registro na versao atual.

        Roda depois da extracao, e sobre TODAS as refs aceitas -- nao so as
        que foram extraidas agora. Os dois caches sao independentes: uma track
        com features em cache pode nao ter apresentacao nenhuma (biblioteca
        analisada antes desta fase existir, ou PRESENTATION_VERSION bumpada).

        Nao emite progresso: ler tags e ~1ms e nao decodifica audio, entao uma
        barra so piscaria. E nao alimenta failures(): uma track sem metadado
        legivel continua classificavel, e poluir a aba Modelo com isso
        esconderia as falhas de analise, que sao as que importam.
        """
        cancelou = should_cancel if should_cancel is not None else (lambda: False)

        for ref in refs:
            if cancelou():
                return True
            if self.presentation.get(ref.sha1) is not None:
                continue
            try:
                tags = read_tags(ref.path)
                capa = extract_cover(ref.path)
                chave = read_key(ref.path)
            except Exception:
                # read_tags/extract_cover/read_key ja contem tudo o que sabem
                # conter; chegar aqui e algo fora deles (o proprio open
                # falhando por permissao, arquivo removido no meio do scan).
                # Grava vazio em vez de deixar a track sem registro: sem isto,
                # ela seria retentada a cada scan, para sempre.
                tags, capa, chave = VAZIO, None, None
            self.presentation.put(ref.sha1, tags, capa, chave)

        return False

    def presentation_for(self, sha1: str) -> PresentationRecord | None:
        return self.presentation.get(sha1)

    def cover_path_for(self, sha1: str) -> Path | None:
        return self.presentation.cover_path(sha1)

    def key_for(self, sha1: str) -> Key | None:
        registro = self.presentation.get(sha1)
        return registro.key if registro is not None else None

    def key_source_for(self, sha1: str) -> str | None:
        """"tag" | "audio" | "none" | None (nunca tentada). Ver presentation."""
        registro = self.presentation.get(sha1)
        return registro.key_source if registro is not None else None

    def _grava_key_detectada(self, sha1: str, chave: Key | None) -> None:
        """Registra o resultado de uma deteccao pelo audio, sem salvar em disco.

        Achou: "audio". Nao achou (ou a deteccao falhou): "none", para nao ser
        retentada. Separado do save porque quem detecta em lote grava dezenas
        de tracks por vez e salva so de tempos em tempos; `ensure_key` grava
        uma e salva na hora.
        """
        self.presentation.set_key(
            sha1,
            chave,
            KEY_SOURCE_AUDIO if chave is not None else KEY_SOURCE_NONE,
        )

    def _salva_apresentacao(self) -> None:
        try:
            self.presentation.save()
        except OSError:
            # Disco cheio ou permissao: a key vale nesta sessao (esta em
            # memoria) e a proxima deteccao refaz o trabalho. Nada disso e
            # motivo para derrubar a tela.
            pass

    def ensure_key(self, sha1: str, path: Path) -> Key | None:
        """Estima a key pelo audio se a track ainda nao tem. Devolve a key ou None.

        A tag manda: key ja gravada (de tag ou de uma deteccao anterior) volta
        sem decodificar nada. `key_source == "none"` tambem volta direto -- e
        "tentei e nao deu", e re-decodificar o mesmo arquivo a cada vez que a
        track reaparece na Revisao so repetiria o custo (alguns segundos de
        chroma_cqt) para o mesmo resultado.

        Chamado sob demanda pela tela, nunca pelo scan, pelo mesmo motivo de
        ensure_peaks: decodificar a biblioteca inteira dobraria o scan para um
        dado que talvez nunca apareca na tela.

        Falha vira "none", nao excecao e nao FailedItem: uma track sem key
        continua perfeitamente classificavel, e poluir a aba Modelo com isso
        esconderia as falhas de analise, que sao as que importam.
        """
        registro = self.presentation.get(sha1)
        if registro is None:
            # Sem registro nao ha onde gravar sem fabricar tags vazias (ver
            # PresentationCache.set_key). Cai para "sem key" sem persistir.
            return None
        if registro.key is not None or registro.key_source == KEY_SOURCE_NONE:
            return registro.key

        try:
            chave = detect_key(Path(path))
        except Exception:
            # AudioDecodeError (arquivo sumiu, formato quebrado, ffmpeg
            # travado) ou qualquer falha do librosa.
            chave = None

        self._grava_key_detectada(sha1, chave)
        self._salva_apresentacao()
        return chave

    def _alvos_de_key(self, calibrar: bool) -> tuple[list[TrackRef], int, int]:
        """(alvos, pulados, com_tag) do lote, sobre as tracks rotuladas.

        O escopo e `_labeled` inteiro, de todos os perfis: e o mesmo conjunto
        que `library_state` mostra na Biblioteca, entao "o acervo inteiro" do
        lote e o que o usuario ve na tela. A inbox fica de fora: a Revisao ja
        detecta sob demanda a track exibida (`ensure_key`).

        Alvo normal: tem registro de apresentacao, sem key e nunca tentada
        (`key_source is None`). Sem registro nao ha onde gravar (ver
        `PresentationCache.set_key`); key de tag nunca e sobrescrita; "none"
        nao e retentado. Alvo de calibracao: a track COM tag, que e o gabarito.
        Dedup por sha1: o mesmo conteudo em duas pastas decodifica uma vez.
        """
        alvos: list[TrackRef] = []
        pulados = 0
        com_tag = 0
        vistos: set[str] = set()
        for ref in self._labeled:
            if ref.sha1 in vistos:
                continue
            vistos.add(ref.sha1)
            registro = self.presentation.get(ref.sha1)
            if registro is None:
                pulados += 1
                continue
            tem_tag = registro.key is not None and registro.key_source == KEY_SOURCE_TAG
            com_tag += tem_tag
            if calibrar:
                eh_alvo = tem_tag
            else:
                eh_alvo = registro.key is None and registro.key_source is None
            if eh_alvo:
                alvos.append(ref)
            else:
                pulados += 1
        return alvos, pulados, com_tag

    def detect_keys_batch(
        self,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
        *,
        calibrar: bool = False,
    ) -> KeyBatchReport:
        """Estima pelo audio a key de todas as tracks rotuladas que ainda nao tem.

        Acao explicita do usuario (`dj keys`, `POST /api/key/batch`), nunca
        parte do scan: a regra "sob demanda, nunca no scan" continua valendo
        porque o custo (segundos de chroma_cqt por track) so e pago quando
        alguem pede. Decodifica + chroma em POOL DE PROCESSOS, pelo mesmo
        motivo do scan (ver `_roda_em_blocos`); o `set_key` e o save ficam no
        processo pai, que e dono do parquet.

        Gravacao: `set_key` por track e `presentation.save()` a cada
        `_KEY_BATCH_SAVE_EVERY` e no fim -- inclusive no cancelamento e se algo
        inesperado estourar, para o parcial nunca se perder. Falha por track
        (decode, excecao, worker morto) degrada para "none" e NAO entra em
        `failures()`, como em `ensure_key`.

        `calibrar=True` mede a estimativa contra as tags e NAO grava nada: nem
        `set_key`, nem `save`. Ver KeyBatchReport.
        """
        cancelou = should_cancel if should_cancel is not None else (lambda: False)
        alvos, pulados, com_tag = self._alvos_de_key(calibrar)
        total = len(alvos)
        estado = {"feitas": 0, "detected": 0, "none": 0, "exato": 0, "vizinho": 0, "sujas": 0}

        def _processa(ref: TrackRef, resultado: tuple[Key | None, str | None]) -> None:
            chave, _erro = resultado
            estado["feitas"] += 1
            estado["detected" if chave is not None else "none"] += 1
            if calibrar:
                registro = self.presentation.get(ref.sha1)
                tag = registro.key if registro is not None else None
                if chave is not None and tag is not None:
                    estado["exato"] += chave == tag
                    estado["vizinho"] += is_harmonic_neighbor(chave, tag)
            else:
                self._grava_key_detectada(ref.sha1, chave)
                estado["sujas"] += 1
                if estado["sujas"] >= _KEY_BATCH_SAVE_EVERY:
                    self._salva_apresentacao()
                    estado["sujas"] = 0
            if on_progress is not None:
                on_progress(estado["feitas"], total, ref.path.name)

        def _worker_morto(falha: Exception) -> tuple[Key | None, str | None]:
            return None, f"worker falhou: {falha}"

        cancelado = False
        try:
            # Mesma regra do scan: empacotado forca pool (nunca decodificar +
            # chroma no processo principal do .app; ver `_empacotado`), e fora
            # do bundle o atalho sequencial poupa o spawn para 1 alvo.
            usa_pool = total > 0 and (_empacotado() or (self._max_workers > 1 and total > 1))
            if not usa_pool:
                for ref in alvos:
                    if cancelou():
                        cancelado = True
                        break
                    try:
                        resultado = self._detector_de_key(ref.path)
                    except Exception as falha:
                        resultado = _worker_morto(falha)
                    _processa(ref, resultado)
            else:
                _aquece_cache_numba()
                _aquece_cache_do_chroma()
                cancelado = self._roda_em_blocos(
                    alvos,
                    submete=lambda executor, ref: executor.submit(self._detector_de_key, ref.path),
                    processa=_processa,
                    resultado_de_worker_morto=_worker_morto,
                    cancelou=cancelou,
                )
        finally:
            if not calibrar and estado["sujas"] > 0:
                self._salva_apresentacao()

        return KeyBatchReport(
            total=total,
            detected=estado["detected"],
            none=estado["none"],
            skipped=pulados,
            cancelled=cancelado,
            calibrar=calibrar,
            com_tag=com_tag,
            acerto_exato=estado["exato"],
            acerto_vizinho=estado["vizinho"],
        )

    def peaks_for(self, sha1: str) -> Path | None:
        """Caminho dos buckets ja computados, ou None. Nunca computa."""
        return self.peaks.path_for(sha1)

    def ensure_peaks(self, sha1: str, path: Path) -> Path | None:
        """Computa os buckets se ainda nao existirem. Devolve o caminho ou None.

        Chamado sob demanda pela tela, nunca pelo scan: a STFT da track
        inteira custa alguns segundos, e paga-la durante o scan dobraria o
        tempo de uma biblioteca grande para produzir dado que talvez nunca
        apareca na tela.

        Falha vira None, nao excecao e nao FailedItem: uma track sem onda
        colorida continua perfeitamente classificavel, e poluir a aba Modelo
        com isso esconderia as falhas de analise, que sao as que importam.
        """
        existente = self.peaks.path_for(sha1)
        if existente is not None:
            return existente

        try:
            bandas = compute_bands(Path(path))
        except Exception:
            # AudioDecodeError (arquivo sumiu, formato quebrado, ffmpeg
            # travado) ou qualquer falha do librosa. A onda cai no render
            # mono e o usuario nem percebe.
            return None

        try:
            return self.peaks.put(sha1, bandas)
        except OSError:
            # Disco cheio ou permissao: o computo foi em vao, mas a tela
            # segue funcionando com o fallback mono.
            return None

    def _analysis(self, ref: TrackRef) -> TrackAnalysis:
        analise = self.cache.get(ref.sha1, self.extractor.name)
        assert analise is not None
        return analise

    def train(self) -> Metrics:
        matriz = np.asarray([self._analysis(ref).vector for ref in self._labeled])
        rotulos = [ref.label for ref in self._labeled if ref.label is not None]
        self.model.fit(matriz, rotulos, min_examples=self.config.min_examples)
        self.model.save(self.model_path)
        self._decisions_since_train = 0
        assert self.model.metrics_ is not None
        self._registrar_treino(self.model.metrics_)
        return self.model.metrics_

    def _registrar_treino(self, metrics: Metrics) -> None:
        """Uma linha por treino no historico do dashboard.

        Falha de disco degrada sem derrubar o treino: metrics seguem
        validas na tela; so o painel de historico/deltas fica sem a nova
        entrada (e o usuario retreina ou conserta o disco depois). Nomes de
        campo e cap ficam no training_history; daqui sai so o append.
        """
        historico = training_history.load(self.history_path)
        entrada = TrainingEntry(
            ts=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            extractor=self.extractor.name,
            version=training_history.next_version(historico, self.extractor.name),
            n_examples=metrics.n_examples,
            accuracy=metrics.accuracy,
            ordinal_mae=metrics.ordinal_mae,
            weighted_f1=weighted_f1(metrics.confusion),
        )
        try:
            training_history.append(self.history_path, entrada)
        except OSError:
            print("falha ao gravar historico de treino", file=sys.stderr)

    def failures(self) -> list[FailedItem]:
        return list(self._failures)

    def class_counts(self) -> tuple[int, ...]:
        """Exemplos rotulados por classe, na ordem de LABEL_ORDER.

        Tres posicoes sempre, mesmo com a biblioteca vazia: a aba Modelo
        desenha a barra em zero, e barra em zero e informacao ("falta esta
        classe"), nao ausencia de linha.
        """
        contagem = Counter(ref.label for ref in self._labeled if ref.label is not None)
        return tuple(contagem.get(rotulo, 0) for rotulo in LABEL_ORDER)

    @property
    def decisions_since_train(self) -> int:
        """Decisoes desde o ultimo treino. So leitura: quem incrementa e
        decide()/reclassify(), quem zera e train()."""
        return self._decisions_since_train

    def queue(self) -> list[QueueItem]:
        vivos = [
            ref
            for ref in self._inbox
            if ref.path.is_file() and ref.profile == self.config.active_profile
        ]
        self._inbox = vivos
        if not vivos or not self.model.is_fitted:
            return []

        matriz = np.asarray([self._analysis(ref).vector for ref in vivos])
        predicoes = self.model.predict(matriz)

        itens = []
        for ref, predicao in zip(vivos, predicoes, strict=True):
            analise = self._analysis(ref)
            itens.append(
                QueueItem(
                    sha1=ref.sha1,
                    filename=ref.path.name,
                    path=ref.path,
                    label=predicao.label,
                    score=predicao.score,
                    confidence=predicao.confidence,
                    bpm=analise.bpm,
                    duration_s=analise.duration_s,
                    energy_curve=analise.energy_curve,
                    peak_offset_s=analise.peak_offset_s,
                )
            )
        return sorted(itens, key=lambda item: item.confidence)

    def path_for(self, sha1: str) -> Path:
        for ref in self._inbox:
            if ref.sha1 == sha1 and ref.profile == self.config.active_profile:
                return ref.path
        raise KeyError(f"Track fora da fila: {sha1}")

    def decide(self, sha1: str, label: Label) -> bool:
        ref = next(
            (r for r in self._inbox if r.sha1 == sha1 and r.profile == self.config.active_profile),
            None,
        )
        if ref is None:
            return False

        try:
            destino = move_to_folder(ref.path, self.config.folders[label])
        except FileVanishedError:
            # Arquivo-fonte sumiu entre o scan e a decisao: retry nao ajuda,
            # nao ha o que mover. Este e o unico caso que legitimamente sai
            # da fila sem o arquivo ter sido movido.
            self._inbox = [r for r in self._inbox if r.sha1 != sha1]
            return False
        # Qualquer outra excecao de move_to_folder (disco cheio, permissao,
        # etc.) propaga sem que ref seja removido de self._inbox, entao a
        # track continua na fila e um retry posterior a encontra de novo.

        # O arquivo mudou de pasta mas e byte-a-byte o mesmo: reaponta a
        # entrada do sha1 em vez de deixar o proximo scan reler o arquivo
        # inteiro so porque o caminho mudou.
        self.sha1_cache.rename(ref.path, destino)
        self.sha1_cache.save()

        posicao = next(i for i, r in enumerate(self._inbox) if r.sha1 == sha1)
        self._ultima_decisao = _UltimaDecisao(
            sha1=sha1,
            origem_dir=ref.path.parent,
            destino=destino,
            label=label,
            posicao=posicao,
            origem_label=None,
            profile=self.config.active_profile,
        )
        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        self._labeled.append(
            TrackRef(path=destino, label=label, sha1=ref.sha1, profile=self.config.active_profile)
        )
        return self._conta_decisao()

    def _conta_decisao(self) -> bool:
        """Soma uma decisao e retreina se bateu o limite. Devolve se treinou."""
        self._decisions_since_train += 1
        if self._decisions_since_train >= self.config.retrain_every:
            self.train()
            return True
        return False

    def reclassify(self, sha1: str, label: Label) -> bool:
        """Move uma track ja rotulada para a pasta de outro rotulo.

        Corrigir um rotulo errado e o sinal mais forte que o modelo recebe --
        e um exemplo que ele ja tinha, com o alvo trocado. Por isso conta para
        retrain_every igual a uma decisao nova e entra na mesma pilha de undo.

        Levanta KeyError se a sha1 nao esta na biblioteca, para quem chama
        distinguir "nao encontrei" de "nao retreinei" (as duas coisas que um
        `return False` sozinho confundiria) -- mesmo contrato de path_for.
        """
        ref = next((r for r in self._labeled if r.sha1 == sha1), None)
        if ref is None:
            raise KeyError(f"Track fora da biblioteca: {sha1}")
        if ref.label is label:
            # Reclassificar para o mesmo rotulo nao e erro nem decisao: mover
            # o arquivo para a pasta onde ele ja esta so renomearia o arquivo
            # com um sufixo " (1)", via _destino_livre.
            return False

        try:
            perfil_nome = ref.profile or self.config.active_profile
            perfil = self.config.profiles.get(perfil_nome)
            if perfil is None:
                perfil = self.config.profiles[self.config.active_profile]
            destino = move_to_folder(ref.path, perfil.folders[label])
        except FileVanishedError:
            # Mesma regra de decide: o arquivo sumiu por fora, retry nao ajuda.
            # Sai da biblioteca porque ele realmente nao esta mais la.
            self._labeled = [r for r in self._labeled if r.sha1 != sha1]
            return False

        self.sha1_cache.rename(ref.path, destino)
        self.sha1_cache.save()

        self._ultima_decisao = _UltimaDecisao(
            sha1=sha1,
            origem_dir=ref.path.parent,
            destino=destino,
            label=label,
            posicao=0,  # nao usado quando origem_label nao e None
            origem_label=ref.label,
            profile=perfil_nome,
        )
        self._labeled = [
            TrackRef(path=destino, label=label, sha1=sha1, profile=perfil_nome)
            if r.sha1 == sha1 else r
            for r in self._labeled
        ]
        return self._conta_decisao()

    def remove(self, sha1: str) -> bool:
        """Manda o arquivo da track para a lixeira do SO e tira ela da fila.

        Nao conta como decisao e NAO entra na pilha do Ctrl+Z: remover nao
        ensina nada ao modelo (nenhum rotulo novo), e _UltimaDecisao desfaz
        moves entre pastas da biblioteca -- restaurar da lixeira por codigo
        e fragil (o SO renomeia em colisao e o send2trash nao devolve o
        caminho final). A rede de seguranca e a propria lixeira: o usuario
        restaura pelo Finder e re-escaneia.

        Levanta KeyError se a sha1 nao esta na fila (mesmo contrato de
        path_for/reclassify, para o worker distinguir "saiu por fora" de
        "lixeira falhou"). Falha do send2trash (arquivo ja removido por fora,
        permissao) degrada: reporta em failures(), mantem a track na fila e
        devolve False -- nunca derruba o comando.
        """
        ref = next(
            (r for r in self._inbox if r.sha1 == sha1 and r.profile == self.config.active_profile),
            None,
        )
        if ref is None:
            raise KeyError(f"Track fora da fila: {sha1}")

        try:
            self._trash(ref.path)
        except Exception as erro:
            self._failures.append(
                FailedItem(
                    filename=ref.path.name,
                    reason=f"Falha ao mover para a lixeira: {erro}",
                    category="lixeira",
                )
            )
            return False

        # O arquivo saiu do acervo: esquece a entrada do sha1 em vez de
        # reapontar (o invariante do rename() vale para moves internos).
        self.sha1_cache.forget(ref.path)
        self.sha1_cache.save()
        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        return True

    def undo_last(self) -> bool:
        """Desfaz a ultima decisao ou reclassificacao. Um nivel apenas.

        Para onde a track volta depende de onde ela veio (origem_label): a
        fila de revisao, se saiu da inbox; a biblioteca com o rotulo antigo,
        se foi uma reclassificacao.

        Nao "destreina" o modelo: o exemplo sai de _labeled, mas os pesos
        ja ajustados so mudam no proximo train(). Reverter o ajuste exigiria
        guardar o modelo anterior a cada decisao, e o efeito de um unico
        exemplo em RidgeCV nao justifica esse custo.
        """
        decisao = self._ultima_decisao
        if decisao is None:
            return False

        # Consome antes de tentar mover: seja qual for o desfecho, esta
        # decisao nao pode ser desfeita duas vezes.
        self._ultima_decisao = None

        try:
            de_volta = undo_move(decisao.destino, decisao.origem_dir)
        except FileVanishedError:
            return False

        self.sha1_cache.rename(decisao.destino, de_volta)
        self.sha1_cache.save()

        if decisao.origem_label is None:
            # Veio da inbox: volta para a fila de revisao, na posicao original.
            self._labeled = [ref for ref in self._labeled if ref.sha1 != decisao.sha1]
            self._inbox.insert(
                min(decisao.posicao, len(self._inbox)),
                TrackRef(path=de_volta, label=None, sha1=decisao.sha1, profile=decisao.profile),
            )
        else:
            # Veio de outra pasta rotulada (reclassify): continua na biblioteca,
            # so volta a ter o rotulo antigo. Nunca entra na inbox -- ela nunca
            # esteve la.
            self._labeled = [
                TrackRef(
                    path=de_volta,
                    label=decisao.origem_label,
                    sha1=decisao.sha1,
                    profile=decisao.profile,
                )
                if ref.sha1 == decisao.sha1
                else ref
                for ref in self._labeled
            ]

        self._decisions_since_train = max(0, self._decisions_since_train - 1)
        return True

    def bulk_approve(self, min_confidence: float) -> int:
        alvos = [item for item in self.queue() if item.confidence >= min_confidence]
        for item in alvos:
            self.decide(item.sha1, item.label)
        return len(alvos)
