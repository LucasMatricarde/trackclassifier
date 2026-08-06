import os
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
from .labels import Label
from .library import Sha1Cache, TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel

_CACHE_SAVE_EVERY = 10

ProgressCallback = Callable[[int, int, str], None]


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
        self._max_workers = max_workers or min(os.cpu_count() or 1, 8)

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

    def analyze_all(self, on_progress: ProgressCallback | None = None) -> None:
        self._failures = []
        candidatos = scan_labeled(self.config, self.sha1_cache) + scan_inbox(
            self.config, self.sha1_cache
        )
        # Salva antes de extrair: a varredura sozinha ja custou o I/O, e uma
        # interrupcao durante a extracao nao pode jogar esse trabalho fora.
        self.sha1_cache.save()
        aceitos = self._analyze(candidatos, on_progress)
        self._labeled = [ref for ref in aceitos if ref.label is not None]
        self._inbox = [ref for ref in aceitos if ref.label is None]
        self.cache.save()

    def _analyze(
        self, refs: list[TrackRef], on_progress: ProgressCallback | None = None
    ) -> list[TrackRef]:
        aceitos: list[TrackRef] = []
        pendentes: list[TrackRef] = []
        for ref in refs:
            if self.cache.get(ref.sha1, self.extractor.name) is not None:
                aceitos.append(ref)
            else:
                pendentes.append(ref)

        if not pendentes:
            return aceitos

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

        usa_pool = self._max_workers > 1 and total > 1

        if not usa_pool:
            for ref in pendentes:
                analise, erro = extract_one(self.extractor, ref.path)
                _processa_resultado(ref, analise, erro)
        else:
            coletados: set[str] = set()

            def _processa_e_marca(ref: TrackRef, analise, erro: str | None) -> None:
                _processa_resultado(ref, analise, erro)
                coletados.add(ref.sha1)

            try:
                with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
                    futuros = {
                        executor.submit(extract_one, self.extractor, ref.path): ref
                        for ref in pendentes
                    }
                    for futuro in as_completed(futuros):
                        ref = futuros[futuro]
                        try:
                            analise, erro = futuro.result()
                        except Exception as falha_do_worker:
                            # extract_one ja captura excecoes da propria extracao,
                            # entao chegar aqui significa que o worker morreu
                            # (segfault em ffmpeg/librosa, OOM, BrokenProcessPool).
                            # Contem a falha como qualquer outra em vez de derrubar
                            # o scan inteiro: o cache ja salvo e preservado, e uma
                            # re-execucao tenta de novo so o que falhou.
                            analise, erro = None, f"worker falhou: {falha_do_worker}"
                        _processa_e_marca(ref, analise, erro)
            except Exception as falha_do_pool:
                # Isto e distinto do try/except por-future acima: aqui o
                # PROPRIO pool falhou -- construcao (OSError por exaustao de
                # fd/semaforo) ou .submit() (BrokenProcessPool se um worker
                # morre durante o startup do pool, antes de qualquer future
                # existir, ou RuntimeError se chamado apos shutdown). Nenhum
                # desses e capturado pelo try/except de futuro.result() porque
                # podem acontecer antes de qualquer future ser criado. Contem
                # como falha todo pendente ainda nao coletado, em vez de deixar
                # a excecao propagar de _analyze/analyze_all e derrubar o scan
                # inteiro sem chamar o cache.save() final -- os saves
                # periodicos ja feitos ate aqui continuam no disco.
                for ref in pendentes:
                    if ref.sha1 not in coletados:
                        _processa_e_marca(
                            ref, None, f"pool de execucao falhou: {falha_do_pool}"
                        )

        # as_completed devolve em ordem de conclusao, nao de entrada. Reordena
        # pela ordem original de `refs` para que _labeled/_inbox fiquem
        # deterministicos entre execucoes -- library.py ja ordena de forma
        # estavel, e essa garantia nao pode se perder aqui.
        posicao = {ref.sha1: i for i, ref in enumerate(refs)}
        return sorted(aceitos, key=lambda ref: posicao[ref.sha1])

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
