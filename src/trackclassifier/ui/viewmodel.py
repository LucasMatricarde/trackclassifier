"""Traducao de TrackService para dados de tela.

Este modulo nao importa Qt, e isso e regra de fronteira, nao acaso: e o
que permite testar a logica de tela -- o que aparece na linha, quantas
faltam, quando a fila esvazia -- com pytest puro, sem QApplication e sem
dispositivo de audio.
"""

from dataclasses import dataclass

from ..labels import LABEL_ORDER
from ..service import TrackService

#: Quantas proximas mostrar no rodape da aba Revisao.
PROXIMAS = 3

#: Ordem estavel dos rotulos (-1, neutra, +1) para cabecalhos e matriz de
#: confusao. Reexportado do dominio para model_tab.py nao importar labels
#: direto -- a UI so fala com o dominio pelo viewmodel.
LABELS_EM_ORDEM = tuple(rotulo.value for rotulo in LABEL_ORDER)


@dataclass(frozen=True)
class TrackRow:
    sha1: str
    filename: str
    label: str | None
    predicted: str | None
    score: float | None
    confidence: float | None
    bpm: float
    duration_s: float
    energy_curve: tuple[float, ...]
    peak_offset_s: float
    # Caminho no disco, para a aba Revisao entregar ao player -- o sha1
    # sozinho basta para identidade, mas nao para tocar o arquivo. Guardado
    # como string (nao Path) porque este modulo e a fronteira de dados-puros
    # da UI, e Path carrega comportamento de mais. Quem consome converte:
    # review_tab faz Path(row.path_hint) antes de chamar BasePlayer.load.
    path_hint: str
    # Tags lidas por presentation.py. Todas opcionais: um acervo de promos e
    # rips costuma vir sem metadado nenhum, e isso nao e um estado de erro.
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    #: Caminho de covers/<sha1><ext>, ja verificado como existente por
    #: PresentationCache.cover_path. String pelo mesmo motivo de path_hint:
    #: este modulo e a fronteira de dados puros, e Path carrega comportamento
    #: de mais. Quem consome converte.
    cover_path: str | None = None

    @property
    def display_title(self) -> str:
        """O que a tela mostra como titulo.

        Sem tag, o nome do arquivo e a unica identificacao que o usuario tem
        -- e e o que a coluna Arquivo mostrava antes desta fase, entao nada
        se perde ao troca-la por Titulo.
        """
        return self.title or self.filename


@dataclass(frozen=True)
class ReviewState:
    current: TrackRow | None
    upcoming: tuple[TrackRow, ...]
    low_confidence: bool
    remaining: int


@dataclass(frozen=True)
class LibraryState:
    rows: tuple[TrackRow, ...]


@dataclass(frozen=True)
class ModelState:
    accuracy: float | None
    ordinal_mae: float | None
    confusion: tuple[tuple[int, ...], ...] | None
    n_examples: int
    failures: tuple[tuple[str, str], ...]


def format_duration(seconds: float) -> str:
    total = int(max(0.0, seconds))
    return f"{total // 60}:{total % 60:02d}"


def _row_da_fila(item, service: TrackService) -> TrackRow:
    registro = service.presentation_for(item.sha1)
    capa = service.cover_path_for(item.sha1)
    return TrackRow(
        sha1=item.sha1,
        filename=item.filename,
        label=None,
        predicted=item.label.value,
        score=item.score,
        confidence=item.confidence,
        bpm=item.bpm,
        duration_s=item.duration_s,
        energy_curve=tuple(item.energy_curve),
        peak_offset_s=item.peak_offset_s,
        path_hint=str(item.path),
        title=registro.title if registro is not None else None,
        artist=registro.artist if registro is not None else None,
        genre=registro.genre if registro is not None else None,
        cover_path=str(capa) if capa is not None else None,
    )


def review_state(service: TrackService) -> ReviewState:
    fila = service.queue()
    if not fila:
        return ReviewState(
            current=None,
            upcoming=(),
            low_confidence=service.model.low_confidence_mode,
            remaining=0,
        )
    return ReviewState(
        current=_row_da_fila(fila[0], service),
        upcoming=tuple(_row_da_fila(item, service) for item in fila[1 : 1 + PROXIMAS]),
        low_confidence=service.model.low_confidence_mode,
        remaining=len(fila),
    )


def library_state(service: TrackService) -> LibraryState:
    linhas = []
    for ref in service._labeled:
        analise = service._analysis(ref)
        registro = service.presentation_for(ref.sha1)
        capa = service.cover_path_for(ref.sha1)
        linhas.append(
            TrackRow(
                sha1=ref.sha1,
                filename=ref.path.name,
                label=ref.label.value if ref.label is not None else None,
                predicted=None,
                score=None,
                confidence=None,
                bpm=analise.bpm,
                duration_s=analise.duration_s,
                energy_curve=tuple(analise.energy_curve),
                peak_offset_s=analise.peak_offset_s,
                path_hint=str(ref.path),
                title=registro.title if registro is not None else None,
                artist=registro.artist if registro is not None else None,
                genre=registro.genre if registro is not None else None,
                cover_path=str(capa) if capa is not None else None,
            )
        )
    return LibraryState(rows=tuple(linhas))


def model_state(service: TrackService) -> ModelState:
    metricas = service.model.metrics_
    falhas = tuple((falha.filename, falha.reason) for falha in service.failures())
    if metricas is None:
        return ModelState(
            accuracy=None,
            ordinal_mae=None,
            confusion=None,
            n_examples=0,
            failures=falhas,
        )
    return ModelState(
        accuracy=metricas.accuracy,
        ordinal_mae=metricas.ordinal_mae,
        confusion=tuple(tuple(linha) for linha in metricas.confusion),
        n_examples=metricas.n_examples,
        failures=falhas,
    )
