"""Testes do SettingsField -- widget de campo de pasta com rotulo, ponto,
chip, campo, botao, erro."""

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from trackclassifier.ui.widgets.settings_field import SettingsField


def _bombeia(timeout_ms=1000, ate=None):
    prazo = QDeadlineTimer(timeout_ms)
    while not prazo.hasExpired() and not (ate and ate()):
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)


def _escolher_falso(titulo, atual):
    return ""


class TestSettingsField:
    def test_campo_destino_tem_ponto_rotulo_chip_campo_botao_erro(self, qapp):
        campo = SettingsField("up", _escolher_falso)

        assert campo.ponto is not None
        assert campo.ponto.width() == 7
        assert campo.ponto.height() == 7

        assert isinstance(campo.rotulo, QLabel)
        assert campo.rotulo.objectName() == "FieldLabel"
        assert campo.rotulo.text() == "+1"

        assert isinstance(campo.chip, QLabel)
        assert campo.chip.objectName() == "Chip"
        assert campo.chip.isHidden()

        assert isinstance(campo.campo, QLineEdit)
        assert campo.campo.objectName() == "FieldPath"

        assert isinstance(campo.botao, QPushButton)
        assert campo.botao.text() == "ESCOLHER"

        assert isinstance(campo._erro, QLabel)
        assert campo._erro.objectName() == "FieldError"
        assert campo._erro.isHidden()

    def test_campo_entrada_nao_tem_ponto(self, qapp):
        for chave in ("inbox", "data_dir", "root"):
            campo = SettingsField(chave, _escolher_falso)
            assert campo.ponto is None, f"Campo {chave} nao deveria ter ponto"

    def test_rotulos_usam_vocabulario_dominio(self, qapp):
        assert SettingsField("up", _escolher_falso).rotulo.text() == "+1"
        assert SettingsField("neutral", _escolher_falso).rotulo.text() == "neutra"
        assert SettingsField("down", _escolher_falso).rotulo.text() == "-1"
        assert SettingsField("inbox", _escolher_falso).rotulo.text() == "Pasta de entrada"
        assert SettingsField("root", _escolher_falso).rotulo.text() == "Criar a estrutura em"
        assert SettingsField("data_dir", _escolher_falso).rotulo.text() == "Pasta de dados do app"

    def test_mostra_erro_define_property_invalid_e_repolir(self, qapp):
        campo = SettingsField("up", _escolher_falso)

        campo.mostra_erro("Esta pasta nao existe")

        assert campo.campo.property("state") == "invalid"
        assert not campo._erro.isHidden()
        assert campo._erro.text() == "Esta pasta nao existe"

    def test_mostra_erro_limpo_remove_property_e_esconde(self, qapp):
        campo = SettingsField("up", _escolher_falso)
        campo.mostra_erro("Erro anterior")

        campo.mostra_erro("")

        assert campo.campo.property("state") in (None, "")
        assert campo._erro.isHidden()

    def test_mostra_chip_define_texto_visibilidade_e_property(self, qapp):
        from trackclassifier.ui.counts import NAO_ENCONTRADA

        campo = SettingsField("up", _escolher_falso)

        campo.mostra_chip("5 TRACKS")

        assert campo.chip.text() == "5 TRACKS"
        assert not campo.chip.isHidden()
        assert campo.chip.property("state") in (None, "")

        campo.mostra_chip(NAO_ENCONTRADA)

        assert campo.chip.text() == NAO_ENCONTRADA
        assert campo.chip.property("state") == "danger"

    def test_mostra_chip_vazio_esconde(self, qapp):
        campo = SettingsField("up", _escolher_falso)
        campo.mostra_chip("5 TRACKS")

        campo.mostra_chip("")

        assert campo.chip.isHidden()

    def test_chip_do_campo_retorna_texto_quando_visivel(self, qapp):
        campo = SettingsField("up", _escolher_falso)

        assert campo.chip_do_campo() == ""

        campo.mostra_chip("3 TRACKS")

        assert campo.chip_do_campo() == "3 TRACKS"

        campo.mostra_chip("")

        assert campo.chip_do_campo() == ""

    def test_erro_retorna_mensagem_quando_visivel(self, qapp):
        campo = SettingsField("up", _escolher_falso)

        assert campo.erro() == ""

        campo.mostra_erro("Erro de teste")

        assert campo.erro() == "Erro de teste"

        campo.mostra_erro("")

        assert campo.erro() == ""

    def test_texto_e_set_texto(self, qapp):
        campo = SettingsField("inbox", _escolher_falso)

        assert campo.texto() == ""

        campo.set_texto("/caminho/qualquer")

        assert campo.texto() == "/caminho/qualquer"

    def test_escolher_chama_callback_e_preenche_campo(self, qapp, tmp_path):
        destino = tmp_path / "escolhida"
        destino.mkdir()

        escolhidas = [str(destino)]

        def escolher(titulo, atual):
            return escolhidas.pop(0) if escolhidas else ""

        campo = SettingsField("inbox", escolher)

        campo.escolher()

        assert campo.texto() == str(destino)

    def test_campo_visivel_false_quando_widget_escondido(self, qapp):
        campo = SettingsField("up", _escolher_falso)
        campo.setVisible(False)

        assert campo.isHidden()

    def test_ponto_tem_cor_da_classe_correta(self, qapp):
        from trackclassifier.ui.tokens import classification_base

        campo_up = SettingsField("up", _escolher_falso)
        campo_neutral = SettingsField("neutral", _escolher_falso)
        campo_down = SettingsField("down", _escolher_falso)

        assert f"background: {classification_base('animada')}" in campo_up.ponto.styleSheet()
        assert f"background: {classification_base('neutro')}" in campo_neutral.ponto.styleSheet()
        assert f"background: {classification_base('lento')}" in campo_down.ponto.styleSheet()

    def test_rotulo_destino_herda_cor_da_classe(self, qapp):
        from trackclassifier.ui.tokens import classification_base

        campo_up = SettingsField("up", _escolher_falso)
        campo_down = SettingsField("down", _escolher_falso)

        assert f"color: {classification_base('animada')}" in campo_up.rotulo.styleSheet()
        assert f"color: {classification_base('lento')}" in campo_down.rotulo.styleSheet()

    def test_sinal_changed_emitido_ao_digitar(self, qapp):
        campo = SettingsField("inbox", _escolher_falso)
        emitidos = []
        campo.changed.connect(lambda: emitidos.append(True))

        campo.set_texto("novo caminho")

        assert len(emitidos) == 1
