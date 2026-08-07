# Telas v0.2 "instrumento" — Modelo, Biblioteca, Revisao, estados — design

Data: 2026-08-07

## Objetivo

Fechar a direcao v0.2 nas tres abas que ainda estao na linguagem v0.1: **Modelo**
(hoje `QLabel` com alinhamento por `f"{v:>8}"`), **Biblioteca** (linha de faixa
unica generica) e **Revisao** (cabecalho e palpite em texto corrido). Mais a
fase de estados e teclado, que a auditoria do design system apontou como
lacuna e nunca entrou.

Configuracao e Primeiro uso ja foram entregues em `c279b55`; os tokens v0.2 em
`4f79eeb`. Esta spec e o que resta.

Referencia visual: `design/mockups/` (copiado do pack de mockups). Os arquivos
de `mockups/` abrem no navegador sem servidor; `design/mockups/LEIA-ME.md` tem
as medidas em texto.

## Este design substitui decisoes de tres specs anteriores

O pack de mockups e posterior as specs de tela e as contradiz em quatro pontos.
Onde houver conflito, **vale o pack**. As specs antigas ficam como estao — sao
o registro de por que a decisao mudou, nao documentacao do alvo.

| Ponto | Spec antiga | Decisao final (pack) | Por que |
|---|---|---|---|
| Anatomia da linha | Duas faixas: metadado 16px sobre onda 22px (`linha-instrumento`) | **Faixa unica de 44px**, onda como coluna de 480 | Rodada 3a da exploracao. Duas faixas custam ~20% das linhas por tela e a onda de 480px ja e o corpo do componente sem precisar da largura inteira |
| Classe na linha | Chip de texto colorido | **Indicador ordinal de 3 segmentos 9x9** na ordem `LABEL_ORDER` | Tres classes ordenadas leem melhor como escala que como rotulo. Ativo em `classification.<x>.base`; inativos com `inset 1px border.default`, sem preenchimento |
| Capa no topo da Revisao | `size.art.review-header` (72px) | **`size.art.player` (56px)** | O token de 72 existe e fica orfao. Nao apagar nesta spec — decidir na fase 4 junto dos outros orfaos |
| Painel "por que este palpite" | Regua de score com limiares e tracos das tracks rotuladas, atalho `D` | **Cortado** | Verificado no `fonte/Revisao.dc.html`: nao existe no mockup. Junto some a necessidade de `scores_rotulados`/`thresholds` no `ReviewState` |

## Linha da Biblioteca — a anatomia fechada

Faixa unica de 44px (`size.row.comfortable`):

    capa 38 · titulo/artista flex (min 220) · onda 480 · genero 96 ·
    bpm 52 · key 56 · classe 72 · dur 52
    gap 10 · padding 12 esquerda / 20 direita (8 reservados pro scrollbar)

Compacta (32px): mesmas colunas, capa 28, onda 20 de altura.

- **Onda**: altura 28 (comfortable) / 20 (compact), fundo `surface.waveform`,
  `radius.xs`, barras de `size.wave.bar` (2px) sem gap.
- **Capa**: `radius.sm`. Sem capa, inicial do titulo em `font.family.mono` /
  `text.disabled` sobre `surface.2`. Carregando, caixa vazia `surface.1` nas
  mesmas dimensoes. **Nao tingir o placeholder com a cor de Camelot** — a capa
  ausente nao carrega significado, e tingi-la quebra `cor-pertence-ao-dado`.
- **Key**: `camelot_color(n)` de fundo, texto `text.inverse`, `radius.xs`,
  padding 2/5.
- **Cabecalho**: micro-label 10px mono, `font.case.label` +
  `font.tracking.widest`, `text.muted`. Hairline entre colunas com largura zero
  (`box-shadow inset` no HTML; em `QPainter`, uma linha desenhada, **nao** um
  `border-left`) — senao a coluna desloca um pixel.

### Estados de linha

| Estado | Tratamento |
|---|---|
| Default | transparente |
| Hover | `surface.1` |
| Selected | `surface.2` + barra de 2px em `surface.selection-bar` na borda esquerda |
| Focus (teclado) | Selected + anel interno de `size.focus-ring` em `accent.base` |
| Pendente | onda vira caixa `surface.waveform`; bpm/key/classe em travessao |
| Falhou | titulo em `text.muted`, motivo em `state.danger` no lugar da onda |
| Tocando | ▶ sobre a capa, playhead `waveband.playhead` na onda, duracao vira tempo restante em `text.primary` |

Selecao e foco **nunca** usam preenchimento colorido: `accent.base` e
`classification.animada.base` sao a mesma cor na v0.2, e o preenchimento
confundiria selecao com classe.

## Aba Modelo

Tres cards em `surface.1` (`radius.md`, padding 14/16) na primeira faixa:
metricas 280 · matriz flex · balanco 300.

- **Matriz** — grid `64px repeat(3,1fr)`, gap 4, celulas de 44 em mono tabular.
  Cor por severidade ordinal `|i-j|`, nao por contagem: 0 → `surface.2` +
  `inset 1px border.default` / `text.primary`; 1 → `classification.neutro.bg` /
  `.text`; 2 → `state.danger` a 12% / `state.danger`. Celula zerada em
  `text.disabled`. Rotulos de linha e coluna em `classification.<x>.base`,
  ordem de `LABEL_ORDER` sempre. Legenda de tres itens abaixo — sem ela a
  escala de cor e adivinhacao.
- **Balanco** — barra de 6px por classe, normalizada pela maior, em
  `classification.<x>.base`. A recomendacao de rotular mais da classe
  minoritaria e **derivada**: so aparece quando a menor fica abaixo de ~70% da
  maior.
- **Acao** — RETREINAR (contorno acento) + trilho de 3px com
  `n / m ATE O RETREINO AUTOMATICO`. Bloqueado: borda `border.subtle`, texto
  `text.disabled`, motivo em `state.danger` ao lado. A regra de bloqueio vive
  em `model.fit()`; o viewmodel consulta, a UI nao duplica.
- **Falhas** — agrupadas por motivo. Badge com a contagem em `state.danger`
  sobre tinta 12%, arquivos em mono `text.muted`. Cabecalho da secao com
  `N ARQUIVOS · M MOTIVOS`. Quarenta arquivos com "ffmpeg nao encontrado" sao
  **um** problema, nao quarenta.
- **Detalhe tecnico** — uma linha recolhida (`alpha_`, `thresholds_`,
  `extractor.name`) com resumo em `text.disabled`.

## Aba Revisao

Chrome: barra de titulo 30 · abas 36 · rodape de decisao 64 · status 24.
Conteudo com padding 16 e gap 12.

- **Topo** — capa `size.art.player` (56), titulo `font.size.large` (15px,
  `font.weight.medium`), `artista · genero` 11px `text.secondary`. Album fica
  de fora: o mockup mostra so os dois. A direita, um bloco por numero — KEY
  (chip Camelot), BPM, DURACAO, RESTAM — micro-label acima, valor em mono 15px
  tabular.
- **Onda** — ocupa toda a altura livre (`addWidget(waveform, 1)`), minimo
  `size.wave.player` (96). Fundo `surface.waveform`, `radius.xs`. Playhead 1px
  `waveband.playhead` com o tempo ao lado sobre scrim. Marca do `peak_offset_s`
  em branco a 35%, rotulada `PICO m:ss`. Grade de compasso em `waveband.grid` a
  cada 32 barras — e o unico consumidor desse token, que sai da lista de
  orfaos.
- **Player** — faixa de 36 em `surface.1`, `radius.md`; botao 26, tempo em mono
  tabular, volume como trilho de 2px com marcador.
- **Palpite** — faixa em `surface.1` com a mesma escala ordinal de 3 segmentos
  (aqui 5x20), rotulo da classe em `classification.<x>.text`, confianca como
  trilho de 2px + numero em mono, e o aviso de `low_confidence_mode` em
  micro-label a direita.
- **Proximas** — tres linhas na anatomia da Biblioteca em densidade `compact`,
  sem alteracao.
- **Rodape** — teclas 1/2/3 como alvos de 40px: digito em mono 15px
  `text.primary`, rotulo da classe em `classification.<x>.text`, borda
  `border.strong`. E a afordancia do teclado, nao decoracao. `espaco tocar`,
  `← → navegar`, `Z desfazer` ao lado; aprovar em bloco a direita com o limiar
  visivel.

## Fases

Ordem obrigatoria. Cada fase e um commit.

**Fase 0 — infraestrutura visual.** `design/mockups/` entra no repo (os
`mockups/*.html` standalone + `LEIA-ME.md`; `fonte/` fica de fora, precisa de
runtime proprio). Space Grotesk e JetBrains Mono empacotadas em
`src/trackclassifier/ui/fonts/`, registradas por
`QFontDatabase.addApplicationFont` no bootstrap da UI e declaradas como dado no
`packaging/trackclassifier.spec`. Ambas sao OFL — redistribuicao permitida, o
`OFL.txt` de cada uma vai junto. Sem isso nenhuma tela se parece com o mockup, e
o CI nunca teria as fontes.

**Fase 1 — aba Modelo.** Maior delta visual pelo menor risco: nao toca delegate
nem player.

**Fase 2 — linha instrumento.** O delegate parametrizado por densidade, os sete
estados, o cabecalho micro-label. E o componente compartilhado com a Revisao,
entao vem antes dela.

**Fase 3 — aba Revisao.** Consome o delegate da fase 2 em `compact`.

**Fase 4 — estados, teclado e orfaos.** `setFocusPolicy`, anel de foco, 1/2/3 e
Z na Biblioteca (roteando por `worker.decide`, que ja distingue `decide` de
`reclassify` via `path_for` — a barra diz RECLASSIFICAR, nao CLASSIFICAR),
`setAccessibleName`/`setAccessibleDescription` nos widgets pintados a mao (hoje
ha **zero** ocorrencias em `ui/widgets/`), os empty states do mockup 06. Junto,
a decisao dos orfaos: `radius.pill` e `size.sidebar` saem (nenhuma tela os usa),
`size.art.review-header` idem, `motion.*` continua `$deprecated` sem consumidor
porque QSS nao suporta `transition`.

## Dados novos fora da UI

`ModelState` ganha:

| Campo | Origem |
|---|---|
| `class_counts: tuple[int, ...]` | `service._labeled` na ordem de `LABEL_ORDER` |
| `decisions_since_train: int` | `service._decisions_since_train` |
| `retrain_every: int` | `service.config.retrain_every` |
| `train_blocked_reason: str \| None` | classes ausentes em `_labeled` |
| `alpha: float \| None` | `service.model.alpha_` |
| `thresholds: tuple[float, float] \| None` | `service.model.thresholds_` |
| `extractor_name: str` | `service.extractor.name` |

`FailedItem` ganha um campo de categoria. Hoje `reason` e a string da excecao e
varia por arquivo (`"Falha ao decodificar X: <stderr do ffmpeg>"`), entao
agrupar pela string completa nao agrupa nada. Categoria explicita e mais limpa
que fatiar por prefixo ate os dois-pontos.

`ReviewState` **nao muda** — o painel que exigia `scores_rotulados` foi cortado.

`failures` continua plano no viewmodel: o agrupamento e apresentacao e mora no
`ModelTab`.

## Fronteiras que continuam valendo

- `ui/viewmodel.py` nao importa Qt (ha teste gramatical).
- So a thread do `ServiceWorker` fala com `TrackService`.
- Nenhum hex fora de `design/design-tokens.json` (ha teste varrendo `ui/`).
- `_DelegateComFundo` existe porque um `paint()` que nao chama a base apaga o
  fundo de selecao — o contrato se mantem.
- Sinais publicos nao mudam: `ModelTab.train_requested`,
  `ReviewTab.decide_requested/undo_requested/bulk_approve_requested/
  peaks_requested/scan_requested`.

## Estrutura de arquivos

`model_tab.py` tem 2,6 KB hoje e ganha tres cards com pintura propria. Em vez de
crescer pro tamanho de `settings_form.py` (16 KB), os cards saem para
`ui/widgets/`: matriz de confusao, balanco de classes e lista de falhas
agrupada viram widgets proprios, e `model_tab.py` fica sendo o layout e a
traducao de `ModelState`.

O delegate de linha fica em `ui/widgets/delegates.py`, parametrizado por
densidade — um so, usado pelas duas abas, e nao um por tela.

## Fora de escopo

- **Progresso de scan por track na tabela.** O estado "Pendente" existe no
  componente, mas para aparecer de verdade `analyze_all` teria que emitir por
  track e o `TrackModel` atualizar linha a linha. Outra spec.
- **Modo claro.** O sistema e `mode: dark` e continua sendo.
- **Qualquer coisa do scan v2 / `handcrafted-v2`.** Nao misturar no mesmo
  commit: se algo regredir, e preciso saber qual dos dois.
- **Importancia das features** e **historico de metricas** na aba Modelo.
- **Reordenar a fila da Revisao** por outro criterio que nao confianca. A ordem
  por incerteza e a tese do produto.

## Testes

- Delegate: um teste por estado de linha, verificando o pintado via
  `QStyleOptionViewItem` — `test_delegates.py` ja faz isso. Capa ausente e capa
  carregando nao levantam excecao nem mudam a altura da linha.
- Matriz: contagens zero na diagonal inteira e na antidiagonal inteira nao
  quebram coloracao nem legenda.
- Balanco: com as tres classes iguais, a linha de recomendacao **nao** aparece.
- Agrupamento de falhas: dez arquivos com o mesmo tipo viram um grupo, badge 10.
- `train_requested` nao e emitido com o botao desabilitado.
- `model_state()` com modelo nao treinado devolve `class_counts` real (nao
  zeros) e `train_blocked_reason` preenchido quando falta classe.
- Marcador de pico com `peak_offset_s == 0.0` e com `peak_offset_s >
  duration_s` (cache antigo inconsistente) fica dentro dos limites da onda.
- `QTest.keyClick` de 1/2/3 emite `decide_requested` com o label certo e roteia
  decide vs. reclassify; `Z` emite `undo_requested`.
- Fontes empacotadas: `addApplicationFont` devolve id valido e a familia
  resolvida por `QFont("Space Grotesk").exactMatch()` e verdadeira.
- Continuam valendo: `viewmodel` sem Qt, nenhum hex fora do JSON.

## Riscos

- **Os testes de delegate comparam imagens.** A linha muda de anatomia inteira
  na fase 2 — quase todos vao quebrar. Reescrever comparando "estado A difere
  de estado B", nao cor absoluta, e o unico jeito de eles sobreviverem a
  proxima mudanca de paleta.
- **O `paint()` da linha ficou 16x mais rapido em `ba53271`.** A anatomia nova
  tem mais elementos por linha. Medir o paint depois da fase 2 e comparar com o
  numero registrado la — 29,5 ms no primeiro paint, 5,6 ms por parada de
  rolagem — antes de dar a fase por fechada.
- **Dados de exemplo dos mockups sao ficticios.** Nomes reais de promos sao bem
  mais longos que "Kernel Panic". A coluna de titulo (flex, min 220) precisa ser
  validada com a biblioteca real antes de fechar as larguras.
