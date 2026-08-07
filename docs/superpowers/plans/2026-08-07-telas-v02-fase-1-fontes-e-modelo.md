# Telas v0.2 — Fase 0 e 1: fontes empacotadas e aba Modelo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empacotar Space Grotesk e JetBrains Mono no repo (sem elas nenhuma tela
se parece com o mockup) e reescrever a aba Modelo, que hoje e o unico lugar do
app ainda em `QLabel` com alinhamento por `f"{v:>8}"`.

**Architecture:** A aba Modelo vira um layout fino que traduz `ModelState` e
delega o desenho a tres widgets proprios em `ui/widgets/`. Nenhum deles conhece
`TrackService` — todos recebem dados puros do viewmodel, como ja acontece com os
delegates. `ModelState` ganha sete campos; a regra de "pode treinar?" continua
morando em `model.py` e o viewmodel a consulta por uma funcao compartilhada, em
vez de reimplementar.

**Tech Stack:** PySide6, pytest, ruff. Nenhuma dependencia nova em runtime.

Depende de: `docs/superpowers/specs/2026-08-07-telas-v02-instrumento-design.md`
(Fases 0 e 1).

## Global Constraints

- **Portugues sem acentos** em nomes locais, funcoes internas, comentarios,
  docstrings, mensagens de erro e nomes de teste. API publica (dataclasses,
  metodos, campos) em ingles.
- **Nenhum hex fora de `design/design-tokens.json`.** `tests/test_tokens.py::
  test_nenhum_hex_fora_do_json` varre `src/trackclassifier/ui/**/*.py` atras de
  `#RRGGBB`. Cor derivada (tinta com alfa) sai de um token por codigo, nunca de
  um literal novo.
- **`ui/viewmodel.py` nao importa Qt.** Ha teste gramatical que falha se
  importar.
- **Widget nao chama `TrackService`.** So a thread do `ServiceWorker` fala com
  o servico.
- **Sinal publico nao muda:** `ModelTab.train_requested()`.
- **Rotulo de botao** em `font.family.mono`, caixa alta, `font.tracking.widest`,
  via `ui/typography.py::estiliza_label`.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.
- Commits: conventional commits com escopo — `feat(trackclassifier):`.
- Rodar tudo com `uv run`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/ui/fonts/*.ttf` | Os quatro arquivos de fonte (OFL) + os dois `OFL.txt`. |
| `src/trackclassifier/ui/fonts.py` | **Criar.** `registra_fontes()` — carrega os TTF no `QFontDatabase` e devolve as familias registradas. |
| `src/trackclassifier/ui/__main__.py` | Chama `registra_fontes()` depois do `QApplication` e antes do `setStyleSheet`. |
| `packaging/trackclassifier.spec` | Os TTF entram em `datas`. |
| `design/mockups/` | Os seis mockups standalone + `LEIA-ME.md`, referencia visual das fases. |
| `src/trackclassifier/ui/colors.py` | **Criar.** `tinta(cor, alpha)` — deriva rgba a partir de um token, para nao nascer literal de cor novo. |
| `src/trackclassifier/model.py` | `classes_faltando(labels)` extraida de `fit()` e reusada pelo viewmodel. |
| `src/trackclassifier/service.py` | `FailedItem.category`, `class_counts()`, `decisions_since_train`. |
| `src/trackclassifier/ui/viewmodel.py` | `ModelState` ganha sete campos; `model_state()` os preenche. |
| `src/trackclassifier/ui/widgets/confusion_matrix.py` | **Criar.** Matriz colorida por severidade ordinal + legenda. |
| `src/trackclassifier/ui/widgets/class_balance.py` | **Criar.** Tres barras + a recomendacao derivada. |
| `src/trackclassifier/ui/widgets/failure_list.py` | **Criar.** Falhas agrupadas por categoria, com badge de contagem. |
| `src/trackclassifier/ui/model_tab.py` | Layout dos tres cards, barra de acao, detalhe tecnico. |

---

### Task 1: as fontes entram no repo

**Files:**
- Create: `src/trackclassifier/ui/fonts/SpaceGrotesk-Regular.ttf`
- Create: `src/trackclassifier/ui/fonts/SpaceGrotesk-Medium.ttf`
- Create: `src/trackclassifier/ui/fonts/JetBrainsMono-Regular.ttf`
- Create: `src/trackclassifier/ui/fonts/JetBrainsMono-Medium.ttf`
- Create: `src/trackclassifier/ui/fonts/OFL-SpaceGrotesk.txt`
- Create: `src/trackclassifier/ui/fonts/OFL-JetBrainsMono.txt`
- Create: `src/trackclassifier/ui/fonts.py`
- Modify: `src/trackclassifier/ui/__main__.py`
- Modify: `packaging/trackclassifier.spec`
- Test: `tests/test_fonts.py`

**Interfaces:**
- Produces: `trackclassifier.ui.fonts.registra_fontes() -> list[str]` — devolve
  as familias efetivamente registradas, em ordem de carregamento. Lista vazia
  significa que nenhum TTF foi aceito pelo Qt.
- Produces: `trackclassifier.ui.fonts.DIRETORIO: Path` — a pasta dos TTF, usada
  pelo `.spec` do PyInstaller e pelo teste.

> **Antes de comecar:** os quatro TTF precisam ser baixados. Espere a
> autorizacao explicita do usuario antes de baixar qualquer arquivo, informando
> nome, origem e tamanho. Origem: repositorios oficiais no GitHub —
> `floriankarsten/space-grotesk` (OFL) e `JetBrains/JetBrainsMono` (OFL). Nao
> substituir por fonte de terceiro nem por CDN.

- [ ] **Step 1: Escrever o teste que falha**

```python
"""As fontes do mockup viajam com o app -- nem a maquina nem o CI as tem."""

from pathlib import Path

import pytest

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

    # O app tem que subir sem as fontes -- feio, mas funcional. Uma
    # instalacao quebrada nao pode impedir o usuario de classificar.
    assert fonts.registra_fontes() == []
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `uv run pytest tests/test_fonts.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.fonts'`

- [ ] **Step 3: Baixar as fontes** (so depois da autorizacao do usuario)

Os quatro TTF vao para `src/trackclassifier/ui/fonts/` com exatamente os nomes
do teste. Os dois `OFL.txt` de cada projeto viram `OFL-SpaceGrotesk.txt` e
`OFL-JetBrainsMono.txt` na mesma pasta.

- [ ] **Step 4: Implementar `ui/fonts.py`**

```python
"""As fontes do mockup viajam com o app.

Space Grotesk e JetBrains Mono estao em primeiro na pilha de
`font.family.*` dos tokens, com fallback para Inter e SF Mono. O fallback
funciona -- o app nao quebra sem elas -- mas a tela nao se parece com o
mockup, e o CI nunca teria as fontes instaladas. Ambas sao OFL, entao
redistribuir dentro do repo e permitido desde que a licenca va junto.

QFontDatabase.addApplicationFont exige um QGuiApplication vivo: chamar
antes do QApplication devolve -1 para todos os arquivos, em silencio.
"""

from pathlib import Path

from PySide6.QtGui import QFontDatabase

DIRETORIO = Path(__file__).parent / "fonts"

#: Cache do resultado. Registrar o mesmo arquivo duas vezes devolve um id
#: novo e duplica a familia na lista do Qt; os testes sobem a UI varias
#: vezes na mesma QApplication de sessao e cairiam nisso.
_registradas: list[str] | None = None


def registra_fontes() -> list[str]:
    """Carrega os TTF e devolve as familias registradas, sem repetir.

    Lista vazia quando a pasta sumiu ou nenhum arquivo foi aceito: o app
    sobe assim mesmo, no fallback. Uma instalacao quebrada nao pode
    impedir o usuario de classificar.
    """
    global _registradas
    if _registradas is not None:
        return _registradas

    familias: list[str] = []
    for arquivo in sorted(DIRETORIO.glob("*.ttf")):
        identificador = QFontDatabase.addApplicationFont(str(arquivo))
        if identificador == -1:
            # Arquivo corrompido ou formato recusado. Nao e motivo para
            # derrubar o app -- as outras tres podem ter entrado.
            continue
        for familia in QFontDatabase.applicationFontFamilies(identificador):
            if familia not in familias:
                familias.append(familia)

    _registradas = familias
    return familias
```

- [ ] **Step 5: Rodar o teste e ver passar**

Run: `uv run pytest tests/test_fonts.py -v`
Expected: PASS, 5 testes.

- [ ] **Step 6: Ligar no bootstrap da UI**

Em `src/trackclassifier/ui/__main__.py`, importar `from .fonts import
registra_fontes` e chamar logo depois de `app = QApplication(sys.argv)`, antes
do `setStyleSheet`:

```python
    app = QApplication(sys.argv)
    # Antes do QSS: a folha nomeia "Space Grotesk" e "JetBrains Mono" na
    # frente da pilha de fallback, e o Qt resolve a familia no momento em
    # que aplica o estilo.
    registra_fontes()
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))
```

- [ ] **Step 7: Ligar no PyInstaller**

Em `packaging/trackclassifier.spec`, dentro da lista `datas` (linha 25):

```python
datas = [
    (str(raiz / "src" / "trackclassifier" / "ui" / "app.qss"), "trackclassifier/ui"),
    (str(raiz / "config.example.toml"), "."),
]
# As fontes nao sao descobertas pela analise de imports (sao dado, nao
# modulo) e sem elas o .app cai no fallback do sistema -- o mesmo motivo
# do app.qss estar aqui em cima.
datas += [
    (str(caminho), "trackclassifier/ui/fonts")
    for caminho in (raiz / "src" / "trackclassifier" / "ui" / "fonts").iterdir()
]
```

- [ ] **Step 8: Verificar**

Run: `uv run pytest tests/test_fonts.py tests/test_main.py -v && uv run ruff check .`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/trackclassifier/ui/fonts src/trackclassifier/ui/fonts.py \
        src/trackclassifier/ui/__main__.py packaging/trackclassifier.spec \
        tests/test_fonts.py
git commit -m "feat(trackclassifier): Space Grotesk e JetBrains Mono viajam com o app"
```

---

### Task 2: os mockups viram referencia versionada

**Files:**
- Create: `design/mockups/*.html` (seis arquivos) e `design/mockups/LEIA-ME.md`

**Interfaces:**
- Produces: nada de codigo. As tres specs de tela ja referenciam
  `design/mockups/...` e hoje apontam para arquivos que nao existem.

- [ ] **Step 1: Copiar**

```bash
mkdir -p design/mockups
cp /Users/lucasmatricarde/Downloads/pack/mockups/*.html design/mockups/
cp /Users/lucasmatricarde/Downloads/pack/LEIA-ME.md design/mockups/
```

`fonte/` fica de fora: precisa do `support.js` ao lado e de um runtime proprio.
Os arquivos de `mockups/` sao standalone — abrem no navegador sem servidor e sem
rede, que e o que a referencia precisa ser daqui a seis meses.

- [ ] **Step 2: Verificar que abrem**

Run: `open design/mockups/04-modelo.html`
Expected: a janela do mockup renderiza (fundo `#0B0E11`, tres cards).

- [ ] **Step 3: Commit**

```bash
git add design/mockups
git commit -m "docs(trackclassifier): mockups da v0.2 entram no repo como referencia"
```

---

### Task 3: `classes_faltando` sai de dentro de `fit()`

**Files:**
- Modify: `src/trackclassifier/model.py:84-92`
- Test: `tests/test_model_core.py`

**Interfaces:**
- Produces: `trackclassifier.model.classes_faltando(labels: Iterable[Label]) ->
  list[str]` — os `value` das classes de `LABEL_ORDER` ausentes, na ordem
  ordinal. Lista vazia significa que da para treinar.

A regra "faltam classes" vive em `fit()`. A aba Modelo precisa dela **antes** do
clique, para desabilitar o botao com motivo. Duplicar a regra na UI e o comeco
de duas regras divergindo; extrair e reusar nao.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_classes_faltando_devolve_na_ordem_ordinal():
    from trackclassifier.labels import Label
    from trackclassifier.model import classes_faltando

    assert classes_faltando([Label.NEUTRAL]) == ["-1", "+1"]


def test_classes_faltando_vazio_quando_as_tres_existem():
    from trackclassifier.labels import Label
    from trackclassifier.model import classes_faltando

    assert classes_faltando([Label.UP, Label.DOWN, Label.NEUTRAL]) == []


def test_classes_faltando_sem_exemplo_nenhum_devolve_as_tres():
    from trackclassifier.model import classes_faltando

    assert classes_faltando([]) == ["-1", "neutra", "+1"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_model_core.py -k classes_faltando -v`
Expected: FAIL com `ImportError: cannot import name 'classes_faltando'`

- [ ] **Step 3: Implementar**

No topo de `model.py`, depois dos imports:

```python
def classes_faltando(labels: Iterable[Label]) -> list[str]:
    """Classes de LABEL_ORDER ausentes, na ordem ordinal.

    Vazio = da para treinar. Extraida de fit() porque a aba Modelo precisa
    da mesma resposta ANTES do clique, para desabilitar o botao com o
    motivo visivel. Duas copias da regra e uma copia a mais do que cabe.
    """
    presentes = set(labels)
    return [rotulo.value for rotulo in LABEL_ORDER if rotulo not in presentes]
```

`fit()` passa a usar:

```python
    def fit(self, X: np.ndarray, labels: list[Label], min_examples: int = 15) -> None:
        faltando = classes_faltando(labels)
        if faltando:
            raise NotEnoughClassesError(
                "Nao da para treinar sem exemplos de todas as classes. "
                f"Faltam rotulos: {', '.join(faltando)}"
            )
```

Adicionar `from collections.abc import Iterable` aos imports.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_model_core.py tests/test_model_calibration.py -v`
Expected: PASS. Os testes existentes de `NotEnoughClassesError` continuam
verdes — a mensagem nao mudou.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/model.py tests/test_model_core.py
git commit -m "refactor(trackclassifier): classes_faltando vira funcao reusavel"
```

---

### Task 4: `FailedItem` ganha categoria

**Files:**
- Modify: `src/trackclassifier/service.py:144-147` (a dataclass) e os dois
  lugares que a constroem (`:228` e `:271`)
- Test: `tests/test_service.py`

**Interfaces:**
- Produces: `FailedItem(filename: str, reason: str, category: str)`. `category`
  e o tipo do erro, estavel entre arquivos; `reason` continua sendo a mensagem
  completa, que varia.

Hoje `reason` e a string da excecao: `"Falha ao decodificar promo_04.m4a:
<stderr do ffmpeg inteiro>"`. Agrupar por `reason` nao agrupa nada — quarenta
arquivos com o mesmo problema viram quarenta grupos de um. A alternativa
(fatiar por prefixo ate os dois-pontos) e adivinhacao sobre a forma da string.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_failed_item_carrega_categoria_estavel_entre_arquivos():
    from trackclassifier.service import FailedItem

    a = FailedItem(filename="a.m4a", reason="Falha ao decodificar a.m4a: x", category="decode")
    b = FailedItem(filename="b.m4a", reason="Falha ao decodificar b.m4a: y", category="decode")

    # A razao difere (traz o nome do arquivo e o stderr), a categoria nao.
    # E isso que permite a aba Modelo mostrar "2 arquivos" e nao "2 motivos".
    assert a.reason != b.reason
    assert a.category == b.category


def test_categoria_default_mantem_construcao_de_duas_posicoes():
    from trackclassifier.service import FailedItem

    # Chamadas antigas (filename, reason) continuam validas -- a categoria
    # cai em "outros", que e verdade e nao mente sobre o agrupamento.
    assert FailedItem(filename="a.m4a", reason="qualquer coisa").category == "outros"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_service.py -k failed_item -v`
Expected: FAIL com `TypeError: FailedItem.__init__() got an unexpected keyword argument 'category'`

- [ ] **Step 3: Implementar**

```python
@dataclass(frozen=True)
class FailedItem:
    filename: str
    reason: str
    #: Tipo do erro, estavel entre arquivos. `reason` traz o nome do
    #: arquivo e o stderr do ffmpeg, entao varia sempre e nao serve para
    #: agrupar -- a aba Modelo agrupa por isto. Default "outros" para nao
    #: obrigar todo caminho de erro a classificar o que nao sabe.
    category: str = "outros"
```

Os dois construtores existentes passam a nomear a categoria:

```python
                FailedItem(
                    filename=self.cache.path.name,
                    reason=self.cache.load_error,
                    category="cache ilegivel",
                )
```

```python
                self._failures.append(
                    FailedItem(filename=ref.path.name, reason=erro, category=_categoria(erro))
                )
```

E a funcao que traduz a mensagem em categoria, junto das outras helpers de
modulo em `service.py`:

```python
#: Prefixo da mensagem -> categoria mostrada na aba Modelo. A ordem
#: importa: a primeira que casar ganha.
_CATEGORIAS = (
    ("ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("ffprobe nao encontrado", "ffmpeg nao encontrado"),
    ("Falha ao decodificar", "falha ao decodificar"),
    ("Arquivo vazio", "arquivo vazio ou curto demais"),
)


def _categoria(erro: str) -> str:
    """Categoria a partir do inicio da mensagem, nao da mensagem inteira.

    A mensagem completa carrega o nome do arquivo e o stderr do ffmpeg --
    unica por arquivo. Casar so o comeco e o que faz quarenta arquivos sem
    ffmpeg virarem um problema em vez de quarenta.
    """
    for prefixo, categoria in _CATEGORIAS:
        if erro.startswith(prefixo):
            return categoria
    return "outros"
```

- [ ] **Step 4: Conferir os prefixos contra as mensagens reais**

Run: `uv run grep -rn "raise AudioDecodeError\|AudioDecodeError(" src/trackclassifier/`
Expected: as mensagens levantadas batem com os prefixos de `_CATEGORIAS`.
**Se nao baterem, corrigir `_CATEGORIAS` — nao a mensagem.** Adicionar um teste
por prefixo que sobreviveu.

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest tests/test_service.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/service.py tests/test_service.py
git commit -m "feat(trackclassifier): FailedItem carrega categoria para agrupar falhas"
```

---

### Task 5: o servico expoe o que a aba Modelo precisa

**Files:**
- Modify: `src/trackclassifier/service.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Produces: `TrackService.class_counts() -> tuple[int, ...]` — contagem por
  classe na ordem de `LABEL_ORDER`, sempre com tres posicoes.
- Produces: `TrackService.decisions_since_train -> int` — propriedade de leitura
  sobre `_decisions_since_train`.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_class_counts_segue_a_ordem_ordinal(servico_com_biblioteca):
    servico = servico_com_biblioteca
    contagens = servico.class_counts()

    # Tres posicoes sempre, na ordem de LABEL_ORDER (-1, neutra, +1). A
    # aba Modelo desenha as barras nessa ordem e nao reordena.
    assert len(contagens) == 3
    assert sum(contagens) == len(servico._labeled)


def test_class_counts_com_biblioteca_vazia_devolve_zeros(servico_vazio):
    assert servico_vazio.class_counts() == (0, 0, 0)


def test_decisions_since_train_e_legivel_de_fora(servico_vazio):
    assert servico_vazio.decisions_since_train == 0
```

Use as fixtures que `tests/test_service.py` ja tem para montar servico com e sem
biblioteca; se os nomes diferirem de `servico_com_biblioteca`/`servico_vazio`,
adote os do arquivo em vez de criar fixtures novas.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_service.py -k "class_counts or decisions_since" -v`
Expected: FAIL com `AttributeError: 'TrackService' object has no attribute 'class_counts'`

- [ ] **Step 3: Implementar**

```python
    def class_counts(self) -> tuple[int, ...]:
        """Exemplos rotulados por classe, na ordem de LABEL_ORDER.

        Tres posicoes sempre, mesmo com a biblioteca vazia: a aba Modelo
        desenha a barra em zero, que e informacao ("falta esta classe"), e
        nao ausencia de linha.
        """
        contagem = Counter(ref.label for ref in self._labeled if ref.label is not None)
        return tuple(contagem.get(rotulo, 0) for rotulo in LABEL_ORDER)

    @property
    def decisions_since_train(self) -> int:
        """Decisoes desde o ultimo treino. So leitura -- quem incrementa e
        decide()/reclassify(), e quem zera e train()."""
        return self._decisions_since_train
```

Imports: `from collections import Counter` e `from .labels import LABEL_ORDER`
(conferir se `LABEL_ORDER` ja esta importado antes de duplicar).

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/service.py tests/test_service.py
git commit -m "feat(trackclassifier): servico expoe balanco de classes e contador de decisoes"
```

---

### Task 6: `ModelState` carrega os sete campos novos

**Files:**
- Modify: `src/trackclassifier/ui/viewmodel.py` (`ModelState` e `model_state`)
- Test: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `model.classes_faltando`, `service.class_counts()`,
  `service.decisions_since_train`, `FailedItem.category`.
- Produces:

```python
@dataclass(frozen=True)
class ModelState:
    accuracy: float | None
    ordinal_mae: float | None
    confusion: tuple[tuple[int, ...], ...] | None
    n_examples: int
    failures: tuple[tuple[str, str, str], ...]   # (filename, reason, category)
    class_counts: tuple[int, ...]
    decisions_since_train: int
    retrain_every: int
    train_blocked_reason: str | None
    low_confidence: bool
    alpha: float | None
    thresholds: tuple[float, float] | None
    extractor_name: str
```

`failures` cresce de tupla de 2 para tupla de 3. `ModelTab` e o unico consumidor
— confirmar com `grep -rn "\.failures" src/ tests/` antes de mudar.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_model_state_nao_treinado_traz_balanco_real_e_motivo(servico_sem_treino):
    from trackclassifier.ui.viewmodel import model_state

    estado = model_state(servico_sem_treino)

    # Metricas ausentes e balanco presente: nao treinado e o estado normal
    # do inicio, nao um erro, e o balanco e justamente o que diz o que
    # rotular em seguida.
    assert estado.accuracy is None
    assert estado.class_counts == servico_sem_treino.class_counts()
    assert estado.n_examples == sum(estado.class_counts)


def test_model_state_bloqueia_treino_com_motivo_quando_falta_classe(servico_so_com_neutras):
    from trackclassifier.ui.viewmodel import model_state

    estado = model_state(servico_so_com_neutras)

    assert estado.train_blocked_reason is not None
    # O motivo nomeia as classes que faltam, na ordem ordinal, com o
    # vocabulario do dominio -- nunca as chaves da config.
    assert "-1" in estado.train_blocked_reason
    assert "+1" in estado.train_blocked_reason


def test_model_state_sem_classe_faltando_libera_o_treino(servico_com_as_tres_classes):
    from trackclassifier.ui.viewmodel import model_state

    assert model_state(servico_com_as_tres_classes).train_blocked_reason is None


def test_model_state_traz_o_contador_de_retreino(servico_sem_treino):
    from trackclassifier.ui.viewmodel import model_state

    estado = model_state(servico_sem_treino)

    assert estado.decisions_since_train == servico_sem_treino.decisions_since_train
    assert estado.retrain_every == servico_sem_treino.config.retrain_every


def test_model_state_traz_o_detalhe_tecnico(servico_sem_treino):
    from trackclassifier.ui.viewmodel import model_state

    estado = model_state(servico_sem_treino)

    assert estado.extractor_name == servico_sem_treino.extractor.name
    # Com o modelo nao treinado, alpha e thresholds sao os defaults do
    # TrackModel e nao dizem nada sobre a biblioteca -- por isso vem None.
    assert estado.alpha is None
    assert estado.thresholds is None


def test_model_state_leva_a_categoria_da_falha(servico_com_falha):
    from trackclassifier.ui.viewmodel import model_state

    (falha,) = model_state(servico_com_falha).failures

    assert len(falha) == 3
    assert falha[2] == servico_com_falha.failures()[0].category
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_viewmodel.py -k model_state -v`
Expected: FAIL com `AttributeError: 'ModelState' object has no attribute 'class_counts'`

- [ ] **Step 3: Implementar**

```python
@dataclass(frozen=True)
class ModelState:
    accuracy: float | None
    ordinal_mae: float | None
    confusion: tuple[tuple[int, ...], ...] | None
    n_examples: int
    #: (filename, reason, category). A categoria e o que a aba Modelo usa
    #: para agrupar -- reason varia por arquivo e nao agrupa nada.
    failures: tuple[tuple[str, str, str], ...]
    class_counts: tuple[int, ...]
    decisions_since_train: int
    retrain_every: int
    #: None = da para treinar. Texto = o motivo, ja pronto para a tela. A
    #: regra vem de model.classes_faltando, nao e reimplementada aqui.
    train_blocked_reason: str | None
    low_confidence: bool
    alpha: float | None
    thresholds: tuple[float, float] | None
    extractor_name: str


def _motivo_do_bloqueio(service: TrackService) -> str | None:
    faltando = classes_faltando(
        ref.label for ref in service._labeled if ref.label is not None
    )
    if not faltando:
        return None
    return (
        f"Faltam exemplos de {', '.join(faltando)} — o modelo precisa "
        "das tres classes para treinar."
    )


def model_state(service: TrackService) -> ModelState:
    metricas = service.model.metrics_
    falhas = tuple(
        (falha.filename, falha.reason, falha.category) for falha in service.failures()
    )
    contagens = service.class_counts()
    comum = {
        "failures": falhas,
        "class_counts": contagens,
        "decisions_since_train": service.decisions_since_train,
        "retrain_every": service.config.retrain_every,
        "train_blocked_reason": _motivo_do_bloqueio(service),
        "low_confidence": service.model.low_confidence_mode,
        "extractor_name": service.extractor.name,
    }
    if metricas is None:
        # alpha_ e thresholds_ existem no TrackModel desde o __init__ com
        # valores default. Expor os defaults como se fossem resultado de
        # treino seria mentira -- por isso None enquanto nao ha metricas.
        return ModelState(
            accuracy=None,
            ordinal_mae=None,
            confusion=None,
            n_examples=sum(contagens),
            alpha=None,
            thresholds=None,
            **comum,
        )
    return ModelState(
        accuracy=metricas.accuracy,
        ordinal_mae=metricas.ordinal_mae,
        confusion=tuple(tuple(linha) for linha in metricas.confusion),
        n_examples=metricas.n_examples,
        alpha=service.model.alpha_,
        thresholds=service.model.thresholds_,
        **comum,
    )
```

Import novo no topo: `from ..model import classes_faltando`. Continua sem Qt.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_viewmodel.py -v`
Expected: PASS. Se o teste gramatical de "viewmodel nao importa Qt" quebrar, o
import novo esta errado — `model.py` nao importa Qt.

- [ ] **Step 5: Ajustar o consumidor existente**

`model_tab.py:75` faz `for nome, motivo in state.failures`. Com a tupla de tres,
vira `for nome, motivo, _categoria in state.failures`. E so a ponte ate a Task
12 reescrever o arquivo — mas tem que ficar verde agora.

- [ ] **Step 6: Verificar**

Run: `uv run pytest && uv run ruff check .`
Expected: PASS na suite inteira.

- [ ] **Step 7: Commit**

```bash
git add src/trackclassifier/ui/viewmodel.py src/trackclassifier/ui/model_tab.py \
        tests/test_viewmodel.py
git commit -m "feat(trackclassifier): ModelState carrega balanco, contador e detalhe tecnico"
```

---

### Task 7: `colors.tinta` — cor derivada sem literal novo

**Files:**
- Create: `src/trackclassifier/ui/colors.py`
- Test: `tests/test_colors.py`

**Interfaces:**
- Produces: `trackclassifier.ui.colors.tinta(cor: str, alpha: float) -> str` —
  devolve `"rgba(r,g,b,a)"` a partir de um token hex. Levanta `ValueError` se
  `alpha` sair de `[0, 1]`.

A matriz de confusao precisa de `state.danger` a 12%. Escrever
`"rgba(240,87,92,0.12)"` a mao passa no teste de hex (ele so procura `#RRGGBB`)
e mesmo assim duplica a paleta: o dia em que o vermelho mudar no JSON, este
literal fica para tras em silencio.

- [ ] **Step 1: Escrever o teste que falha**

```python
import pytest

from trackclassifier.ui.colors import tinta
from trackclassifier.ui.tokens import COLOR_STATE_DANGER


def test_tinta_deriva_rgba_do_token():
    assert tinta(COLOR_STATE_DANGER, 0.12) == "rgba(240,87,92,0.12)"


def test_tinta_com_alfa_cheio_mantem_a_cor_visivel():
    assert tinta(COLOR_STATE_DANGER, 1.0) == "rgba(240,87,92,1.0)"


def test_tinta_recusa_alfa_fora_da_faixa():
    with pytest.raises(ValueError):
        tinta(COLOR_STATE_DANGER, 1.4)


def test_tinta_recusa_cor_que_nao_e_hex_de_seis_digitos():
    # rgba(...) entra como cor em varios tokens de borda. Passar um deles
    # aqui e erro de chamada, nao caso a tratar -- e o mais provavel.
    with pytest.raises(ValueError):
        tinta("rgba(255,255,255,0.05)", 0.5)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_colors.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.colors'`

- [ ] **Step 3: Implementar**

```python
"""Cor derivada de token, para nao nascer literal de cor novo.

O teste que varre `ui/` procura `#RRGGBB` -- entao escrever
`"rgba(240,87,92,0.12)"` a mao passaria. E mesmo assim seria a paleta
duplicada: no dia em que o vermelho mudar no JSON, o literal fica para
tras sem ninguem perceber. Derivar do token e o que amarra os dois.
"""


def tinta(cor: str, alpha: float) -> str:
    """'#F0575C', 0.12 -> 'rgba(240,87,92,0.12)'.

    Aceita so hex de seis digitos: os tokens de borda ja sao rgba, e
    passar um deles aqui e erro de chamada, nao caso a tratar.
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"alpha fora de [0, 1]: {alpha}")
    if not (cor.startswith("#") and len(cor) == 7):
        raise ValueError(f"esperado hex de seis digitos, veio: {cor}")
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_colors.py -v`
Expected: PASS, 4 testes.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/colors.py tests/test_colors.py
git commit -m "feat(trackclassifier): tinta() deriva rgba do token em vez de duplicar a paleta"
```

---

### Task 8: `MicroLabel` entra no QSS gerado

**Files:**
- Modify: `design/build_tokens.py` (template do QSS)
- Modify: `src/trackclassifier/ui/app.qss` (**gerado** — sai de `build_tokens.py`)
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: `QLabel#MicroLabel` no `app.qss` — 10px (`font.size.micro`), mono,
  `text.muted`, sem padding.

Os tres widgets das tasks seguintes usam micro-label (o `MATRIZ DE CONFUSAO`, o
`REAL X PREVISTO`, o `12 ARQUIVOS · 3 MOTIVOS`, o `6 / 10 ATE O RETREINO`). Hoje
existem `SectionLabel` (11px sans com padding 12/8/6/8, do formulario) e
`SectionHeader` (10px mono, mas `text.secondary`). Nenhum dos dois serve, e
repetir o `setStyleSheet` em cinco lugares e o comeco de cinco versoes do mesmo
rotulo.

**`app.qss` e gerado. Nao editar a mao** — mexer no template e rodar o gerador.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_qss_tem_micro_label():
    from trackclassifier.ui.__main__ import QSS

    qss = QSS.read_text(encoding="utf-8")

    assert "QLabel#MicroLabel" in qss


def test_micro_label_usa_o_tamanho_micro_e_a_mono():
    import json

    from trackclassifier.ui.__main__ import QSS

    tokens = json.loads((RAIZ / "design" / "design-tokens.json").read_text())
    micro = tokens["font"]["size"]["micro"]["value"]
    qss = QSS.read_text(encoding="utf-8")

    bloco = qss.split("QLabel#MicroLabel")[1].split("}")[0]
    assert f"font-size: {micro}" in bloco
    assert "JetBrains Mono" in bloco
```

Conferir o formato real de `design-tokens.json` antes de escrever o segundo
teste: se `font.size.micro` nao for um dict com `value`, ajuste o acesso —
`test_tokens.py` ja tem um helper de leitura do JSON, reuse-o.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_tokens.py -k micro_label -v`
Expected: FAIL com `assert 'QLabel#MicroLabel' in qss`.

- [ ] **Step 3: Implementar no template**

Em `design/build_tokens.py`, logo depois do bloco `QLabel#SectionHeader`:

```
/* Micro-label: o rotulo de 10px em caixa alta que aparece em toda tela da
   v0.2 -- cabecalho de coluna, nome de card, contador. A caixa alta e o
   tracking vem de ui/typography.py, pelo mesmo motivo do SectionHeader.
   Sem padding de proposito: quem posiciona e o layout de quem usa. */
QLabel#MicroLabel {{
    color: {textMuted};
    font-family: {fontMono};
    font-size: {fontMicro};
}}
```

Conferir os nomes das variaveis do `.format` que o template ja usa (`textMuted`,
`fontMono`, `fontCaption`...) e adicionar `fontMicro` ao dicionario se ainda nao
estiver la.

- [ ] **Step 4: Regerar e revisar o diff**

Run: `uv run python design/build_tokens.py && git diff src/trackclassifier/ui/app.qss`
Expected: o diff tem **so** o bloco novo. Qualquer outra linha mexida e sinal de
que o template quebrou em outro lugar — nao commitar sem entender.

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add design/build_tokens.py src/trackclassifier/ui/app.qss tests/test_tokens.py
git commit -m "feat(trackclassifier): MicroLabel entra no QSS, o rotulo de 10px da v0.2"
```

---

### Task 9: widget da matriz de confusao

**Files:**
- Create: `src/trackclassifier/ui/widgets/confusion_matrix.py`
- Test: `tests/test_confusion_matrix.py`

**Interfaces:**
- Consumes: `colors.tinta`, `typography.estiliza_label`, `viewmodel.
  LABELS_EM_ORDEM`.
- Produces: `ConfusionMatrix(QWidget)` com
  `set_confusion(confusion: tuple[tuple[int, ...], ...] | None) -> None`.
  `None` esconde a grade e mostra so o cabecalho.
- Produces: `severidade(i: int, j: int) -> int` — `abs(i - j)`, exposta para o
  teste e para a legenda usarem a mesma definicao que as celulas.

Medidas do mockup (`design/mockups/04-modelo.html`): grid `64px repeat(3,1fr)`,
gap 4 (`SPACE_2`), celula de 44px de altura, numero em `FONT_SIZE_SMALL` mono
tabular, rotulo de linha/coluna em `FONT_SIZE_MICRO` com
`FONT_TRACKING_WIDEST`, altura 20 no cabecalho.

- [ ] **Step 1: Escrever o teste que falha**

```python
import pytest

from trackclassifier.ui.tokens import (
    COLOR_CLASSIFICATION_NEUTRO_BG,
    COLOR_STATE_DANGER,
    COLOR_SURFACE_2,
    COLOR_TEXT_DISABLED,
)
from trackclassifier.ui.widgets.confusion_matrix import ConfusionMatrix, severidade

CHEIA = ((62, 10, 2), (13, 68, 8), (3, 11, 37))


def test_severidade_e_a_distancia_ordinal():
    assert severidade(0, 0) == 0
    assert severidade(0, 1) == 1
    assert severidade(0, 2) == 2
    assert severidade(2, 0) == 2


def test_diagonal_usa_superficie_e_as_bordas(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    estilo = matriz.celula(1, 1).styleSheet()

    assert COLOR_SURFACE_2 in estilo


def test_erro_grave_usa_a_tinta_de_danger(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    # 0,2 e 2,0 sao os dois cantos de distancia 2 -- confundir lento com
    # animada. O vermelho aparece so neles.
    assert COLOR_STATE_DANGER in matriz.celula(0, 2).styleSheet()
    assert COLOR_STATE_DANGER in matriz.celula(2, 0).styleSheet()
    assert COLOR_STATE_DANGER not in matriz.celula(0, 1).styleSheet()


def test_erro_leve_usa_o_bg_de_neutro(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    assert COLOR_CLASSIFICATION_NEUTRO_BG in matriz.celula(0, 1).styleSheet()


def test_celula_zerada_fica_apagada(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((0, 0, 0), (0, 0, 0), (0, 0, 0)))

    # Presente mas sem chamar atencao: uma matriz de zeros nao pode
    # parecer uma matriz de erros graves.
    assert COLOR_TEXT_DISABLED in matriz.celula(0, 2).styleSheet()


def test_diagonal_toda_zerada_nao_quebra(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((0, 5, 5), (5, 0, 5), (5, 5, 0)))

    assert matriz.celula(0, 0).text() == "0"


def test_sem_matriz_esconde_a_grade(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)
    matriz.set_confusion(None)

    assert not matriz.grade.isVisibleTo(matriz)


def test_valores_aparecem_na_ordem_real_x_previsto(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    # Linha = real, coluna = previsto: a convencao de hoje, mantida.
    assert matriz.celula(0, 1).text() == "10"
    assert matriz.celula(1, 0).text() == "13"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_confusion_matrix.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
"""Matriz de confusao colorida por severidade ordinal, nao por contagem.

As tres classes sao ordenadas. Confundir neutra com animada e um deslize;
confundir lento com animada e um erro grave. `ordinal_mae` ja pesa isso, e
a matriz antiga tratava toda celula fora da diagonal igual -- o dado
estava la e a tela escondia.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..colors import tinta
from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_CLASSIFICATION_NEUTRO_BG,
    COLOR_CLASSIFICATION_NEUTRO_TEXT,
    COLOR_STATE_DANGER,
    COLOR_SURFACE_2,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_MICRO,
    RADIUS_XS,
    SPACE_2,
    SPACE_3,
    SPACE_5,
    classification_base,
)
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

#: Rotulo do dominio -> nome da classe no design system. Mesma tabela que
#: delegates.py: tokens.py e gerado e nao pode conhecer o dominio.
_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_CELULA = 44
_ALTURA_CABECALHO = 20
_LARGURA_ROTULO = 64
#: Opacidade da tinta de danger no erro grave. 12% e o suficiente para o
#: vermelho ler como fundo sem competir com o numero em cima.
_ALFA_GRAVE = 0.12


def severidade(i: int, j: int) -> int:
    """Distancia ordinal entre a classe real e a prevista."""
    return abs(i - j)


def _estilo_da_celula(i: int, j: int, valor: int) -> str:
    distancia = severidade(i, j)
    if distancia == 0:
        fundo, frente = COLOR_SURFACE_2, COLOR_TEXT_PRIMARY
        borda = f"border: 1px solid {COLOR_BORDER_DEFAULT};"
    elif distancia == 1:
        fundo, frente = COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT
        borda = ""
    else:
        fundo, frente = tinta(COLOR_STATE_DANGER, _ALFA_GRAVE), COLOR_STATE_DANGER
        borda = ""
    # Zero vira apagado depois da cor de severidade, nao no lugar dela: o
    # fundo continua dizendo onde a celula fica na escala, e so o numero
    # para de chamar atencao.
    if valor == 0:
        frente = COLOR_TEXT_DISABLED
    return f"background: {fundo}; color: {frente}; border-radius: {RADIUS_XS}px; {borda}"


class ConfusionMatrix(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("SectionLabel")
        estiliza_label(titulo, "Matriz de confusao")

        convencao = QLabel()
        convencao.setObjectName("MicroLabel")
        estiliza_label(convencao, "real x previsto")

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(SPACE_3)
        cabecalho.addWidget(titulo)
        cabecalho.addWidget(convencao)
        cabecalho.addStretch(1)

        self.grade = QWidget()
        grade = QGridLayout(self.grade)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(SPACE_2)
        grade.setColumnMinimumWidth(0, _LARGURA_ROTULO)
        for coluna in range(1, 4):
            grade.setColumnStretch(coluna, 1)

        self._celulas: dict[tuple[int, int], QLabel] = {}
        for indice, rotulo in enumerate(LABELS_EM_ORDEM):
            grade.addWidget(self._rotulo(rotulo, _ALTURA_CABECALHO), 0, indice + 1)
            grade.addWidget(self._rotulo(rotulo, _ALTURA_CELULA, direita=True), indice + 1, 0)

        for i in range(3):
            for j in range(3):
                celula = QLabel("0")
                celula.setObjectName("Numeric")
                celula.setAlignment(Qt.AlignmentFlag.AlignCenter)
                celula.setFixedHeight(_ALTURA_CELULA)
                self._celulas[(i, j)] = celula
                grade.addWidget(celula, i + 1, j + 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_5)
        layout.addLayout(cabecalho)
        layout.addWidget(self.grade)
        layout.addWidget(self._legenda())

    def _rotulo(self, texto: str, altura: int, direita: bool = False) -> QLabel:
        rotulo = QLabel()
        estiliza_label(rotulo, texto)
        rotulo.setFixedHeight(altura)
        alinhamento = (
            Qt.AlignmentFlag.AlignRight if direita else Qt.AlignmentFlag.AlignHCenter
        )
        rotulo.setAlignment(alinhamento | Qt.AlignmentFlag.AlignVCenter)
        rotulo.setStyleSheet(
            f"color: {classification_base(_CLASSE[texto])}; font-size: {FONT_SIZE_MICRO};"
        )
        return rotulo

    def _legenda(self) -> QWidget:
        """Sem legenda, a escala de cor e adivinhacao."""
        faixa = QWidget()
        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_5)
        for distancia, texto in (
            (0, "acerto"),
            (1, "erro leve · 1 classe"),
            (2, "erro grave · 2 classes"),
        ):
            item = QLabel()
            item.setObjectName("MicroLabel")
            estiliza_label(item, texto)
            amostra = QLabel()
            amostra.setFixedSize(10, 10)
            amostra.setStyleSheet(_estilo_da_celula(0, distancia, 1))
            layout.addWidget(amostra)
            layout.addWidget(item)
        layout.addStretch(1)
        return faixa

    def celula(self, i: int, j: int) -> QLabel:
        """Acesso por (real, previsto) -- e o que o teste inspeciona."""
        return self._celulas[(i, j)]

    def set_confusion(self, confusion: tuple[tuple[int, ...], ...] | None) -> None:
        # Modelo nao treinado esconde a grade inteira em vez de mostrar
        # nove zeros: uma matriz zerada e um resultado, "ainda nao ha
        # matriz" e outra coisa.
        self.grade.setVisible(confusion is not None)
        if confusion is None:
            return
        for i, linha in enumerate(confusion):
            for j, valor in enumerate(linha):
                celula = self._celulas[(i, j)]
                celula.setText(str(valor))
                celula.setStyleSheet(_estilo_da_celula(i, j, valor))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_confusion_matrix.py -v`
Expected: PASS, 8 testes.

- [ ] **Step 5: Verificar que nao nasceu hex**

Run: `uv run pytest tests/test_tokens.py::test_nenhum_hex_fora_do_json -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/widgets/confusion_matrix.py tests/test_confusion_matrix.py
git commit -m "feat(trackclassifier): matriz de confusao colorida por severidade ordinal"
```

---

### Task 10: widget de balanco do treino

**Files:**
- Create: `src/trackclassifier/ui/widgets/class_balance.py`
- Test: `tests/test_class_balance.py`

**Interfaces:**
- Produces: `ClassBalance(QWidget)` com
  `set_counts(counts: tuple[int, ...]) -> None`.
- Produces: `recomendacao(counts: tuple[int, ...]) -> str | None` — funcao pura,
  testavel sem Qt. `None` quando o treino esta equilibrado.

Medidas do mockup: barra de 6px de altura, `RADIUS_XS`, trilho em
`COLOR_BORDER_SUBTLE`, preenchimento em `classification_base`, rotulo e
contagem em mono 11px tabular, gap 10 entre classes, a recomendacao separada por
uma linha de 1px em `COLOR_BORDER_SUBTLE` com 10px de respiro acima.

- [ ] **Step 1: Escrever o teste que falha**

```python
from trackclassifier.ui.widgets.class_balance import ClassBalance, recomendacao

LIMIAR = 0.70


def test_sem_recomendacao_quando_as_tres_sao_iguais():
    assert recomendacao((50, 50, 50)) is None


def test_sem_recomendacao_logo_acima_do_limiar():
    # 71 / 100 = 71% > 70%: desbalanceado, mas nao o suficiente para
    # ocupar espaco na tela toda vez.
    assert recomendacao((71, 100, 100)) is None


def test_recomendacao_nomeia_a_classe_minoritaria():
    texto = recomendacao((74, 89, 51))

    assert texto is not None
    # +1 tem 51/89 = 57% da maior. E a classe a rotular.
    assert "+1" in texto
    assert "57%" in texto


def test_recomendacao_com_biblioteca_vazia_nao_divide_por_zero():
    assert recomendacao((0, 0, 0)) is None


def test_recomendacao_com_uma_classe_zerada():
    texto = recomendacao((0, 40, 40))

    assert texto is not None
    assert "-1" in texto
    assert "0%" in texto


def test_barra_da_maior_classe_ocupa_tudo(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    # Normalizada pela maior: a barra de neutra vai a 100% e as outras
    # sao lidas em relacao a ela.
    assert balanco.proporcao(1) == 1.0


def test_barra_proporcional_a_maior(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    assert balanco.proporcao(2) == round(51 / 89, 4)


def test_contagem_aparece_no_rotulo(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    assert balanco.contagem(0).text() == "74"


def test_biblioteca_vazia_desenha_tres_barras_em_zero(qapp):
    balanco = ClassBalance()
    balanco.set_counts((0, 0, 0))

    # Barra em zero e informacao ("falta esta classe"), nao ausencia de
    # linha -- por isso nao esconde nada.
    assert all(balanco.proporcao(i) == 0.0 for i in range(3))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_class_balance.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
"""Balanco do treino: o dado mais acionavel da aba.

Nenhuma metrica atual revela que a biblioteca tem 51 animadas contra 89
neutras -- e e isso que explica os erros. A aba tem que terminar em "o que
faco agora", e a resposta quase sempre e a classe minoritaria.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_CAPTION,
    RADIUS_XS,
    SPACE_2,
    SPACE_3,
    SPACE_5,
    classification_base,
)
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_BARRA = 6
#: Abaixo disto a classe minoritaria vira recomendacao na tela. Acima, o
#: treino esta equilibrado o bastante e o texto so ocuparia espaco.
_LIMIAR_DESBALANCO = 0.70


def recomendacao(counts: tuple[int, ...]) -> str | None:
    """Texto derivado, nao fixo: some quando o treino esta equilibrado."""
    maior = max(counts, default=0)
    if maior == 0:
        # Biblioteca vazia nao esta desbalanceada, esta vazia. O empty
        # state da aba ja cobre esse caso.
        return None
    indice = min(range(len(counts)), key=lambda i: counts[i])
    proporcao = counts[indice] / maior
    if proporcao >= _LIMIAR_DESBALANCO:
        return None
    rotulo = LABELS_EM_ORDEM[indice]
    maior_rotulo = LABELS_EM_ORDEM[counts.index(maior)]
    return (
        f"{rotulo} tem {proporcao:.0%} dos exemplos de {maior_rotulo}. "
        f"Rotular mais {rotulo} e o que mais reduz o erro agora."
    )


class ClassBalance(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("SectionLabel")
        estiliza_label(titulo, "Balanco do treino")

        self._contagens: list[QLabel] = []
        self._barras: list[QWidget] = []
        self._proporcoes = [0.0, 0.0, 0.0]

        barras = QVBoxLayout()
        barras.setContentsMargins(0, 0, 0, 0)
        # O mockup usa 10 entre classes; a escala tem 8 (SPACE_4) e 12
        # (SPACE_5). Fica com SPACE_5 -- inventar um valor fora da escala
        # e o comeco de nao ter escala nenhuma.
        barras.setSpacing(SPACE_5)
        for rotulo in LABELS_EM_ORDEM:
            barras.addWidget(self._faixa(rotulo))

        self._recomendacao = QLabel("")
        self._recomendacao.setWordWrap(True)
        self._recomendacao.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
            f"border-top: 1px solid {COLOR_BORDER_SUBTLE}; padding-top: 10px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_5)
        layout.addWidget(titulo)
        layout.addLayout(barras)
        layout.addWidget(self._recomendacao)
        layout.addStretch(1)

    def _faixa(self, rotulo: str) -> QWidget:
        cor = classification_base(_CLASSE[rotulo])

        nome = QLabel(rotulo)
        nome.setObjectName("Numeric")
        nome.setStyleSheet(f"color: {cor}; font-size: {FONT_SIZE_CAPTION};")

        contagem = QLabel("0")
        contagem.setObjectName("Numeric")
        contagem.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )
        self._contagens.append(contagem)

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.addWidget(nome)
        topo.addStretch(1)
        topo.addWidget(contagem)

        trilho = QWidget()
        trilho.setFixedHeight(_ALTURA_BARRA)
        trilho.setStyleSheet(
            f"background: {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_XS}px;"
        )
        preenchimento = QWidget(trilho)
        preenchimento.setStyleSheet(f"background: {cor}; border-radius: {RADIUS_XS}px;")
        self._barras.append(preenchimento)

        faixa = QWidget()
        layout = QVBoxLayout(faixa)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addLayout(topo)
        layout.addWidget(trilho)
        return faixa

    def proporcao(self, indice: int) -> float:
        return self._proporcoes[indice]

    def contagem(self, indice: int) -> QLabel:
        return self._contagens[indice]

    def set_counts(self, counts: tuple[int, ...]) -> None:
        maior = max(counts, default=0)
        for indice, valor in enumerate(counts):
            self._contagens[indice].setText(str(valor))
            # Normaliza pela maior, nao pelo total: com 74/89/51 o olho
            # compara as classes entre si, que e a pergunta.
            self._proporcoes[indice] = round(valor / maior, 4) if maior else 0.0
        self._atualiza_barras()

        texto = recomendacao(counts)
        self._recomendacao.setText(texto or "")
        self._recomendacao.setVisible(texto is not None)

    def _atualiza_barras(self) -> None:
        for indice, preenchimento in enumerate(self._barras):
            trilho = preenchimento.parentWidget()
            largura = int(trilho.width() * self._proporcoes[indice])
            preenchimento.setGeometry(0, 0, largura, _ALTURA_BARRA)

    def resizeEvent(self, event) -> None:  # noqa: N802 (assinatura do Qt)
        # O preenchimento e filho posicionado a mao dentro do trilho: sem
        # isto ele fica com a largura do primeiro layout e nao acompanha a
        # janela.
        super().resizeEvent(event)
        self._atualiza_barras()
```

Corrigir o `SPACE_4 if False else 10` para o token certo ao implementar: o gap
de 10 entre classes nao tem token exato (`SPACE_4` e 8, `SPACE_5` e 12). Usar
`SPACE_5` e ajustar o mockup mentalmente, **nao** inventar constante — anotar a
escolha num comentario.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_class_balance.py -v`
Expected: PASS, 9 testes.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/widgets/class_balance.py tests/test_class_balance.py
git commit -m "feat(trackclassifier): balanco do treino com recomendacao derivada"
```

---

### Task 11: widget de falhas agrupadas

**Files:**
- Create: `src/trackclassifier/ui/widgets/failure_list.py`
- Test: `tests/test_failure_list.py`

**Interfaces:**
- Produces: `FailureList(QWidget)` com
  `set_failures(failures: tuple[tuple[str, str, str], ...]) -> None`.
  Esconde o widget inteiro quando a tupla e vazia.
- Produces: `agrupa(failures) -> list[tuple[str, list[str]]]` — funcao pura,
  `(categoria, [arquivos])`, ordenada por contagem decrescente.

Medidas do mockup: cada grupo e um card `COLOR_SURFACE_1`, `RADIUS_SM`, padding
10/14, gap 6 entre cards. Badge com a contagem em `COLOR_STATE_DANGER` sobre
`tinta(danger, 0.12)`, `RADIUS_XS`, padding 2/6. Arquivos em mono 11px
`COLOR_TEXT_MUTED`, uma linha so com elipse, e `+N` quando passa de cinco.

- [ ] **Step 1: Escrever o teste que falha**

```python
from trackclassifier.ui.widgets.failure_list import FailureList, agrupa

FALHAS = (
    ("promo_04.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("set_rip_b.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("rip_side_a.flac", "Falha ao decodificar rip_side_a.flac: x", "falha ao decodificar"),
)


def test_agrupa_por_categoria_e_nao_por_razao():
    grupos = agrupa(FALHAS)

    # As duas razoes de decode diferem (trazem o nome do arquivo); a
    # categoria e a mesma. Sem isso, dez arquivos viram dez grupos.
    assert [categoria for categoria, _ in grupos] == [
        "ffmpeg nao encontrado",
        "falha ao decodificar",
    ]


def test_grupo_maior_vem_primeiro():
    grupos = agrupa(FALHAS)

    assert len(grupos[0][1]) == 2


def test_agrupa_dez_do_mesmo_tipo_em_um_grupo():
    dez = tuple(
        (f"arq_{i}.m4a", f"Falha ao decodificar arq_{i}.m4a: x", "falha ao decodificar")
        for i in range(10)
    )

    grupos = agrupa(dez)

    assert len(grupos) == 1
    assert len(grupos[0][1]) == 10


def test_sem_falhas_esconde_a_secao(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)
    lista.set_failures(())

    # Secao some inteira. Nao mostrar lista vazia com "nenhuma falha".
    assert lista.isHidden()


def test_cabecalho_conta_arquivos_e_motivos(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)

    assert lista.resumo.text() == "3 ARQUIVOS · 2 MOTIVOS"


def test_badge_mostra_a_contagem_do_grupo(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)

    assert lista.badge(0).text() == "2"


def test_lista_de_arquivos_resume_depois_de_cinco(qapp):
    sete = tuple(
        (f"arq_{i}.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado") for i in range(7)
    )

    lista = FailureList()
    lista.set_failures(sete)

    assert lista.arquivos(0).text().endswith("· +2")


def test_trocar_de_conjunto_nao_acumula_cards(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)
    lista.set_failures(FALHAS[:1])

    assert lista.total_de_grupos() == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_failure_list.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
"""Falhas agrupadas por categoria.

Quarenta arquivos com "ffmpeg nao encontrado" sao UM problema, nao
quarenta. A lista plana de antes fazia o usuario rolar quarenta linhas
para descobrir que ha uma coisa a consertar.
"""

from collections import defaultdict

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..colors import tinta
from ..tokens import (
    COLOR_STATE_DANGER,
    COLOR_SURFACE_1,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_SMALL,
    RADIUS_SM,
    RADIUS_XS,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)
from ..typography import estiliza_label, texto_de_label

#: Quantos nomes cabem numa linha antes de virar "+N". Cinco e o que o
#: mockup mostra sem estourar a largura do card com nomes reais de promo.
_ARQUIVOS_VISIVEIS = 5
_ALFA_BADGE = 0.12


def agrupa(failures: tuple[tuple[str, str, str], ...]) -> list[tuple[str, list[str]]]:
    """(categoria, arquivos), maior grupo primeiro."""
    por_categoria: dict[str, list[str]] = defaultdict(list)
    for filename, _reason, category in failures:
        por_categoria[category].append(filename)
    return sorted(por_categoria.items(), key=lambda item: -len(item[1]))


class FailureList(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("SectionLabel")
        estiliza_label(titulo, "Falhas de analise")

        self.resumo = QLabel("")
        self.resumo.setObjectName("MicroLabel")

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(SPACE_3)
        cabecalho.addWidget(titulo)
        cabecalho.addWidget(self.resumo)
        cabecalho.addStretch(1)

        self._cards = QVBoxLayout()
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(SPACE_3)

        self._badges: list[QLabel] = []
        self._arquivos: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_4)
        layout.addLayout(cabecalho)
        layout.addLayout(self._cards)
        layout.addStretch(1)

    def badge(self, indice: int) -> QLabel:
        return self._badges[indice]

    def arquivos(self, indice: int) -> QLabel:
        return self._arquivos[indice]

    def total_de_grupos(self) -> int:
        return len(self._badges)

    def set_failures(self, failures: tuple[tuple[str, str, str], ...]) -> None:
        self._limpa()
        self.setVisible(bool(failures))
        if not failures:
            return

        grupos = agrupa(failures)
        self.resumo.setText(
            texto_de_label(f"{len(failures)} arquivos · {len(grupos)} motivos")
        )
        for categoria, arquivos in grupos:
            self._cards.addWidget(self._card(categoria, arquivos))

    def _limpa(self) -> None:
        # Trocar o conjunto de falhas nao pode empilhar cards antigos --
        # set_failures roda a cada atualizacao de estado da aba.
        self._badges.clear()
        self._arquivos.clear()
        while self._cards.count():
            item = self._cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _card(self, categoria: str, arquivos: list[str]) -> QWidget:
        badge = QLabel(str(len(arquivos)))
        badge.setObjectName("Numeric")
        badge.setStyleSheet(
            f"color: {COLOR_STATE_DANGER};"
            f"background: {tinta(COLOR_STATE_DANGER, _ALFA_BADGE)};"
            f"border-radius: {RADIUS_XS}px; padding: 2px 6px;"
            f"font-size: {FONT_SIZE_CAPTION};"
        )
        self._badges.append(badge)

        motivo = QLabel(categoria)
        motivo.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SMALL};"
        )

        topo = QHBoxLayout()
        topo.setSpacing(SPACE_5)
        topo.addWidget(badge)
        topo.addWidget(motivo)
        topo.addStretch(1)

        visiveis = arquivos[:_ARQUIVOS_VISIVEIS]
        texto = " · ".join(visiveis)
        if len(arquivos) > _ARQUIVOS_VISIVEIS:
            texto += f" · +{len(arquivos) - _ARQUIVOS_VISIVEIS}"
        nomes = QLabel(texto)
        nomes.setObjectName("Numeric")
        nomes.setStyleSheet(
            f"color: {COLOR_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION};"
        )
        self._arquivos.append(nomes)

        card = QWidget()
        card.setStyleSheet(
            f"background: {COLOR_SURFACE_1}; border-radius: {RADIUS_SM}px;"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(SPACE_3)
        layout.addLayout(topo)
        layout.addWidget(nomes)
        return card
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_failure_list.py -v`
Expected: PASS, 8 testes.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/widgets/failure_list.py tests/test_failure_list.py
git commit -m "feat(trackclassifier): falhas de analise agrupadas por categoria"
```

---

### Task 12: `ModelTab` monta os cards

**Files:**
- Modify: `src/trackclassifier/ui/model_tab.py` (reescrita)
- Test: `tests/test_model_tab.py` (criar)

**Interfaces:**
- Consumes: `ConfusionMatrix`, `ClassBalance`, `FailureList`, `ModelState`.
- Produces: `ModelTab(QWidget)` com `train_requested = Signal()` (inalterado) e
  `set_state(state: ModelState) -> None`.

Layout do mockup: primeira faixa com tres cards (`280 · flex · 300`), gap 12,
cada card em `COLOR_SURFACE_1`, `RADIUS_SM`, padding 14/16. Segunda faixa: card
de acao com o botao RETREINAR, o motivo ou o trilho de progresso, e o aviso de
`low_confidence` a direita. Terceira: as falhas. Rodape: o detalhe tecnico
recolhivel.

- [ ] **Step 1: Escrever o teste que falha**

```python
import pytest

from trackclassifier.ui.model_tab import ModelTab
from trackclassifier.ui.viewmodel import ModelState

BASE = dict(
    accuracy=0.78,
    ordinal_mae=0.243,
    confusion=((62, 10, 2), (13, 68, 8), (3, 11, 37)),
    n_examples=214,
    failures=(),
    class_counts=(74, 89, 51),
    decisions_since_train=6,
    retrain_every=10,
    train_blocked_reason=None,
    low_confidence=False,
    alpha=1.8,
    thresholds=(-0.33, 0.41),
    extractor_name="handcrafted-v1",
)


def estado(**mudancas) -> ModelState:
    return ModelState(**{**BASE, **mudancas})


def test_metricas_aparecem_treinado(qapp):
    aba = ModelTab()
    aba.set_state(estado())

    assert aba.acuracia.text() == "78.0%"
    assert aba.erro_ordinal.text() == "0.243"
    assert aba.exemplos.text() == "214"


def test_nao_treinado_esconde_metricas_e_mantem_balanco(qapp):
    aba = ModelTab()
    aba.set_state(estado(accuracy=None, ordinal_mae=None, confusion=None))

    # Nao treinado e o estado normal do inicio, nao um erro: o balanco e
    # as falhas continuam valendo.
    assert not aba.metricas.isVisibleTo(aba)
    assert aba.balanco.isVisibleTo(aba)


def test_botao_desabilita_com_motivo_visivel(qapp):
    aba = ModelTab()
    aba.set_state(estado(train_blocked_reason="Faltam exemplos de +1"))

    assert not aba.botao_retreinar.isEnabled()
    assert aba.motivo.text() == "Faltam exemplos de +1"


def test_train_requested_nao_sai_com_botao_desabilitado(qapp):
    aba = ModelTab()
    aba.set_state(estado(train_blocked_reason="Faltam exemplos de +1"))
    disparos = []
    aba.train_requested.connect(lambda: disparos.append(1))

    aba.botao_retreinar.click()

    assert disparos == []


def test_train_requested_sai_com_botao_habilitado(qapp):
    aba = ModelTab()
    aba.set_state(estado())
    disparos = []
    aba.train_requested.connect(lambda: disparos.append(1))

    aba.botao_retreinar.click()

    assert disparos == [1]


def test_contador_de_retreino(qapp):
    aba = ModelTab()
    aba.set_state(estado(decisions_since_train=6, retrain_every=10))

    # Sem acento e em caixa alta: o texto passa por texto_de_label, e a
    # convencao do repo e portugues sem acento ate na copy de tela.
    assert aba.progresso.text() == "6 / 10 ATE O RETREINO AUTOMATICO"


def test_aviso_de_baixa_confianca_some_quando_falso(qapp):
    aba = ModelTab()
    aba.set_state(estado(low_confidence=False))

    assert not aba.aviso.isVisibleTo(aba)


def test_detalhe_tecnico_resume_fechado(qapp):
    aba = ModelTab()
    aba.set_state(estado())

    assert "1.80" in aba.detalhe.text()
    assert "handcrafted-v1" in aba.detalhe.text()


def test_detalhe_tecnico_sem_treino_nao_inventa_numero(qapp):
    aba = ModelTab()
    aba.set_state(estado(alpha=None, thresholds=None))

    # alpha_ e thresholds_ tem default no TrackModel; mostra-los como se
    # fossem resultado de treino seria mentira.
    assert "1.80" not in aba.detalhe.text()
    assert "handcrafted-v1" in aba.detalhe.text()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_model_tab.py -v`
Expected: FAIL com `AttributeError: 'ModelTab' object has no attribute 'acuracia'`

- [ ] **Step 3: Implementar**

Reescrever `model_tab.py` inteiro. Estrutura:

- `_card(titulo: str) -> tuple[QWidget, QVBoxLayout]` — helper local que devolve
  o `QWidget` com `background: COLOR_SURFACE_1; border-radius: RADIUS_SM` e
  padding 14/16, ja com o `SectionLabel` em cima.
- `self.metricas` — o card de 280px de largura fixa, com as tres linhas
  `rotulo a esquerda / valor mono 18px a direita`. Guardar `self.exemplos`,
  `self.acuracia`, `self.erro_ordinal` como atributos: sao o que o teste le.
- `self.matriz = ConfusionMatrix()` dentro do card flex.
- `self.balanco = ClassBalance()` dentro do card de 300px.
- Card de acao: `self.botao_retreinar` (com `estiliza_label(botao,
  "Retreinar")` e `setProperty("variant", "primary")`), `self.motivo`
  (`COLOR_STATE_DANGER`, escondido quando `train_blocked_reason is None`),
  o trilho de 3px + `self.progresso`, e `self.aviso` a direita.
- `self.falhas = FailureList()`.
- `self.detalhe` — `QLabel` clicavel de uma linha; o texto fechado e
  `f"alpha {alpha:.2f} · cortes {t1:.3f} / {t2:.3f} · {extractor_name}"`, e
  quando `alpha is None` cai para so o `extractor_name`.

`set_state` distribui: `self.matriz.set_confusion(state.confusion)`,
`self.balanco.set_counts(state.class_counts)`,
`self.falhas.set_failures(state.failures)`, e o resto e formatacao local.

O botao desabilitado nao pode emitir: `self.botao_retreinar.setEnabled(
state.train_blocked_reason is None)` — o Qt ja engole o `click()` de um botao
desabilitado, e o teste confirma isso em vez de assumir.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_model_tab.py -v`
Expected: PASS, 9 testes.

- [ ] **Step 5: Verificar a suite inteira**

Run: `uv run pytest && uv run ruff check .`
Expected: PASS. `tests/test_window.py` monta a `MainWindow` com as quatro abas —
se ele quebrar, a assinatura de `ModelTab` mudou sem querer.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/model_tab.py tests/test_model_tab.py
git commit -m "feat(trackclassifier): aba Modelo redesenhada sobre os tokens v0.2"
```

---

### Task 13: ver com os proprios olhos

**Files:**
- Modify: este arquivo (registrar o resultado)

Um teste de pixel nao pega "a paleta ficou lavada" nem "a coluna deslocou um
pixel". A Fase 1 do plano anterior fechou com esta etapa e vale repetir o metodo.

- [ ] **Step 1: Subir a janela real com o estado do cache**

Script offscreen que monta a `MainWindow` com o servico real, cancela o
auto-scan e popula do cache (`service.extractor.name` ajustado para bater com o
parquet existente, como no plano da Fase 1), e grava um PNG da aba Modelo.

Um scan de verdade re-extrairia a biblioteca inteira — ~30 min para tirar uma
screenshot. Nao faca isso.

- [ ] **Step 2: Comparar contra `design/mockups/04-modelo.html`**

Abrir os dois lado a lado. Conferir, nesta ordem: alturas de card, gap entre
cards, altura da celula da matriz (44), a cor de cada nivel de severidade, o
peso do numero em mono, e se as fontes empacotadas realmente entraram (o "0" da
JetBrains Mono tem corte diagonal; o do fallback nao).

- [ ] **Step 3: Registrar aqui o que destoou**

Escrever nesta secao o que bateu, o que nao bateu e o que ficou para as fases
seguintes. Se algo destoar por erro (e nao por escopo de fase futura),
consertar antes de fechar.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-07-telas-v02-fase-1-fontes-e-modelo.md
git commit -m "docs(trackclassifier): registra a verificacao visual da aba Modelo"
```

---

## Fora de escopo desta fase

- **Fases 2, 3 e 4** — linha instrumento, aba Revisao, teclado e orfaos. Cada
  uma ganha seu proprio plano.
- **Importancia das features** e **historico de metricas** na aba Modelo.
- **Empty state da aba Modelo** com biblioteca vazia. O `LEIA-ME.md` marca a
  copy ("Nenhum exemplo rotulado" / "Classifique tracks na Revisao...") como
  **nova, ainda nao revisada** — nao existe em `empty_state.py`. Entra na Fase 4
  junto dos outros empty states, com a copy decidida de uma vez.
- **Qualquer coisa do scan v2 / `handcrafted-v2`.**

## Riscos

- **`ModelState.failures` muda de tupla-2 para tupla-3.** Rodar
  `grep -rn "\.failures" src/ tests/` antes da Task 6 e conferir cada
  consumidor. Se houver outro alem de `model_tab.py`, ele entra na mesma task.
- **`QLabel` com `setStyleSheet` por widget e o padrao ja usado em
  `settings_form.py`**, entao segue a casa — mas cada `setStyleSheet` custa um
  reparse da folha. Se a aba Modelo ficar visivelmente lenta ao atualizar,
  a saida e agrupar por `objectName` no `app.qss`, nao otimizar caso a caso.
- **As fontes so aparecem depois do `QApplication`.** Se algum teste montar
  widget sem a fixture `qapp`, `registra_fontes()` devolve lista vazia em
  silencio e o teste passa medindo a fonte errada. Todo teste de widget aqui usa
  `qapp`.
