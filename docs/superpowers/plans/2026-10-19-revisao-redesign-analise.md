# Redesenho visual da aba Revisao — analise e plano

> **For agentic workers:** Use superpowers:subagent-driven-development (ou
> superpowers:executing-plans) para implementar task por task. Steps usam
> checkbox (`- [ ]`).

**Goal:** Corrigir os campos oversizacionados e os icones quebrados/errados da
aba Revisao, e fechar o furo entre o que foi implementado (`GuessBar`,
`UpcomingList`) e o que foi efetivamente ligado.

**Spec:** `docs/superpowers/specs/2026-08-07-aba-revisao-design.md`
**Plano de implementacao original:** `docs/superpowers/plans/2026-08-07-telas-v02-fase-3-revisao.md`

## Global Constraints

- **Portugues sem acentos** em codigo: variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. API publica
  (dataclasses, metodos de classe, campos JSON) em ingles.
- Comentarios explicam **porque**, nao o que.
- **Nenhum literal `#RRGGBB` fora de `design/design-tokens.json`.**
- `ui/viewmodel.py` nao importa Qt.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.
- `uv run pytest` inteiro antes de cada commit que toque `ui/` (~70s).
- Commits: conventional commits com escopo.

---

## Problemas identificados

### 1. Campos oversizacionados — `DashboardChip` padding (QSS)

**Onde:** `src/trackclassifier/ui/app.qss:104`

```qss
QLabel#DashboardChip {
    color: #AFBCD2; background: #09131A;
    border: 1px solid rgba(255,255,255,0.10); border-radius: 3px;
    padding: 4px 8px;
}
```

**Problema:** A regra `padding: 4px 8px` (8px horizontal) e proporcionalmente
excessiva para os valores que cabem dentro do chip: BPM ("138"), duracao
("3:45"), formato ("MP3"), key ("11A"). O padding vertical de 4px tambem
espessa o chip desnecessariamente. No mockup r2 (spec linha 35), a fila de
chips deve ser densa — cada chip cabe numa linha, sem ocupar meia altura de
linha.

**Impacto:** A linha de chips no `ReviewHeader` ocupa mais espaco vertical do
que o necessario, empurrando os stat cards para baixo ou forçando overflow
horizontal.

**Correcao:** Reduzir `padding` para `2px 6px` (SPACE_2 horizontal, SPACE_1
vertical — ja existem como tokens). Isso mantem o border-radius de 3px e a
visual de chip, mas encurta a caixa pra valores curtos. Ajustar `design-tokens.json`
se houver um token de padding de chip; senao, hardcode no QSS como as outras
regras `QLabel#DashboardChip` ja fazem (nao usam token de padding).

### 2. Altura inconsistente dos `ClassActionCard` (codigo vs QSS vs token)

**Onde:** `src/trackclassifier/ui/widgets/class_action_card.py:23` e
`src/trackclassifier/ui/app.qss:54`

```python
# codigo:
self.setMinimumHeight(76)
```

```qss
/* QSS: */
QPushButton#ClassActionCard { min-height: 90px; ... }
```

**Problema:** Tres valores diferentes para a mesma coisa:
- `SIZE_CONTROL_CLASS_CARD = 94` (token, `tokens.py:122`) — nunca usado pelo card
- `setMinimumHeight(76)` (codigo)
- `min-height: 90px` (QSS)

O QSS vence o `setMinimumHeight` em Qt, entao o card efetivamente mede 90px,
mas o codigo diz 76 e o token diz 94 — confusao de manutencao. Alem dis, o
conteudo do card (label + subtitle + shortcut) nao preenche 90px: ha
whitespace vertical entre o titulo e o rodape do card.

**Correcao:**
- Remover `self.setMinimumHeight(76)` do codigo — o QSS ja governa a altura.
- Ajustar o QSS de `min-height: 90px` para `min-height: 76px` (ou
  `SIZE_CONTROL_CLASS_CARD` se o token for adotado). 76px e a altura que
  acomoda titulo (15px) + subtitulo (11px) + kbd (10px) + spacings
  (`SPACE_4` x2 + `SPACE_3` top/bottom do card) com folga razoavel.
- Se adotar o token: mudar QSS para `min-height: SIZE_CONTROL_CLASS_CARD` —
  mas isso exigiria o QSS usar `var(--size-control-class-card)` ou o build
  de tokens injetar o valor. Verificar `design/build_tokens.py` para ver como
  tokens viram QSS.

### 3. Icones de transporte quebrados — unicode no lugar de SVG

**Onde:** `src/trackclassifier/ui/widgets/player_bar.py:34-35,90,93`

```python
_PLAY = "▶"
_PAUSE = "❚❚"
self._previous = QPushButton("◀❚")
self._next = QPushButton("❚▶")
```

**Problema:** A barra de transporte usa glifos unicode (U+25B6, U+275A) em
vez dos SVG's disponiveis (`icons/play.svg`, `pause.svg`, `prev.svg`,
`next.svg`). O proprio codigo documenta o problema (`player_bar.py:84-87`):
a familia sans do QSS nao tem esses glifos, e o Qt cai num glifo de
substituicao — aparece um quadradinho no canto do botao.

**Icones SVG disponiveis mas nao usados:**
`icons/play.svg`, `icons/pause.svg`, `icons/prev.svg`, `icons/next.svg`,
`icons/volume.svg`.

**Correcao:** Substituir os textos unicode por `QIcon` usando o helper
existente `ui/icons.py::icon(nome, cor, tamanho)` — o mesmo mecanismo usado
em `app_header.py` para os nav icons e o botao de scan. Os SVGs usam
`currentColor` como placeholder, e `icon()` substitui pela cor do token e
rasteriza com `QSvgRenderer`.

```python
from PySide6.QtGui import QIcon
from ..icons import icon
from ..tokens import COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, SIZE_ICON_BASE, SIZE_ICON_LARGE

self._botao = QPushButton()
self._botao.setIcon(icon("play", COLOR_TEXT_PRIMARY, SIZE_ICON_LARGE))
self._botao.setIconSize(QSize(SIZE_ICON_LARGE, SIZE_ICON_LARGE))

self._previous = QPushButton()
self._previous.setIcon(icon("prev", COLOR_TEXT_SECONDARY, SIZE_ICON_BASE))
self._previous.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))

self._next = QPushButton()
self._next.setIcon(icon("next", COLOR_TEXT_SECONDARY, SIZE_ICON_BASE))
self._next.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))
```

O botao de play/pause muda de icone via `_muda_estado` (ja existe), e o
icone muda com `setIcon`. Ver `app_header.py:34-49` para o padrao de icone
com estados (On/Off).

**Nota de integridade:** `icons/volume.svg` existe mas `VolumeRail` e
propositalmente pintado a mao (veja sua docstring). Isso e correto — o
`volume.svg` e para outro contexto, nao para o rail. Fora de escopo.

### 4. `GuessBar` construido mas nao ligado na Revisao

**Onde:** `src/trackclassifier/ui/widgets/guess_bar.py` (existe) vs
`src/trackclassifier/ui/review_tab.py` (nao usa)

**Problema:** O `GuessBar` — faixa com escala ordinal, classe, confianca +
metodo de aviso, meter de 2px, numero, warning text — foi implementado
(`docs/superpowers/plans/2026-08-07-telas-v02-fase-3-revisao.md` Task 3)
mas **nunca foi importado nem instanciado** em `review_tab.py`. Em vez disso,
`ReviewHeader` tem sua propria versao inline de prediction/confidence
(`review_header.py:64-73`) que:

- Nao tem a escala ordinal (`OrdinalScale`)
- Nao tem o texto de aviso ("Modelo com poucos exemplos")
- Duplica a logica de `LIMIAR_ATENCAO` importada de `guess_bar.py` (apenas
  para a cor do meter, sem o texto)

**Correcao:** Substituir a secao de prediction/confidence do `ReviewHeader`
pelo `GuessBar`. Isso envolve:
- Remover os widgets `prediction`, `confidence`, `confidence_bar` do header
- Importar e instanciar `GuessBar` em `review_header.py`
- Chamar `guess_bar.set_guess(...)` de onde o header recebe `row` e
  `low_confidence`
- Manter o stat card de **progresso** (que nao existe no `GuessBar`) — o
  progress card continua separado

**Risco:** O `GuessBar` tem `objectName = "GuessBar"` e uma regra QSS
(`app.qss:11`) que ja existe. O header stat card tem a regra
`QWidget#ReviewStatCard`. Verificar se o layout da substituicao mantem a
altura esperada.

### 5. `UpcomingList` construido mas nao ligado na Revisao

**Onde:** `src/trackclassifier/ui/widgets/upcoming_list.py` (existe) vs
`src/trackclassifier/ui/review_tab.py` (usa `ReviewQueueStrip`)

**Problema:** O `UpcomingList` — uma `QTableView` compacta com delegates
de capa, titulo, onda, key, classificacao — foi implementado (Task 4 do
plano) mas **nunca foi importado nem usado**. Em vez disso, `review_tab.py`
instancia `ReviewQueueStrip` (`review_tab.py:101`), que e uma lista
horizontal simplificada com apenas capa + titulo (sem onda, sem key, sem
classificacao).

O `ReviewQueueStrip` tambem tem uma estrutura mais pesada do que precisa —
cria um `TrackTableModel` interno (`review_queue.py:21`) que e redundante
com a janela local da `ReviewTab`.

**Correcao:** Substituir `ReviewQueueStrip` por `UpcomingList` em
`review_tab.py`. Isso envolve:
- Importar `UpcomingList` em vez de `ReviewQueueStrip`
- Adaptar a chamada de `set_rows` (o `UpcomingList.set_rows` aceita
  `(rows)` sem `remaining` e `atual`; o `ReviewQueueStrip.set_rows` recebe
  `(rows, *, remaining, atual)`) — passar apenas as proximas (excluindo a
  atual) ou a janela inteira dependendo do design
- Remover `ReviewQueueStrip` e `tests/test_dashboard_widgets.py` (se for
  o unico teste que o cobre), ou manter para a Biblioteca se for reusado

**Caveat:** Verificar se `UpcomingList` e usado na Biblioteca — se sim,
manter. O `review_queue.py` parece ser exclusivo da Revisao.

### 6. Dead code: `_coluna_da_key()` em `review_tab.py`

**Onde:** `src/trackclassifier/ui/review_tab.py:187-207`

**Problema:** O metodo `_coluna_da_key()` (que monta um micro-label "Key"
sobre o `KeyChip`) e **chamado em nenhum lugar**. O `grep` confirma: a unica
referencia e a definicao. O header ja tem o key chip sem micro-label
(`review_header.py:44`), e o `_coluna_da_key` nunca e invocado.

**Correcao:** Remover o metodo e os imports associados
(`estiliza_label`, `SPACE_2`) se nao forem usados em outro lugar do arquivo.
Verificar uso de `SPACE_2` e `estiliza_label` no resto de `review_tab.py`
antes de remover imports.

### 7. `BulkAction` button sem icon

**Onde:** `src/trackclassifier/ui/widgets/player_bar.py:117-119`

```python
self.botao_bloco = QPushButton()  # sem texto, sem icon
```

**Problema:** O botao "Aprovar em bloco" tem `setText` vindo de
`set_bulk_label` (que define "Aprovar em bloco (confianca >= 0.75)") — entao
nao esta totalmente vazio, mas nao tem icon. Comparado com os outros
icones SVG disponiveis, ficaria mais consistente.

**Prioridade:** Baixa — e um botao de texto, nao quebrado. Fora do escopo
imediato se o foco e icones de transporte + campos.

---

## Plano de implementacao

### Task A: Corrigir padding dos `DashboardChip` (Issue 1)

**Files:**
- Modify: `src/trackclassifier/ui/app.qss` (ou `design/design-tokens.json`
  + `design/build_tokens.py` se houver token de padding)
- Test: existente (`tests/test_review_widgets.py` ou `tests/test_window.py`)
  continua valendo; acrescentar assert de largura minima se houver

**Steps:**
- [ ] Step 1: Confirmar que `padding: 4px 8px` e o unico lugar — sim,
  `app.qss:104`
- [ ] Step 2: Mudar para `padding: 2px 6px`
- [ ] Step 3: Rodar `uv run pytest tests/test_review_widgets.py -v`
- [ ] Step 4: `uv run ruff check .`
- [ ] Step 5: Commit

### Task B: Unificar altura dos `ClassActionCard` (Issue 2)

**Files:**
- Modify: `src/trackclassifier/ui/widgets/class_action_card.py` (remover
  `setMinimumHeight(76)`)
- Modify: `src/trackclassifier/ui/app.qss` (mudar `min-height: 90px` para
  `min-height: 76px` ou token)
- Test: `tests/test_review_widgets.py` (se existir teste de altura)

**Steps:**
- [ ] Step 1: Remover `setMinimumHeight(76)` do codigo
- [ ] Step 2: Verificar `design/build_tokens.py` para ver se `SIZE_CONTROL_CLASS_CARD`
  pode ser usado no QSS (ou hardcode 76px)
- [ ] Step 3: Atualizar QSS
- [ ] Step 4: Rodar `uv run pytest`
- [ ] Step 5: Lint e commit

### Task C: Icones SVG para transporte (Issue 3)

**Files:**
- Modify: `src/trackclassifier/ui/widgets/player_bar.py` (trocar unicode
  por `QIcon` dos SVG's)
- Modify: `src/trackclassifier/ui/app.qss` (ajustar estilos de botao se
  necessario — o QSS atual pode ter regras especificas para botao de texto)
- Test: `tests/test_player_bar.py` (adaptar `texto_do_botao` — agora sera
  vazio; usar `icon().isNull()` para verificar)

**Steps:**
- [ ] Step 1: Confirmar padrao de carregamento de icons — `icons.py::icon(nome, cor, tamanho)`, usado em `app_header.py:114-118` e `:34-49`
- [ ] Step 2: Trocar `_PLAY`/`_PAUSE`/previous/next por `QIcon`
- [ ] Step 3: Adaptar testes (`test_botao_reflete_o_estado_do_player` checa
  `texto_do_botao` — precisa mudar para checar `icon()`)
- [ ] Step 4: `uv run pytest tests/test_player_bar.py -v`
- [ ] Step 5: `uv run pytest` inteiro
- [ ] Step 6: Lint e commit

### Task D: Ligar `GuessBar` no header (Issue 4)

**Files:**
- Modify: `src/trackclassifier/ui/widgets/review_header.py` (substituir
  prediction/confidence inline por `GuessBar`)
- Test: `tests/test_review_widgets.py` (se testa header)

**Steps:**
- [ ] Step 1: Importar `GuessBar` em `review_header.py`
- [ ] Step 2: Remover widgets `prediction`, `confidence`, `confidence_bar`
  do `__init__`
- [ ] Step 3: Instanciar `GuessBar` no lugar — manter no stat card ou por
  fora? O mockup r2 mostra o GuessBar como uma faixa separada, nao dentro
  do card. Decidir layout.
- [ ] Step 4: Chamar `guess_bar.set_guess(label, confidence, low_confidence)`
  no `set_track`
- [ ] Step 5: Manter stat card de progresso separado
- [ ] Step 6: `uv run pytest tests/test_review_widgets.py -v`
- [ ] Step 7: `uv run pytest` inteiro
- [ ] Step 8: Lint e commit

### Task E: Ligar `UpcomingList` na Revisao (Issue 5)

**Files:**
- Modify: `src/trackclassifier/ui/review_tab.py` (trocar `ReviewQueueStrip`
  por `UpcomingList`)
- Modify: `src/trackclassifier/ui/widgets/upcoming_list.py` (talvez adaptar
  `set_rows` — aceita `(rows)` sem `remaining`/`atual`)
- Delete: `src/trackclassifier/ui/widgets/review_queue.py` (se `ReviewQueueStrip`
  for exclusivo da Revisao)
- Delete: `tests/test_dashboard_widgets.py` (se for exclusivo do queue strip)

**Steps:**
- [ ] Step 1: Verificar se `ReviewQueueStrip` e usado fora da Revisao
  — grep confirma: so em `review_tab.py`
- [ ] Step 2: Verificar assinatura de `UpcomingList.set_rows` vs chamada
  atual — `ReviewQueueStrip.set_rows(rows, *, remaining, atual)` vs
  `UpcomingList.set_rows(rows)`
- [ ] Step 3: Adaptar chamada em `_atualiza_exibicao`
- [ ] Step 4: Remover `ReviewQueueStrip`/`review_queue.py` se nao reusado
- [ ] Step 5: `uv run pytest tests/test_review_widgets.py -v`
- [ ] Step 6: `uv run pytest` inteiro
- [ ] Step 7: Lint e commit

### Task F: Remover dead code `_coluna_da_key()` (Issue 6)

**Files:**
- Modify: `src/trackclassifier/ui/review_tab.py` (remover metodo)
- Test: nenhum (nao ha teste)

**Steps:**
- [ ] Step 1: Verificar uso de `estiliza_label` e `SPACE_2` no resto do
  arquivo antes de remover imports
- [ ] Step 2: Remover metodo e imports nao-usados
- [ ] Step 3: `uv run ruff check .` (isso sobrara imports nao usados)
- [ ] Step 4: `uv run pytest tests/test_review_widgets.py -v`
- [ ] Step 5: Commit

---

## Ordem e dependencias

- Task F (dead code) pode ir primeiro — isolado, sem risco
- Task A (padding) e Task B (altura card) sao estilisticas e independentes
- Task C (icones) e Task D (GuessBar) sao independentes entre si
- Task E (UpcomingList) depende de analisar se `ReviewQueueStrip` e reusado
  na Biblioteca — confirmado: nao e. Pode vir em qualquer ordem relativa
  aas outras
- `uv run pytest` inteiro roda a cada commit que toca `ui/` (gate do CI)

## Referencias cruzadas

- Spec: `docs/superpowers/specs/2026-08-07-aba-revisao-design.md`
- Plano original: `docs/superpowers/plans/2026-08-07-telas-v02-fase-3-revisao.md`
- Tokens: `src/trackclassifier/ui/tokens.py`, `design/design-tokens.json`
- Build de tokens: `design/build_tokens.py`
