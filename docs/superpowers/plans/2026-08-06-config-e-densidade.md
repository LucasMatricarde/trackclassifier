# Configuração, primeiro uso e densidade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao TrackClassifier um caminho de interface para configurar as pastas — hoje inexistente, o que impede o app de rodar com dados reais — e corrigir os defeitos de densidade e o componente de player que a spec anterior previu e nunca foi construído.

**Architecture:** A validação de configuração nasce pura em `config.py` (sem Qt, testável sem `QApplication`), consumida por um `SettingsForm` que serve tanto ao diálogo de primeiro uso quanto à 4ª aba. Aplicar configuração em tempo de execução vira um slot novo no `ServiceWorker`, respeitando a regra de que só a thread do worker é dona do `TrackService`. O `PlayerBar` é ligação de sinal ao `BasePlayer` existente, sem lógica de reprodução nova.

**Tech Stack:** Python 3.11–3.13, PySide6, `tomllib` (leitura) + `tomli-w` (escrita), pytest com `QT_QPA_PLATFORM=offscreen`.

**Spec:** `docs/superpowers/specs/2026-08-06-config-e-densidade-design.md`

## Global Constraints

- **Português sem acentos** em todo `src/`: variáveis locais, funções internas, comentários, docstrings, mensagens de erro e nomes de teste. API pública (dataclasses, métodos de classe, campos) em inglês.
- **Nenhum hex fora de `design/design-tokens.json`.** `ui/tokens.py` e `ui/app.qss` são gerados por `uv run python design/build_tokens.py` — nunca editados à mão. `tests/test_tokens.py::test_nenhum_hex_fora_do_json` falha se um literal aparecer em `ui/`.
- **`ui/viewmodel.py` não importa Qt.** `tests/test_viewmodel.py` lê o módulo e falha gramaticalmente se um import de PySide6 aparecer.
- **Camadas de `ui/`:** `viewmodel.py` → `worker.py` → widgets. Um widget nunca chama `TrackService` direto.
- **ruff:** `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` é gate do CI.
- **Comentários explicam por quê, não o quê** — longos quando a decisão não é óbvia.
- **Commits:** conventional commits com escopo, ex. `feat(trackclassifier):`.
- Rodar `uv sync --extra dev` antes de qualquer coisa. `ffmpeg`/`ffprobe` no PATH.

## File Structure

```
src/trackclassifier/
  config.py            + SettingsDraft, SettingsError, validate_settings,
                         apply_draft, save_config, read_raw
  cli.py               - _prepara_config_padrao, - _mostra_erro_grafico
  ui/
    __main__.py        QApplication antes de carregar config; primeiro uso
    settings_form.py   NOVO  formulario puro, sem chrome de dialogo
    first_run.py       NOVO  QDialog = SettingsForm + boas-vindas
    settings_tab.py    NOVO  4a aba = SettingsForm + Salvar
    worker.py          + reload_config
    window.py          4a aba, Escanear encaixado, empty state ligado ao scan
    review_tab.py      PlayerBar, empty state, capa escondida, margens
    library_tab.py     empty state, margens
    model_tab.py       empty state, botao sem esticar, margens
    widgets/
      empty_state.py   NOVO
      player_bar.py    NOVO
design/
  build_tokens.py      + #Hint; #SectionLabel deixa de ser generico
pyproject.toml         + tomli-w
CLAUDE.md              atualiza a secao do executavel do macOS
```

**Ordem das tarefas e por quê:** 1–3 constroem o domínio de configuração sem Qt, e são o que desbloqueia o app. 4–6 constroem a interface de configuração em cima dele. 7 aplica em runtime. 8–11 são densidade e componentes visuais, independentes entre si — quem executar pode reordenar 8–11 sem quebrar nada.

---

### Task 1: `tomli-w` e `save_config`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/trackclassifier/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `Config` (já existe em `config.py`), `Label` (de `labels.py`).
- Produces: `save_config(path: Path, config: Config) -> None`.

- [ ] **Step 1: Adicionar a dependência**

Em `pyproject.toml`, na lista `dependencies`, depois de `"mutagen>=1.48.1",`:

```toml
    "tomli-w>=1.0",
```

- [ ] **Step 2: Instalar**

Run: `uv sync --extra dev`
Expected: instala `tomli-w` sem erro.

- [ ] **Step 3: Escrever o teste que falha**

Acrescentar ao fim de `tests/test_config.py`:

```python
def test_save_config_faz_round_trip_com_apostrofo_e_acento(tmp_path):
    """O motivo de usar tomli-w em vez de serializar a mao.

    Uma pasta chamada "DJ's Tracks" ou "Musicas Novas" quebra um escape
    caseiro em silencio -- o TOML sai sintaticamente valido e com o caminho
    errado dentro.
    """
    from trackclassifier.config import save_config

    pastas = {}
    for rotulo, nome in (
        (Label.UP, "DJ's Tracks +1"),
        (Label.NEUTRAL, "Musicas"),
        (Label.DOWN, 'Aspas " no meio'),
    ):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()

    original = Config(
        folders=pastas, inbox=inbox, data_dir=dados, retrain_every=7, min_examples=3
    )
    destino = tmp_path / "config.toml"
    save_config(destino, original)

    recarregado = load_config(destino)

    assert recarregado.folders == original.folders
    assert recarregado.inbox == original.inbox
    assert recarregado.data_dir == original.data_dir
    assert recarregado.retrain_every == 7
    assert recarregado.min_examples == 3


def test_save_config_cria_o_diretorio_pai(tmp_path):
    """Empacotado o destino e ~/.trackclassifier/config.toml, e a pasta
    pode nao existir na primeira gravacao."""
    from trackclassifier.config import save_config

    pastas = {}
    for rotulo, nome in ((Label.UP, "up"), (Label.NEUTRAL, "neutral"), (Label.DOWN, "down")):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()

    destino = tmp_path / "sem" / "pai" / "config.toml"
    save_config(
        destino,
        Config(folders=pastas, inbox=inbox, data_dir=dados, retrain_every=10, min_examples=15),
    )

    assert destino.is_file()
```

- [ ] **Step 4: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_config.py -k "save_config" -v`
Expected: FAIL com `ImportError: cannot import name 'save_config'`.

- [ ] **Step 5: Implementar**

Em `src/trackclassifier/config.py`, acrescentar `import tomli_w` ao topo (depois de `import tomllib`) e ao fim do arquivo:

```python
def save_config(path: Path, config: Config) -> None:
    """Grava o Config como TOML, criando o diretorio-pai se faltar.

    Usa tomli_w em vez de montar a string a mao: um caminho com aspas ou
    apostrofo -- "DJ's Tracks" e comum num acervo real -- exige escape de
    string basica TOML, e o erro nao aparece na gravacao, so na leitura
    seguinte, com o caminho silenciosamente errado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dados = {
        "folders": {
            "up": str(config.folders[Label.UP]),
            "neutral": str(config.folders[Label.NEUTRAL]),
            "down": str(config.folders[Label.DOWN]),
            "inbox": str(config.inbox),
        },
        "model": {
            "retrain_every": config.retrain_every,
            "min_examples": config.min_examples,
        },
        "paths": {"data_dir": str(config.data_dir)},
    }
    with path.open("wb") as handle:
        tomli_w.dump(dados, handle)
```

- [ ] **Step 6: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS, incluindo os quatro testes que já existiam.

- [ ] **Step 7: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/trackclassifier/config.py tests/test_config.py
git commit -m "feat(trackclassifier): save_config grava o TOML via tomli-w"
```

---

### Task 2: `read_raw` e o rascunho de configuração

**Files:**
- Modify: `src/trackclassifier/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `save_config` da Task 1.
- Produces:
  - `read_raw(path: Path) -> dict`
  - `SettingsDraft` (dataclass congelada, campos: `inbox: str`, `up: str`, `neutral: str`, `down: str`, `data_dir: str`, `retrain_every: int`, `min_examples: int`, `create_under_root: bool`, `root: str`)
  - `SettingsDraft.from_raw(raw: dict) -> SettingsDraft` (classmethod)
  - `NOMES_DE_PASTA: dict[str, str]` — mapeia chave de config para nome de subpasta.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_config.py`:

```python
def test_read_raw_devolve_dicionario_vazio_quando_o_arquivo_nao_existe(tmp_path):
    from trackclassifier.config import read_raw

    assert read_raw(tmp_path / "inexistente.toml") == {}


def test_read_raw_devolve_dicionario_vazio_quando_o_toml_e_invalido(tmp_path):
    """Config corrompido nao pode derrubar o dialogo que existe justamente
    para consertar config."""
    from trackclassifier.config import read_raw

    quebrado = tmp_path / "config.toml"
    quebrado.write_text("[folders\nup = ", encoding="utf-8")

    assert read_raw(quebrado) == {}


def test_read_raw_nao_valida_pastas_inexistentes(tmp_path):
    """A diferenca para load_config: read_raw entrega o que esta escrito,
    mesmo apontando para pasta que sumiu -- e o que preenche o formulario."""
    from trackclassifier.config import read_raw

    cfg = _write_config(tmp_path, folders_exist=False)

    raw = read_raw(cfg)

    assert raw["folders"]["up"] == str(tmp_path / "up")


def test_draft_from_raw_le_um_config_completo(tmp_path):
    from trackclassifier.config import SettingsDraft, read_raw

    cfg = _write_config(tmp_path)

    draft = SettingsDraft.from_raw(read_raw(cfg))

    assert draft.up == str(tmp_path / "up")
    assert draft.inbox == str(tmp_path / "inbox")
    assert draft.retrain_every == 10
    assert draft.min_examples == 15
    assert draft.create_under_root is False
    assert draft.root == ""


def test_draft_from_raw_aceita_dicionario_vazio():
    """Primeiro uso: nao ha nada em disco, e o formulario abre em branco."""
    from trackclassifier.config import SettingsDraft

    draft = SettingsDraft.from_raw({})

    assert draft.up == ""
    assert draft.inbox == ""
    assert draft.retrain_every == 10
    assert draft.min_examples == 15
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_config.py -k "read_raw or draft" -v`
Expected: FAIL com `ImportError: cannot import name 'read_raw'`.

- [ ] **Step 3: Implementar**

Em `src/trackclassifier/config.py`, acrescentar ao fim:

```python
#: Nome da subpasta criada para cada rotulo no modo "criar a estrutura".
#: Vem do vocabulario que o app ja usa na tela e nos atalhos 1/2/3 -- nao
#: inventamos jargao novo so para o disco.
NOMES_DE_PASTA: Final = {"up": "+1", "neutral": "neutra", "down": "-1"}

_RETRAIN_PADRAO: Final = 10
_MIN_EXEMPLOS_PADRAO: Final = 15


def read_raw(path: Path) -> dict:
    """Le o TOML sem validar nada. {} quando ausente ou ilegivel.

    Existe por causa do caso "config existe mas uma pasta sumiu":
    load_config levanta ConfigError e nao devolve nada aproveitavel, entao o
    dialogo de configuracao nao teria com que se preencher e o usuario
    redigitaria os quatro caminhos por causa de um que mudou. Nao substitui
    load_config em lugar nenhum -- nao valida, nao expande, nao cria pasta.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError):
        # Config corrompido nao pode derrubar justamente a tela que serve
        # para consertar config.
        return {}


@dataclass(frozen=True)
class SettingsDraft:
    """O que o formulario tem digitado, ainda sem garantia de ser valido.

    Strings, nao Path: e o texto cru do campo, que pode estar vazio ou
    apontar para algo inexistente enquanto o usuario digita.
    """

    inbox: str
    up: str
    neutral: str
    down: str
    data_dir: str
    retrain_every: int
    min_examples: int
    #: True no modo "criar a estrutura": up/neutral/down sao derivados de
    #: `root` e ainda nao existem no disco.
    create_under_root: bool
    root: str

    @classmethod
    def from_raw(cls, raw: dict) -> "SettingsDraft":
        pastas = raw.get("folders", {})
        modelo = raw.get("model", {})
        caminhos = raw.get("paths", {})
        return cls(
            inbox=str(pastas.get("inbox", "")),
            up=str(pastas.get("up", "")),
            neutral=str(pastas.get("neutral", "")),
            down=str(pastas.get("down", "")),
            data_dir=str(caminhos.get("data_dir", "")),
            retrain_every=int(modelo.get("retrain_every", _RETRAIN_PADRAO)),
            min_examples=int(modelo.get("min_examples", _MIN_EXEMPLOS_PADRAO)),
            create_under_root=False,
            root="",
        )
```

Acrescentar `Final` ao import de `typing` no topo do arquivo:

```python
from typing import Final
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/config.py tests/test_config.py
git commit -m "feat(trackclassifier): read_raw e SettingsDraft para o formulario de config"
```

---

### Task 3: Validação pura e criação da estrutura

**Files:**
- Modify: `src/trackclassifier/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `SettingsDraft`, `NOMES_DE_PASTA` da Task 2; `Config`, `Label`.
- Produces:
  - `SettingsError` (dataclass congelada: `field: str`, `message: str`)
  - `validate_settings(draft: SettingsDraft) -> list[SettingsError]`
  - `apply_draft(draft: SettingsDraft) -> Config`

Valores válidos de `SettingsError.field`: `"inbox"`, `"up"`, `"neutral"`, `"down"`, `"root"`, `"data_dir"`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_config.py`:

```python
def _draft(tmp_path, **overrides):
    from trackclassifier.config import SettingsDraft

    base = {
        "inbox": str(tmp_path / "inbox"),
        "up": str(tmp_path / "up"),
        "neutral": str(tmp_path / "neutral"),
        "down": str(tmp_path / "down"),
        "data_dir": str(tmp_path / "data"),
        "retrain_every": 10,
        "min_examples": 15,
        "create_under_root": False,
        "root": "",
    }
    base.update(overrides)
    return SettingsDraft(**base)


def test_validate_aceita_quatro_pastas_existentes_e_distintas(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    assert validate_settings(_draft(tmp_path)) == []


def test_validate_acusa_campo_vazio(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path, up=""))

    assert [e.field for e in erros] == ["up"]


def test_validate_acusa_pasta_inexistente(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path))

    assert [e.field for e in erros] == ["up"]


def test_validate_acusa_pastas_repetidas(tmp_path):
    """inbox igual a neutral faria apply mover o arquivo para dentro da
    propria pasta, e o O_CREAT|O_EXCL de _destino_livre responderia criando
    um duplicado com nome novo, sem erro nenhum. Falha silenciosa vira
    validacao."""
    from trackclassifier.config import validate_settings

    for nome in ("up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path, inbox=str(tmp_path / "neutral")))

    assert erros != []
    assert any("mesma pasta" in e.message for e in erros)


def test_validate_no_modo_raiz_nao_exige_que_as_subpastas_existam(tmp_path):
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    erros = validate_settings(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert erros == []


def test_validate_no_modo_raiz_exige_a_raiz(tmp_path):
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()

    erros = validate_settings(
        _draft(
            tmp_path,
            create_under_root=True,
            root=str(tmp_path / "nao_existe"),
            up="",
            neutral="",
            down="",
        )
    )

    assert [e.field for e in erros] == ["root"]


def test_validate_no_modo_raiz_acusa_inbox_dentro_da_raiz(tmp_path):
    """A inbox dentro da raiz colidiria com uma das subpastas criadas ou
    faria o scan enxergar as tracks ja classificadas como pendentes."""
    from trackclassifier.config import validate_settings

    raiz = tmp_path / "acervo"
    raiz.mkdir()
    dentro = raiz / "+1"
    dentro.mkdir()

    erros = validate_settings(
        _draft(
            tmp_path,
            create_under_root=True,
            root=str(raiz),
            inbox=str(dentro),
            up="",
            neutral="",
            down="",
        )
    )

    assert erros != []


def test_validate_nao_cria_pasta_nenhuma(tmp_path):
    """Validar roda a cada tecla digitada; criar pasta a cada tecla nao."""
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    validate_settings(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert list(raiz.iterdir()) == []


def test_apply_draft_cria_as_tres_subpastas_na_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    config = apply_draft(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert config.folders[Label.UP] == raiz / "+1"
    assert config.folders[Label.NEUTRAL] == raiz / "neutra"
    assert config.folders[Label.DOWN] == raiz / "-1"
    assert all(pasta.is_dir() for pasta in config.folders.values())


def test_apply_draft_reaproveita_subpasta_que_ja_existe(tmp_path):
    """Reabrir a configuracao no modo raiz nao pode falhar por a pasta ja
    ter sido criada da vez anterior."""
    from trackclassifier.config import apply_draft

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    (raiz / "+1").mkdir(parents=True)

    config = apply_draft(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert config.folders[Label.UP] == raiz / "+1"


def test_apply_draft_usa_as_pastas_informadas_fora_do_modo_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    config = apply_draft(_draft(tmp_path))

    assert config.folders[Label.UP] == tmp_path / "up"
    assert config.inbox == tmp_path / "inbox"
    assert config.data_dir.is_dir()


def test_apply_draft_expande_til(tmp_path, monkeypatch):
    from trackclassifier.config import apply_draft

    monkeypatch.setenv("HOME", str(tmp_path))
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    config = apply_draft(
        _draft(
            tmp_path,
            inbox="~/inbox",
            up="~/up",
            neutral="~/neutral",
            down="~/down",
            data_dir="~/data",
        )
    )

    assert config.inbox == tmp_path / "inbox"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_config.py -k "validate or apply_draft" -v`
Expected: FAIL com `ImportError: cannot import name 'validate_settings'`.

- [ ] **Step 3: Implementar**

Em `src/trackclassifier/config.py`, acrescentar ao fim:

```python
@dataclass(frozen=True)
class SettingsError:
    """Erro amarrado a um campo do formulario, nao a uma caixa modal.

    `field` e uma das chaves: inbox, up, neutral, down, root, data_dir.
    """

    field: str
    message: str


def _subpastas_da_raiz(root: str) -> dict[str, Path]:
    raiz = Path(root).expanduser()
    return {chave: raiz / nome for chave, nome in NOMES_DE_PASTA.items()}


def _caminhos_do_draft(draft: SettingsDraft) -> dict[str, Path]:
    """Os quatro destinos finais, ja resolvidos, nos dois modos."""
    if draft.create_under_root:
        pastas = _subpastas_da_raiz(draft.root)
    else:
        pastas = {
            "up": Path(draft.up).expanduser(),
            "neutral": Path(draft.neutral).expanduser(),
            "down": Path(draft.down).expanduser(),
        }
    pastas["inbox"] = Path(draft.inbox).expanduser()
    return pastas


def validate_settings(draft: SettingsDraft) -> list[SettingsError]:
    """Valida sem tocar no disco alem de perguntar se um caminho existe.

    Quem cria pasta e apply_draft, chamada so depois disto passar. A
    separacao e o que permite validar a cada tecla digitada no formulario
    sem criar uma pasta a cada tecla digitada.
    """
    erros: list[SettingsError] = []

    if not draft.inbox.strip():
        erros.append(SettingsError("inbox", "Escolha a pasta de entrada."))
    elif not Path(draft.inbox).expanduser().is_dir():
        erros.append(SettingsError("inbox", "Esta pasta nao existe."))

    if draft.create_under_root:
        if not draft.root.strip():
            erros.append(SettingsError("root", "Escolha onde criar a estrutura."))
        elif not Path(draft.root).expanduser().is_dir():
            erros.append(SettingsError("root", "Esta pasta nao existe."))
    else:
        for chave, valor in (("up", draft.up), ("neutral", draft.neutral), ("down", draft.down)):
            if not valor.strip():
                erros.append(SettingsError(chave, "Escolha a pasta de destino."))
            elif not Path(valor).expanduser().is_dir():
                erros.append(SettingsError(chave, "Esta pasta nao existe."))

    if erros:
        # Sem os quatro caminhos resolvidos, checar repeticao produziria
        # ruido em cima de erro que o usuario ja esta vendo.
        return erros

    # Duas chaves apontando para a mesma pasta e falha silenciosa, nao
    # ruidosa: decidir "neutra" com inbox == neutral manda apply mover o
    # arquivo para dentro da propria pasta, e o os.open(O_CREAT|O_EXCL) de
    # _destino_livre responde reservando um nome novo -- o usuario ganha uma
    # copia duplicada e nenhuma mensagem.
    vistos: dict[Path, str] = {}
    for chave, caminho in _caminhos_do_draft(draft).items():
        resolvido = caminho.resolve()
        anterior = vistos.get(resolvido)
        if anterior is not None:
            erros.append(
                SettingsError(chave, f"Esta e a mesma pasta de '{anterior}'. Use pastas distintas.")
            )
        else:
            vistos[resolvido] = chave

    return erros


def apply_draft(draft: SettingsDraft) -> Config:
    """Materializa o rascunho: cria as pastas do modo raiz e devolve Config.

    So deve ser chamada depois de validate_settings devolver lista vazia --
    nao revalida.
    """
    pastas = _caminhos_do_draft(draft)
    if draft.create_under_root:
        for chave in NOMES_DE_PASTA:
            # exist_ok: reabrir a configuracao no modo raiz nao pode falhar
            # so porque a pasta foi criada na vez anterior.
            pastas[chave].mkdir(parents=True, exist_ok=True)

    data_dir = Path(draft.data_dir or ".trackclassifier").expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        folders={
            Label.UP: pastas["up"],
            Label.NEUTRAL: pastas["neutral"],
            Label.DOWN: pastas["down"],
        },
        inbox=pastas["inbox"],
        data_dir=data_dir,
        retrain_every=draft.retrain_every,
        min_examples=draft.min_examples,
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/config.py tests/test_config.py
git commit -m "feat(trackclassifier): validacao pura de config e criacao da estrutura de pastas"
```

---

### Task 4: `#Hint` no design system

**Files:**
- Modify: `design/design-tokens.json`
- Modify: `design/build_tokens.py`
- Regenerate: `src/trackclassifier/ui/tokens.py`, `src/trackclassifier/ui/app.qss`
- Test: `tests/test_tokens.py` (já cobre; nenhum teste novo)

**Interfaces:**
- Produces: seletor QSS `QLabel#Hint` — texto auxiliar sem padding; `QLabel#FieldError` — mensagem de erro ao lado do campo, na cor `state.danger`.

**Contexto:** `#SectionLabel` carrega `padding: 12px 8px 6px 8px` e hoje veste cinco widgets dos quais só "Falhas de analise" é cabeçalho de seção. Esse padding é a causa dos três alinhamentos diferentes na Revisão.

- [ ] **Step 1: Acrescentar o template do QSS**

Em `design/build_tokens.py`, logo depois do bloco `QLabel#SectionLabel {{ ... }}`:

```python
QLabel#Hint {{
    color: {textMuted};
    font-size: {fontCaption};
}}

QLabel#FieldError {{
    color: {stateDanger};
    font-size: {fontCaption};
}}
```

- [ ] **Step 2: Conferir o nome da chave do token de perigo**

Run: `uv run python -c "import json;d=json.load(open('design/design-tokens.json'));print(d['color']['state'])"`
Expected: mostra `danger`, confirmando que `css_name` produz `stateDanger`. Se o nome gerado divergir, use o que `build_tokens.py::css_name` produz — não invente.

- [ ] **Step 3: Regenerar**

Run: `uv run python design/build_tokens.py`
Expected: `src/trackclassifier/ui/app.qss` passa a conter `QLabel#Hint` e `QLabel#FieldError`.

- [ ] **Step 4: Rodar os testes de token**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS — os gerados estão em dia com o JSON.

- [ ] **Step 5: Commit**

```bash
git add design/build_tokens.py src/trackclassifier/ui/tokens.py src/trackclassifier/ui/app.qss
git commit -m "feat(design): #Hint e #FieldError para texto auxiliar sem padding de secao"
```

---

### Task 5: `SettingsForm`

**Files:**
- Create: `src/trackclassifier/ui/settings_form.py`
- Test: `tests/test_settings_form.py`

**Interfaces:**
- Consumes: `SettingsDraft`, `SettingsError`, `validate_settings`, `NOMES_DE_PASTA` (Tasks 2–3).
- Produces:
  - `SettingsForm(QWidget)` com:
    - `set_draft(draft: SettingsDraft) -> None`
    - `draft() -> SettingsDraft`
    - `show_errors(erros: list[SettingsError]) -> None`
    - `validity_changed = Signal(bool)` — emitido quando o formulário passa a ser (ou deixa de ser) válido.
  - `escolher_pasta` é injetável: `SettingsForm(escolher_pasta=callable)` recebe `Callable[[str, str], str]` que dado (título, caminho atual) devolve o caminho escolhido ou `""`. O default abre `QFileDialog.getExistingDirectory`. Isso é o que torna o teste possível sem diálogo nativo.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_settings_form.py`:

```python
"""O formulario de configuracao. Roda offscreen (conftest), sem dialogo nativo.

O picker de pasta e injetado: QFileDialog.getExistingDirectory abre uma
janela modal de verdade e trava a suite. Injetar o callable e o que permite
exercitar o clique no botao "Escolher" de verdade, pelo caminho real do
widget, em vez de so chamar set_draft.
"""

import pytest

from trackclassifier.config import SettingsDraft
from trackclassifier.ui.settings_form import SettingsForm


@pytest.fixture
def form(qapp, tmp_path):
    escolhidas = []

    def escolher(titulo, atual):
        return escolhidas.pop(0) if escolhidas else ""

    widget = SettingsForm(escolher_pasta=escolher)
    widget._escolhidas_do_teste = escolhidas
    return widget


def _draft_cheio(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()
    return SettingsDraft(
        inbox=str(tmp_path / "inbox"),
        up=str(tmp_path / "up"),
        neutral=str(tmp_path / "neutral"),
        down=str(tmp_path / "down"),
        data_dir=str(tmp_path / "data"),
        retrain_every=10,
        min_examples=15,
        create_under_root=False,
        root="",
    )


def test_round_trip_de_draft(form, tmp_path):
    original = _draft_cheio(tmp_path)

    form.set_draft(original)

    assert form.draft() == original


def test_formulario_vazio_e_invalido(form):
    form.set_draft(SettingsDraft.from_raw({}))

    assert form.is_valid() is False


def test_formulario_completo_e_valido(form, tmp_path):
    form.set_draft(_draft_cheio(tmp_path))

    assert form.is_valid() is True


def test_modo_raiz_esconde_os_tres_pickers(form, tmp_path):
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    (tmp_path / "inbox").mkdir()

    form.set_draft(
        SettingsDraft(
            inbox=str(tmp_path / "inbox"),
            up="",
            neutral="",
            down="",
            data_dir=str(tmp_path / "data"),
            retrain_every=10,
            min_examples=15,
            create_under_root=True,
            root=str(raiz),
        )
    )

    assert form.is_valid() is True
    assert form.campo_visivel("up") is False
    assert form.campo_visivel("root") is True


def test_show_errors_marca_o_campo_culpado(form, tmp_path):
    from trackclassifier.config import SettingsError

    form.set_draft(_draft_cheio(tmp_path))

    form.show_errors([SettingsError("up", "Esta pasta nao existe.")])

    assert form.erro_do_campo("up") == "Esta pasta nao existe."
    assert form.erro_do_campo("inbox") == ""


def test_show_errors_limpa_a_marcacao_anterior(form, tmp_path):
    from trackclassifier.config import SettingsError

    form.set_draft(_draft_cheio(tmp_path))
    form.show_errors([SettingsError("up", "Esta pasta nao existe.")])

    form.show_errors([])

    assert form.erro_do_campo("up") == ""


def test_botao_escolher_preenche_o_campo(form, tmp_path):
    """Exercita o caminho real do botao, nao so set_draft."""
    destino = tmp_path / "escolhida"
    destino.mkdir()
    form._escolhidas_do_teste.append(str(destino))

    form.escolher_para_o_teste("inbox")

    assert form.draft().inbox == str(destino)


def test_validity_changed_dispara_ao_completar(form, tmp_path):
    recebidos = []
    form.validity_changed.connect(recebidos.append)

    form.set_draft(_draft_cheio(tmp_path))

    assert recebidos[-1] is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_settings_form.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.settings_form'`.

- [ ] **Step 3: Implementar**

Criar `src/trackclassifier/ui/settings_form.py`:

```python
"""Formulario de configuracao, sem chrome de dialogo.

Um widget so, usado em dois lugares: dentro do FirstRunDialog na primeira
abertura e dentro da aba Configuracao depois. Toda a validacao mora em
config.validate_settings (puro, sem Qt) -- aqui so ha desenho e ligacao de
sinal, que e o que permite testar as regras sem QApplication.
"""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import NOMES_DE_PASTA, SettingsDraft, SettingsError, validate_settings
from .tokens import SPACE_2, SPACE_5, SPACE_6

_TITULOS = {
    "inbox": "Pasta de entrada",
    "root": "Criar a estrutura em",
    "up": "Destino +1",
    "neutral": "Destino neutra",
    "down": "Destino -1",
    "data_dir": "Dados do app",
}


class _CampoDePasta(QWidget):
    """Linha do formulario: campo de texto, botao Escolher e erro embaixo."""

    changed = Signal()

    def __init__(self, chave: str, escolher_pasta, parent=None) -> None:
        super().__init__(parent)
        self.chave = chave
        self._escolher_pasta = escolher_pasta

        self.campo = QLineEdit()
        self.campo.textChanged.connect(self.changed)

        botao = QPushButton("Escolher...")
        botao.clicked.connect(self.escolher)

        self._erro = QLabel("")
        self._erro.setObjectName("FieldError")
        self._erro.setVisible(False)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(SPACE_2)
        linha.addWidget(self.campo, 1)
        linha.addWidget(botao)

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(SPACE_2)
        fora.addLayout(linha)
        fora.addWidget(self._erro)

    def escolher(self) -> None:
        caminho = self._escolher_pasta(_TITULOS[self.chave], self.campo.text())
        if caminho:
            self.campo.setText(caminho)

    def texto(self) -> str:
        return self.campo.text()

    def set_texto(self, valor: str) -> None:
        self.campo.setText(valor)

    def mostra_erro(self, mensagem: str) -> None:
        self._erro.setText(mensagem)
        # setVisible(False) em vez de texto vazio: um QLabel vazio ainda
        # ocupa a altura da linha, e o formulario pularia de altura a cada
        # tecla digitada enquanto o caminho esta incompleto.
        self._erro.setVisible(bool(mensagem))

    def erro(self) -> str:
        return self._erro.text() if self._erro.isVisible() else ""


def _abre_dialogo_de_pasta(titulo: str, atual: str) -> str:
    return QFileDialog.getExistingDirectory(None, titulo, atual)


class SettingsForm(QWidget):
    #: Emitido quando o formulario passa a ser, ou deixa de ser, valido.
    validity_changed = Signal(bool)

    def __init__(
        self,
        escolher_pasta: Callable[[str, str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Injetavel por causa do teste: QFileDialog.getExistingDirectory abre
        # uma janela modal nativa e travaria a suite. Com o callable injetado
        # da para exercitar o botao "Escolher" pelo caminho real do widget.
        escolher = escolher_pasta or _abre_dialogo_de_pasta

        self._valido = False
        self._campos: dict[str, _CampoDePasta] = {}

        self._modo_raiz = QCheckBox("Nao tenho as pastas ainda - criar a estrutura para mim")
        self._modo_raiz.toggled.connect(self._alterna_modo)

        self._ajuda_raiz = QLabel(
            "Serao criadas as subpastas "
            + ", ".join(NOMES_DE_PASTA.values())
            + " dentro da pasta escolhida."
        )
        self._ajuda_raiz.setObjectName("Hint")

        self._retrain = QSpinBox()
        self._retrain.setRange(1, 1000)
        self._min_exemplos = QSpinBox()
        self._min_exemplos.setRange(1, 1000)

        formulario = QFormLayout()
        formulario.setSpacing(SPACE_5)
        for chave in ("inbox",):
            self._campos[chave] = _CampoDePasta(chave, escolher)
            formulario.addRow(_TITULOS[chave], self._campos[chave])

        formulario.addRow("", self._modo_raiz)

        for chave in ("root", "up", "neutral", "down", "data_dir"):
            self._campos[chave] = _CampoDePasta(chave, escolher)
            formulario.addRow(_TITULOS[chave], self._campos[chave])

        formulario.addRow("Retreinar a cada", self._retrain)
        formulario.addRow("Minimo de exemplos", self._min_exemplos)

        for campo in self._campos.values():
            campo.changed.connect(self._revalida)
        self._retrain.valueChanged.connect(self._revalida)
        self._min_exemplos.valueChanged.connect(self._revalida)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addLayout(formulario)
        layout.addWidget(self._ajuda_raiz)
        layout.addStretch(1)

        self._alterna_modo(False)

    # ---- estado --------------------------------------------------------

    def set_draft(self, draft: SettingsDraft) -> None:
        self._modo_raiz.setChecked(draft.create_under_root)
        for chave in ("inbox", "root", "up", "neutral", "down", "data_dir"):
            self._campos[chave].set_texto(getattr(draft, chave))
        self._retrain.setValue(draft.retrain_every)
        self._min_exemplos.setValue(draft.min_examples)
        self._revalida()

    def draft(self) -> SettingsDraft:
        return SettingsDraft(
            inbox=self._campos["inbox"].texto(),
            up=self._campos["up"].texto(),
            neutral=self._campos["neutral"].texto(),
            down=self._campos["down"].texto(),
            data_dir=self._campos["data_dir"].texto(),
            retrain_every=self._retrain.value(),
            min_examples=self._min_exemplos.value(),
            create_under_root=self._modo_raiz.isChecked(),
            root=self._campos["root"].texto(),
        )

    def is_valid(self) -> bool:
        return self._valido

    # ---- erros ---------------------------------------------------------

    def show_errors(self, erros: list[SettingsError]) -> None:
        por_campo = {erro.field: erro.message for erro in erros}
        for chave, campo in self._campos.items():
            campo.mostra_erro(por_campo.get(chave, ""))

    def erro_do_campo(self, chave: str) -> str:
        return self._campos[chave].erro()

    def campo_visivel(self, chave: str) -> bool:
        return self._campos[chave].isVisible()

    # ---- interno -------------------------------------------------------

    def escolher_para_o_teste(self, chave: str) -> None:
        """Aciona o botao Escolher do campo. Existe para o teste chamar o
        mesmo caminho que o clique real percorre."""
        self._campos[chave].escolher()

    def _alterna_modo(self, criar: bool) -> None:
        self._campos["root"].setVisible(criar)
        self._ajuda_raiz.setVisible(criar)
        for chave in ("up", "neutral", "down"):
            self._campos[chave].setVisible(not criar)
        self._revalida()

    def _revalida(self) -> None:
        erros = validate_settings(self.draft())
        valido = not erros
        if valido != self._valido:
            self._valido = valido
            self.validity_changed.emit(valido)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_settings_form.py -v`
Expected: PASS.

Se `test_modo_raiz_esconde_os_tres_pickers` falhar em `campo_visivel`, a causa provável é o widget nunca ter sido mostrado — `isVisible()` só reflete a hierarquia depois de um `show()`. Nesse caso trocar o assert por `campo_visivel` implementado como `not self._campos[chave].isHidden()`, que é o estado explícito e não depende de o pai estar visível.

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/settings_form.py tests/test_settings_form.py
git commit -m "feat(trackclassifier): SettingsForm com validacao por campo"
```

---

### Task 6: `FirstRunDialog` e o primeiro uso em `ui/__main__.py`

**Files:**
- Create: `src/trackclassifier/ui/first_run.py`
- Modify: `src/trackclassifier/ui/__main__.py`
- Modify: `src/trackclassifier/cli.py:30-53,101-124`
- Test: `tests/test_first_run.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `SettingsForm` (Task 5); `read_raw`, `SettingsDraft`, `validate_settings`, `apply_draft`, `save_config` (Tasks 1–3).
- Produces:
  - `FirstRunDialog(QDialog)` com `__init__(caminho: Path, escolher_pasta=None, parent=None)` e propriedade `config: Config | None`.
  - `ui/__main__.py::main(config_path: str = "config.toml") -> int` — mesma assinatura, comportamento novo.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_first_run.py`:

```python
"""Primeiro uso: config ausente ou invalido abre o dialogo, nao um erro."""

import pytest

from trackclassifier.config import load_config, save_config
from trackclassifier.ui.first_run import FirstRunDialog


def _pastas(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()


def test_abre_em_branco_quando_nao_ha_config(qapp, tmp_path):
    dialogo = FirstRunDialog(tmp_path / "config.toml")

    assert dialogo.form.draft().inbox == ""
    assert dialogo.config is None


def test_abre_preenchido_quando_o_config_existe_mas_a_pasta_sumiu(qapp, tmp_path):
    """O caso que hoje e beco sem saida: em vez de mandar editar um TOML, o
    dialogo abre com o que deu para ler."""
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    save_config(caminho, load_config_de_teste(tmp_path, caminho))
    (tmp_path / "up").rmdir()

    dialogo = FirstRunDialog(caminho)

    assert dialogo.form.draft().inbox == str(tmp_path / "inbox")
    assert dialogo.form.draft().up == str(tmp_path / "up")


def load_config_de_teste(tmp_path, caminho):
    from trackclassifier.config import Config
    from trackclassifier.labels import Label

    return Config(
        folders={
            Label.UP: tmp_path / "up",
            Label.NEUTRAL: tmp_path / "neutral",
            Label.DOWN: tmp_path / "down",
        },
        inbox=tmp_path / "inbox",
        data_dir=tmp_path / "data",
        retrain_every=10,
        min_examples=15,
    )


def test_confirmar_grava_o_arquivo_e_expoe_o_config(qapp, tmp_path):
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    dialogo = FirstRunDialog(caminho)
    dialogo.form.set_draft(
        dialogo.form.draft().__class__(
            inbox=str(tmp_path / "inbox"),
            up=str(tmp_path / "up"),
            neutral=str(tmp_path / "neutral"),
            down=str(tmp_path / "down"),
            data_dir=str(tmp_path / "data"),
            retrain_every=10,
            min_examples=15,
            create_under_root=False,
            root="",
        )
    )

    dialogo.confirmar()

    assert caminho.is_file()
    assert dialogo.config is not None
    assert load_config(caminho).inbox == tmp_path / "inbox"


def test_confirmar_no_modo_raiz_cria_as_subpastas(qapp, tmp_path):
    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    caminho = tmp_path / "config.toml"

    dialogo = FirstRunDialog(caminho)
    dialogo.form.set_draft(
        dialogo.form.draft().__class__(
            inbox=str(tmp_path / "inbox"),
            up="",
            neutral="",
            down="",
            data_dir=str(tmp_path / "data"),
            retrain_every=10,
            min_examples=15,
            create_under_root=True,
            root=str(raiz),
        )
    )

    dialogo.confirmar()

    assert (raiz / "+1").is_dir()
    assert (raiz / "neutra").is_dir()
    assert (raiz / "-1").is_dir()


def test_confirmar_com_formulario_invalido_nao_grava(qapp, tmp_path):
    caminho = tmp_path / "config.toml"
    dialogo = FirstRunDialog(caminho)

    dialogo.confirmar()

    assert not caminho.exists()
    assert dialogo.config is None
    assert dialogo.form.erro_do_campo("inbox") != ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_first_run.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.first_run'`.

- [ ] **Step 3: Implementar o diálogo**

Criar `src/trackclassifier/ui/first_run.py`:

```python
"""Dialogo de primeira abertura -- e de conserto de config quebrado.

Dispara pela AUSENCIA do arquivo de config, nao por uma flag "ja abriu
antes" guardada em algum lugar: o estado que importa e ter ou nao ter
configuracao utilizavel, e ele ja mora no disco.

Cobre tambem o config que existe mas ficou invalido (pasta apagada ou
renomeada). Antes isso era beco sem saida -- um QMessageBox mandando editar
um TOML e reabrir o app.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..config import (
    Config,
    ConfigError,
    SettingsDraft,
    apply_draft,
    load_config,
    read_raw,
    save_config,
    validate_settings,
)
from .settings_form import SettingsForm
from .tokens import SPACE_5, SPACE_6

_BOAS_VINDAS = (
    "Antes de comecar, diga onde ficam as suas tracks. "
    "Voce pode mudar isso depois na aba Configuracao."
)


class FirstRunDialog(QDialog):
    def __init__(self, caminho: Path, escolher_pasta=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Track classifier")
        self._caminho = Path(caminho)
        self._config: Config | None = None

        intro = QLabel(_BOAS_VINDAS)
        intro.setWordWrap(True)

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        # read_raw e nao load_config: quando o config existe mas uma pasta
        # sumiu, load_config levanta e nao devolve nada aproveitavel -- o
        # usuario redigitaria os quatro caminhos por causa de um que mudou.
        self.form.set_draft(SettingsDraft.from_raw(read_raw(self._caminho)))

        self._botoes = QDialogButtonBox()
        self._comecar = self._botoes.addButton("Comecar", QDialogButtonBox.ButtonRole.AcceptRole)
        self._comecar.setProperty("variant", "primary")
        self._botoes.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._botoes.accepted.connect(self.confirmar)
        self._botoes.rejected.connect(self.reject)

        self._comecar.setEnabled(self.form.is_valid())
        self.form.validity_changed.connect(self._comecar.setEnabled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(intro)
        layout.addWidget(self.form, 1)
        layout.addWidget(self._botoes)

    @property
    def config(self) -> Config | None:
        return self._config

    def confirmar(self) -> None:
        rascunho = self.form.draft()
        erros = validate_settings(rascunho)
        if erros:
            self.form.show_errors(erros)
            return
        self.form.show_errors([])

        config = apply_draft(rascunho)
        save_config(self._caminho, config)
        # Rele do disco: e o que garante que o que a janela vai usar e
        # exatamente o que foi gravado, e nao um Config em memoria que
        # divergiria de um arquivo mal gravado.
        try:
            self._config = load_config(self._caminho)
        except ConfigError as erro:
            self.form.show_errors([_erro_generico(str(erro))])
            return
        self.accept()


def _erro_generico(mensagem: str):
    from ..config import SettingsError

    return SettingsError("inbox", mensagem)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_first_run.py -v`
Expected: PASS.

- [ ] **Step 5: Reescrever `ui/__main__.py`**

Substituir o conteúdo inteiro de `src/trackclassifier/ui/__main__.py` por:

```python
"""Ponto de entrada da janela. Carrega o QSS gerado e sobe o QApplication."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from ..config import Config, ConfigError, load_config
from ..service import TrackService
from .first_run import FirstRunDialog
from .window import MainWindow

QSS = Path(__file__).parent / "app.qss"


def _tenta_carregar(caminho: Path) -> Config | None:
    """None quando nao da para usar -- ausente, ilegivel ou pasta sumida.

    Nao distingue os casos de proposito: os tres levam ao mesmo lugar, o
    dialogo, que se preenche sozinho com o que houver de aproveitavel.
    """
    try:
        return load_config(caminho)
    except ConfigError:
        return None


def main(config_path: str = "config.toml") -> int:
    caminho = Path(config_path)

    # QApplication PRECISA existir antes do dialogo. Ate a fase anterior o
    # load_config rodava aqui em cima e um ConfigError abortava o programa
    # antes de haver Qt -- por isso o erro so podia virar texto no stderr.
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))

    config = _tenta_carregar(caminho)
    if config is None:
        dialogo = FirstRunDialog(caminho)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            # Cancelar fecha o app sem gravar nada. Sai com 0: desistir da
            # configuracao nao e falha do programa.
            return 0
        config = dialogo.config
        assert config is not None  # accept() so acontece com config carregado

    janela = MainWindow(TrackService(config), config_path=caminho)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

Nota para quem executa: `MainWindow` ainda não aceita `config_path`. Esse parâmetro é adicionado na Task 7 — até lá, este arquivo não roda. Se preferir manter a suíte verde entre commits, faça a Task 7 antes de rodar a suíte inteira, ou passe `MainWindow(TrackService(config))` aqui e acrescente o argumento na Task 7.

- [ ] **Step 6: Limpar `cli.py`**

Em `src/trackclassifier/cli.py`:

1. Apagar a função `_prepara_config_padrao` inteira (linhas 30–42) e `_mostra_erro_grafico` inteira (linhas 45–53).
2. Apagar o import de `ConfigError` da linha 5 **apenas se** ele não for mais usado — ele ainda é, no `except` do bloco headless (linha 128). Manter.
3. Substituir o bloco do comando `review` (linhas 101–124) por:

```python
    if argumentos.comando == "review":
        # A janela faz o proprio scan (ver Task 9 da fase 1): construir um
        # TrackService aqui so pra descartar seria reler o parquet inteiro e
        # desempacotar o model.joblib duas vezes -- ui/__main__.py monta o
        # seu proprio.
        #
        # O try/except de ConfigError saiu junto com _prepara_config_padrao:
        # config ausente ou invalido agora abre o FirstRunDialog dentro de
        # ui.__main__, que e o unico lugar com QApplication vivo para exibir
        # qualquer coisa. Copiar o config.example.toml para o home era pior
        # que nao copiar -- transformava "nao tem config" em "config
        # apontando para /Users/SEU_USUARIO", que e justamente a condicao que
        # dispara o dialogo, escondida atras de um arquivo que existe.
        print("Abrindo a janela de revisao...")
        from .ui.__main__ import main as abre_janela

        return abre_janela(str(Path(argumentos.config)))
```

- [ ] **Step 7: Ajustar os testes de CLI**

Run: `uv run pytest tests/test_cli.py -v`
Expected: falham os testes que exercitam `_prepara_config_padrao` ou o `ConfigError` no `review`.

Para cada falha, remova o teste se ele cobria só a função apagada, ou reescreva-o para o comportamento novo. Não invente comportamento para manter um teste verde: a cópia do `config.example.toml` deixou de existir de propósito.

- [ ] **Step 8: Suíte inteira**

Run: `uv run pytest`
Expected: PASS (com a ressalva do Step 5 sobre a ordem em relação à Task 7).

- [ ] **Step 9: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 10: Commit**

```bash
git add src/trackclassifier/ui/first_run.py src/trackclassifier/ui/__main__.py \
        src/trackclassifier/cli.py tests/test_first_run.py tests/test_cli.py
git commit -m "feat(trackclassifier): dialogo de primeiro uso substitui o config copiado a mao"
```

---

### Task 7: `reload_config` no worker e a 4ª aba

**Files:**
- Create: `src/trackclassifier/ui/settings_tab.py`
- Modify: `src/trackclassifier/ui/worker.py`
- Modify: `src/trackclassifier/ui/window.py`
- Test: `tests/test_worker.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `SettingsForm` (Task 5); `apply_draft`, `save_config`, `validate_settings`, `read_raw`, `SettingsDraft` (Tasks 1–3).
- Produces:
  - `ServiceWorker.reload_config(config: Config) -> None` — `@Slot(object)`.
  - `SettingsTab(QWidget)` com `config_saved = Signal(object)` (carrega um `Config`), `set_scanning(bool) -> None`, e atributo `form: SettingsForm`.
  - `MainWindow.__init__(service, config_path: Path)`.

- [ ] **Step 1: Escrever o teste do worker**

Acrescentar ao fim de `tests/test_worker.py`:

```python
def test_reload_config_troca_o_servico_e_reemite_estado(qapp, tmp_path):
    """Salvar a configuracao precisa recriar o TrackService: mudou pasta ou
    data_dir, mudaram o cache e o modelo. Recriar DENTRO da thread do worker
    e o que mantem a regra de uma so thread dona do servico."""
    from tests.test_viewmodel import ExtratorFalso, _config
    from trackclassifier.service import TrackService
    from trackclassifier.ui.worker import ServiceWorker

    primeiro = _config(tmp_path / "a")
    segundo = _config(tmp_path / "b")
    worker = ServiceWorker(TrackService(primeiro, extractor=ExtratorFalso(), max_workers=1))

    recebidos = []
    worker.states_changed.connect(lambda *estados: recebidos.append(estados))

    worker.reload_config(segundo)

    assert recebidos != []
    assert worker._service.config.inbox == segundo.inbox
```

Se `_config` não aceitar um diretório inexistente, crie os pais antes: `(tmp_path / "a").mkdir()` e `(tmp_path / "b").mkdir()`.

Se `TrackService` não expuser `.config`, troque o último assert por uma verificação de comportamento — por exemplo, que `library_state(worker._service).rows` reflete o acervo do segundo config.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_worker.py -k reload_config -v`
Expected: FAIL com `AttributeError: 'ServiceWorker' object has no attribute 'reload_config'`.

- [ ] **Step 3: Implementar o slot**

Em `src/trackclassifier/ui/worker.py`, acrescentar `Config` ao import (`from ..config import Config`) e o slot logo depois de `refresh`:

```python
    @Slot(object)
    def reload_config(self, config: Config) -> None:
        """Troca o TrackService por um construido sobre a config nova.

        Roda na thread do worker, como todo o resto: recriar o servico na
        thread da GUI colocaria dois donos no mesmo parquet, que e
        exatamente o que a arquitetura desta UI existe para evitar.

        Limitacao conhecida, tratada na tela e nao aqui: durante um scan o
        loop de eventos desta thread esta parado dentro de analyze_all, entao
        este slot -- enfileirado -- so rodaria quando o scan terminasse. A
        aba Configuracao desabilita Salvar enquanto escaneia, com o motivo
        dito ao lado do botao.
        """
        try:
            self._service = TrackService(config)
        except Exception as erro:
            # Mesma politica do resto do worker: degrada e reporta, nunca
            # derruba a janela. O servico antigo continua de pe.
            self.error.emit(f"Falha ao aplicar a configuracao: {erro}")
            return
        self.refresh()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_worker.py -v`
Expected: PASS.

- [ ] **Step 5: Escrever o teste da aba**

Criar `tests/test_settings_tab.py`:

```python
"""A 4a aba: mesmo formulario do primeiro uso, mais Salvar."""

from trackclassifier.config import SettingsDraft, load_config
from trackclassifier.ui.settings_tab import SettingsTab


def _pastas(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()


def _draft(tmp_path):
    return SettingsDraft(
        inbox=str(tmp_path / "inbox"),
        up=str(tmp_path / "up"),
        neutral=str(tmp_path / "neutral"),
        down=str(tmp_path / "down"),
        data_dir=str(tmp_path / "data"),
        retrain_every=10,
        min_examples=15,
        create_under_root=False,
        root="",
    )


def test_salvar_grava_e_emite_o_config(qapp, tmp_path):
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    aba = SettingsTab(caminho)
    aba.form.set_draft(_draft(tmp_path))

    emitidos = []
    aba.config_saved.connect(emitidos.append)

    aba.salvar()

    assert caminho.is_file()
    assert load_config(caminho).inbox == tmp_path / "inbox"
    assert len(emitidos) == 1


def test_salvar_invalido_nao_grava_e_marca_o_campo(qapp, tmp_path):
    caminho = tmp_path / "config.toml"
    aba = SettingsTab(caminho)

    aba.salvar()

    assert not caminho.exists()
    assert aba.form.erro_do_campo("inbox") != ""


def test_salvar_desabilitado_durante_scan(qapp, tmp_path):
    """Durante um scan o worker esta preso em analyze_all e um slot
    enfileirado so rodaria no fim -- o botao dizer isso e melhor que a
    configuracao aplicar sozinha dez minutos depois."""
    _pastas(tmp_path)
    aba = SettingsTab(tmp_path / "config.toml")
    aba.form.set_draft(_draft(tmp_path))
    assert aba.botao_habilitado() is True

    aba.set_scanning(True)

    assert aba.botao_habilitado() is False

    aba.set_scanning(False)

    assert aba.botao_habilitado() is True
```

- [ ] **Step 6: Rodar e ver falhar**

Run: `uv run pytest tests/test_settings_tab.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 7: Implementar a aba**

Criar `src/trackclassifier/ui/settings_tab.py`:

```python
"""Aba Configuracao: o mesmo SettingsForm do primeiro uso, mais Salvar.

Um formulario so nos dois papeis -- uma validacao, uma copia da regra de
qual pasta pode ser igual a qual.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..config import (
    ConfigError,
    SettingsDraft,
    SettingsError,
    apply_draft,
    load_config,
    read_raw,
    save_config,
    validate_settings,
)
from .settings_form import SettingsForm
from .tokens import SPACE_4, SPACE_5, SPACE_6

_MOTIVO_SCAN = "Aguarde o scan terminar para salvar."


class SettingsTab(QWidget):
    #: Carrega o Config recem-gravado. object porque Signal nao aceita uma
    #: dataclass arbitraria como tipo declarado.
    config_saved = Signal(object)

    def __init__(self, caminho: Path, escolher_pasta=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caminho = Path(caminho)
        self._escaneando = False

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        self.form.set_draft(SettingsDraft.from_raw(read_raw(self._caminho)))
        self.form.validity_changed.connect(lambda _valido: self._atualiza_botao())

        self._botao = QPushButton("Salvar")
        self._botao.setProperty("variant", "primary")
        self._botao.clicked.connect(self.salvar)

        self._motivo = QLabel("")
        self._motivo.setObjectName("Hint")

        rodape = QHBoxLayout()
        rodape.setSpacing(SPACE_4)
        rodape.addWidget(self._motivo)
        rodape.addStretch(1)
        rodape.addWidget(self._botao)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self.form, 1)
        layout.addLayout(rodape)

        self._atualiza_botao()

    def set_scanning(self, escaneando: bool) -> None:
        self._escaneando = escaneando
        self._motivo.setText(_MOTIVO_SCAN if escaneando else "")
        self._atualiza_botao()

    def botao_habilitado(self) -> bool:
        return self._botao.isEnabled()

    def salvar(self) -> None:
        rascunho = self.form.draft()
        erros = validate_settings(rascunho)
        if erros:
            self.form.show_errors(erros)
            return
        self.form.show_errors([])

        config = apply_draft(rascunho)
        save_config(self._caminho, config)
        try:
            gravado = load_config(self._caminho)
        except ConfigError as erro:
            self.form.show_errors([SettingsError("inbox", str(erro))])
            return
        self.config_saved.emit(gravado)

    def _atualiza_botao(self) -> None:
        self._botao.setEnabled(self.form.is_valid() and not self._escaneando)
```

- [ ] **Step 8: Rodar e ver passar**

Run: `uv run pytest tests/test_settings_tab.py -v`
Expected: PASS.

- [ ] **Step 9: Ligar na janela**

Em `src/trackclassifier/ui/window.py`:

1. Trocar a assinatura para `def __init__(self, service: TrackService, config_path: Path | None = None) -> None:` e acrescentar `from pathlib import Path` ao topo.
2. Depois de `self.model_tab = ModelTab()`:

```python
        # config_path opcional: os testes de fumaca da janela montam um
        # TrackService direto, sem arquivo de config em disco. Sem caminho,
        # a aba nao aparece -- e melhor que uma aba que grava num lugar
        # inventado.
        self.settings_tab = SettingsTab(config_path) if config_path is not None else None
```

3. Depois de `self.tabs.addTab(self.model_tab, "Modelo")`:

```python
        if self.settings_tab is not None:
            self.tabs.addTab(self.settings_tab, "Configuracao")
```

4. Em `_conecta`, acrescentar:

```python
        if self.settings_tab is not None:
            self.settings_tab.config_saved.connect(self._aplica_config)
```

5. Acrescentar o método:

```python
    def _aplica_config(self, config) -> None:
        # Overload de 3 argumentos pelo mesmo motivo do refresh e do scan:
        # e o unico que despacha via fila de eventos do worker em vez de
        # rodar na thread de quem chamou.
        QTimer.singleShot(0, self._worker, lambda: self._worker.reload_config(config))
        self.statusBar().showMessage("Configuracao aplicada.", 4000)
```

6. Em `_inicia_scan`, depois de `self._botao_scan.setText(TEXTO_CANCELAR)`:

```python
        if self.settings_tab is not None:
            self.settings_tab.set_scanning(True)
```

7. Em `_scan_concluido`, depois de `self._botao_scan.setEnabled(True)`:

```python
        if self.settings_tab is not None:
            self.settings_tab.set_scanning(False)
```

8. Import: `from .settings_tab import SettingsTab`.

- [ ] **Step 10: Teste de janela**

Acrescentar ao fim de `tests/test_window.py`:

```python
def test_janela_sem_config_path_nao_mostra_a_aba_configuracao(qapp, tmp_path):
    config = _config(tmp_path)
    janela = MainWindow(_servico(config))
    try:
        titulos = [janela.tabs.tabText(i) for i in range(janela.tabs.count())]
        assert "Configuracao" not in titulos
    finally:
        janela.close()


def test_janela_com_config_path_mostra_a_aba_configuracao(qapp, tmp_path):
    from trackclassifier.config import save_config

    config = _config(tmp_path)
    caminho = tmp_path / "config.toml"
    save_config(caminho, config)

    janela = MainWindow(_servico(config), config_path=caminho)
    try:
        titulos = [janela.tabs.tabText(i) for i in range(janela.tabs.count())]
        assert titulos[-1] == "Configuracao"
    finally:
        janela.close()
```

- [ ] **Step 11: Suíte inteira**

Run: `uv run pytest`
Expected: PASS.

- [ ] **Step 12: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 13: Commit**

```bash
git add src/trackclassifier/ui/settings_tab.py src/trackclassifier/ui/worker.py \
        src/trackclassifier/ui/window.py tests/test_settings_tab.py \
        tests/test_worker.py tests/test_window.py
git commit -m "feat(trackclassifier): aba Configuracao aplica sem reabrir o app"
```

---

### Task 8: `EmptyState`

**Files:**
- Create: `src/trackclassifier/ui/widgets/empty_state.py`
- Test: `tests/test_empty_state.py`

**Interfaces:**
- Produces: `EmptyState(QWidget)` com `__init__(titulo: str, subtitulo: str = "", acao: str = "", parent=None)` e `action_clicked = Signal()`. Sem `acao`, nenhum botão é criado.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_empty_state.py`:

```python
"""O empty state e o rosto do app: as tres abas abrem vazias."""

from trackclassifier.ui.widgets.empty_state import EmptyState


def test_sem_acao_nao_cria_botao(qapp):
    vazio = EmptyState("Fila vazia")

    assert vazio.tem_botao() is False


def test_com_acao_emite_ao_clicar(qapp):
    vazio = EmptyState("Fila vazia", "Escaneie a inbox", "Escanear")
    recebidos = []
    vazio.action_clicked.connect(lambda: recebidos.append(True))

    vazio.acionar()

    assert vazio.tem_botao() is True
    assert recebidos == [True]


def test_subtitulo_vazio_nao_ocupa_altura(qapp):
    """Um QLabel vazio ainda reserva a altura da linha e desloca o bloco
    centralizado para cima."""
    vazio = EmptyState("Fila vazia")

    assert vazio.subtitulo_visivel() is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_empty_state.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

Criar `src/trackclassifier/ui/widgets/empty_state.py`:

```python
"""Bloco centralizado para tela sem conteudo.

Existe porque as tres abas abrem vazias -- e uma frase no canto superior
esquerdo dentro de um vazio de altura inteira e o que o app mostrava antes.
A acao opcional e o ponto: "Fila vazia. Use Escanear" manda o usuario
procurar um botao; um botao Escanear aqui dispara o scan.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_5


class EmptyState(QWidget):
    action_clicked = Signal()

    def __init__(
        self,
        titulo: str,
        subtitulo: str = "",
        acao: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._titulo = QLabel(titulo)
        self._titulo.setObjectName("TrackTitle")
        self._titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitulo = QLabel(subtitulo)
        self._subtitulo.setObjectName("Hint")
        self._subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitulo.setVisible(bool(subtitulo))

        self._botao: QPushButton | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_5)
        layout.addStretch(1)
        layout.addWidget(self._titulo)
        layout.addWidget(self._subtitulo)

        if acao:
            self._botao = QPushButton(acao)
            self._botao.setProperty("variant", "primary")
            self._botao.clicked.connect(self.action_clicked)
            # Num QVBoxLayout o botao esticaria a largura inteira e leria
            # como faixa de fundo, nao como botao.
            layout.addWidget(self._botao, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

    def set_texto(self, titulo: str, subtitulo: str = "") -> None:
        self._titulo.setText(titulo)
        self._subtitulo.setText(subtitulo)
        self._subtitulo.setVisible(bool(subtitulo))

    def tem_botao(self) -> bool:
        return self._botao is not None

    def subtitulo_visivel(self) -> bool:
        return not self._subtitulo.isHidden()

    def acionar(self) -> None:
        """Aciona o botao. Existe para o teste percorrer o mesmo caminho do
        clique real."""
        if self._botao is not None:
            self._botao.click()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_empty_state.py -v`
Expected: PASS.

- [ ] **Step 5: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/empty_state.py tests/test_empty_state.py
git commit -m "feat(trackclassifier): EmptyState centralizado com acao opcional"
```

---

### Task 9: `PlayerBar`

**Files:**
- Create: `src/trackclassifier/ui/widgets/player_bar.py`
- Test: `tests/test_player_bar.py`

**Interfaces:**
- Consumes: `BasePlayer` de `ui/widgets/player.py` — sinais `position_changed(int)`, `duration_changed(int)`, `playing_changed(bool)`; métodos `toggle()`, `set_volume(float)`.
- Produces: `PlayerBar(QWidget)` com `__init__(player, parent=None)`, e para teste: `texto_do_tempo() -> str`, `texto_do_botao() -> str`, `acionar_play() -> None`.

**Contexto:** a spec de 2026-08-05 listou `widgets/transport_bar.py` e `widgets/now_playing.py`; nenhum foi construído. Os tokens `SIZE_CONTROL_PRIMARY` e a regra `QWidget#PlayerBar` no QSS estão sem consumidor desde então.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_player_bar.py`:

```python
"""A barra de transporte. Usa SimulatedPlayer -- sem dispositivo de audio."""

from trackclassifier.ui.widgets.player import SimulatedPlayer
from trackclassifier.ui.widgets.player_bar import PlayerBar


def test_tempo_comeca_zerado(qapp):
    barra = PlayerBar(SimulatedPlayer())

    assert barra.texto_do_tempo() == "0:00 / 0:00"


def test_tempo_acompanha_os_sinais_do_player(qapp):
    player = SimulatedPlayer()
    barra = PlayerBar(player)

    player.duration_changed.emit(185_000)
    player.position_changed.emit(65_000)

    assert barra.texto_do_tempo() == "1:05 / 3:05"


def test_botao_reflete_o_estado_do_player(qapp):
    """O Space em MainWindow chama player.toggle() sem passar por aqui --
    se o botao guardasse estado proprio, dessincronizaria na primeira vez
    que o usuario usasse o teclado."""
    player = SimulatedPlayer()
    barra = PlayerBar(player)
    inicial = barra.texto_do_botao()

    player.playing_changed.emit(True)

    assert barra.texto_do_botao() != inicial

    player.playing_changed.emit(False)

    assert barra.texto_do_botao() == inicial


def test_clique_no_play_chama_toggle(qapp):
    class _Espiao(SimulatedPlayer):
        def __init__(self):
            super().__init__()
            self.chamadas = 0

        def toggle(self):
            self.chamadas += 1

    player = _Espiao()
    barra = PlayerBar(player)

    barra.acionar_play()

    assert player.chamadas == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_player_bar.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

Criar `src/trackclassifier/ui/widgets/player_bar.py`:

```python
"""Barra de transporte da aba Revisao.

Fica na Revisao e nao no rodape da janela de proposito: so ela tem track
corrente. O Space e desabilitado fora dela (ver window._atualiza_atalhos_de_revisao)
e a Biblioteca nao toca nada -- um rodape global prometeria playback la.

Nao ha logica de reproducao aqui. Tudo e ligacao de sinal ao BasePlayer que
a aba ja recebe; em especial o rotulo do botao vem de playing_changed e nao
de um flag proprio, senao o atalho de teclado (que chama player.toggle()
sem passar por este widget) dessincronizaria o botao na primeira vez.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from ..tokens import SIZE_CONTROL_PRIMARY, SPACE_4, SPACE_5
from ..viewmodel import format_duration

_PLAY = "▶"
_PAUSE = "❚❚"
_VOLUME_INICIAL = 80


class PlayerBar(QWidget):
    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # objectName e o que liga a regra QWidget#PlayerBar do app.qss --
        # ela existia desde a fase 1 sem nenhum widget para vestir.
        self.setObjectName("PlayerBar")
        self._player = player
        self._posicao_ms = 0
        self._duracao_ms = 0

        self._botao = QPushButton(_PLAY)
        self._botao.setFixedSize(SIZE_CONTROL_PRIMARY, SIZE_CONTROL_PRIMARY)
        self._botao.clicked.connect(self._player.toggle)

        self._tempo = QLabel("")
        self._tempo.setObjectName("Numeric")

        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(_VOLUME_INICIAL)
        self._volume.setFixedWidth(100)
        self._volume.valueChanged.connect(self._muda_volume)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_5, SPACE_4)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._botao)
        layout.addWidget(self._tempo)
        layout.addStretch(1)
        layout.addWidget(QLabel("Volume"))
        layout.addWidget(self._volume)

        self._player.position_changed.connect(self._muda_posicao)
        self._player.duration_changed.connect(self._muda_duracao)
        self._player.playing_changed.connect(self._muda_estado)

        self._muda_volume(_VOLUME_INICIAL)
        self._atualiza_tempo()

    # ---- reacoes aos sinais do player ----------------------------------

    def _muda_posicao(self, ms: int) -> None:
        self._posicao_ms = ms
        self._atualiza_tempo()

    def _muda_duracao(self, ms: int) -> None:
        self._duracao_ms = ms
        self._atualiza_tempo()

    def _muda_estado(self, tocando: bool) -> None:
        self._botao.setText(_PAUSE if tocando else _PLAY)

    def _muda_volume(self, valor: int) -> None:
        self._player.set_volume(valor / 100)

    def _atualiza_tempo(self) -> None:
        self._tempo.setText(
            f"{format_duration(self._posicao_ms / 1000)} / "
            f"{format_duration(self._duracao_ms / 1000)}"
        )

    # ---- superficie de teste -------------------------------------------

    def texto_do_tempo(self) -> str:
        return self._tempo.text()

    def texto_do_botao(self) -> str:
        return self._botao.text()

    def acionar_play(self) -> None:
        self._botao.click()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_player_bar.py -v`
Expected: PASS.

Se `format_duration` arredondar diferente do esperado em `1:05 / 3:05`, confira a implementação em `ui/viewmodel.py` e ajuste os milissegundos do teste — não mude `format_duration`, que já tem teste próprio.

- [ ] **Step 5: Verificar que nenhum hex vazou**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS.

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/player_bar.py tests/test_player_bar.py
git commit -m "feat(trackclassifier): PlayerBar liga o transporte que so existia no teclado"
```

---

### Task 10: Densidade e empty states nas três abas

**Files:**
- Modify: `src/trackclassifier/ui/review_tab.py`
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `src/trackclassifier/ui/model_tab.py`
- Modify: `src/trackclassifier/ui/window.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `EmptyState` (Task 8), `PlayerBar` (Task 9).
- Produces: `ReviewTab.scan_requested = Signal()`, `LibraryTab.scan_requested = Signal()` — emitidos pelo botão do empty state.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_window.py`:

```python
def test_revisao_vazia_esconde_o_bloco_da_track(qapp, tmp_path):
    """O stretch=1 da onda sobre um bloco vazio e o que produzia o vazio de
    altura inteira nas capturas."""
    config = _config(tmp_path)
    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(_servico(config)))

    assert aba.bloco_visivel() is False


def test_revisao_com_track_mostra_o_bloco(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico.analyze_all()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba.bloco_visivel() is True


def test_empty_state_da_revisao_pede_scan(qapp, tmp_path):
    config = _config(tmp_path)
    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(_servico(config)))

    pedidos = []
    aba.scan_requested.connect(lambda: pedidos.append(True))
    aba.acionar_empty_state()

    assert pedidos == [True]


def test_capa_ausente_nao_reserva_espaco(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico.analyze_all()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    # ExtratorFalso nao produz capa, entao o QLabel de 44x44 ficaria
    # reservando o buraco.
    assert aba.capa_visivel() is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_window.py -k "vazia or empty_state or capa_ausente" -v`
Expected: FAIL com `AttributeError: 'ReviewTab' object has no attribute 'bloco_visivel'`.

- [ ] **Step 3: Reestruturar `review_tab.py`**

Em `src/trackclassifier/ui/review_tab.py`:

1. Imports novos:

```python
from .tokens import SIZE_ART_PLAYER, SPACE_1, SPACE_5, SPACE_6
from .widgets.empty_state import EmptyState
from .widgets.player_bar import PlayerBar
```

`SPACE_4` não entra aqui — o `review_tab.py` só usa 1, 5 e 6. Importar sem usar
falha no ruff (`F401`), que é gate do CI.

2. Acrescentar o sinal na classe, junto dos outros:

```python
    scan_requested = Signal()
```

3. Trocar o `_legenda` e o `_aviso` de `SectionLabel` para `Hint`:

```python
        self._aviso.setObjectName("Hint")
        ...
        self._legenda.setObjectName("Hint")
        ...
        self._proximas.setObjectName("Hint")
```

O `_subtitulo` também: `self._subtitulo.setObjectName("Hint")`.

4. Substituir o bloco de montagem de layout (hoje das linhas 93 a 114) por:

```python
        # Capa a esquerda, titulo e subtitulo empilhados, numeros a direita.
        textos = QVBoxLayout()
        textos.setSpacing(SPACE_1)
        textos.addWidget(self._titulo)
        textos.addWidget(self._subtitulo)

        topo = QHBoxLayout()
        topo.setSpacing(SPACE_5)
        topo.addWidget(self._capa)
        topo.addLayout(textos, 1)
        topo.addWidget(self._key_chip)
        topo.addWidget(self._numeros)

        self._player_bar = PlayerBar(self._player)

        # Tudo que so faz sentido com uma track vira um widget so: com a fila
        # vazia ele some inteiro e o EmptyState ocupa o lugar. Antes o
        # stretch=1 da onda esticava um bloco vazio pela altura da janela.
        self._bloco = QWidget()
        conteudo = QVBoxLayout(self._bloco)
        conteudo.setContentsMargins(0, 0, 0, 0)
        conteudo.setSpacing(SPACE_5)
        conteudo.addLayout(topo)
        conteudo.addWidget(self._waveform, 1)
        conteudo.addWidget(self._player_bar)
        conteudo.addWidget(self._palpite)
        conteudo.addWidget(self._aviso)
        conteudo.addWidget(self._proximas)

        rodape = QHBoxLayout()
        rodape.setSpacing(SPACE_5)
        rodape.addWidget(self._legenda)
        rodape.addStretch(1)
        # Sem o stretch acima o botao ocuparia a largura da janela e leria
        # como faixa de fundo.
        rodape.addWidget(botao_bloco)

        self._vazio = EmptyState(
            VAZIO_TITULO, VAZIO_SUBTITULO, "Escanear"
        )
        self._vazio.action_clicked.connect(self.scan_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._bloco, 1)
        self._rodape = rodape
        layout.addLayout(rodape)
```

5. Substituir a constante `VAZIO` no topo do módulo por duas, mantendo `VAZIO` como o texto que `empty_text()` devolve (para não quebrar quem já o consome):

```python
VAZIO_TITULO = "Fila vazia"
VAZIO_SUBTITULO = "Nenhuma track nova na inbox."
VAZIO = f"{VAZIO_TITULO}. {VAZIO_SUBTITULO}"
```

6. Em `_atualiza_exibicao`, substituir o bloco `if atual is None:` por:

```python
        self._vazio.setVisible(atual is None)
        self._bloco.setVisible(atual is not None)

        if atual is None:
            self._titulo.setText(VAZIO)
            self._subtitulo.setText("")
            self._capa.setVisible(False)
            self._numeros.setText("")
            self._palpite.setText("")
            self._waveform.set_row(None)
            self._carregada = None
            self._key_chip.set_key(None)
            return
```

7. Em `_mostra_capa`, trocar cada `self._capa.clear()` por:

```python
            self._capa.clear()
            # setVisible(False) e nao so clear(): o QLabel tem tamanho fixo
            # de 44x44, entao limpar o pixmap deixa o buraco reservado.
            self._capa.setVisible(False)
```

e, no caminho de sucesso, depois de `self._capa.setPixmap(pixmap)`:

```python
        self._capa.setVisible(True)
```

8. Acrescentar a superfície de teste ao fim da classe:

```python
    def bloco_visivel(self) -> bool:
        return not self._bloco.isHidden()

    def capa_visivel(self) -> bool:
        return not self._capa.isHidden()

    def acionar_empty_state(self) -> None:
        self._vazio.acionar()
```

- [ ] **Step 4: Rodar os testes da Revisão**

Run: `uv run pytest tests/test_window.py -v`
Expected: PASS.

- [ ] **Step 5: Densidade e empty state na Biblioteca**

Em `src/trackclassifier/ui/library_tab.py`:

1. Acrescentar `scan_requested = Signal()` à classe e o import de `EmptyState` e dos tokens `SPACE_4, SPACE_5, SPACE_6`.
2. Substituir a montagem do layout (hoje linhas 65–72) por:

```python
        barra = QHBoxLayout()
        barra.setSpacing(SPACE_4)
        barra.addWidget(self._busca, 1)
        barra.addWidget(self._filtro)
        barra.addWidget(self._notacao)

        self._vazio = EmptyState(
            "Nenhuma track analisada",
            "Escaneie a inbox para popular a biblioteca.",
            "Escanear",
        )
        self._vazio.action_clicked.connect(self.scan_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addLayout(barra)
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._table, 1)
```

3. Ao fim de `_reaplica_filtros`, depois da chamada a `self._model.sort(...)`:

```python
        # O empty state so aparece quando a biblioteca inteira esta vazia --
        # busca sem resultado e outro estado, e trocar a tabela por um botao
        # "Escanear" ali esconderia o campo de busca que o usuario acabou de
        # digitar.
        vazia = not self._todas
        self._vazio.setVisible(vazia)
        self._table.setVisible(not vazia)
```

- [ ] **Step 6: Densidade e empty state no Modelo**

Em `src/trackclassifier/ui/model_tab.py`, substituir a montagem do layout (linhas 33–38) por:

```python
        acao = QHBoxLayout()
        acao.addWidget(botao)
        # Sem o stretch o botao primario ocupa a largura da janela e vira
        # uma faixa ciana em vez de um botao.
        acao.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._metricas)
        layout.addWidget(self._confusao)
        layout.addLayout(acao)
        layout.addWidget(rotulo_falhas)
        layout.addWidget(self._falhas, 1)
```

com os imports `QHBoxLayout` e `from .tokens import SPACE_5, SPACE_6`.

- [ ] **Step 7: Encaixar o `Escanear` e ligar os empty states**

Em `src/trackclassifier/ui/window.py`:

1. Depois de `self._botao_scan = QPushButton(TEXTO_ESCANEAR)`:

```python
        # Como cornerWidget o botao herda o min-height de 28px do QSS mais
        # padding e borda -- cerca de 42px contra os ~24px da tab bar, que e
        # o que estica a faixa e faz o botao sobrar para fora dela.
        self._botao_scan.setProperty("variant", "ghost")
        self._botao_scan.setMaximumHeight(self.tabs.tabBar().sizeHint().height())
```

2. Em `_conecta`:

```python
        self.review_tab.scan_requested.connect(self._clique_no_botao_scan)
        self.library_tab.scan_requested.connect(self._clique_no_botao_scan)
```

- [ ] **Step 8: Suíte inteira**

Run: `uv run pytest`
Expected: PASS.

- [ ] **Step 9: Lint**

Run: `uv run ruff check .`
Expected: sem erro.

- [ ] **Step 10: Commit**

```bash
git add src/trackclassifier/ui/review_tab.py src/trackclassifier/ui/library_tab.py \
        src/trackclassifier/ui/model_tab.py src/trackclassifier/ui/window.py \
        tests/test_window.py
git commit -m "fix(trackclassifier): margens por token, empty states e botoes que param de esticar"
```

---

### Task 11: Documentação e verificação do bundle

**Files:**
- Modify: `CLAUDE.md`
- Modify: `config.example.toml` (só o comentário do topo)

- [ ] **Step 1: Atualizar `CLAUDE.md`**

Na seção "Executavel do macOS", substituir o terceiro marcador (que começa com "**Config nao pode ser relativo ao cwd.**") por:

```markdown
- **Config nao pode ser relativo ao cwd.** Empacotado (`sys.frozen`), o
  default vira `~/.trackclassifier/config.toml`. Quando ele nao existe -- ou
  existe apontando para uma pasta que sumiu -- a janela abre o
  `FirstRunDialog` (`ui/first_run.py`), que grava o arquivo pela primeira
  vez. Nao ha mais copia do `config.example.toml` para o home: ela
  transformava "nao tem config" em "config apontando para
  /Users/SEU_USUARIO", escondendo do app a unica condicao que dispara o
  dialogo. `dj scan` e `dj train` seguem headless, com `ConfigError` no
  stderr e sem importar Qt.
```

- [ ] **Step 2: Acrescentar a nota sobre a aba na seção de Arquitetura**

Ao fim da seção que descreve as camadas de `ui/`, acrescentar:

```markdown
`config.py` cresceu para servir a tela: alem de `load_config`, ele expoe
`read_raw` (parse sem validar, para preencher o formulario quando o config
esta quebrado), `SettingsDraft` (o texto cru dos campos), `validate_settings`
(puro, roda a cada tecla) e `apply_draft` (cria as pastas, roda uma vez ao
salvar). A separacao entre validar e aplicar e o que permite validar a cada
tecla sem criar uma pasta a cada tecla -- e o que mantem toda a regra
testavel sem `QApplication`.
```

- [ ] **Step 3: Atualizar o comentário do `config.example.toml`**

Substituir a primeira linha por:

```toml
# Referencia dos campos. A janela grava este arquivo sozinha no primeiro uso
# (ui/first_run.py); copiar a mao so e necessario para `dj scan`/`dj train`
# sem nunca ter aberto a janela.
```

- [ ] **Step 4: Suíte inteira e lint**

Run: `uv run pytest && uv run ruff check .`
Expected: PASS, sem erro de lint.

- [ ] **Step 5: Verificar o bundle com PATH mínimo**

Esta é a verificação que o `CLAUDE.md` exige depois de qualquer mudança em `cli.py` — e esta fase mexeu nele.

```bash
uv sync --extra dev --extra audio --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

Depois, com o config padrão movido para fora do caminho, para exercitar o primeiro uso de verdade:

```bash
mv ~/.trackclassifier/config.toml ~/.trackclassifier/config.toml.bak 2>/dev/null; env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin ./dist/TrackClassifier.app/Contents/MacOS/TrackClassifier
```

Expected: o `FirstRunDialog` abre em branco. Preencher, confirmar, e a janela principal aparece. Restaurar depois com `mv ~/.trackclassifier/config.toml.bak ~/.trackclassifier/config.toml`.

Este passo é manual e não tem assert automatizado — é o único que reproduz o PATH mínimo que o Finder dá.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md config.example.toml
git commit -m "docs(trackclassifier): primeiro uso substitui a copia do config de exemplo"
```

---

## Self-Review

**Cobertura da spec:**

| Requisito da spec | Task |
|---|---|
| `save_config` com `tomli-w` | 1 |
| `read_raw`, `SettingsDraft` | 2 |
| `validate_settings`, `apply_draft`, `SettingsError`, pastas distintas, criação na raiz | 3 |
| `#Hint` / `#SectionLabel` deixa de ser genérico | 4 |
| `SettingsForm`, dois modos de destino, erro por campo | 5 |
| `FirstRunDialog`, gatilho por ausência de config, ordem em `__main__`, remoção de `_prepara_config_padrao` e `_mostra_erro_grafico` | 6 |
| 4ª aba, `reload_config`, `Salvar` bloqueado durante scan | 7 |
| Empty states | 8, 10 |
| `PlayerBar` | 9 |
| Margens por token, botões sem esticar, `Escanear` encaixado, capa escondida | 10 |
| `CLAUDE.md` atualizado, verificação do bundle | 11 |

**Consistência de tipos:** `SettingsDraft` tem os mesmos nove campos nas Tasks 2, 3, 5, 6 e 7. `SettingsError(field, message)` idem. `validate_settings` sempre recebe `SettingsDraft` e devolve `list[SettingsError]`. `apply_draft` sempre devolve `Config`. `EmptyState.acionar()` e `SettingsForm.escolher_para_o_teste()` são as superfícies de teste, usadas com o mesmo nome em todos os testes que as citam.

**Risco conhecido, registrado e não escondido:** a Task 6 deixa `ui/__main__.py` referenciando `MainWindow(..., config_path=...)`, parâmetro que só nasce na Task 7. O Step 5 da Task 6 diz isso explicitamente e dá as duas saídas. Quem executar em ordem não é surpreendido; quem executar fora de ordem lê o aviso antes de rodar.
