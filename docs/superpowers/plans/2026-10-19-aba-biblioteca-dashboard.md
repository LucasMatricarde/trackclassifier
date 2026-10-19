# Aba Biblioteca — rodada de fidelidade ao dashboard — plano de implementacao

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development ou superpowers:executing-plans.

**Goal:** Tornar a Biblioteca fiel ao mockup do dashboard
(`design/mockup/TrackClassifier Music Library Dashboard.png`) sobre os tokens
v0.5, trazendo para a tela o que ja existe no servico (contagem por classe,
album, key, genero, remover) e dando ao inspector a anatomia de ficha tecnica.

**Architecture:** `LibraryTab` continua sendo o layout e a traducao de
`LibraryState`; o que ganha desenho proprio sai para `ui/widgets/`
(`class_chips.py`, `actions_delegate.py`, `inspector_*`). `viewmodel.py`
continua sem Qt. Os quatro sinais publicos **nao mudam**; `remove_requested` e
adicao.

Depende de: `specs/2026-10-19-aba-biblioteca-dashboard-design.md`.

## Global Constraints

- Portugues sem acentos no codigo; API publica em ingles.
- Nenhum `#RRGGBB` fora do JSON, inclusive em docstring. Cor derivada vem de
  `colors.tinta()`/`para_qcolor()`.
- `ui/viewmodel.py` nao importa Qt (ha teste).
- `TrackTableModel.data()` e caminho quente (~88 mil chamadas num scroll):
  coluna nova nao constroi objeto por celula.
- Todo filtro novo passa por `_reaplica_filtros` → `_agenda_peaks`.
- So a thread do `ServiceWorker` fala com `TrackService`.
- `SEM_ORDEM` e `ALINHAMENTO` (library_header) sao por indice CRU: mexer nas
  colunas obriga a mexer nos dois.
- Depois de cada task: `uv run pytest` e `uv run ruff check .` limpos, e um
  commit (`feat(ui):`, `fix(ui):`, `test(ui):`).

## Fase 0 — destravar (feita)

- [x] **Task 0.1:** regenerar `ui/tokens.py` + `ui/app.qss` da v0.5 que estava no
      JSON sem os gerados (`cdf6b27`).
- [x] **Task 0.2:** `design/render_biblioteca.py` — render offscreen da aba com o
      acervo real, somente leitura, para o antes/depois. Nao chama `analyze_all`,
      nao computa buckets, neutraliza o scan do boot e processa `DeferredDelete`
      (sem isso o `HintBar` sai duplicado na imagem).

## Fase 1 — cabecalho e chips de classe

### Task 1.1: `color.surface.hover`

**Files:** Modify `design/design-tokens.json`, `design/build_tokens.py`;
Regenerate `src/trackclassifier/ui/tokens.py`, `src/trackclassifier/ui/app.qss`;
Test `tests/test_tokens.py`

- [ ] **Step 1:** Teste — `COLOR_SURFACE_HOVER` existe e e diferente de
      `COLOR_SURFACE_0` (com `surface.1` ≈ `surface.0` depois da v0.5, um hover
      igual ao fundo e a mesma coisa que hover nenhum).
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Adicionar `color.surface.hover` ao JSON (`$changelog` com a
      razao) e trocar `{surface1}` por `{surfaceHover}` em
      `QTableView::item:hover` no template do `build_tokens.py`.
- [ ] **Step 4:** `uv run python design/build_tokens.py`, rodar e ver passar.
- [ ] **Step 5:** Commit.

### Task 1.2: `LibraryState` com contagens e `TrackRow.album`

**Files:** Modify `ui/viewmodel.py`, `src/trackclassifier/ui/library_tab.py`;
Test `tests/test_viewmodel.py` (ou o teste que cobre `library_state`)

- [ ] **Step 1:** Testes — `library_state` devolve `class_counts` com tres
      posicoes na ordem de `LABEL_ORDER` e `total` igual ao numero de rotuladas;
      biblioteca vazia devolve `(0, 0, 0)` e `0`; `TrackRow.album` chega do
      `PresentationCache`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar: `class_counts: tuple[int, ...]` e `total: int` no
      `LibraryState` (default `(0, 0, 0)`/`0` para nao quebrar construcao
      posicional), `album: str | None = None` no `TrackRow`, e o preenchimento
      em `library_state` com `service.class_counts()`.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 1.3: widget `ClassChips`

**Files:** Create `src/trackclassifier/ui/widgets/class_chips.py`; Modify
`design/build_tokens.py` (QSS); Regenerate `app.qss`; Test
`tests/test_class_chips.py`

- [ ] **Step 1:** Testes — ordem dos chips e `Todos` primeiro, depois
      `LABEL_ORDER`; `mudou` emite o rotulo e **so quando muda**; clicar no chip
      aceso nao emite; `set_contagens((71, 186, 206), 464)` escreve `464` no
      chip `Todos` e os tres numeros nos outros; `set_contagens` com biblioteca
      vazia nao esconde chip nenhum; `rotulo_ativo()`/`acionar(rotulo)` existem
      para o teste usar o mesmo caminho do clique.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar `ClassChips` (`QButtonGroup` exclusivo, um
      `QPushButton#ClassChip` por rotulo com dois `QLabel` filhos — sans e mono —
      marcados `WA_TransparentForMouseEvents`, `setFixedHeight(SIZE_CONTROL_BASE)`
      para alinhar com o `Segmented` ao lado). QSS novo no template:
      `QPushButton#ClassChip`, `:hover`, `:checked` (mesma superficie de
      `Segment:checked`), `QLabel#ClassChipLabel`, `QLabel#ClassChipCount`.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 1.4: a aba usa os chips e o cabecalho de tela

**Files:** Modify `ui/library_tab.py`, `design/build_tokens.py` (QSS
`ScreenTitle`/`ScreenSubtitle`); Test `tests/test_library_tab.py`

- [ ] **Step 1:** Testes — `set_state` escreve as contagens nos chips; filtrar
      por chip restringe as linhas; `_acao_sem_resultado("Filtro: todos")`
      devolve o chip "Todos" ao estado aceso; o titulo usa `#ScreenTitle` e ha
      `#ScreenSubtitle` com a copy do design. Substituir todo
      `aba._filtro.setCurrentText(...)` por `aba._chips.acionar(...)`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar: remover o `QComboBox` `_filtro` e o `_TODOS` como
      texto de combo; `_reaplica_filtros` le `self._chips.rotulo_ativo()`;
      cabecalho em `ScreenTitle` + `ScreenSubtitle`; `Segmented` da densidade
      continua ao lado dos combos que restarem.
- [ ] **Step 4:** `uv run pytest` inteiro (a suite da Revisao compartilha
      `MainWindow`, nada dela pode quebrar). **Step 5:** Commit.

### Task 1.5: ver com os proprios olhos

- [ ] **Step 1:** `uv run python design/render_biblioteca.py` e comparar com
      `bib_antes.png` e com o mockup.
- [ ] **Step 2:** Conferir os estados: biblioteca vazia, busca sem resultado,
      selecao, sem buckets.
- [ ] **Step 3:** Registrar aqui o que destoou. **Step 4:** Commit.

## Fase 2 — filtros

### Task 2.1: busca por album e micro-labels

- [ ] **Step 1:** Testes — `_casa` acha por album; o placeholder cita album;
      micro-label existe acima de cada controle e nao quebra a linha.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 2.2: combos de Genero, Key e Ordenar por

- [ ] **Step 1:** Testes — os valores de Genero saem do estado, ordenados e sem
      repeticao, com "Todos" na frente; Key sai em ordem de roda; escolher um
      Genero restringe as linhas; "Ordenar por" muda a ordem do modelo e o
      indicador do cabecalho, e nao so o combo.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

## Fase 3 — colunas `#` e de acoes

### Task 3.1: coluna `#`

**Files:** Modify `ui/widgets/track_model.py`, `ui/widgets/library_header.py`,
`ui/library_tab.py`; Test `tests/test_library_tab.py`,
`tests/test_library_header.py`

- [ ] **Step 1:** Testes — `INDICE` e a coluna 0 e empurra as outras; o numero e
      a posicao na lista exibida (depois de ordenar e filtrar, 1..N sem buraco);
      `INDICE` e `ACOES` entram em `SEM_ORDEM` e ganham alinhamento proprio no
      `ALINHAMENTO`; a coluna nao ordena.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar (`Column.INDICE` no
      inicio, `_WIDTHS`/`_ESTILO_POR_COLUNA`, `DisplayRole` = `row + 1`, mapas do
      cabecalho atualizados).
- [ ] **Step 4:** Medir o `data()` de novo (o numero de chamadas nao pode
      crescer mais que linearmente com as colunas novas). **Step 5:** Commit.

### Task 3.2: coluna de acoes

**Files:** Create `src/trackclassifier/ui/widgets/actions_delegate.py`; Modify
`ui/library_tab.py`, `ui/window.py` (liga `remove_requested` ao worker);
Test `tests/test_library_tab.py`

- [ ] **Step 1:** Testes — o menu tem as tres classes, revelar e remover;
      escolher uma classe emite `decide_requested` com a sha1 da LINHA do indice
      clicado (nao da linha selecionada); remover emite `remove_requested(sha1)`;
      clique fora da coluna ACOES nao abre menu.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

## Fase 4 — inspector em ficha tecnica

### Task 4.1: a ficha

- [ ] **Step 1:** Testes — a ficha mostra Genero/BPM/Key/Duracao/Classe;
      `Confianca` so aparece quando `confidence` nao e `None`; sem key nao ha
      chip (travessao); capa ausente cai no placeholder.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 4.2: estado vazio do inspector

- [ ] **Step 1:** Testes — sem selecao NAO usa `setEnabled(False)` no painel
      inteiro; a anatomia permanece (capa fantasma, campos vazios, acoes
      desabilitadas); selecionar uma linha preenche sem trocar de layout.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 4.3: onda com seek

- [ ] **Step 1:** Testes — clicar na onda pede seek para a fracao
      correspondente; a onda usa buckets quando existem e a curva quando nao;
      sem track nao ha seek.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar (reusar
      `waveform_view`/`waveform_render`; `player.seek(ms)` se faltar).
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 4.4: acoes rapidas e acoes de arquivo

- [ ] **Step 1:** Testes — os tres alvos emitem `classify_requested`; o digito do
      atalho aparece; revelar usa `path_hint`; remover pede confirmacao e so
      entao emite `remove_requested`.
- [ ] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 4.5: ver com os proprios olhos (final)

- [ ] **Step 1:** Render final contra o mockup, lado a lado com `bib_antes.png`.
- [ ] **Step 2:** Conferir os cinco estados da tabela do design.
- [ ] **Step 3:** Registrar os desvios que ficaram. **Step 4:** Commit.

## Fora de escopo

Ver a secao homonima do design: BPM por faixa, "adicionar a fila de revisao",
view Cards, checkbox de selecao multipla, abas do inspector, coluna ARTISTA
repetida, e a troca da escala ordinal pelo chip de texto na coluna CLASSE.

## Riscos

- `library_tab.py` (556 linhas) nao pode engordar: desenho sai para `widgets/`.
- `SEM_ORDEM`/`ALINHAMENTO` por indice cru: e o ponto mais facil de quebrar em
  silencio ao inserir coluna nas duas pontas.
- `tests/test_library_tab.py` acessa `aba._filtro`: a troca por chips e a
  substituicao do acesso fazem parte da Task 1.4, nao um efeito colateral.
