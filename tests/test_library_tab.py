"""Computo preguicoso das ondas: quem pede agora e a aba, olhando o viewport.

A versao anterior pedia de dentro do WaveformDelegate.paint(), uma vez por
sha1 -- mas paint() nao tem como saber o que continua na tela. Rolar a
biblioteca inteira (354 tracks reais) pintava as ~300 sem buckets uma vez
cada e enfileirava ~300 computos de ~0,4s na MESMA thread que atende
decide/undo/train: depois de um scroll ate o fim, uma decisao pelo teclado
ficava sem resposta por ~2 minutos.

Estes testes cobrem o que substituiu isso: LibraryTab pergunta ao
QTableView quais linhas o viewport cobre, com um atraso que absorve o
arrasto (ATRASO_PEAKS_MS) e um teto de quantos computos ficam em voo ao
mesmo tempo (MAX_PEAKS_EM_VOO).
"""

from PySide6.QtTest import QTest

from trackclassifier.ui.library_tab import ATRASO_PEAKS_MS, MAX_PEAKS_EM_VOO, LibraryTab
from trackclassifier.ui.viewmodel import LibraryState, TrackRow
from trackclassifier.ui.widgets.player import SimulatedPlayer


def _linha(indice: int, peaks_path: str | None = None) -> TrackRow:
    return TrackRow(
        sha1=f"sha{indice:04d}",
        filename=f"track{indice:04d}.wav",
        label="+1",
        predicted=None,
        score=None,
        confidence=None,
        bpm=120.0,
        duration_s=180.0,
        energy_curve=(0.1, 0.4, 0.2),
        peak_offset_s=1.0,
        path_hint=f"/fake/track{indice:04d}.wav",
        peaks_path=peaks_path,
    )


def _aba_com(
    n_linhas: int, altura_viewport: int = 140, player=None
) -> LibraryTab:
    """LibraryTab populada, mostrada, com viewport de altura conhecida.

    140px / 44px por linha (SIZE_ROW_COMFORTABLE) cabe ~3 linhas -- o bastante
    pra provar que a tabela nao pede o que esta fora da tela quando ha muito
    mais linhas do que isso.
    """
    aba = LibraryTab(player or SimulatedPlayer())
    aba.set_state(LibraryState(rows=tuple(_linha(i) for i in range(n_linhas))))
    aba.resize(400, altura_viewport + 80)  # +80: barra de busca, cabecalho etc
    aba._table.setFixedHeight(altura_viewport)
    aba.show()
    QTest.qWaitForWindowExposed(aba)
    return aba


def _forca_disparo_imediato(aba: LibraryTab) -> None:
    """Zera o atraso para os testes que nao sao sobre o atraso em si."""
    aba._timer_peaks.setInterval(0)


def test_pede_so_as_linhas_visiveis_no_viewport(qapp, tmp_path):
    aba = _aba_com(n_linhas=200, altura_viewport=140)
    _forca_disparo_imediato(aba)

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))
    aba._agenda_peaks()
    QTest.qWait(50)

    ultima_visivel = aba._table.rowAt(aba._table.viewport().height() - 1)
    assert 0 < ultima_visivel < 199, "o teste nao prova nada se tudo estiver visivel"

    # O teto (MAX_PEAKS_EM_VOO) tambem entra em jogo aqui -- o que importa e
    # que nada ALEM da faixa visivel jamais seja pedido.
    assert pedidos, "nada foi pedido"
    for sha1 in pedidos:
        indice = int(sha1.removeprefix("sha"))
        assert indice <= ultima_visivel, f"{sha1} esta fora do viewport"


def test_nao_pede_antes_do_timer_disparar(qapp, tmp_path):
    aba = _aba_com(n_linhas=50, altura_viewport=140)
    assert aba._timer_peaks.interval() == ATRASO_PEAKS_MS

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    barra = aba._table.verticalScrollBar()
    assert barra.maximum() > 0, "o teste precisa de scroll de verdade"
    barra.setValue(barra.maximum())

    # Logo apos rolar, o timer esta armado mas ainda nao disparou.
    assert aba._timer_peaks.isActive()
    assert pedidos == []

    QTest.qWait(ATRASO_PEAKS_MS + 150)

    assert pedidos != []


def test_nunca_excede_o_teto_de_computos_em_voo(qapp, tmp_path):
    aba = _aba_com(n_linhas=200, altura_viewport=800)  # viewport grande: cabem >MAX
    _forca_disparo_imediato(aba)

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))
    aba._agenda_peaks()
    QTest.qWait(50)

    assert len(pedidos) == MAX_PEAKS_EM_VOO
    assert len(aba._peaks_em_voo) == MAX_PEAKS_EM_VOO


def test_peaks_prontos_libera_vaga_e_o_proximo_e_pedido(qapp, tmp_path):
    aba = _aba_com(n_linhas=200, altura_viewport=800)
    _forca_disparo_imediato(aba)

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))
    aba._agenda_peaks()
    QTest.qWait(50)
    assert len(pedidos) == MAX_PEAKS_EM_VOO

    aba.peaks_prontos(pedidos[0], "/fake/pronto.npy")
    QTest.qWait(50)

    assert len(pedidos) == MAX_PEAKS_EM_VOO + 1
    assert pedidos[0] not in aba._peaks_em_voo
    assert len(aba._peaks_em_voo) == MAX_PEAKS_EM_VOO


def test_peaks_falharam_libera_vaga_e_nao_repete_a_mesma_sha1(qapp, tmp_path):
    aba = _aba_com(n_linhas=200, altura_viewport=800)
    _forca_disparo_imediato(aba)

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))
    aba._agenda_peaks()
    QTest.qWait(50)
    assert len(pedidos) == MAX_PEAKS_EM_VOO

    falha = pedidos[0]
    aba.peaks_falharam(falha)
    QTest.qWait(50)

    assert falha not in aba._peaks_em_voo
    assert falha in aba._peaks_sem_sucesso
    # Vaga liberada: um pedido novo saiu no lugar.
    assert len(pedidos) == MAX_PEAKS_EM_VOO + 1
    # Mas nunca a mesma sha1 que acabou de falhar.
    assert pedidos.count(falha) == 1


def test_set_state_reabre_sha1_que_falharam(qapp, tmp_path):
    aba = _aba_com(n_linhas=1, altura_viewport=140)
    _forca_disparo_imediato(aba)
    aba._peaks_sem_sucesso.add("sha0000")

    aba.set_state(LibraryState(rows=(_linha(0),)))

    assert "sha0000" not in aba._peaks_sem_sucesso


def test_set_state_nao_esquece_o_que_esta_em_voo(qapp, tmp_path):
    # Diferente de _peaks_sem_sucesso: o pedido em voo continua na fila do
    # worker de verdade, e a resposta ainda vai chegar -- limpar aqui deixaria
    # o teto contando errado (mais vagas do que computos realmente pendentes).
    aba = _aba_com(n_linhas=1, altura_viewport=140)
    aba._peaks_em_voo.add("sha0000")

    aba.set_state(LibraryState(rows=(_linha(0),)))

    assert "sha0000" in aba._peaks_em_voo


def test_track_ja_com_peaks_path_nao_e_pedida(qapp, tmp_path):
    aba = LibraryTab(SimulatedPlayer())
    aba.set_state(LibraryState(rows=(_linha(0, peaks_path="/fake/ja-existe.npy"),)))
    _forca_disparo_imediato(aba)
    aba.resize(400, 220)
    aba._table.setFixedHeight(140)
    aba.show()
    QTest.qWaitForWindowExposed(aba)

    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))
    aba._agenda_peaks()
    QTest.qWait(50)

    assert pedidos == []


def test_densidade_compacta_encolhe_linha_capa_e_onda(qapp):
    from trackclassifier.ui.library_tab import LibraryTab
    from trackclassifier.ui.tokens import (
        SIZE_ART_ROW_COMPACT,
        SIZE_ROW_COMFORTABLE,
        SIZE_ROW_COMPACT,
    )
    from trackclassifier.ui.widgets.delegates import SIZE_WAVE_ROW_COMPACT

    aba = LibraryTab(SimulatedPlayer())
    assert aba._table.verticalHeader().defaultSectionSize() == SIZE_ROW_COMFORTABLE

    aba._densidade.set_selecionado(1)

    # Os tres andam juntos: encolher a linha sem encolher a capa faz a capa
    # transbordar, e encolher a capa sem a onda deixa um vazio no meio.
    assert aba._table.verticalHeader().defaultSectionSize() == SIZE_ROW_COMPACT
    assert aba._cover_delegate._lado == SIZE_ART_ROW_COMPACT
    assert aba._waveform_delegate._altura == SIZE_WAVE_ROW_COMPACT


def test_segmento_de_densidade_abre_em_confortavel(qapp):
    from trackclassifier.ui.library_tab import LibraryTab

    aba = LibraryTab(SimulatedPlayer())

    assert aba._densidade.selecionado() == 0

    aba._densidade.set_selecionado(1)

    assert aba._densidade.selecionado() == 1


def test_indice_compacta_bate_com_o_rotulo_visivel(qapp):
    """Achado do code review: _aplica_densidade decidia `indice == 1` sem
    nenhum vinculo com _ROTULOS_DENSIDADE -- reordenar o tuple (copy, locale)
    inverteria a densidade em silencio, e o teste acima (que so confere
    indice/tamanho) nao pegaria. Este amarra o rotulo VISIVEL do segmento
    aceso ao comportamento, entao quebra se a ordem mudar."""
    from trackclassifier.ui.library_tab import _INDICE_COMPACTA, LibraryTab
    from trackclassifier.ui.tokens import SIZE_ROW_COMPACT
    from trackclassifier.ui.typography import texto_de_label

    aba = LibraryTab(SimulatedPlayer())

    aba._densidade.set_selecionado(_INDICE_COMPACTA)

    assert aba._densidade.texto_selecionado() == texto_de_label("Compacta")
    assert aba._table.verticalHeader().defaultSectionSize() == SIZE_ROW_COMPACT


def test_busca_sem_resultado_tem_estado_proprio(qapp):
    """Tres estados, nao dois: vazia, sem resultado e com linhas."""
    from trackclassifier.ui.library_tab import LibraryTab
    from trackclassifier.ui.viewmodel import LibraryState, TrackRow

    linha = TrackRow(
        sha1="a",
        filename="Halide.wav",
        label="+1",
        predicted=None,
        score=None,
        confidence=None,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=(0.1, 0.2),
        peak_offset_s=1.0,
        path_hint="/tmp/Halide.wav",
        title="Halide",
    )

    aba = LibraryTab(SimulatedPlayer())
    aba.set_state(LibraryState(rows=(linha,)))
    assert not aba._sem_resultado.isVisibleTo(aba)

    aba._busca.setText("nao existe nenhuma track assim")

    # Escanear NAO e oferecido aqui: nao traria de volta o que o filtro
    # escondeu, e o botao mandaria o usuario para o lugar errado.
    assert aba._sem_resultado.isVisibleTo(aba)
    assert not aba._vazio.isVisibleTo(aba)
    # A tabela CONTINUA na tela, encolhida ate o cabecalho: o usuario ainda
    # esta dentro dela. Ver test_a_busca_sem_resultado_mantem_o_cabecalho.
    assert aba._table.isVisibleTo(aba)


def test_biblioteca_vazia_continua_oferecendo_escanear(qapp):
    from trackclassifier.ui.library_tab import LibraryTab
    from trackclassifier.ui.viewmodel import LibraryState

    aba = LibraryTab(SimulatedPlayer())
    aba.set_state(LibraryState(rows=()))

    assert aba._vazio.isVisibleTo(aba)
    assert not aba._sem_resultado.isVisibleTo(aba)


#: Termo que nao casa com nenhum `_linha`, cujo filename e "track0000.wav".
_IMPOSSIVEL = "nao-existe-nenhuma-track-com-isso"


def test_a_busca_sem_resultado_mantem_o_cabecalho(qapp):
    """Biblioteca vazia e busca sem resultado sao estados diferentes: na
    segunda o usuario ainda esta DENTRO da tabela, e esconder o cabecalho
    junto com as linhas apaga a referencia de onde ele esta."""
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)

    assert aba._sem_resultado.isVisibleTo(aba)
    assert aba._table.isVisibleTo(aba)
    assert aba._table.maximumHeight() == aba._table.horizontalHeader().height()


def test_a_biblioteca_vazia_esconde_a_tabela_inteira(qapp):
    """Sem nenhuma track nao ha coluna que valha mostrar."""
    aba = LibraryTab(SimulatedPlayer())
    aba.set_state(LibraryState(rows=()))

    assert aba._vazio.isVisibleTo(aba)
    assert not aba._table.isVisibleTo(aba)


def test_a_copy_sem_resultado_cita_o_termo_e_o_filtro(qapp):
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)
    aba._filtro.setCurrentText("+1")
    titulo, subtitulo = aba._texto_sem_resultado()

    assert _IMPOSSIVEL in titulo
    assert "+1" in titulo
    assert "5" in subtitulo
    assert "nome do arquivo" in subtitulo


def test_a_copy_sem_resultado_escapa_html_do_termo_de_busca(qapp):
    """Achado Important da revisao final.

    O termo vem direto do QLineEdit (texto livre do usuario) e e
    interpolado num QLabel RichText -- sem escapar, "<b>drum" virava
    negrito de verdade e "Sk8 <tag>" sumia com tudo depois de "<tag>",
    porque o Qt le como uma tag HTML real em vez de texto literal.
    """
    aba = _aba_com(5)

    aba._busca.setText("Sk8 <tag>")
    titulo, _ = aba._texto_sem_resultado()

    # html.escape troca "<" por "&lt;" etc -- o literal digitado nao aparece
    # mais cru no titulo, mas os caracteres originais continuam presentes em
    # forma segura, e nada depois de "<tag>" foi silenciosamente descartado.
    assert "<tag>" not in titulo
    assert "&lt;tag&gt;" in titulo
    assert "Sk8" in titulo


def test_sem_filtro_a_copy_nao_inventa_filtro(qapp):
    """'Todos' e a ausencia de filtro; cita-lo faria o usuario procurar um
    filtro que ele nao ligou."""
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)
    titulo, _ = aba._texto_sem_resultado()

    assert "Todos" not in titulo


def test_sem_termo_a_copy_fala_so_do_filtro(qapp):
    aba = _aba_com(5)

    aba._filtro.setCurrentText("-1")
    titulo, _ = aba._texto_sem_resultado()

    assert "-1" in titulo
    assert "Nada em" not in titulo


def test_limpar_busca_devolve_as_linhas(qapp):
    aba = _aba_com(5)
    aba._busca.setText(_IMPOSSIVEL)

    aba._sem_resultado.acionar("Limpar busca")

    assert aba._busca.text() == ""
    assert aba._table.isVisibleTo(aba)
    assert not aba._sem_resultado.isVisibleTo(aba)


def test_a_acao_de_filtro_volta_para_todos(qapp):
    aba = _aba_com(5)
    aba._busca.setText(_IMPOSSIVEL)
    aba._filtro.setCurrentText("-1")

    aba._sem_resultado.acionar("Filtro: todos")

    assert aba._filtro.currentText() == "Todos"


def test_duplo_clique_toca_a_linha(qapp):
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)

    aba.toca_linha(0)

    # is_playing e property em BasePlayer, nao metodo.
    assert player.is_playing is True
    assert aba._model._tocando == aba._model.row_at(0).sha1


def test_a_posicao_do_player_move_o_playhead_da_linha(qapp):
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)
    aba.toca_linha(0)

    # _linha tem duration_s=180.0, entao 30s e ~1/6 da track.
    aba._atualiza_tocando(30_000)

    assert 0.0 < aba._waveform_delegate._fracao <= 1.0


def test_trocar_de_track_solta_a_anterior(qapp):
    """Duas linhas com play ao mesmo tempo seria mentira: o player e um so."""
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)

    aba.toca_linha(0)
    aba.toca_linha(1)

    assert aba._model._tocando == aba._model.row_at(1).sha1
