# Mockups — linha instrumento, tokens v0.2

Mockups da UI do TrackClassifier, feitos sobre `design-tokens.v0.2.json` e sobre
as specs em `docs/superpowers/specs/`. Nenhum valor aqui foi inventado: cores,
espaçamentos e tamanhos vêm dos tokens, e a estrutura vem do código lido em
`src/trackclassifier/ui/`.

## O que tem aqui

| Arquivo | Tela | Fonte no repo |
|---|---|---|
| `mockups/01-primeiro-uso.html` | `FirstRunDialog` | `ui/first_run.py`, `ui/settings_form.py` |
| `mockups/02-revisao.html` | Aba Revisão | `ui/review_tab.py`, `ui/widgets/player_bar.py`, `waveform_view.py`, `key_chip.py` |
| `mockups/03-biblioteca-exploracao.html` | Aba Biblioteca — 4 rodadas de exploração | `ui/library_tab.py`, `ui/widgets/delegates.py`, `track_model.py` |
| `mockups/04-modelo.html` | Aba Modelo | `ui/model_tab.py`, `ui/viewmodel.py` |
| `mockups/05-configuracao.html` | Aba Configuração | `ui/settings_tab.py`, `ui/settings_form.py` |
| `mockups/06-estados.html` | Vazios, busca sem resultado, linha tocando, cabeçalho ordenável | `ui/widgets/empty_state.py`, `track_model.py` |

`mockups/` são arquivos únicos: abrem no navegador sem servidor e sem rede.
`fonte/` é o código dos mesmos mockups (precisa de `support.js` ao lado).

O mockup 03 é a exploração inteira, com as rodadas empilhadas — a mais nova em
cima. **A direção fechada é a `3a`** (janela completa) com as medidas em `3b`.
As rodadas anteriores ficam para o registro da decisão.

## A direção, em uma frase

Instrumento de estúdio, não aplicativo de consumo: superfícies com matiz frio,
um único signal color quente, números em mono tabular, micro-labels em caixa
alta com tracking largo, raio de canto quase zero.

## A linha da Biblioteca (direção fechada)

Faixa **única** de 44px (`size.row.comfortable`), não duas.

    capa 38 · titulo·artista flex (min 220) · onda 480 · genero 96 · bpm 52 · key 56 · classe 72 · dur 52
    gap 10 · padding 12 esquerda / 20 direita (8 reservados para o scrollbar)

Compacta (32px): mesmas colunas, capa 28, onda 20 de altura.

- **Onda**: altura 28 (comfortable) / 20 (compact), fundo `surface.waveform`,
  `radius.xs`, barras de `size.wave.bar` (2px) sem gap.
- **Capa**: `radius.sm`. Sem capa → inicial em `font.family.mono` /
  `text.disabled` sobre `surface.2`. Carregando → caixa vazia `surface.1`,
  mesmas dimensões. **Não tingir o placeholder com a cor de Camelot.**
- **Key**: `camelot_color(n)` de fundo, texto `text.inverse`, `radius.xs`,
  padding 2/5.
- **Classe**: indicador ordinal de 3 segmentos 9×9 na ordem `LABEL_ORDER`
  (-1, neutra, +1). Ativo em `classification.<classe>.base`; inativos com
  `inset 1px border.default`, sem preenchimento. Substitui o chip de texto.
- **Cabeçalho**: micro-label 10px mono, `font.case.label` +
  `font.tracking.widest`, `text.muted`. Hairline entre colunas com largura
  zero (`box-shadow inset`, não `border-left`) — senão a coluna desloca.

### Estados de linha

| Estado | Tratamento |
|---|---|
| Default | transparente |
| Hover | `surface.1` |
| Selected | `surface.2` + barra de 2px em `surface.selection-bar` na borda esquerda |
| Focus (teclado) | Selected + anel interno de `size.focus-ring` em `accent.base` |
| Pendente | onda vira caixa `surface.waveform`; bpm/key/classe em travessão |
| Falhou | título em `text.muted`, motivo em `state.danger` no lugar da onda |
| Tocando | ▶ sobre a capa, playhead `waveband.playhead` na onda, duração vira tempo restante em `text.primary` |

Seleção e foco **nunca** usam preenchimento colorido — `accent.base` e
`classification.animada.base` são a mesma cor, e o preenchimento confundiria
seleção com classe.

## Revisão

Chrome: barra de título 30 · abas 36 · rodapé de decisão 64 · status 24.
Conteúdo com padding 16 e gap 12.

- **Topo**: capa `size.art.player` (56), título `font.size.large` (15px,
  `font.weight.medium`), artista · gênero 11px `text.secondary`. À direita, um
  bloco por número — KEY (chip Camelot), BPM, DURAÇÃO, RESTAM — cada um com
  micro-label acima e o valor em mono 15px tabular.
- **Onda**: ocupa toda a altura livre (no código é `addWidget(waveform, 1)`),
  mínimo `size.wave.player` (96). Fundo `surface.waveform`, `radius.xs`.
  Playhead 1px `waveband.playhead` com o tempo ao lado sobre scrim. Marca do
  `peak_offset_s` em branco a 35% de opacidade, rotulada `PICO m:ss`.
  Grade de compasso em `waveband.grid` a cada 32 barras.
- **Player**: faixa de 36 em `surface.1`, `radius.md`; botão 26, tempo em mono
  tabular, volume como trilho de 2px com marcador.
- **Palpite**: faixa em `surface.1` com a mesma escala ordinal de 3 segmentos
  (aqui 5×20), o rótulo da classe em `classification.<x>.text`, a confiança
  como trilho de 2px + número em mono, e o aviso de baixa confiança em
  micro-label à direita.
- **Próximas**: três linhas na anatomia da Biblioteca, sem alteração.
- **Rodapé**: as teclas 1/2/3 como alvos de 40px — dígito em mono 15px
  `text.primary`, rótulo da classe em `classification.<x>.text`, borda
  `border.strong`. É a afordância do teclado, não decoração.

## Modelo

Três cards em `surface.1` (`radius.md`, padding 14/16) na primeira faixa:
métricas 280 · matriz flex · balanço 300.

- **Matriz**: grid `64px repeat(3,1fr)`, gap 4, células de 44 em mono tabular.
  Cor por severidade ordinal `|i-j|`: 0 → `surface.2` + `inset 1px
  border.default` / `text.primary`; 1 → `classification.neutro.bg` /
  `.text`; 2 → `state.danger` a 12% / `state.danger`. Rótulos de linha e coluna
  em `classification.<x>.base`. Legenda de três itens abaixo.
- **Balanço**: barra de 6px por classe, normalizada pela maior, na cor
  `classification.<x>.base`. A recomendação só aparece quando a menor classe
  fica abaixo de ~70% da maior.
- **Ação**: RETREINAR (contorno acento) + trilho de 3px com
  `n / m ATÉ O RETREINO AUTOMÁTICO`. Bloqueado → borda `border.subtle`, texto
  `text.disabled`, motivo em `state.danger` ao lado.
- **Falhas**: agrupadas por motivo. Badge com a contagem em `state.danger`
  sobre tinta 12%, arquivos em mono `text.muted`. Cabeçalho da seção com
  `N ARQUIVOS · M MOTIVOS`.
- **Detalhe técnico**: uma linha recolhida com resumo em `text.disabled`.

## Configuração e primeiro uso

Formulário de largura máxima 760, quatro seções na ordem do fluxo do arquivo,
gap 18 entre seções e 8 dentro.

- **Campo**: rótulo 11px `text.secondary` + chip de contagem à direita; input de
  28 em `surface.2`, borda `border.default`, `radius.md`, caminho em mono 11px;
  botão ESCOLHER neutro ao lado. Erro embaixo em `state.danger`, com a borda do
  input em `state.danger`.
- **Chips**: `N NOVAS`, `N TRACKS`, `N ANÁLISES · N MB`, em mono 10px caixa alta
  com `font.tracking.wide` sobre `surface.2`. `NÃO ENCONTRADA` em `state.danger`
  sobre tinta 12%. Enquanto a contagem não chegou, o chip **não existe** — sem
  spinner, sem placeholder.
- **Destinos**: ponto de 7px + rótulo em `classification.<x>.base`, na ordem de
  `LABEL_ORDER`. Vocabulário do domínio (-1, neutra, +1), nunca as chaves da
  config.
- **Modo raiz**: card com borda `accent.base`. Marcado, esconde os três
  destinos e mostra a raiz.
- **Rodapé**: 56 em `surface.1`, motivo à esquerda, SALVAR à direita.
- **Primeiro uso**: mesmo formulário, diálogo de 720, margem `space.8` (32),
  pergunta em `font.size.display` (22px `font.weight.medium`), o card de raiz já
  marcado, e CANCELAR + COMEÇAR no rodapé.

## Decisão de sistema: rótulo de botão

Mono, caixa alta, `font.tracking.widest`, tratamento **contorno**:

- acento: borda e texto `accent.base`; hover `accent.bg` + `accent.hover`
- neutro: borda `border.strong`, texto `text.primary`; hover `surface.2`
- desabilitado: borda `border.subtle`, texto `text.disabled`

Vale para `SALVAR`, `COMEÇAR`, `CANCELAR`, `ESCOLHER`, `RETREINAR`, `ESCANEAR`.
Aplicar no `app.qss` de uma vez — metade dos botões em mono e metade em sans é
pior que qualquer uma das duas.

## Tokens que os mockups decidem

- `waveband.grid` — **usar**: grade de compasso na onda grande da Revisão, a
  cada 32 barras (64px). Sai da lista de órfãos.
- `radius.pill` — não usado em nenhuma tela. Candidato a apagar.
- `size.sidebar` — nenhuma tela tem sidebar. Candidato a apagar.
- `motion.*` — continua sem consumidor (QSS não suporta `transition`).

## Como usar isto para implementar

1. Abra o mockup no navegador ao lado do app rodando. Compare medida por medida.
2. Leia o **código do mockup** (`fonte/`) quando precisar de um valor exato —
   ele está no `style` inline, em px, não escondido numa folha de estilo.
3. Traduza, não copie: os mockups são HTML/CSS e o alvo é QSS + `QPainter`.
   Flex, `box-shadow` e `<canvas>` não têm equivalente direto. O que transfere é
   **medida, cor, tipografia e hierarquia**.
4. Nenhum hex vai para o código: tudo sai de `design-tokens.json` via
   `build_tokens.py` (há teste varrendo `ui/` atrás de hex literal).

## O que os mockups não decidem

- Progresso de scan por track na tabela (precisa de `analyze_all` emitindo por
  track — outra spec).
- Modo claro. O sistema é `mode: dark` e continua sendo.
- Qualquer coisa do scan v2 / `handcrafted-v2`.

## Dados de exemplo

Títulos, artistas e números nos mockups são fictícios. Substitua por uma
amostra real da biblioteca antes de usar como referência de largura de coluna —
nomes reais de promos são bem mais longos.

## Copy que precisa de revisão

O empty state do Modelo ("Nenhum exemplo rotulado" / "Classifique tracks na
Revisao para o modelo ter o que aprender") é **novo** — não existe no código.
Os outros vêm verbatim de `empty_state.py`, `library_tab.py` e `review_tab.py`.
