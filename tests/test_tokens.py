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
    RAIZ / "web" / "src" / "styles" / "tokens.css",
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


def _tokens_css_gerado():
    """build_css sobre o JSON de verdade (modulo, tokens achatados)."""
    import json

    modulo = _build_tokens_module()
    dados = json.loads((RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8"))
    tokens = modulo.flatten(dados)
    return modulo, tokens, modulo.build_css(tokens)


def test_css_gerado_nao_redefine_nome_que_o_json_emite():
    """Regressao do bug dos aliases colidentes.

    A primeira versao do bloco de aliases remapeava nomes que o proprio
    dump do JSON emite (--space-*, --radius-md, --font-size-caption...).
    Em :root o alias sobrescreve o token e cria cadeias inteiras de
    var() (--space-1 -> ... -> --space-8 = 32px para todo espacamento do
    web). A regra agora: alias so pode ter nome que o JSON NAO emite --
    nome colidente e renomeado no CSS consumidor.
    """
    modulo, tokens, css = _tokens_css_gerado()

    nomes_json = {modulo.css_name(path) for path, _valor, _desc in tokens}
    aliases = set()
    for nome, valor in re.findall(r"^\s+(--[\w-]+):\s*(.+);$", css, re.M):
        if valor.strip().startswith("var("):
            aliases.add(nome)

    colidentes = aliases & nomes_json
    assert colidentes == set(), (
        f"alias redefine token do JSON: {sorted(colidentes)}. "
        "Renomeie o consumo no web para o nome do JSON."
    )


def test_css_gerado_nao_tem_autorreferencia_nem_ciclo_de_var():
    """`--x: var(--x)` e invalidado pelo navegador ("invalid at computed-value
    time") e o token some sem erro -- o modo de falha mais silencioso do CSS.
    Ciclos mais longos (a -> b -> a) caem na mesma regra.
    """
    _modulo, _tokens, css = _tokens_css_gerado()

    referencias = {}
    for nome, valor in re.findall(r"^\s+(--[\w-]+):\s*(.+);$", css, re.M):
        alvo = re.fullmatch(r"var\((--[\w-]+)\)", valor.strip())
        if alvo:
            referencias[nome] = alvo.group(1)

    for origem in referencias:
        visitados = set()
        atual = origem
        while atual in referencias:
            assert atual not in visitados, (
                f"ciclo de var() comecando em {origem}: {atual} ja visitado"
            )
            visitados.add(atual)
            atual = referencias[atual]


def test_todo_var_consumido_no_web_existe_no_tokens_css():
    """Caca var(--x) em web/src (css + tsx) e exige a definicao no tokens.css
    gerado. var() sem definicao vira "invalid at computed-value time" e o
    estilo cai no default do navegador -- foi assim que a app inteira
    renderizou em serif quando o tokens.css ficou incompleto.
    """
    _modulo, _tokens, css = _tokens_css_gerado()
    definidos = set(re.findall(r"^\s+(--[\w-]+):", css, re.M))

    consumidos = set()
    web_src = RAIZ / "web" / "src"
    for padrao in ("*.css", "*.tsx", "*.ts"):
        for caminho in web_src.rglob(padrao):
            if caminho.name == "tokens.css":
                continue
            consumidos.update(re.findall(r"var\((--[\w-]+)", caminho.read_text(encoding="utf-8")))

    # Nomes terminados em "-" vem de template literals (`var(--color-class-
    # ${rotulo})`): o regex captura so o prefixo estatico. Vale se ALGUM
    # token definido tem esse prefixo -- a expansao completa nao existe no
    # codigo-fonte.
    faltantes = {
        nome
        for nome in consumidos
        if nome not in definidos
        and not (nome.endswith("-") and any(d.startswith(nome) for d in definidos))
    }
    assert faltantes == set(), f"var() sem definicao em tokens.css: {sorted(faltantes)}"


def test_hex_no_web_existe_no_json():
    """Equivalente web do test_nenhum_hex_fora_do_json, com uma folga: o
    canvas nao resolve var(), entao WaveformCanvas mantem fallbacks hex
    defensivos. A regra e: todo hex em web/src tem que ser um valor que
    existe no design-tokens.json -- hex inventado (como o teal #00D4AA que
    sobreviveu como fallback depois da troca de acento) falha aqui.
    """
    import json

    dados = json.loads((RAIZ / "design" / "design-tokens.json").read_text(encoding="utf-8"))
    valores_json = {
        str(valor).lower()
        for _path, valor, _desc in _build_tokens_module().flatten(dados)
    }

    ofensores = []
    web_src = RAIZ / "web" / "src"
    for padrao in ("*.css", "*.tsx", "*.ts"):
        for caminho in web_src.rglob(padrao):
            if caminho.name == "tokens.css":
                continue
            for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
                for hex_ in re.findall(r"#[0-9A-Fa-f]{6}\b", linha):
                    if hex_.lower() not in valores_json:
                        ofensores.append(f"{caminho.relative_to(RAIZ)}:{numero} {hex_}")

    assert ofensores == [], f"hex no web fora de design-tokens.json: {ofensores}"


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


def test_hover_de_linha_difere_do_fundo_da_tabela():
    """O hover de linha tem token proprio, e nao surface.1.

    Ate a v0.5 `QTableView::item:hover` usava {surface1}. Quando surface.1
    fechou em #09131A -- praticamente o surface.0 do fundo da tabela -- o
    hover deixou de existir na pratica: a linha nao responde mais ao mouse,
    e esse e o unico retorno visual de "o ponteiro esta aqui". O teste cobre
    as duas metades: o token existir e a regra do QSS usar ELE, e nao um
    vizinho que por acaso esta com o mesmo valor hoje.
    """
    from trackclassifier.ui.tokens import COLOR_SURFACE_0, COLOR_SURFACE_HOVER

    assert COLOR_SURFACE_HOVER != COLOR_SURFACE_0

    qss = (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")

    regra = qss.split("QTableView::item:hover")[1].split("}")[0]
    assert COLOR_SURFACE_HOVER in regra


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


def _bloco(qss: str, seletor: str) -> str:
    """Corpo da regra de `seletor`, exigindo a linha do seletor exata.

    `split(seletor)` sozinho pega o primeiro lugar onde o nome aparece no
    arquivo, e um nome pode aparecer antes em outra regra do mesmo id
    (QLabel#ClassChipLabel aparece antes em
    QLabel#ClassChipLabel[class="low"]). Exigir a linha do seletor desempata.

    Serve para regra de uma linha ou de varias: o corte e no primeiro `}` de
    qualquer forma, entao nao ha `\n` depois do `{` na busca.
    """
    return qss.split(f"\n{seletor} {{", 1)[1].split("}", 1)[0]


def test_chip_de_classe_usa_a_cor_da_classe():
    """`selecao-vs-classe` no JSON: "chips de classe usam azul, ambar e coral".

    Sem este teste, errar a cor deixaria os quatro chips com a mesma cara sem
    quebrar nada -- e a cor e o que identifica a classe antes de o olho ler o
    rotulo (mockup, barra de filtros).
    """
    from trackclassifier.ui.tokens import (
        COLOR_CLASSIFICATION_ANIMADA_BASE,
        COLOR_CLASSIFICATION_LENTO_BASE,
        COLOR_CLASSIFICATION_NEUTRO_BASE,
    )

    qss = (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")
    esperado = {
        "low": COLOR_CLASSIFICATION_LENTO_BASE,
        "neutral": COLOR_CLASSIFICATION_NEUTRO_BASE,
        "high": COLOR_CLASSIFICATION_ANIMADA_BASE,
    }

    for tone, cor in esperado.items():
        for nome in ("QLabel#ClassChipLabel", "QLabel#ClassChipCount"):
            assert cor in _bloco(qss, f'{nome}[class="{tone}"]')


def test_o_chip_de_classe_separa_rotulo_sans_de_contagem_mono():
    """`mono-para-numero`: o numero alinha em coluna, o rotulo nao. Duas fontes
    nao cabem numa string so -- e por isso o chip tem dois QLabel filhos."""
    from trackclassifier.ui.tokens import FONT_FAMILY_MONO, FONT_FAMILY_SANS

    qss = (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")

    assert FONT_FAMILY_SANS in _bloco(qss, "QLabel#ClassChipLabel")
    assert FONT_FAMILY_MONO in _bloco(qss, "QLabel#ClassChipCount")


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
        # abordagem escolhida no PR #22 (main) -- e isso fecha em ~31-32px,
        # nao nos 28px do mockup: 6px de padding em cada lado + 2px de borda
        # + a altura de linha da fonte somam mais do que o min-height
        # descontado teria dado. Gap real e pre-existente do PR #22, nao
        # desta task -- documentado aqui porque este teste e o unico do
        # repo que mede o WIDGET renderizado (o resto so confere o texto
        # do QSS).
        botao = QPushButton("Limpar")
        assert botao.sizeHint().height() == SIZE_CONTROL_BASE

        # QLineEdit oscila 31-32 conforme a FONTE que resolve o stack sans:
        # Inter (instalada nesta maquina) tem metrica que fecha em 31; o
        # fallback Space Grotesk (o que o CI encontra, sem Inter no runner)
        # fecha em 32. Faixa em vez de numero exato, como no QComboBox
        # abaixo -- o docstring acima ja documenta o gap de ~31-32 do PR #22.
        assert 31 <= QLineEdit().sizeHint().height() <= 32

        # QComboBox oscila +-1px entre plataformas sob Fusion (31 no macOS
        # local, 30 no runner Linux do CI -- a seta do dropdown entra na
        # conta do sizeHint de um jeito que o padding sozinho nao fixa).
        # Faixa em vez de numero exato: o que importa e ficar perto de
        # SIZE_CONTROL_BASE, nao o pixel exato de uma plataforma.
        altura_combo = QComboBox().sizeHint().height()
        assert SIZE_CONTROL_BASE + 1 <= altura_combo <= SIZE_CONTROL_BASE + 4

        # QSpinBox foge da regra acima sob QT_QPA_PLATFORM=offscreen (o modo
        # deste teste e do CI, ver conftest.py): o estilo Fusion, que e o
        # fallback headless, soma uma sobra fixa na conta de CT_SpinBox por
        # fora do content-box do QSS -- confirmado empiricamente variando a
        # borda de 0 a 3px (a sobra nao muda) e escondendo as setas com
        # setButtonSymbols(NoButtons) (a sobra tambem nao muda, entao nao e
        # espaco reservado pros botoes). No estilo nativo macOS -- o que o
        # .app empacotado usa de verdade -- essa sobra nao existe e o mesmo
        # QSS bate exato em SIZE_CONTROL_BASE, igual ao QPushButton generico.
        # A sobra em si varia por plataforma sob Fusion (33 no macOS local,
        # 31 no runner Linux do CI -- mesma causa do QComboBox acima, so que
        # maior aqui porque o estilo reserva espaco pros botoes de seta):
        # faixa generosa, nao numero exato.
        altura_spin = QSpinBox().sizeHint().height()
        assert SIZE_CONTROL_BASE + 2 <= altura_spin <= SIZE_CONTROL_BASE + 6
    finally:
        QApplication.instance().setStyleSheet(anterior)
