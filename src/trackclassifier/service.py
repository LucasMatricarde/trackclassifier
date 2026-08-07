import os
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .apply import FileVanishedError, move_to_folder, undo_move
from .cache import AnalysisCache
from .config import Config
from .extraction import extract_one
from .features import FeatureExtractor, HandcraftedExtractor, TrackAnalysis
from .keys import Key
from .labels import Label
from .library import Sha1Cache, TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel
from .peaks import compute_bands
from .presentation import (
    VAZIO,
    PeaksStore,
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_key,
    read_tags,
)

_CACHE_SAVE_EVERY = 10


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

    A causa raiz do SIGSEGV documentado no CLAUDE.md era outra do que se
    suspeitava. A hipotese original ("correlaciona com concorrencia, pool de
    1 nunca morreu") vinha de medir a RETENTATIVA do bloco quebrado -- que ja
    era um pool de 1 *subprocesso*, nao execucao direta. O gate
    `total > 1 and max_workers > 1` mais abaixo tem outra origem (evitar o
    overhead de subir um subprocesso so para 1 arquivo) e nunca tinha sido
    testado isoladamente: com `TRACKCLASSIFIER_MAX_WORKERS=1`, ou com
    qualquer teto quando so ha 1 pendente, `usa_pool` da False e
    `extract_one` roda direto na thread do CLI/janela -- fora de qualquer
    subprocesso. Reproduzido de forma deterministica no bundle (nao
    intermitente): SIGSEGV em ~11s, sempre, chamando o extrator UMA vez com
    UMA track de 320kbps real, sem pool nenhum envolvido. A mesma chamada,
    mesmo arquivo, rodando dentro de um `ProcessPoolExecutor(max_workers=1)`
    (ainda um unico subprocesso) nunca falhou nas mesmas condicoes. E a
    mesma chamada, fora do bundle (`uv run dj scan`), tambem nunca falhou --
    o numpy e o mesmo, o codigo e o mesmo, so o lancamento via bootloader do
    PyInstaller difere.
    A "intermitencia" relatada antes era esse mesmo bug escondido atras de
    testes que sempre passavam por pool (>1 pendente, >1 worker): cada
    subprocesso corre o risco uma vez; com centenas de tracks, uma morte rara
    ja bastava para a cascata de BrokenProcessPool.
    Causa raiz de POR QUE rodar fora de subprocesso crasha continua aberta
    (suspeita: dispatch de SIMD do numpy colidindo com o bootstrap da thread
    pool interna do scipy/ducc0 na primeira chamada do processo -- ver
    threads ociosas em `ducc_thread_pool::worker_main` no backtrace). Mas o
    gatilho determinista foi isolado, e o fix e nao depender de entender o
    numpy: nunca deixar o processo principal chamar `extract_one`.
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


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


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


@dataclass(frozen=True)
class FailedItem:
    filename: str
    reason: str


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


class TrackService:
    def __init__(
        self,
        config: Config,
        extractor: FeatureExtractor | None = None,
        max_workers: int | None = None,
    ):
        self.config = config
        self.extractor = extractor or HandcraftedExtractor()
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.sha1_cache = Sha1Cache(config.data_dir / "sha1.json")
        self.presentation = PresentationCache(
            config.data_dir / "presentation.parquet",
            config.data_dir / "covers",
        )
        self.peaks = PeaksStore(config.data_dir / "peaks")
        self.model_path = config.data_dir / "model.joblib"
        self.model = self._load_model()
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

    def analyze_all(
        self,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> bool:
        """Varre, extrai o que falta e reconstroi _labeled/_inbox.

        should_cancel e consultado entre extracoes; devolve True se o scan foi
        interrompido. Interromper NAO e falhar: o que nao foi extraido
        simplesmente continua pendente para o proximo scan, sem entrar em
        failures(). O que ja foi extraido esta no cache e e preservado.
        """
        self._failures = []
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
                self._failures.append(FailedItem(filename=ref.path.name, reason=erro))
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
            coletados: set[str] = set()

            def _processa_e_marca(ref: TrackRef, analise, erro: str | None) -> None:
                _processa_resultado(ref, analise, erro)
                coletados.add(ref.sha1)

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
            #
            # Todo item do bloco sai marcado (sucesso ou falha) antes do bloco
            # seguinte, entao o laco termina sempre -- sem orcamento de
            # tentativas e sem risco de girar numa track ruim.
            _fixa_threads_dos_workers()
            tamanho_do_bloco = max(self._max_workers * 4, 1)

            for inicio in range(0, len(pendentes), tamanho_do_bloco):
                if cancelado:
                    break
                bloco = pendentes[inicio : inicio + tamanho_do_bloco]
                try:
                    with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
                        futuros = {
                            executor.submit(extract_one, self.extractor, ref.path): ref
                            for ref in bloco
                        }
                        for futuro in as_completed(futuros):
                            ref = futuros[futuro]
                            try:
                                analise, erro = futuro.result()
                            except Exception:
                                # extract_one ja captura excecoes da propria
                                # extracao, entao chegar aqui significa que o
                                # worker morreu. Nao marca como falha: a
                                # retentativa isolada abaixo tenta de novo.
                                continue
                            _processa_e_marca(ref, analise, erro)

                            if cancelou():
                                cancelado = True
                                # Todos os futuros do bloco ja foram submetidos,
                                # entao nao basta parar de submeter: shutdown
                                # com cancel_futures descarta os que ainda nao
                                # comecaram. Os que JA estao rodando terminam --
                                # matar um processo no meio de um
                                # ffmpeg/librosa nao e opcao, entao o
                                # cancelamento custa, no pior caso, uma
                                # extracao (5-15s). wait=False porque o
                                # __exit__ do `with` ja faz o shutdown(wait=True)
                                # que espera os em voo; adiantar o descarte da
                                # fila e o unico objetivo desta chamada.
                                executor.shutdown(wait=False, cancel_futures=True)
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
                            analise, erro = solo.submit(
                                extract_one, self.extractor, ref.path
                            ).result()
                    except Exception as falha:
                        analise, erro = None, f"worker falhou: {falha}"
                    _processa_e_marca(ref, analise, erro)

        # as_completed devolve em ordem de conclusao, nao de entrada. Reordena
        # pela ordem original de `refs` para que _labeled/_inbox fiquem
        # deterministicos entre execucoes -- library.py ja ordena de forma
        # estavel, e essa garantia nao pode se perder aqui.
        posicao = {ref.sha1: i for i, ref in enumerate(refs)}
        return sorted(aceitos, key=lambda ref: posicao[ref.sha1]), cancelado

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
        return self.model.metrics_

    def failures(self) -> list[FailedItem]:
        return list(self._failures)

    def queue(self) -> list[QueueItem]:
        vivos = [ref for ref in self._inbox if ref.path.is_file()]
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
            if ref.sha1 == sha1:
                return ref.path
        raise KeyError(f"Track fora da fila: {sha1}")

    def decide(self, sha1: str, label: Label) -> bool:
        ref = next((r for r in self._inbox if r.sha1 == sha1), None)
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
        )
        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        self._labeled.append(TrackRef(path=destino, label=label, sha1=ref.sha1))
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
            destino = move_to_folder(ref.path, self.config.folders[label])
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
        )
        self._labeled = [
            TrackRef(path=destino, label=label, sha1=sha1) if r.sha1 == sha1 else r
            for r in self._labeled
        ]
        return self._conta_decisao()

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
                TrackRef(path=de_volta, label=None, sha1=decisao.sha1),
            )
        else:
            # Veio de outra pasta rotulada (reclassify): continua na biblioteca,
            # so volta a ter o rotulo antigo. Nunca entra na inbox -- ela nunca
            # esteve la.
            self._labeled = [
                TrackRef(path=de_volta, label=decisao.origem_label, sha1=decisao.sha1)
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
