"""As fontes do mockup viajam com o app -- nem a maquina nem o CI as tem."""

from trackclassifier.ui import fonts

ESPERADAS = ("Space Grotesk", "JetBrains Mono")


def test_diretorio_tem_os_quatro_arquivos_e_as_licencas():
    ttfs = sorted(p.name for p in fonts.DIRETORIO.glob("*.ttf"))
    assert ttfs == [
        "JetBrainsMono-Medium.ttf",
        "JetBrainsMono-Regular.ttf",
        "SpaceGrotesk-Medium.ttf",
        "SpaceGrotesk-Regular.ttf",
    ]
    # OFL exige que a licenca acompanhe a redistribuicao. Sem este teste,
    # um `rm` distraido transforma o repo numa violacao silenciosa.
    licencas = sorted(p.name for p in fonts.DIRETORIO.glob("OFL-*.txt"))
    assert licencas == ["OFL-JetBrainsMono.txt", "OFL-SpaceGrotesk.txt"]


def test_registra_fontes_devolve_as_duas_familias(qapp):
    familias = fonts.registra_fontes()

    for esperada in ESPERADAS:
        assert esperada in familias


def test_familia_registrada_resolve_no_qfont(qapp):
    from PySide6.QtGui import QFont

    fonts.registra_fontes()

    for esperada in ESPERADAS:
        # exactMatch e o unico jeito de distinguir "a familia existe" de
        # "o Qt caiu no fallback e devolveu Helvetica com outro nome".
        assert QFont(esperada).exactMatch(), esperada


def test_registrar_duas_vezes_nao_duplica(qapp):
    primeira = fonts.registra_fontes()
    segunda = fonts.registra_fontes()

    # main() roda uma vez, mas os testes sobem a UI varias vezes na mesma
    # QApplication de sessao. Registrar de novo nao pode crescer a lista.
    assert primeira == segunda


def test_diretorio_ausente_nao_levanta(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "DIRETORIO", tmp_path / "nao-existe")
    # O cache guarda o resultado da primeira chamada; sem zerar, este
    # teste leria o sucesso dos anteriores em vez do diretorio vazio.
    monkeypatch.setattr(fonts, "_registradas", None)

    # O app tem que subir sem as fontes -- feio, mas funcional. Uma
    # instalacao quebrada nao pode impedir o usuario de classificar.
    assert fonts.registra_fontes() == []
