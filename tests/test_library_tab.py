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


def _aba_com(n_linhas: int, altura_viewport: int = 140) -> LibraryTab:
    """LibraryTab populada, mostrada, com viewport de altura conhecida.

    140px / 44px por linha (SIZE_ROW_COMFORTABLE) cabe ~3 linhas -- o bastante
    pra provar que a tabela nao pede o que esta fora da tela quando ha muito
    mais linhas do que isso.
    """
    aba = LibraryTab()
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
    aba = LibraryTab()
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

    aba = LibraryTab()
    assert aba._table.verticalHeader().defaultSectionSize() == SIZE_ROW_COMFORTABLE

    aba._densidade.setChecked(True)

    # Os tres andam juntos: encolher a linha sem encolher a capa faz a capa
    # transbordar, e encolher a capa sem a onda deixa um vazio no meio.
    assert aba._table.verticalHeader().defaultSectionSize() == SIZE_ROW_COMPACT
    assert aba._cover_delegate._lado == SIZE_ART_ROW_COMPACT
    assert aba._waveform_delegate._altura == SIZE_WAVE_ROW_COMPACT


def test_rotulo_da_densidade_diz_para_onde_o_clique_leva(qapp):
    from trackclassifier.ui.library_tab import LibraryTab

    aba = LibraryTab()
    assert aba._densidade.text() == "COMPACTA"

    aba._densidade.setChecked(True)

    assert aba._densidade.text() == "CONFORTAVEL"
