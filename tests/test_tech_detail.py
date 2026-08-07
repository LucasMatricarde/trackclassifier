from PySide6.QtCore import Qt

from trackclassifier.ui.widgets.tech_detail import TechDetail, resumo_tecnico


def test_resumo_tecnico_sem_treino_nao_inventa_numero():
    # alpha_ e thresholds_ tem default no TrackModel; mostra-los como se
    # fossem resultado de treino seria mentira.
    assert resumo_tecnico(None, None, "handcrafted-v1") == "handcrafted-v1"


def test_resumo_tecnico_treinado_traz_alpha_e_cortes():
    texto = resumo_tecnico(1.8, (-0.33, 0.41), "handcrafted-v1")

    assert texto == "alpha 1.80 · cortes -0.330 / 0.410 · handcrafted-v1"


def test_comeca_fechado_mostrando_so_o_resumo(qapp):
    rodape = TechDetail()
    rodape.set_detail(1.8, (-0.33, 0.41), "handcrafted-v1")

    assert not rodape.botao.isChecked()
    assert rodape.resumo.isVisibleTo(rodape)
    assert not rodape.corpo.isVisibleTo(rodape)


def test_abrir_troca_resumo_pelo_corpo(qapp):
    rodape = TechDetail()
    rodape.set_detail(1.8, (-0.33, 0.41), "handcrafted-v1")

    rodape.botao.setChecked(True)

    assert rodape.corpo.isVisibleTo(rodape)
    assert not rodape.resumo.isVisibleTo(rodape)


def test_corpo_aberto_mostra_os_tres_valores(qapp):
    rodape = TechDetail()
    rodape.set_detail(1.8, (-0.33, 0.41), "handcrafted-v1")
    rodape.botao.setChecked(True)

    assert rodape._alpha.text() == "1.80"
    assert rodape._cortes.text() == "-0.330 / 0.410"
    assert rodape._extrator.text() == "handcrafted-v1"


def test_sem_treino_esconde_alpha_e_cortes_mesmo_aberto(qapp):
    rodape = TechDetail()
    rodape.set_detail(None, None, "handcrafted-v1")
    rodape.botao.setChecked(True)

    assert not rodape._caixa_alpha.isVisibleTo(rodape)
    assert not rodape._caixa_cortes.isVisibleTo(rodape)
    assert rodape._extrator.text() == "handcrafted-v1"


def test_fundo_pinta_por_inteiro(qapp):
    # QWidget so pinta o `background:` do QSS sozinho para a classe base;
    # numa SUBCLASSE (TechDetail e uma), sem WA_StyledBackground o fundo
    # fica mudo no paint normal e so aparece por acidente num grab()
    # isolado -- o card rodava com metade da largura vazando a cor da
    # janela por tras, so visivel com o app de verdade rodando.
    rodape = TechDetail()

    assert rodape.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)


def test_gatilho_nao_grita_caixa_alta(qapp):
    # "Detalhe tecnico" e um rotulo de linha, nao um cabecalho de secao:
    # o tratamento MicroLabel (uppercase + tracking.widest + moldura de
    # botao) pesa como uma acao, e esta linha e so um metadado que abre.
    rodape = TechDetail()
    rodape.set_detail(1.8, (-0.33, 0.41), "handcrafted-v1")

    assert "Detalhe tecnico" in rodape.botao.text()
    assert "DETALHE" not in rodape.botao.text()
