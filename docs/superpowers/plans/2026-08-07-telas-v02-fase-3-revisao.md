# Telas v0.2 — Fase 3: a aba Revisão — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development ou superpowers:executing-plans.

**Goal:** Redesenhar a Revisão sobre a v0.2 e tornar visivel o que ja existe no
modelo e nao chega a tela: o `peak_offset_s` (hoje so posiciona o player), a
confianca como medidor, e as proximas na anatomia da Biblioteca em vez de um
`QLabel` de texto corrido.

**Architecture:** `ReviewTab` continua sendo o layout e a traducao de
`ReviewState`; o que ganha desenho proprio sai para `ui/widgets/`. Os sinais
publicos **nao mudam**. A onda grande continua sendo `WaveformView`, que ganha o
marcador de pico e a grade de compasso.

Depende de: `specs/2026-08-07-telas-v02-instrumento-design.md`, Fase 1 (`Meter`,
`MicroLabel`, `para_qcolor`) e Fase 2 (a linha, reusada em `compact`).

## Global Constraints

- Portugues sem acentos; API publica em ingles.
- Nenhum `#RRGGBB` fora do JSON, inclusive em docstring.
- `ui/viewmodel.py` nao importa Qt.
- **Sinais inalterados:** `decide_requested(str, str)`, `undo_requested()`,
  `bulk_approve_requested(float)`, `peaks_requested(str, str)`,
  `scan_requested()`.
- `ReviewState` **nao ganha campo**: o painel "por que este palpite" foi
  cortado (nao existe no mockup 02), e com ele a necessidade de
  `scores_rotulados`/`thresholds`.
- ruff `line-length = 100`.

---

## Anatomia (do `fonte/Revisao.dc.html`, medidas em px)

| Bloco | Medidas |
|---|---|
| Topo | capa 56 `radius.sm`; titulo 15px `weight.medium`; `artista · genero` 11px `text.secondary`; a direita quatro blocos (KEY, BPM, DURACAO, RESTAM), micro-label 10px acima e valor mono 15px tabular, gap 20 |
| Onda | flex, minimo 96, `surface.waveform`, `radius.xs`. Playhead 1px `waveband.playhead` com o tempo ao lado. Pico: linha 1px branca a 35% + `PICO m:ss` sobre scrim `rgba(11,14,17,0.82)`. Grade de compasso `waveband.grid` a cada 32 barras |
| Player | faixa 36 `surface.1` `radius.md`; botao 26 com borda `border.strong`; tempo mono 11px; `VOLUME` micro-label + trilho 100x2 com marcador |
| Palpite | faixa `surface.1` `radius.md`, padding 10/12, gap 16: `PALPITE`, escala ordinal 5x20 (gap 3), rotulo da classe mono 13px em `classification.<x>.text`, trilho de confianca 2px (max 260) + `confianca 0.82` mono 11px, aviso de `low_confidence` em micro-label a direita |
| Proximas | `PROXIMAS` micro-label + 3 linhas na anatomia da Biblioteca, `compact` |
| Rodape | 64 `surface.1`: tres alvos de 40px (digito mono 15px `text.primary` + rotulo da classe em `classification.<x>.text`, borda `border.strong`), depois `espaco tocar`, `← → navegar`, `Z desfazer`; aprovar em bloco a direita |

O rodape **e a afordancia do teclado, nao decoracao**: classificar centenas de
tracks com o mouse e inviavel, e o alvo desenhado e o que ensina a tecla.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `ui/widgets/ordinal_scale.py` | **Criar.** `desenha_escala(painter, rect, aceso, lado, gap)` — a funcao de desenho, compartilhada; e `OrdinalScale(QWidget)`, a versao widget. Hoje a escala so existe dentro do `ClassificationDelegate`. |
| `ui/widgets/metric_block.py` | **Criar.** `MetricBlock` — micro-label acima, valor mono abaixo. Quatro no topo da Revisao; o mesmo par existe na aba Modelo, mas la e rotulo-a-esquerda/valor-a-direita, que e outra forma. |
| `ui/widgets/decision_bar.py` | **Criar.** `DecisionBar` — os tres alvos de decisao e a legenda de atalhos. Emite `decidido(str)`. |
| `ui/widgets/guess_bar.py` | **Criar.** `GuessBar` — palpite: escala, rotulo, medidor de confianca, aviso. |
| `ui/widgets/waveform_view.py` | Marcador de pico, grade de compasso, tempo ao lado do playhead. |
| `ui/widgets/upcoming_list.py` | **Criar.** `UpcomingList` — as tres proximas, reusando os delegates da Biblioteca em `compact`. |
| `ui/review_tab.py` | Layout e traducao de `ReviewState`. |

---

### Task 1: a escala ordinal vira compartilhada

**Files:** Create `ui/widgets/ordinal_scale.py`; Modify `ui/widgets/delegates.py`;
Test `tests/test_ordinal_scale.py`

**Interfaces:**
- `desenha_escala(painter: QPainter, centro: QPoint, aceso: int | None, *, lado: int, gap: int) -> None`
- `OrdinalScale(QWidget)` com `set_label(rotulo: str | None)`.

- [x] **Step 1:** Teste — a funcao acende so a posicao pedida; `None` deixa os
      tres em contorno; o widget e a funcao pintam a mesma coisa no mesmo
      tamanho.
- [x] **Step 2:** Rodar e ver falhar.
- [x] **Step 3:** Extrair de `ClassificationDelegate.paint` sem mudar o
      desenho; o delegate passa a chamar a funcao.
- [x] **Step 4:** `tests/test_delegates.py` continua verde — e a prova de que a
      extracao nao mudou pixel.
- [x] **Step 5:** Commit.

### Task 2: a onda grande marca o pico e o compasso

**Files:** Modify `ui/widgets/waveform_view.py`; Test `tests/test_waveform_view.py`

`peak_offset_s` esta no `QueueItem` desde sempre e hoje so posiciona o player.
Animada vs. lento se decide no drop, nao na intro: sem a marca, o usuario
arrasta o playhead procurando o ponto toda vez.

- [x] **Step 1:** Testes — marca dentro dos limites com `peak_offset_s == 0.0` e
      com `peak_offset_s > duration_s` (cache antigo inconsistente); a grade
      nao aparece com largura zero; o tempo do playhead acompanha o progresso.
- [x] **Step 2:** Rodar e ver falhar.
- [x] **Step 3:** Implementar. `waveband.grid` a cada 32 barras — e o unico
      consumidor desse token, que sai da lista de orfaos.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 3: palpite, metricas e alvos de decisao

**Files:** Create `ui/widgets/metric_block.py`, `guess_bar.py`, `decision_bar.py`;
Test um arquivo por widget

- [x] **Step 1:** Testes — `MetricBlock` sem valor nao mostra rotulo orfao;
      `GuessBar` esconde o aviso quando `low_confidence` e falso e some inteira
      com modelo nao treinado; `DecisionBar` emite `decidido` com o rotulo
      certo e marca o alvo do palpite.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 4: as proximas usam a linha da Biblioteca

**Files:** Create `ui/widgets/upcoming_list.py`; Test `tests/test_upcoming_list.py`

Hoje e um `QLabel` com os titulos concatenados. Vira `QTableView` com o mesmo
`TrackTableModel` e os mesmos delegates em `compact` — o componente e o mesmo,
so a densidade muda.

- [x] **Step 1:** Testes — tres linhas no maximo; fila com menos de tres nao
      deixa linha vazia; a lista some com a fila vazia.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Rodar e ver passar. **Step 5:** Commit.

### Task 5: `ReviewTab` monta tudo

**Files:** Modify `ui/review_tab.py`; Test `tests/test_review_tab.py`

- [x] **Step 1:** Testes — os cinco sinais continuam com a mesma assinatura;
      fila vazia com biblioteca cheia diz "tudo classificado" e **nao** oferece
      escanear como acao primaria; modelo nao treinado esconde o palpite e
      mantem os tres alvos ativos (classificar e o que treina); cabecalho sem
      artista e sem genero nao deixa linha vazia ocupando altura.
- [x] **Step 2:** Rodar e ver falhar. **Step 3:** Implementar.
- [x] **Step 4:** Suite inteira + ruff. **Step 5:** Commit.

### Task 6: ver com os proprios olhos

- [x] **Step 1:** Screenshot offscreen contra `design/mockups/02-revisao.html`.
- [x] **Step 2:** Conferir os estados: fila vazia (duas variantes), modelo nao
      treinado, `low_confidence`, onda sem buckets.
- [x] **Step 3:** Registrar aqui o que destoou. **Step 4:** Commit.

**Como foi verificado:** `ReviewTab` real com `SimulatedPlayer`, `app.qss` e as
fontes, 1180x670, uma track atual e tres proximas (uma delas sem tag), com
`low_confidence` ligado e o progresso em 37%.

**Um bug real e PRE-EXISTENTE, achado so aqui.** `_resample` fazia
`np.pad(mode="edge")` quando a curva tinha menos pontos que barras: a onda
ocupava so os primeiros `len(curva)` pixels e o resto virava um bloco chapado
do ultimo valor. Era invisivel na coluna de 480px da Biblioteca -- onde a curva
quase sempre tem mais pontos que barras -- e so apareceu quando a Fase 3 deu a
largura inteira da janela para a onda. Virou interpolacao, com dois testes.

**Um problema de layout, corrigido:** as legendas de atalho colavam no alvo
`3 +1` e liam como um quarto botao. Ganharam respiro de `SPACE_8` e margem
propria.

**O que bateu:** topo com titulo/`artista · genero` e os tres blocos metricos
alinhados a direita, chip de Camelot, onda de altura livre com grade de
compasso e marca de pico rotulada sobre scrim, tempo ao lado do playhead,
faixa de palpite com escala ordinal + medidor de confianca + aviso, as tres
proximas na anatomia da Biblioteca em `compact`, e o rodape de 64 com os tres
alvos e a legenda.

**Dois desvios registrados, nao corrigidos:**

- **A barra do player continua a da v0.1.** O volume e um `QSlider` azul, e o
  mockup pede um trilho de 2px com marcador. `player_bar.py` nao foi tocado
  nesta fase; entra na Fase 4 junto do resto do chrome, ou vira spec propria.
  Como esta, e o unico elemento da tela que nao fala v0.2.
- **`review_tab.py` ficou em 352 linhas**, e o plano dizia que passar de ~250
  significaria que sobrou desenho nela. Conferido: o que sobrou nao e desenho.
  Sao a janela local de skip/back (`_janela`/`_posicao`), a dedup de pedidos de
  peaks e o carregamento do player -- logica de coordenacao, com comentarios
  longos que explicam races. Extrair isso separaria a coordenacao do unico
  lugar que a usa. Fica.

---

## Fora de escopo

- **Teclado** (1/2/3, Z, espaco, setas) — ja existe em `MainWindow` e continua
  la; a Fase 4 revisa foco e acessibilidade.
- **Painel "por que este palpite"** — cortado, ver acima.
- **Reordenar a fila** por outro criterio que nao confianca. A ordem por
  incerteza e a tese do produto.
- **Album no cabecalho.** A spec da Revisao pedia `album · genero`; o mockup
  mostra `artista · genero`. Vale o mockup.

## Riscos

- **`ReviewTab` tem 336 linhas e vai crescer.** Por isso os cinco blocos saem
  para `widgets/`. Se o arquivo passar de ~250 linhas depois da Task 5, sobrou
  desenho nele que devia ter saido.
- **A janela local de skip/back** (`_janela`/`_posicao`) e sutil e nao tem
  relacao com o visual. Nao encostar: os testes que a cobrem sao o unico aviso.
