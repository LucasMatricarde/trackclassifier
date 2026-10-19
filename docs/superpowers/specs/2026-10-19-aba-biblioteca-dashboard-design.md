# Aba Biblioteca — design (rodada de fidelidade ao dashboard)

Data: 2026-10-19

## Objetivo

Fechar a rodada de fidelidade ao mockup do dashboard na última aba que ainda não
passou por ela — a Revisão passou em `abc1c16`. Referência visual:
`design/mockup/TrackClassifier Music Library Dashboard.png`.

Não é uma tela nova. É (a) tornar visível o que já existe no serviço e hoje não
chega à tela, e (b) alinhar a Biblioteca à linguagem "instrumento" que a Revisão
já fala: contagem por classe, filtro por gênero e key, numeração de linha, ações
por linha e um inspector que é uma ficha técnica em vez de um `QLabel`
multilinha.

Depende de: `docs/superpowers/specs/2026-08-07-aba-revisao-design.md` (a
linguagem da Revisão, que a Biblioteca passa a espelhar) e da v0.5 dos tokens
já regenerada (`cdf6b27`).

## O que já existe e este trabalho não pode quebrar

- `ui/library_tab.py` — `LibraryTab` com os sinais `decide_requested(str, str)`,
  `peaks_requested(str, str)`, `notation_changed(object)`, `scan_requested()`.
  **Os quatro continuam com a mesma assinatura.** `remove_requested(str)` é
  adicionado: é sinal novo, não mudança de contrato.
- **A contenção de peaks** (`MAX_PEAKS_EM_VOO = 3`, `ATRASO_PEAKS_MS = 250`) e o
  caminho único `_reaplica_filtros` → `_agenda_peaks`. Filtro novo que esconda
  linhas precisa continuar passando por lá: quem pede buckets é a aba, olhando o
  viewport, e nunca um `paint()`.
- `ui/viewmodel.py` **não importa Qt** (há teste que falha se importar).
- `TrackTableModel.data()` é caminho quente: ~88 mil chamadas num scroll de 354
  linhas (medido). As colunas novas não podem construir objeto por célula.
- `PixmapCache` por `(sha1, modo, w, h)`; nenhum `paint()` decodifica áudio.
- `LibraryHeader.paintSection` desenhado à mão, `SEM_ORDEM = (0, 2)` por índice
  cru, e a reversão do indicador em `sortIndicatorChanged`.
- **Nenhum `#RRGGBB` fora do `design/design-tokens.json`** (há teste que varre
  `ui/`). Cor derivada vem de `colors.tinta()`/`para_qcolor()`.
- Estados vazios, densidade e o `Segmented` continuam como estão.

## Efeito colateral da v0.5 que este design assume

A regeneração dos tokens (`cdf6b27`) fez `surface.1` e `surface.panel` caírem
para `#09131A`, praticamente igual a `surface.0` (`#0A1119`), o fundo da janela.
Consequência medida no render de antes (`design/render_biblioteca.py`): **os
painéis agora se distinguem só pela borda de 1px**, e o inspector lê como painel
vazio — não porque o desenho dele seja fraco, mas porque o fundo dele deixou de
contrastar. Duas ações entram no escopo por causa disso:

- `color.surface.hover` novo no JSON. `QTableView::item:hover` usa `{surface1}`
  no template do `build_tokens.py`; com `surface.1` ≈ `surface.0` o hover de
  linha ficou invisível. Deixa de ser cosmético: é o único retorno visual de
  "o mouse está nesta linha".
- O inspector ganha **conteúdo estruturado** (ficha técnica), que é o que
  devolve leitura à área sem depender do preenchimento do painel.

Não se mexe no preenchimento dos painéis: a decisão da v0.5 é explícita no
`$changelog` ("o mockup não distingue os dois fundos de chrome") e revertê-la
seria desfazer uma decisão de sistema tomada fora desta tela.

## Decisões de design

### A. Cabeçalho da tela

| Elemento | Como | Token |
| --- | --- | --- |
| "Biblioteca" | `QLabel#ScreenTitle` | `font.size.headline` (24px) + `font.weight.semibold` (600), ambos novos na v0.5 e hoje sem consumidor |
| Linha de apoio | `QLabel#ScreenSubtitle` | `font.size.small` (12px), `text.secondary` |

Hoje o título da aba usa `objectName="ReviewTrackTitle"` (22px), ou seja: o nome
da outra tela. `ScreenTitle` corta essa dependência e dá à Biblioteca o degrau
de hierarquia que o mockup mostra.

Copy da linha de apoio: `Gerencie, visualize e classifique suas musicas.`

### B. Chips de classe com contagem

Widget novo `ui/widgets/class_chips.py` — `ClassChips`, `objectName="ClassChips"`,
sinal `mudou = Signal(str)` emitindo o rótulo (`"Todos"`, `"-1"`, `"neutra"`,
`"+1"`), `QButtonGroup` exclusivo, ordem do mockup: **Todos primeiro, depois
`LABEL_ORDER`**.

Cada chip é um `QPushButton#ClassChip` com dois `QLabel` filhos
(`#ClassChipLabel` em sans e `#ClassChipCount` em mono, com
`WA_TransparentForMouseEvents`). Duas `QLabel` e não uma string concatenada
porque a regra do sistema (`$regra-de-uso.mono-para-numero`) pede o número em
mono e o rótulo em sans: uma string só não carrega duas fontes, e o
`KeyChip` existe pelo mesmo motivo.

Isto substitui o `QComboBox` `_filtro`. O combo dizia "Todos" sem dizer quantos
e, com filtro ligado, escondia que existiam outras 392 tracks — o chip diz as
duas coisas na mesma leitura.

**As contagens são absolutas, não filtradas pela busca.** É o mockup
("neutra 186" continua 186 com a busca ligada) e é o que as torna úteis: com o
filtro já aplicado, uma contagem que encolhesse junto não informaria nada.

Contagens (três, na ordem de `LABEL_ORDER`) e o total entram no `LibraryState`,
não no widget: quem monta a tela continua sendo `library_state(service)`, com
`service.class_counts()` como fonte única — a mesma que a aba Modelo usa.

### C. Filtros

- Busca: incorpora **álbum** (`TrackRow.album` novo, lido de
  `PresentationCache` como `title`/`artist`/`genre` já são). O placeholder passa
  a `Buscar por titulo, artista, album ou arquivo`. O nome do arquivo continua
  no conjunto — metade de um acervo de promos não tem tag nenhuma.
- Micro-labels acima dos controles (`Genero`, `Key`, `Ordenar por`), como no
  mockup: um combo sem rótulo ao lado de outro vira adivinhação depois que os
  dois mostram "Todos".
- `Genero` — valores do acervo, montados do estado (ordenados, sem repetição),
  com "Todos" na frente.
- `Key` — `Todas` + as keys presentes no acervo, em ordem de roda (número
  Camelot, depois modo), não alfabética: é a leitura que a coluna serve.
- `Ordenar por` — espelha o cabeçalho da tabela (`A-Z`/`Z-A` explícito no
  rótulo). Hoje a ordenação só é alcançável clicando no cabeçalho, e o mockup
  mostra as duas portas.

### D. Coluna `#` (numeração de linha)

`Column.INDICE = 0`, mono, `text.muted`, largura 34. **O número é a posição na
lista filtrada e ordenada**, não o índice na `_todas` — é o que faz a coluna
responder "onde estou" e não dar números fora de sequência.

Pintado no `TrackTableModel.data()`: `index.row() + 1` formatado. Sem objeto
novo por célula (caminho quente) e sem `Column` extra na tabela de estilos além
da entrada em `_ESTILO_POR_COLUNA`.

`SEM_ORDEM` e `ALINHAMENTO` do cabeçalho são **por índice cru** e mudam de
posição junto: sem atualizar os dois mapas, a coluna `#` promete ordenação que o
modelo não faz e o cabeçalho desalinha do dado.

### E. Coluna de ações

Última coluna, largura 36, com um `…` desenhado por `ActionsDelegate`. O clique
abre um `QMenu` com: `Classificar como -1/neutra/+1`, `Revelar no Finder`,
`Remover da biblioteca` (danger, com confirmação).

A `QTableView` não emite `clicked` para uma coluna específica de forma
confortável; `LibraryTable` trata em `mousePressEvent` quando
`index.column() is Column.ACOES` e o menu sai de um método só. Reaproveita
`decide_requested` para as três classificações — não é caminho novo de decisão.

`Remover da biblioteca` usa `TrackService.remove()` (send2trash, já existe e já
é usado na Revisão) pela thread do worker: `LibraryTab.remove_requested(str)` →
`ServiceWorker.remove`, como todo o resto.

### F. Inspector como ficha técnica

`TrackInspector` reescrito:

1. Capa (`QSize(120)`) com botão de play circular sobreposto na borda direita e
   `⋮` no canto do painel.
2. Título (`font.size.large`) e artista (`text.secondary`).
3. **Ficha técnica** — pares rótulo esquerda (`text.secondary`, micro) / valor
   direita (mono para número, chip para Key e Classe): `Genero`, `BPM`,
   `Key (Camelot)`, `Duracao`, `Classe atual`, e `Confianca` **apenas quando
   existir**. Na Biblioteca `confidence` é `None` por construção (a track já
   está classificada e a confiança do modelo sobre decisão humana tomada não
   muda ação) — uma linha fixa mostraria um travessão permanente, que é ruído;
   mostrar condicional é a diferença entre "não se aplica" e "faltou dado".
4. Onda com **seek**: a mesma onda da coluna (buckets por banda quando
   existirem, curva mono quando não), com playhead, clicável para posicionar o
   player.
5. `Ações rapidas`: as três classes com o dígito do atalho à direita (o atalho
   existe e não estava escrito em lugar nenhum do painel).
6. Ações de arquivo: `Reproduzir` (Space), `Revelar no Finder`, `Remover da
   biblioteca` (danger).

Sem seleção, o painel **não** fica `setEnabled(False)` com um texto flutuando no
meio: mostra o estado vazio na mesma anatomia (capa fantasma, ficha vazia,
ações desabilitadas). Habilitar/desabilitar o painel inteiro pintava os rótulos
de cinza e ainda assim deixava o texto de placeholder aceso — o estado mais
barulhento e menos informativo possível.

Seek precisa de `player.seek(ms)`: se a API do player não tiver, entra aqui como
método novo (a Revisão já move o playhead por *skip*, então a capacidade existe;
o que falta é o caminho de posição absoluta).

### G. Divergências conscientes do mockup

- **CLASSE continua a escala ordinal de três segmentos**, não o chip de texto do
  mockup. O `ClassificationDelegate` tem a razão escrita: as três classes são
  ORDENADAS (uma escala carrega a ordem na forma; um chip com "+1" obriga o olho
  a traduzir) e o chip colorido competia com o chip de Camelot na coluna ao
  lado. O mockup desenha os dois lado a lado — é a única coisa que ele faz pior
  que o código atual.
- **Sem view "Cards"** e sem `Colunas →`: seria uma segunda view inteira.
- **Sem checkbox de seleção múltipla** por linha: a tabela é seleção única e a
  ação em lote não existe no serviço.
- **Sem a coluna ARTISTA repetida**: o mockup mostra o artista dentro de TÍTULO
  e de novo na coluna ARTISTA. O código já fundiu os dois na mesma célula
  (decisão documentada no `Column`); repetir seria ruído.
- **Sem as abas Informações/Análise/Arquivo** do inspector: parqueado.

## Estados

| Estado | Cabeçalho | Chips | Tabela | Inspector |
| --- | --- | --- | --- | --- |
| Biblioteca vazia | título + linha de apoio | chip único "Todos 0" desabilitado | `EmptyState` com Escanear | vazio na anatomia |
| Busca sem resultado | contagens absolutas | ativos | só o cabeçalho (como hoje) | vazio |
| Seleção | normal | ativos | linha acesa | ficha preenchida |
| Sem buckets | normal | ativos | onda mono | onda mono + seek |
| Track removida | o refresh reescreve o estado | idem | linha some | volta ao vazio |

## Fora de escopo

- BPM como faixa de filtro (o mockup mostra um combo; a faixa precisa de decisão
  de produto sobre os cortes).
- `Adicionar a fila de revisao` (mockup): a fila é derivada de tracks sem
  rótulo; "adicionar" significaria desrotular, e isso não existe no serviço.
- `radius.control` e `size.icon.{small,base,large}` — continuam pendência aberta
  desde a v0.5. Sem `size.icon.*` não há grade de ícones: o `…` e o triângulo de
  play são desenhados como glifos, do mesmo tipo que `SIZE_WAVE_BAR`.

## Riscos

- **`library_tab.py` já tem 556 linhas.** O que é desenho sai para `widgets/`
  (chips, ações, inspector). Se passar de ~560 depois das quatro fases, sobrou
  desenho nele.
- **`data()` é caminho quente.** A coluna `#` responde pelo `DisplayRole` (sem
  objeto novo); a coluna de ações só pinta. Qualquer coisa mais cara que isso
  precisa de teste de tempo, não de olho.
- **Os mapas por índice cru do cabeçalho** (`SEM_ORDEM`, `ALINHAMENTO`) são o
  ponto mais fácil de quebrar em silêncio ao inserir colunas nas duas pontas.
- **`tests/test_library_tab.py` usa `aba._filtro.setCurrentText(...)`** em vários
  testes: quebram de propósito quando o combo vira chips, e a substituição é
  pelo API do widget (`acionar(rotulo)`), não por acesso a botão.
