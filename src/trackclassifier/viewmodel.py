"""Traducao de TrackService para dados de tela.

Este modulo nao importa nenhum toolkit de UI, e isso e regra de fronteira,
nao acaso: e o que permite testar a logica de tela -- o que aparece na
linha, quantas faltam, quando a fila esvazia -- com pytest puro, e o que
deixa `serve.py` montar o JSON da web a partir dos mesmos dados.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from .keys import Key
from .model import classes_faltando, per_class_metrics, weighted_f1
from .profiles import nome_de
from .service import TrackService

#: Quantas proximas mostrar no rodape da aba Revisao.
PROXIMAS = 3


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
    # Caminho no disco, para quem precisa tocar o arquivo -- o sha1 sozinho
    # basta para identidade, mas nao para abrir o audio. Guardado como string
    # (nao Path) porque este modulo e a fronteira de dados-puros, e Path
    # carrega comportamento de mais. Quem consome converte.
    path_hint: str
    # Tags lidas por presentation.py. Todas opcionais: um acervo de promos e
    # rips costuma vir sem metadado nenhum, e isso nao e um estado de erro.
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    #: Album da tag. Entrou na rodada de fidelidade da Biblioteca porque a
    #: busca passou a cobri-lo (o mockup pede "titulo, artista, album ou
    #: arquivo") -- o PresentationCache ja o lia desde a v0.2, mas o campo
    #: morria ali.
    album: str | None = None
    #: Caminho de covers/<sha1><ext>, ja verificado como existente por
    #: PresentationCache.cover_path. String pelo mesmo motivo de path_hint:
    #: este modulo e a fronteira de dados puros, e Path carrega comportamento
    #: de mais. Quem consome converte.
    cover_path: str | None = None
    #: Caminho de peaks/<sha1>.npy quando os buckets por banda ja foram
    #: computados; None enquanto nao foram. Enquanto e None, a onda cai no
    #: render mono derivado de energy_curve -- por isso energy_curve nao pode
    #: sumir da TrackRow, mesmo depois do RGB existir. String (nao Path) pelo
    #: mesmo motivo de path_hint e cover_path: este modulo e a fronteira de
    #: dados puros.
    peaks_path: str | None = None
    #: Tonalidade canonica lida da tag. None quando a track nao tem key na
    #: tag -- a maioria de um acervo de promos. Guardada como Key (pitch +
    #: modo), nunca como string formatada: e o que permite o alternador de
    #: notacao Camelot/classica trocar a exibicao sem reler nada.
    key: Key | None = None
    #: De onde veio a key: "tag", "audio" (estimada por chroma), "none" (a
    #: deteccao por audio foi tentada e nao achou) ou None (nunca tentada).
    #: E o que o front usa para decidir se pede a deteccao e para rotular o
    #: chip como estimativa.
    key_source: str | None = None

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
    profiles: tuple[str, ...]
    active_profile: str


@dataclass(frozen=True)
class LibraryState:
    rows: tuple[TrackRow, ...]
    #: Exemplos por classe, na ordem de LABEL_ORDER. Vem de
    #: service.class_counts() -- a MESMA fonte que a aba Modelo usa, para a
    #: Biblioteca nao ter uma segunda definicao de "quantas de cada classe".
    #: Tres posicoes mesmo com a biblioteca vazia: chip em zero e informacao
    #: ("falta esta classe"), chip ausente seria layout pulando de largura.
    class_counts: tuple[int, ...] = (0, 0, 0)
    #: Tamanho da biblioteca. Igual a len(rows) hoje; separado porque e o
    #: numero que o chip "Todos" mostra e ele nao depende das rows estarem
    #: materializadas na tela.
    total: int = 0
    #: Generos e keys que EXISTEM no acervo, nao os que sobraram do filtro
    #: corrente -- mesma ideia das contagens acima. Sao valores, e nao
    #: TrackRows, porque e o que o filtro exibe (a ordem de roda das keys e
    #: decisao daqui, nao da tela).
    genres: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelState:
    accuracy: float | None
    ordinal_mae: float | None
    confusion: tuple[tuple[int, ...], ...] | None
    n_examples: int
    #: (filename, reason, category). A categoria e o que a aba Modelo usa
    #: para agrupar -- reason carrega o nome do arquivo e nao agrupa nada.
    failures: tuple[tuple[str, str, str], ...]
    #: Exemplos por classe na ordem de LABEL_ORDER. Existe mesmo sem
    #: treino: e o dado que responde "o que rotular agora".
    class_counts: tuple[int, ...]
    decisions_since_train: int
    retrain_every: int
    #: Minimo de exemplos por classe; alimenta o low_confidence_mode e e
    #: editado junto do retrain_every no painel de configuracao da web.
    min_examples: int
    #: None = da para treinar. Texto = o motivo, pronto para a tela.
    train_blocked_reason: str | None
    low_confidence: bool
    #: None enquanto o modelo nao treinou. Os defaults de TrackModel nao
    #: dizem nada sobre esta biblioteca, entao nao viram numero na tela.
    alpha: float | None
    thresholds: tuple[float, float] | None
    extractor_name: str
    # Camada do dashboard web. Fica no fim da dataclass porque os campos
    # precisam de default (default nao precede obrigatorio).
    #: F1 ponderado pelo suporte real, mesmo estimador do sklearn. None
    #: sem treino, como os outros indicadores.
    weighted_f1: float | None = None
    #: (precision, recall, f1) por classe na ordem de LABEL_ORDER, na
    #: confusion LOO. None sem treino. O no-treinado nao tem barra por
    #: classe: precisao/recall do LOO nao existem sem a passada LOO.
    per_class: tuple[tuple[float, float, float], ...] | None = None
    #: Versao do modelo ativo ("v2.1.0"), stampada no historico pelo
    #: treino. None sem treino. Vive aqui e nao no TrackModel porque a
    #: fonte de verdade e a sequencia de treinos gravada em disco.
    version: str | None = None
    #: ISO local do ultimo treino (st_mtime no backfill de artefato antigo).
    last_trained_at: str | None = None
    #: Treinos mais recentes primeiro, ate 12: as linhas da tabela e as
    #: series dos sparklines vem daqui, sem re-ler o JSON na UI.
    #: Linha = (ts, version, n_examples, accuracy, ordinal_mae, weighted_f1).
    history: tuple[tuple[str, str, int, float, float, float], ...] = ()
    #: Delta do treino ativo versus o anterior NA MESMA era do extractor.
    #: Vazio = sem anterior ou era diferente (vetores de feature mudaram --
    #: comparar seria enganar).
    deltas: tuple[tuple[str, float], ...] = ()


def _row_da_fila(item, service: TrackService) -> TrackRow:
    registro = service.presentation_for(item.sha1)
    capa = service.cover_path_for(item.sha1)
    picos = service.peaks_for(item.sha1)
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
        album=registro.album if registro is not None else None,
        cover_path=str(capa) if capa is not None else None,
        peaks_path=str(picos) if picos is not None else None,
        key=service.key_for(item.sha1),
        key_source=service.key_source_for(item.sha1),
    )


def review_state(service: TrackService) -> ReviewState:
    fila = service.queue()
    # Nomes de exibicao: a chave em Config.profiles e o id (slug), e a pill da
    # Revisao troca por nome (profiles.resolver resolve).
    perfis = tuple(nome_de(key, p) for key, p in service.config.profiles.items())
    ativo = nome_de(service.config.active_profile, service.config.profile)
    if not fila:
        return ReviewState(
            current=None,
            upcoming=(),
            low_confidence=service.model.low_confidence_mode,
            remaining=0,
            profiles=perfis,
            active_profile=ativo,
        )
    return ReviewState(
        current=_row_da_fila(fila[0], service),
        upcoming=tuple(_row_da_fila(item, service) for item in fila[1 : 1 + PROXIMAS]),
        low_confidence=service.model.low_confidence_mode,
        remaining=len(fila),
        profiles=perfis,
        active_profile=ativo,
    )


def _generos_do_acervo(rows: Iterable[TrackRow]) -> tuple[str, ...]:
    """Generos que existem no acervo, ordenados e sem repeticao.

    Montado aqui, e nao na tela, pelo mesmo motivo das contagens: o filtro
    nao pode ter uma segunda definicao de "quais generos existem". Vazio e
    None ficam de fora -- tag ausente nao e um genero chamado "".
    """
    return tuple(sorted({row.genre for row in rows if row.genre}))


def _keys_em_ordem_de_roda(camelots: Iterable[str]) -> tuple[str, ...]:
    """Keys presentes, em ordem de roda: numero Camelot e depois modo.

    Nao e ordem alfabetica de proposito. 12A e vizinha de 1A, nao de 1B, e
    como texto "12A" viria antes de "2A" -- o contrario do que a coluna Key
    serve para fazer. Recebe strings ja formatadas ("6A") em vez de Key
    porque a ordem depende so do numero e do modo, que estao no proprio
    rotulo.
    """
    return tuple(sorted(set(camelots), key=lambda k: (int(k[:-1]), k[-1])))


def library_state(service: TrackService) -> LibraryState:
    linhas = []
    for ref in service._labeled:
        analise = service._analysis(ref)
        registro = service.presentation_for(ref.sha1)
        capa = service.cover_path_for(ref.sha1)
        picos = service.peaks_for(ref.sha1)
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
                album=registro.album if registro is not None else None,
                cover_path=str(capa) if capa is not None else None,
                peaks_path=str(picos) if picos is not None else None,
                key=service.key_for(ref.sha1),
                key_source=service.key_source_for(ref.sha1),
            )
        )
    return LibraryState(
        rows=tuple(linhas),
        class_counts=service.class_counts(),
        total=len(linhas),
        genres=_generos_do_acervo(linhas),
        keys=_keys_em_ordem_de_roda(
            linha.key.camelot for linha in linhas if linha.key is not None
        ),
    )


def _motivo_do_bloqueio(service: TrackService) -> str | None:
    """None = da para treinar. A regra vem de model.classes_faltando.

    Nao reimplementar aqui: a mesma pergunta e feita por fit() na hora do
    treino, e duas respostas divergentes dariam um botao habilitado que
    falha ao clicar -- exatamente o comportamento que este campo remove.
    """
    faltando = classes_faltando(ref.label for ref in service._labeled if ref.label is not None)
    if not faltando:
        return None
    return (
        f"Faltam exemplos de {', '.join(faltando)} -- o modelo precisa "
        "das tres classes para treinar."
    )


def model_state(service: TrackService) -> ModelState:
    metricas = service.model.metrics_
    falhas = tuple(
        (falha.filename, falha.reason, falha.category) for falha in service.failures()
    )
    contagens = service.class_counts()
    # Recentes primeiro: a tabela do dashboard exibe o ultimo treino na
    # primeira linha e o cap de 12 cobre tabela e series dos sparklines.
    historia_ordenada = list(reversed(service.historico_treinos()))[:12]
    comum = {
        "failures": falhas,
        "class_counts": contagens,
        "decisions_since_train": service.decisions_since_train,
        "retrain_every": service.config.retrain_every,
        "min_examples": service.config.min_examples,
        "train_blocked_reason": _motivo_do_bloqueio(service),
        "low_confidence": service.model.low_confidence_mode,
        "extractor_name": service.extractor.name,
    }
    if metricas is None:
        # n_examples sai do balanco, e nao de metrics_: sem treino nao ha
        # metrica, mas ha exemplos rotulados -- e a tela mostra quantos.
        # alpha_ e thresholds_ tem default no TrackModel desde o __init__;
        # expo-los como se fossem resultado de treino seria mentira.
        return ModelState(
            accuracy=None,
            ordinal_mae=None,
            confusion=None,
            n_examples=sum(contagens),
            weighted_f1=None,
            per_class=None,
            version=None,
            last_trained_at=None,
            history=tuple(
                (e.ts, e.version, e.n_examples, e.accuracy, e.ordinal_mae, e.weighted_f1)
                for e in historia_ordenada
            ),
            deltas=(),
            alpha=None,
            thresholds=None,
            **comum,
        )
    return ModelState(
        accuracy=metricas.accuracy,
        ordinal_mae=metricas.ordinal_mae,
        confusion=tuple(tuple(linha) for linha in metricas.confusion),
        n_examples=metricas.n_examples,
        weighted_f1=weighted_f1(metricas.confusion),
        per_class=per_class_metrics(metricas.confusion),
        version=historia_ordenada[0].version if historia_ordenada else None,
        last_trained_at=historia_ordenada[0].ts if historia_ordenada else None,
        history=tuple(
            (e.ts, e.version, e.n_examples, e.accuracy, e.ordinal_mae, e.weighted_f1)
            for e in historia_ordenada
        ),
        deltas=_deltas_contra_anterior(service),
        alpha=service.model.alpha_,
        thresholds=service.model.thresholds_,
        **comum,
    )


def _deltas_contra_anterior(service: TrackService) -> tuple[tuple[str, float], ...]:
    """Diferencas do treino ativo versus o treino imediatamente anterior.

    O treino ativo e a ultima entrada gravada: `_registrar_treino` roda no
    unico fluxo que substitui o joblib, e o backfill do boot cobre artefato
    antigo, entao history[-1] e history[-2] sao treino atual e anterior.
    Restricao de era: o extractor determina o vetor de features, entao
    treino de era diferente nao e comparavel e o delta vira ausente -- um
    chip "-2,3%" sobre metricas de uma formula de score antiga contaria a
    verdade errada.
    """
    entradas = service.historico_treinos()
    if len(entradas) < 2:
        return ()
    ativo, anterior = entradas[-1], entradas[-2]
    if ativo.extractor != anterior.extractor:
        return ()
    return (
        ("accuracy", ativo.accuracy - anterior.accuracy),
        ("ordinal_mae", ativo.ordinal_mae - anterior.ordinal_mae),
        ("weighted_f1", ativo.weighted_f1 - anterior.weighted_f1),
    )


def texto_de_atualizacao(release, versao_atual: str, n_tracks: int) -> str:
    """Corpo do dialogo de confirmacao da atualizacao.

    Mora aqui, e nao na tela, porque e a parte que mais precisa de teste e
    a que mais vai mudar de redacao: o usuario decide atualizar ou nao com
    base nestas linhas. O tipo de `release` nao esta anotado de proposito --
    anotar exigiria importar updates.py, e este modulo se mantem sem
    dependencia de nada alem de dataclasses do dominio.
    """
    linhas = [f"Versao {versao_atual} instalada. Versao {release.version} disponivel."]

    if release.notas.strip():
        linhas += ["", release.notas.strip()]

    if release.recomputa:
        linhas += [
            "",
            f"Esta versao recalcula a analise das {n_tracks} tracks da "
            "biblioteca. O proximo scan vai demorar mais que o normal.",
        ]

    linhas += ["", "Suas classificacoes e as pastas do acervo nao sao alteradas."]
    return "\n".join(linhas)
