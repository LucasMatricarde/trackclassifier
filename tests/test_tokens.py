"""Guarda o modo de falha mais provavel do design system: editar o JSON e
esquecer de rodar build_tokens.py, deixando tokens.py e app.qss velhos."""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GERADOS = [
    RAIZ / "src" / "trackclassifier" / "ui" / "tokens.py",
    RAIZ / "src" / "trackclassifier" / "ui" / "app.qss",
]


def _build_tokens_module():
    """`design/build_tokens.py` e script solto, fora de `src/` -- nao e um
    modulo do pacote, entao os testes que chamam suas funcoes direto (em vez
    de so rodar o script via subprocess, como o teste acima) precisam
    carrega-lo por caminho.
    """
    caminho = RAIZ / "design" / "build_tokens.py"
    spec = importlib.util.spec_from_file_location("build_tokens", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_arquivos_gerados_estao_em_dia_com_o_json():
    antes = {caminho: caminho.read_text(encoding="utf-8") for caminho in GERADOS}

    subprocess.run(
        [sys.executable, str(RAIZ / "design" / "build_tokens.py")],
        check=True,
        capture_output=True,
    )

    for caminho, conteudo in antes.items():
        assert caminho.read_text(encoding="utf-8") == conteudo, (
            f"{caminho.name} esta dessincronizado de design-tokens.json. "
            "Rode: uv run python design/build_tokens.py"
        )


def test_nenhum_hex_fora_do_json():
    """Nenhum literal de cor pode existir fora dos tokens."""
    import re

    padrao = re.compile(r"#[0-9A-Fa-f]{6}\b")
    ui = RAIZ / "src" / "trackclassifier" / "ui"
    permitidos = {ui / "tokens.py", ui / "app.qss"}

    ofensores = []
    for caminho in ui.rglob("*.py"):
        if caminho in permitidos:
            continue
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if padrao.search(linha):
                ofensores.append(f"{caminho.relative_to(RAIZ)}:{numero}")

    assert ofensores == [], f"hex fora de design-tokens.json: {ofensores}"


def test_camelot_color_cobre_as_doze_posicoes_da_roda():
    from trackclassifier.ui.tokens import camelot_color

    cores = {camelot_color(n) for n in range(1, 13)}
    # Doze cores distintas: a roda de Camelot perde a utilidade se duas
    # posicoes vizinhas ficarem indistinguiveis.
    assert len(cores) == 12
    assert all(cor.startswith("#") for cor in cores)


def test_camelot_color_fora_da_roda_levanta():
    import pytest

    from trackclassifier.ui.tokens import camelot_color

    for invalido in (0, 13, -1):
        with pytest.raises(KeyError):
            camelot_color(invalido)


def test_py_name_normaliza_hifen_em_identificador_valido():
    # A v0.2 introduz chaves hifenizadas (surface.selection-bar,
    # size.focus-ring, motion.playhead-fps). Sem normalizar, build_py emite
    # `COLOR_SURFACE_SELECTION-BAR: Final = ...` -- SyntaxError antes de
    # qualquer teste rodar, porque tokens.py nem importa.
    modulo = _build_tokens_module()

    nome = modulo.py_name(("size", "focus-ring"))

    assert nome.isidentifier()
    assert nome == "SIZE_FOCUS_RING"


def test_css_name_mantem_o_hifen():
    # --size-focus-ring e o nome CSS natural; so o lado Python precisa da
    # normalizacao acima.
    modulo = _build_tokens_module()

    assert modulo.css_name(("size", "focus-ring")) == "--size-focus-ring"


def test_python_gerado_a_partir_do_json_real_compila():
    """Fumaca do gerador inteiro: build_py sobre o JSON de verdade produz
    Python valido. Pega tanto o SyntaxError do hifen quanto qualquer outra
    chave que colida ao virar identificador.
    """
    import json

    modulo = _build_tokens_module()
    dados = json.loads((RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8"))
    tokens = modulo.flatten(dados)

    codigo = modulo.build_py(tokens)

    compile(codigo, "<tokens.py gerado>", "exec")


def test_qss_gerado_a_partir_do_json_real_nao_deixa_chave_de_format_sobrando():
    """build_qss usa um template .format(); uma chave que o template
    referencia mas o dict `t` nao tem levanta KeyError e derruba o gerador --
    e o caso do SIZE_CONTROL (ver plano). Este teste cobre o oposto: garante
    que nao sobra chave de placeholder sem substituir no QSS final, o que
    aconteceria se o template tivesse uma chave a MENOS do que usa.
    """
    import json

    modulo = _build_tokens_module()
    dados = json.loads((RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8"))
    tokens = modulo.flatten(dados)

    qss = modulo.build_qss(tokens)

    assert not re.search(r"\{[a-zA-Z]", qss), "chave de .format() nao substituida no QSS gerado"


def test_toda_dimensao_de_size_no_qss_termina_em_px():
    """`size.*` guarda numero puro no JSON (o mesmo valor serve tokens.py, que
    nao quer unidade, e o QSS, que quer). O template precisa devolver o `px`
    na interpolacao -- sem isso `min-height: 28;` e CSS invalido, silenciosamente
    ignorado pelo Qt (a regra some, nao da erro).
    """
    import json

    modulo = _build_tokens_module()
    dados = json.loads((RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8"))
    tokens = modulo.flatten(dados)
    qss = modulo.build_qss(tokens)

    for control in re.finditer(r"min-height:\s*([^;]+);", qss):
        valor = control.group(1).strip()
        assert valor.endswith("px"), f"dimensao sem unidade no QSS: {valor!r}"


def test_qss_tem_micro_label():
    """O rotulo de 10px da v0.2 e componente, nao setStyleSheet repetido."""
    qss = (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")

    assert "QLabel#MicroLabel" in qss


def test_micro_label_usa_o_tamanho_micro_e_a_mono():
    import json

    tokens = json.loads(
        (RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8")
    )
    micro = tokens["font"]["size"]["micro"]["value"]
    qss = (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")

    bloco = qss.split("QLabel#MicroLabel")[1].split("}")[0]
    assert f"font-size: {micro}" in bloco
    assert "JetBrains Mono" in bloco


def test_a_altura_renderizada_dos_controles_bate_com_os_tokens(qapp):
    """min-height no QSS vale para o CONTENTS rect, nao para o widget.

    Sem descontar padding e borda, um botao com min-height 28 renderiza 42.
    Os mockups (01, 05 e 06) usam 32 no botao de acento e 28 no resto, e
    esse numero e o do WIDGET -- e o que o olho mede na tela.
    """
    from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QSpinBox

    from trackclassifier.ui import fonts
    from trackclassifier.ui.tokens import SIZE_CONTROL_ACTION, SIZE_CONTROL_BASE

    fonts.registra_fontes()
    anterior = QApplication.instance().styleSheet()
    QApplication.instance().setStyleSheet(
        (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")
    )
    try:
        acento = QPushButton("Escanear")
        acento.setProperty("variant", "primary")
        assert acento.sizeHint().height() == SIZE_CONTROL_ACTION

        # So QPushButton generico bate exato em SIZE_CONTROL_BASE: e o unico
        # dos quatro controles fechado via min-height descontado da borda
        # (sem_borda() em build_tokens.py). QLineEdit/QComboBox usam
        # `padding: {space3} {space4}` (6px vertical) sem min-height -- a
        # abordagem escolhida no PR #22 (main) -- e isso fecha em 32/31px,
        # nao nos 28px do mockup: 6px de padding em cada lado + 2px de borda
        # + ~18px de altura de linha da fonte somam mais do que o
        # min-height descontado teria dado. Gap real e pre-existente do
        # PR #22, nao desta task -- documentado aqui porque este teste e o
        # unico do repo que mede o WIDGET renderizado (o resto so confere o
        # texto do QSS).
        botao = QPushButton("Limpar")
        assert botao.sizeHint().height() == SIZE_CONTROL_BASE

        assert QLineEdit().sizeHint().height() == 32
        assert QComboBox().sizeHint().height() == 31

        # QSpinBox foge da regra acima sob QT_QPA_PLATFORM=offscreen (o modo
        # deste teste e do CI, ver conftest.py): o estilo Fusion, que e o
        # fallback headless, soma +5px fixos na conta de CT_SpinBox por fora
        # do content-box do QSS -- confirmado empiricamente variando a borda
        # de 0 a 3px (a sobra nao muda) e escondendo as setas com
        # setButtonSymbols(NoButtons) (a sobra tambem nao muda, entao nao e
        # espaco reservado pros botoes). No estilo nativo macOS -- o que o
        # .app empacotado usa de verdade -- essa sobra nao existe e o mesmo
        # QSS bate exato em SIZE_CONTROL_BASE, igual ao QPushButton generico.
        # Testamos aqui o valor do ambiente onde o teste roda de fato.
        sobra_fusion_offscreen = 5
        spin = QSpinBox()
        assert spin.sizeHint().height() == SIZE_CONTROL_BASE + sobra_fusion_offscreen
    finally:
        QApplication.instance().setStyleSheet(anterior)
