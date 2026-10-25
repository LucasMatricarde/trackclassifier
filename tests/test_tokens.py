"""Guarda o modo de falha mais provavel do design system: editar o JSON e
esquecer de rodar build_tokens.py, deixando o tokens.css do web velho."""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GERADOS = [RAIZ / "web" / "src" / "styles" / "tokens.css"]


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


def test_css_name_mantem_o_hifen():
    # --size-focus-ring e o nome CSS natural; so o lado Python precisa da
    # normalizacao acima.
    modulo = _build_tokens_module()

    assert modulo.css_name(("size", "focus-ring")) == "--size-focus-ring"
