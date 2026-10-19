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

- [x] **Step 1:** `uv run python design/render_biblioteca.py` e comparar com
      `bib_antes.png` e com o mockup (estado de repouso, 1512x1037, acervo real).
      Achou dois defeitos no chip, corrigidos em `4ccffc7`: os chips saiam
      VAZIOS (`QPushButton::sizeHint()` ignora o layout dos filhos) e o texto
      ficava cinza (regra QSS de descendente nao chega no `QLabel` filho). Depois
      do conserto o recorte da barra bate: rotulo em sans, contagem em mono, cor
      da classe no texto e o chip aceso com fundo e borda da classe.
- [x] **Step 2:** Estados. Biblioteca vazia (chips em zero e desabilitados, texto
      apagado) e acervo cheio foram conferidos POR PIXEL, com o `diag_cor.py`;
      busca sem resultado, selecao e sem buckets seguem cobertos por teste
      (`test_library_tab`, `test_delegates`) e NAO foram olhados a olho nesta
      passada, porque o `render_biblioteca.py` so rende o repouso -- conferir a
      olho exigiria um argumento de estado no script.
- [x] **Step 3:** Registrar aqui o que destoou. **Step 4:** Commit.

**O que destoou do mockup (estado de repouso):**

- Barra: no mockup a busca ocupa ~1/4 da largura e os chips vem logo depois; aqui
  ela estica e empurra chips e combos para a direita. Micro-labels acima dos
  controles e o botao de lista no fim da barra ainda nao existem (Fase 2).
- Colunas `#`, ARQUIVO e a de acoes (`⋯`) nao existem ainda (Fase 3). Checkbox de
  selecao multipla: fora de escopo, por decisao do design.
- CLASSE: o mockup usa badge com o nome ("neutra"); aqui segue a escala ordinal de
  tres segmentos (divergencia consciente, registrada no design).
- Celula TITULO: no mockup sao duas linhas (titulo e artista); aqui e uma so, com
  o artista depois do titulo. Altura de linha 44px aqui, ~54px no mockup.
- Inspector: vazio neste render (nada selecionado), com as acoes rapidas em
  retangulos de borda; no mockup a ficha inteira, com ponto colorido por classe
  nas acoes (Fase 4).
- Rodape: barra de player no mockup (capa, shuffle, repeat, volume, fila); aqui
  HintBar de atalhos + StatusStrip -- fora do escopo das fases 1 a 4.
- Controles que existem aqui e nao estao no mockup: o combo "Camelot" e o
  Segmented de densidade (CONFORTAVEL/COMPACTA).
- Cabecalho: o mockup tem "Tabela | Cards" e "Colunas" a direita do titulo (Cards
  esta parqueado; "Colunas" nao entrou no escopo aprovado).
- Contagem do topo: duas linhas com icone no mockup; aqui uma linha, e o mesmo
  numero aparece de novo na StatusStrip.

## Fase 2 — filtros

### Task 2.1: busca por album

**Ruling ao implementar:** os micro-labels saem desta task e vao para a 2.2,
junto dos tres combos que eles rotulam (`Genero`, `Key`, `Ordenar por` -- os
unicos que o design nomeia). Na 2.1 a barra so tem busca, chips, notacao e
densidade: micro-label sobre eles nao esta no design, e um helper de micro-label
sem chamador seria codigo morto. O teste de "nao quebra a linha" vai junto,
porque so faz sentido quando a barra tem os controles que podem quebrar.

- [x] **Step 1:** Testes — `_casa` acha por album (e termo ausente de titulo,
      artista, album e arquivo continua nao casando); o placeholder cita album.
- [x] **Step 2:** Rodar e ver falhar -- os dois falharam pelo motivo certo (album
      ignorado, placeholder sem album). **Step 3:** Implementado em
      `library_tab.py` (`_casa` e o placeholder).
- [x] **Step 4:** Rodar e ver passar (ruff limpo, suite inteira). **Step 5:**
      Commit. Os testes de album sao puros; so o do placeholder monta a aba.

### Task 2.2: combos de Genero, Key e Ordenar por

- [x] **Step 1:** Testes — os valores de Genero saem do estado, ordenados e sem
      repeticao, com "Todos" na frente; Key sai em ordem de roda; escolher um
      Genero restringe as linhas; "Ordenar por" muda a ordem do modelo e o
      indicador do cabecalho, e nao so o combo. Cada combo tem micro-label
      acima (`Genero`, `Key`, `Ordenar por` -- chegou da 2.1).
- [x] **Step 2:** Rodar e ver falhar -- 7 testes, todos pelo motivo certo
      (campos do `LibraryState` e atributos da aba que ainda nao existiam).
      **Step 3:** Implementado: derivacao pura no viewmodel
      (`_generos_do_acervo`, `_keys_em_ordem_de_roda`) mais `genres`/`keys` no
      `LibraryState`; na aba, os tres combos com micro-label, os dois filtros
      somando ao que chips e busca ja restringiram, e
      `_aplica_ordenacao`/`_espelha_ordenacao` ligando combo e indicador nos
      dois sentidos.
- [x] **Step 4:** Rodar e ver passar (818 passed; ruff limpo com um `--fix` de
      import). **Step 5:** Commit.

**Rulings desta task:**

- **"A barra nao quebra a linha" nao virou teste**: o Qt nao faz wrap de
  `QHBoxLayout`, entao um teste disso passaria por construcao. O risco real --
  barra alta demais, micro-label desalinhado do controle -- so se ve no render.
  Fica para a conferencia visual, como na 1.5.
- **"Ordenar por" usa `Column.header`** (caixa alta) em vez de uma segunda lista
  de nomes em caixa mista: e a unica fonte dos nomes das colunas, e "espelha o
  cabecalho" fica literal. Os itens sao `COLUNA (A-Z)` e `COLUNA (Z-A)`; CAPA e
  WAVEFORM ficam de fora porque `TrackTableModel.sort()` recusa as duas.
- **As keys do combo saem sempre em Camelot**, mesmo com a notacao classica
  ligada: a ordem da roda e a mesma nos dois casos, e trocar de notacao nao pode
  reordenar o combo na frente do usuario.
- `_notacao` (Camelot/Classica) e o Segmented de densidade continuam **sem**
  micro-label, porque o design nomeia so os tres combos -- agora sao dois
  controles sem rotulo convivendo com tres rotulados. Anotado como follow-up.

## Fase 3 — colunas `#` e de acoes

### Task 3.1: coluna `#`

**Files:** Modify `ui/widgets/track_model.py`, `ui/widgets/library_header.py`,
`ui/library_tab.py`; Test `tests/test_library_tab.py`,
`tests/test_library_header.py`

- [x] **Step 1:** Testes — `INDICE` e a coluna 0 e empurra as outras; o numero e
      a posicao na lista exibida (depois de ordenar e filtrar, 1..N sem buraco);
      `INDICE` e `ACOES` entram em `SEM_ORDEM` e ganham alinhamento proprio no
      `ALINHAMENTO`; a coluna nao ordena.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar (`Column.INDICE` no
      inicio, `_WIDTHS`/`_ESTILO_POR_COLUNA`, `DisplayRole` = `row + 1`, mapas do
      cabecalho atualizados).
- [x] **Step 4:** Medir o `data()` de novo (o numero de chamadas nao pode
      crescer mais que linearmente com as colunas novas). **Step 5:** Commit.

**Fechada** (`affe429`). Um teste antigo quebrou de proposito no Step 3 e foi
atualizado: `tests/test_window.py::test_table_model_expoe_as_colunas_da_rodada_3a`
congela os cabecalhos da rodada, entao passou a esperar `#` na frente e `""` no
fim. Teste a mais, fora do Step 1: o combo "Ordenar por" nao oferece `INDICE`
nem `ACOES` (ele e montado do enum, uma coluna nova entraria sozinha).
Medicao do Step 4 feita pelo caminho real, o render de 463 linhas com os
delegates: 1,77s antes x 1,43s depois -- mesmo patamar.

### Task 3.2: coluna de acoes

**Files:** Create `src/trackclassifier/ui/widgets/actions_delegate.py`; Modify
`ui/library_tab.py`, `ui/window.py` (liga `remove_requested` ao worker);
Test `tests/test_library_tab.py`

- [x] **Step 1:** Testes — o menu tem as tres classes, revelar e remover;
      escolher uma classe emite `decide_requested` com a sha1 da LINHA do indice
      clicado (nao da linha selecionada); remover emite `remove_requested(sha1)`;
      clique fora da coluna ACOES nao abre menu.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

**Fechada** (`e163526`). O que o plano nao previa:

- **O remover CONFIRMA, e a Revisao nao.** La o remover e o fluxo principal e
  a lixeira e a rede documentada no docstring dele; aqui a coluna fica colada
  em `Revelar`, que e inofensiva — sem confirmacao, um escorregar de mouse
  apaga a linha em silencio. Testado nos dois sentidos (Sim emite, Nao nao).
- `Revelar no Finder` virou **funcao pura de comando por plataforma**
  (`open -R` / `explorer /select,` / `xdg-open`): testar o caminho real abriria
  a janela na suite, e o CI roda em Linux.
- Os rotulos das tres classes saem de `LABELS_EM_ORDEM`, e nao de strings
  novas no menu: e a mesma fonte do teclado 1/2/3, dos chips e da Revisao.
- O glifo usa **fonte e cor do MODELO** (FontRole/ForegroundRole), e nao
  constante do delegate: `Column.ACOES` passou a ter mono/`text.muted` no
  `_ESTILO_POR_COLUNA`, como a coluna `#` vizinha.
- **Conferido no render (463 linhas), e nao so por teste**: o `…` sai centrado
  e apagado em todas as linhas. Desta vez o render confirmou em vez de
  corrigir — mas foi ele que fechou as duas tasks anteriores.

## Fase 4 — inspector em ficha tecnica

### Task 4.1: a ficha

- [x] **Step 1:** Testes — a ficha mostra Genero/BPM/Key/Duracao/Classe;
      `Confianca` so aparece quando `confidence` nao e `None`; sem key nao ha
      chip (travessao); capa ausente cai no placeholder.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

**Fechada** (`c62fa55`). O que o plano nao previa:

- O par reusa os objectNames do rodape tecnico (`TechDetailLabel`/
  `TechDetailValue`): o QSS do par ja existe, e criar `Inspector*` seria uma
  regra nova para a mesma coisa — com o gerador de tokens em uso por outra
  frente nesta rodada. A familia mono entra por estilo **inline**, porque a
  regra do `TechDetailValue` fixa a sans (mesmo motivo do `_BASE` do
  `KeyChip`).
- Teste antigo atualizado: `test_dashboard_widgets.py::
  test_fila_e_inspector_refletem_a_track_sem_acao_falsa` cravava
  `"Classe: -1" in inspector.details.text()`, e `details` deixou de existir.
- A capa foi de 96 para 120px (`QSize(120)` do design): nenhum teste cravava o
  lado, e 120 cabe no painel de 260 com as margens.
- `set_track(None)` **ja nao desabilita o painel**: o estado vazio mantem a
  anatomia. As acoes ainda ficam habilitadas sem selecao — e o resto da 4.2.

### Task 4.2: estado vazio do inspector

- [x] **Step 1:** Testes — sem selecao NAO usa `setEnabled(False)` no painel
      inteiro; a anatomia permanece (capa fantasma, campos vazios, acoes
      desabilitadas); selecionar uma linha preenche sem trocar de layout.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

**Fechada** (`a0cbfa8`). O que o plano nao previa:

- A 4.1 ja tinha feito metade: `set_track(None)` deixou de desabilitar o painel
  naquele commit. Aqui entrou o resto — as **ações** desligam sozinhas
  (`self.play`, `self.class_buttons`) e a capa do vazio ganhou a moldura
  compartilhada (`_ESTILO_CAPA_FANTASMA`, a mesma do par sem capa).
- `play` e as três de classe **viraram atributos**: eram variáveis locais do
  `__init__`, e sem referência não há como desligar a ação sem desligar o
  painel — que é exatamente o que o design proíbe.
- O teste de "não troca de layout" crava a **identidade** dos widgets e a
  contagem de itens do layout nos dois estados: é o que garante que a
  `Confianca` seja uma caixa escondida (aparece e some) e não uma linha criada
  na hora.

### Task 4.3: onda com seek

- [x] **Step 1:** Testes — clicar na onda pede seek para a fracao
      correspondente; a onda usa buckets quando existem e a curva quando nao;
      sem track nao ha seek.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar (reusar
      `waveform_view`/`waveform_render`; `player.seek(ms)` se faltar).
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

**Fechada** (`c053835`). O que o plano nao previa:

- `player.seek(ms)` **já existia** (e `seek_fraction` também): o "se faltar" não
  foi acionado, e o clique sai como **fração** — quem vira ms é o player.
- O clique vale posição **só quando a linha selecionada é a carregada**. O
  player é um só pro app e a seleção pode apontar para outra track; sem a guarda
  o clique moveria a música que soa, em silêncio (nada na tela aponta para o
  player). A mesma guarda protege o playhead — media A sobre a onda de B é pior
  que playhead nenhum. Testada nos dois sentidos.
- O `WaveformView` emite o clique **sempre** (não sabe o que desenha), então a
  guarda do "sem track não há seek" é do inspector, que passou a guardar
  `self._row`.
- A seleção virou método: agora são três coisas (ficha, onda e playhead), e a
  terceira não pode ser esquecida por quem mexer na primeira.
- Segue em aberto, de propósito: tocar a partir do ponto clicado quando a track
  não está carregada (o `QMediaPlayer` ignora seek antes do load) e pedir os
  buckets da selecionada quando ela está fora do viewport.

### Task 4.4: acoes rapidas e acoes de arquivo

- [x] **Step 1:** Testes — os tres alvos emitem `classify_requested`; o digito do
      atalho aparece; revelar usa `path_hint`; remover pede confirmacao e so
      entao emite `remove_requested`.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

**Fechada** (`e44828f`). O que o plano nao previa:

- As ações de arquivo levam **sha1**, não o caminho: `path_hint`, a confirmação e
  o comando por plataforma já existiam na aba desde a 3.2, e o painel passa pelas
  mesmas portas (`_revelar`, `_remove_com_confirmacao`). A pergunta do remover
  mora num lugar só — duplicar daria duas versões do único fluxo destrutivo.
- O dígito/tecla entra no idioma do `ClassActionCard` (`QLabel#Kbd` alinhado à
  direita, filhos transparentes ao mouse): o QSS já tem a regra, sem objectName
  novo no gerador.
- `Reproduzir` mudou de lugar: foi para o grupo "Ações de arquivo", com revelar e
  remover — tocar é do arquivo, não da classificação.
- O tom de danger do remover é um estilo **inline** (`COLOR_STATE_DANGER`): não há
  regra de QSS para botão danger. O tom, o espaço e o `Kbd` em botão estreito
  ficam para a conferência do render na 4.5, junto com o painel preenchido.

### Task 4.5: ver com os proprios olhos (final)

- [x] **Step 1:** Render final contra o mockup, lado a lado com `bib_antes.png`.
- [x] **Step 2:** Conferir os cinco estados da tabela do design.
- [x] **Step 3:** Registrar os desvios que ficaram. **Step 4:** Commit.

**Fechada.** Renders em `repouso`, `selecao` e `vazio` (1512x1037, acervo real
de 463 tracks) comparados com o mockup e com o `bib_antes.png`. Os cinco
estados:

- **Biblioteca vazia** — render: quatro chips em zero e desabilitados (o ruling
  da 1.3, nao o "chip unico" do design), EmptyState com Escanear, inspector na
  anatomia vazia. Confere.
- **Busca sem resultado** — nao renderizada ("so o cabecalho, como hoje", e o
  script nao tem estado para ela); coberta por `test_library_tab.py`
  (`test_busca_sem_resultado_tem_estado_proprio` e vizinhos de copy).
- **Selecao** — render: linha acesa, ficha preenchida (capa 120px, par de
  campos, onda espectral com reguas 0:00/3:00/6:00 e badge PICO), acoes com
  kbd 1/2/3/Space. Confere.
- **Sem buckets** — coberta por `test_dashboard_widgets.py` (queda para a curva
  mono); no render todas as linhas visiveis tinham buckets em cache.
- **Track removida** — confirmada no codigo: `set_state` → `_reaplica_filtros`
  → `inspector.set_track(None)`, e a linha some no reset do modelo; a emissao
  com confirmacao esta em `test_remover_no_menu_pede_confirmacao_antes_de_emitir`
  e `test_as_acoes_de_arquivo_do_inspector_passam_pelas_portas_da_aba`.

**Desvios que ficaram (todos conscientes ou ja registrados):**

- Coluna CLASSE segue na escala ordinal de tres segmentos (a troca pelo chip de
  texto e fora de escopo no design). Sem checkbox, sem Tabela/Cards/Colunas,
  sem abas do inspector, sem "Adicionar a fila", sem ARTISTA repetida — idem.
- **Achado novo desta rodada**: os botoes de acao do inspector sao
  VISUALMENTE IDENTICOS habilitados e desabilitados (crop pixel a pixel dos
  tres renders). O comportamento esta testado (`isEnabled()`), mas o QSS nao
  tem regra `:disabled` para eles — o usuario nao ve o estado. Follow-up:
  regra `:disabled` no template do `build_tokens.py`.
- O tom de danger do "Remover da biblioteca" e inline (`COLOR_STATE_DANGER`,
  ruling da 4.4): no render le bem, mas segue fora do QSS — junta no mesmo
  follow-up de regra de botao.
- As reguas de tempo da onda do inspector ("0:00 3:00 6:00" e o badge PICO)
  encostam no topo da curva; legivel, mas apertado. Cosmetico, nao registrado
  como defeito.
- Cabecalho da tabela diz `DUR` (o mockup diz `DURACAO`): heranca do modelo de
  colunas, fora desta rodada.
- Abas Modelo/Configuracao com glifos provisorios no lugar de icones: drift
  conhecido, enderecado pela frente de icones da Revisao (rodada 2), fora
  deste plano.
- Player bar do mockup nao existe na Biblioteca: a reproducao e pelo inspector
  (ruling da 4.4). Registrado na 1.5, mantido.

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
