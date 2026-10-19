"""Behavior and geometry of the new dashboard composition."""

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.app_header import AppHeader
from trackclassifier.ui.widgets.review_header import ReviewHeader
from trackclassifier.ui.widgets.review_queue import ReviewQueueStrip
from trackclassifier.ui.widgets.track_inspector import TrackInspector
from trackclassifier.ui.widgets.waveform_overview import WaveformOverview


def _row() -> TrackRow:
    return TrackRow(
        sha1="track-a",
        filename="sample.wav",
        label="-1",
        predicted="neutra",
        score=0.2,
        confidence=0.73,
        bpm=123.0,
        duration_s=433.0,
        energy_curve=(0.2, 0.8, 0.3),
        peak_offset_s=154.0,
        path_hint="/tmp/sample.wav",
        title="The 11th Hour",
        artist="Brunello & Cella Babini",
        genre="Tech House",
    )


def test_header_roteia_pagina_e_scan(qapp):
    header = AppHeader(("Revisao", "Biblioteca", "Modelo", "Configuracao"))
    pages = []
    scans = []
    header.page_requested.connect(pages.append)
    header.scan_requested.connect(lambda: scans.append(True))

    header._buttons[1].click()
    header.scan_button.click()

    assert pages == [1]
    assert scans == [True]
    assert header._buttons[1].isChecked()


def test_review_header_mostra_dados_reais_e_progresso_local(qapp):
    header = ReviewHeader()
    header.set_track(_row(), remaining=30, position=2, low_confidence=False)

    assert header.title.text() == "The 11th Hour"
    assert header.genre.text() == "Tech House"
    assert header.prediction.text() == "neutra"
    assert header.confidence.text() == "0.73"
    assert header.progress.text() == "2 / 30"
    assert header.progress_bar.fraction() == 2 / 30


def test_overview_descarta_peaks_de_outra_track(qapp):
    overview = WaveformOverview()
    overview.set_row(_row())
    overview.set_peaks_path("outra", "/tmp/late.npy")
    # O estado da mini-onda mora no _MiniOnda interno desde que os botoes
    # < > da Fase 4 dividiram o widget em moldura + onda.
    assert overview._mini._peaks_path is None


def test_fila_e_inspector_refletem_a_track_sem_acao_falsa(qapp):
    queue = ReviewQueueStrip()
    queue.set_rows((_row(),), remaining=1)
    assert queue.total() == 1
    assert queue.model().row_at(0).display_title == "The 11th Hour"

    inspector = TrackInspector()
    inspector.set_track(_row())
    assert inspector.isEnabled()
    assert inspector.title.text() == "The 11th Hour"
    assert inspector.ficha["Classe atual"].valor.text() == "-1"


def test_a_ficha_tecnica_tem_os_pares_na_ordem_do_design(qapp):
    """Genero, BPM, Key, Duracao, Classe -- e Confianca depois.

    A ficha substitui a linha unica de texto ("Genero: X\nBPM: Y...") por
    pares rotulo/valor: o olho acha o numero sem ler a frase inteira, e o
    valor numerico pode ficar em mono, que e a regra do sistema."""
    from dataclasses import replace

    from trackclassifier.ui.viewmodel import format_duration

    inspector = TrackInspector()
    inspector.set_track(
        replace(_row(), genre="Progressive House", bpm=128.0, duration_s=433.0)
    )

    assert list(inspector.ficha) == [
        "Genero",
        "BPM",
        "Key (Camelot)",
        "Duracao",
        "Classe atual",
        "Confianca",
    ]
    assert inspector.ficha["Genero"].valor.text() == "Progressive House"
    assert inspector.ficha["BPM"].valor.text() == "128"
    assert inspector.ficha["Duracao"].valor.text() == format_duration(433.0)
    assert inspector.ficha["Classe atual"].valor.text() == "-1"


def test_a_key_da_ficha_e_camelot_e_sem_key_e_travessao(qapp):
    """Camelot sempre: o painel nao segue o alternador de notacao da tabela, e
    o proprio rotulo diz qual notacao esta mostrando.

    Sem key, o chip mostra o travessao apagado -- um chip colorido vazio
    sugeriria que a track TEM tonalidade e o app so nao soube formatar."""
    from dataclasses import replace

    from trackclassifier.keys import Key, KeyNotation, Mode
    from trackclassifier.ui.widgets.key_chip import format_key

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), key=Key(3, Mode.MAJOR)))
    assert inspector.ficha["Key (Camelot)"].valor.text() == Key(3, Mode.MAJOR).camelot

    inspector.set_track(replace(_row(), key=None))
    assert inspector.ficha["Key (Camelot)"].valor.text() == format_key(
        None, KeyNotation.CAMELOT
    )


def test_confianca_so_aparece_quando_existe(qapp):
    """Na Biblioteca a confianca e None por construcao (a track ja esta
    classificada, e a confianca do modelo sobre uma decisao humana tomada nao
    muda acao -- ver o design). Uma linha fixa com travessao seria ruido
    permanente: mostrar condicional e a diferenca entre "nao se aplica" e
    "faltou dado"."""
    from dataclasses import replace

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), confidence=None))
    assert not inspector.ficha["Confianca"].caixa.isVisibleTo(inspector)

    inspector.set_track(replace(_row(), confidence=0.73))
    assert inspector.ficha["Confianca"].caixa.isVisibleTo(inspector)
    assert inspector.ficha["Confianca"].valor.text() == "73%"


def test_capa_ausente_cai_no_placeholder_com_a_inicial(qapp):
    """Sem capa e o caso comum (acervo de promos nao tem tag nenhuma, e sem
    tag nao ha capa): em vez de area vazia, a inicial do titulo sobre o fundo
    de capa -- a mesma leitura que a coluna Capa da tabela ja faz."""
    from dataclasses import replace

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), cover_path=""))

    assert inspector.cover.text() == "T"
    assert inspector.cover.pixmap().isNull()

def test_estado_vazio_mantem_a_anatomia_e_desabilita_as_acoes(qapp):
    """Sem selecao o painel NAO fica setEnabled(False).

    Desabilitar o painel inteiro pintava de cinza os rotulos da ficha E deixava
    o texto de "Selecione uma musica" aceso: o estado mais barulhento e menos
    informativo possivel. O que desabilita sao as ACOES, uma a uma -- a anatomia
    (capa fantasma, ficha vazia) continua na tela, porque e ela que mostra o que
    vai aparecer quando houver selecao.
    """
    from trackclassifier.keys import KeyNotation
    from trackclassifier.ui.widgets.key_chip import format_key

    inspector = TrackInspector()
    inspector.set_track(None)

    assert inspector.isEnabled()
    assert not inspector.play.isEnabled()
    assert [botao.isEnabled() for botao in inspector.class_buttons] == [False, False, False]

    # A anatomia permanece: a capa mantem a moldura (fantasma, sem imagem), os
    # rotulos da ficha seguem na tela com os valores vazios, e a Confianca some
    # -- ela nao e dado que falta, e dado que nao se aplica.
    assert inspector.cover.styleSheet() != ""
    assert inspector.cover.pixmap().isNull()
    assert inspector.title.text() == "Selecione uma musica"
    assert inspector.ficha["Genero"].valor.text() == ""
    assert inspector.ficha["BPM"].valor.text() == ""
    assert inspector.ficha["Duracao"].valor.text() == ""
    assert inspector.ficha["Classe atual"].valor.text() == ""
    assert inspector.ficha["Key (Camelot)"].valor.text() == format_key(
        None, KeyNotation.CAMELOT
    )
    assert not inspector.ficha["Confianca"].caixa.isVisibleTo(inspector)


def test_selecionar_preenche_sem_trocar_de_layout(qapp):
    """Estado vazio e preenchido sao o MESMO layout.

    Se a ficha mudasse de forma ao selecionar (linha entrando, caixa sumindo), o
    painel pularia de posicao a cada clique na tabela e o olho perderia a
    referencia de onde as coisas estao. O unico dado que aparece e a Confianca --
    por isso ela e uma caixa escondida, e nao uma linha criada na hora.
    """
    inspector = TrackInspector()
    inspector.set_track(None)
    valores = [par.valor for par in inspector.ficha.values()]
    caixas = [par.caixa for par in inspector.ficha.values()]
    itens = inspector.layout().count()

    inspector.set_track(_row())

    assert [par.valor for par in inspector.ficha.values()] == valores
    assert [par.caixa for par in inspector.ficha.values()] == caixas
    assert inspector.layout().count() == itens
    assert inspector.play.isEnabled()
    assert all(botao.isEnabled() for botao in inspector.class_buttons)

def _clique_na_onda(inspector, x: int) -> None:
    """Clique de verdade (QTest) no centro vertical da onda, em `x`.

    A janela precisa estar mostrada para o layout dar largura a onda -- a fracao
    e x / largura, entao quem chuta a largura chuta o resultado.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    inspector.show()
    assert inspector.wave.width() > 0  # mostrada: o layout ja deu largura
    QTest.mouseClick(
        inspector.wave,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(x, inspector.wave.height() // 2),
    )


def test_clicar_na_onda_pede_seek_na_fracao_do_clique(qapp):
    """A onda do inspector e a MESMA WaveformView da Revisao (buckets por banda
    quando existem, curva mono quando nao), e o clique vale posicao: o pedido sai
    como fracao, e quem transforma em ms e o player (seek_fraction)."""
    import pytest

    inspector = TrackInspector()
    inspector.set_track(_row())
    inspector.show()
    qapp.processEvents()
    fracoes: list[float] = []
    inspector.seek_requested.connect(fracoes.append)
    meio = inspector.wave.width() // 2

    _clique_na_onda(inspector, meio)

    assert fracoes == [pytest.approx(meio / inspector.wave.width())]


def test_sem_track_a_onda_nao_pede_seek(qapp):
    """O WaveformView emite sempre -- ele nao sabe o que esta desenhando. Sem
    selecao, o clique na area da onda pediria seek da posicao de musica nenhuma,
    entao a guarda e de quem tem a track."""
    inspector = TrackInspector()
    inspector.set_track(None)
    inspector.show()
    qapp.processEvents()
    fracoes: list[float] = []
    inspector.seek_requested.connect(fracoes.append)

    _clique_na_onda(inspector, inspector.wave.width() // 2)

    assert fracoes == []


def test_os_buckets_da_track_selecionada_chegam_na_onda(qapp):
    """Buckets de OUTRA track sao ignorados: um computo lento que termina depois
    de o usuario selecionar outra linha nao pode repintar a onda errada.

    Sem bucket nenhum a onda nao fica vazia -- cai na curva mono, que e o
    contrato do waveform_render, testado onde ele mora.
    """
    from dataclasses import replace

    linha = _row()
    inspector = TrackInspector()
    inspector.set_track(linha)
    assert inspector.wave._peaks_override is None

    inspector.set_peaks_path("outra-sha1", "/tmp/outra.wave")
    assert inspector.wave._peaks_override is None

    inspector.set_peaks_path(linha.sha1, "/tmp/dela.wave")
    assert inspector.wave._peaks_override == "/tmp/dela.wave"

    inspector.set_track(replace(linha, sha1="outra-sha1"))
    assert inspector.wave._peaks_override is None


def test_o_playhead_da_onda_zera_ao_trocar_de_track(qapp):
    """Playhead de uma track nao pode ficar marcado na onda da seguinte: quem
    sobe a posicao e a aba (so quando a que soa E a selecionada), e set_track
    zera -- o WaveformView ja faz isso em set_row."""
    from dataclasses import replace

    inspector = TrackInspector()
    inspector.set_track(_row())
    assert inspector.wave._progress == 0.0

    inspector.set_wave_progress(0.4)
    assert inspector.wave._progress == 0.4

    inspector.set_track(replace(_row(), sha1="outra-sha1"))
    assert inspector.wave._progress == 0.0
