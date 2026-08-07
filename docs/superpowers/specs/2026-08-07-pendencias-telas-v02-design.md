# Pendências das telas v0.2 — design

Data: 2026-08-07

## Objetivo

Fechar as três pendências registradas em
`docs/superpowers/plans/2026-08-07-telas-v02-pendencias.md`: a barra do player,
que ficou em v0.1; o anel de foco de teclado, que a spec original pedia e não
entrou; e a medição de performance da linha nova, que nunca foi feita contra o
número de referência.

Duas delas são código (Fases 1 a 3 abaixo). A terceira não é: é um protocolo de
medição contra a biblioteca real do usuário, descrito na última seção.

## O que já existe e este trabalho não pode quebrar

- `ui/widgets/meter.py` — `Meter`, trilho read-only pintado à mão, usado pelo
  balanço de classes e pelo contador de retreino. **Não é o widget de volume**
  (ver Fase 1).
- `ui/widgets/player_bar.py` — o rótulo do botão vem de `player.playing_changed`
  e não de um flag próprio, porque o atalho de teclado chama `player.toggle()`
  sem passar pelo widget. **Manter esse contrato.**
- `ui/widgets/delegates.py` — `_DelegateComFundo` chama a base para não apagar o
  fundo de seleção; `CoverDelegate` pinta a barra de seleção de 2px na coluna 0.
- `window._registra_atalhos` — 1/2/3 e Ctrl+Z são `QShortcut` com contexto
  `WindowShortcut`, registrados na janela e não em `keyPressEvent` das abas.
  Space/Left/Right são ligados e desligados conforme a aba atual, de propósito.
- `service.undo_last()` — já distingue decisão da inbox de reclassificação pela
  `origem_label` e devolve a track para o lugar certo.
- `ui/viewmodel.py` não importa Qt (há teste gramatical).
- Nenhum hex fora de `design/design-tokens.json` (há teste que varre `ui/`).

## Estado real das pendências

A leitura do código mudou o escopo do item 2 em relação ao que a nota de
pendências registrou:

| Registrado como faltando | Estado real |
|---|---|
| Atalhos 1/2/3 na Biblioteca | **Já existe** — `window._decide_na_aba_atual` roteia para `library_tab.decide_selecionada` |
| Roteamento decide vs. reclassify | **Já existe** — `worker.decide` usa `path_for` para escolher (`worker.py:143`) |
| Anel de foco no delegate | Falta |
| Ctrl+Z fora da Revisão | Falta — `window._desfazer` só age se a aba atual é a Revisão |
| `setAccessibleName` nos pintados | Parcial — três widgets têm, o resto não |

Fora de escopo por decisão explícita: legenda de atalhos na Biblioteca. A
Biblioteca não ganha rodapé de atalhos nesta rodada.

## Fase 1 — a barra do player fala v0.2

O mockup (`design/mockups/02-revisao.html`) define a barra: 36px de altura,
fundo `surface.1`, botão quadrado com borda de 1px, tempo em mono, micro-label
`VOLUME` em caixa alta e um trilho de 100×2px com preenchimento e marcador. Sem
porcentagem escrita.

### `VolumeRail` é widget novo, não subclasse de `Meter`

| | `Meter` | `VolumeRail` |
|---|---|---|
| Interação | nenhuma | clique e arrasto |
| Forma | retângulo de altura cheia, `radius.xs` | traço de 2px centrado + marcador de 2×10 |
| Nome acessível | "Medidor" | "Volume" |

Herdar exigiria reescrever `paintEvent` inteiro e sobrescrever os três pontos
acima — sobra o nome da classe. Um widget próprio de ~60 linhas diz mais a
verdade sobre o que ele é.

Detalhe que não é opcional: **a área de clique é maior que o traço visual**. Um
trilho desenhado com 2px de altura é intocável com o mouse; o widget tem altura
de ~12px, pinta o traço centrado nela e aceita o clique em qualquer ponto da
faixa. É por isso que o widget precisa existir — um `QSlider` estilizado por QSS
não consegue separar as duas alturas.

`VolumeRail` é `NoFocus`. Widget focável aqui não ganharia nada: os dígitos 1/2/3
são `QShortcut` de janela e rodam antes da entrega normal do evento, então nem
com foco o trilho os receberia.

### Mudanças em `PlayerBar`

- `setFixedHeight(SIZE_CONTROL_PRIMARY)` (36) — o fundo `surface.1` já vem da
  regra `QWidget#PlayerBar` do `app.qss`.
- Botão passa de `SIZE_CONTROL_PRIMARY` (36) para `SIZE_CONTROL_BASE` (28). Hoje
  ele usa o token de altura de barra como tamanho de botão; o mockup desenha 26,
  e 28 é o token que existe para controle secundário — não inventar 26.
- `QLabel("Volume")` vira micro-label: `objectName("MicroLabel")` mais
  `estiliza_label`, como o resto da v0.2.
- `QSlider` sai, `VolumeRail` entra; `_muda_volume` continua traduzindo 0..100
  para 0..1 do player.

Nenhum token novo. As dimensões que não têm token (largura de 100, altura de
clique, marcador) ficam como constantes de módulo no widget, com comentário —
mesmo padrão de `_ALTURA_ALVO` em `decision_bar.py`.

### Testes

- Volume inicial 80 chega ao player como 0.8.
- Clique no meio do trilho leva o valor a ~50; clique fora da faixa clampa em 0
  e 100.
- O rótulo do botão continua vindo de `playing_changed` (teste que já existe não
  pode quebrar).
- Nome acessível reflete o valor corrente.

## Fase 2 — o anel de foco de teclado

### O que o anel significa

A tabela da Biblioteca é `SingleSelection` + `SelectRows`: seleção e linha atual
são sempre a mesma linha. Então o anel **não** distingue seleção de linha atual —
não há o que distinguir. Ele responde outra pergunta, que hoje não tem resposta
visual: *o teclado age nesta linha agora?* Com o foco no campo de busca, a linha
continua pintada como selecionada, mas digitar 1/2/3 não a reclassifica.

Isso muda a fonte do dado. `option.state & State_HasFocus` marca só a célula
atual — o anel sairia numa coluna solta. A leitura correta é:

```
option.widget.hasFocus() and option.widget.currentIndex().row() == index.row()
```

### Como ele é pintado: na tabela, não no delegate

`accent.base` e `surface.selection-bar` são a mesma cor (`#FF6B3D`, decisão da
v0.2). Aproveitar isso em vez de contorná-lo: **com foco, a barra de 2px da
esquerda vira o lado esquerdo do anel** e o retângulo fecha contínuo; sem foco,
sobra a barra sozinha. Nada de dois vermelhos vizinhos disputando leitura.

O anel **não** vai no delegate. Três das oito colunas (`GENERO`, `BPM`,
`DURACAO`) não têm delegate próprio — usam o padrão do Qt. Pintar por célula
exigiria dar delegate às três, espalhar a pintura pelas cinco subclasses de
`_DelegateComFundo` e ainda emendar cinco retângulos num só sem costura visível.

Em vez disso, uma subclasse `LibraryTable(QTableView)` desenha o anel em
`paintEvent`, depois de `super().paintEvent()`: um retângulo só, na largura do
viewport, na altura de `visualRect(currentIndex())`. Um lugar, uma implementação,
sem costura.

O foco vira estado explícito do widget (`focusInEvent`/`focusOutEvent` guardam um
booleano e chamam `viewport().update()`), e não uma consulta a `hasFocus()` no
meio do paint. Dois motivos: `QTableView` não repinta o viewport ao ganhar ou
perder foco — sem o `update()` o anel só sumiria na próxima rolagem, o que é pior
que não ter anel — e o booleano é o que torna o comportamento testável com o
`QT_QPA_PLATFORM=offscreen` do `conftest.py`, onde foco real de janela não é
confiável.

Escopo: **só a Biblioteca**. A Revisão não tem tabela focável — `UpcomingList` é
`NoFocus` de propósito.

### Testes

- Tabela com foco: a linha atual tem o anel; a linha vizinha, não.
- Tabela sem foco: nenhuma linha tem anel, a barra de seleção continua.
- Perder o foco repinta (o `update()` é chamado).

## Fase 3 — Ctrl+Z global e nomes acessíveis

### Ctrl+Z deixa de ser exclusivo da Revisão

`window._desfazer` hoje checa `currentWidget() is self.review_tab` e emite
`review_tab.undo_requested`. Passa a chamar `self._worker.undo()` direto, sem
checar a aba: o desfazer é estado do serviço (`_ultima_decisao`), não da tela, e
`undo_last` já sabe devolver uma reclassificação para a biblioteca com o rótulo
antigo em vez de jogá-la na fila de revisão.

`review_tab.undo_requested` continua existindo — outros caminhos da Revisão
podem emiti-lo — mas o atalho não passa mais por ele.

Consequência a registrar: a tecla passa a funcionar na Biblioteca **sem legenda
anunciando**, porque a legenda ficou fora do escopo. É uma dívida conhecida, não
um esquecimento; a `DecisionBar` da Revisão continua sendo a única que
documenta a tecla.

### Nomes acessíveis nos widgets pintados à mão

Um widget desenhado em `paintEvent` não tem texto nenhum para um leitor de tela:
o valor existe só como pixel. Três já resolveram isso (`meter`, `ordinal_scale`,
`confusion_matrix`) e servem de modelo — nome fixo em `setAccessibleName`, valor
corrente em `setAccessibleDescription`, atualizado onde o valor muda.

Faltam: `waveform_view` e `upcoming_list` (pintados, sem texto nenhum);
`key_chip` e `metric_block` (têm texto, mas "11A" e "138" soltos não dizem de que
grandeza são); e os `Meter` dentro de `class_balance` e `guess_bar`, que hoje
anunciam "Medidor" três vezes seguidas sem dizer de qual classe. O `VolumeRail`
já nasce nomeado na Fase 1.

As células da tabela são caso à parte. A tentação é `AccessibleTextRole` no
`TrackTableModel.data()`, e é a escolha errada: `data()` é chamado ~88 mil vezes
por rolagem da biblioteca real, e o próprio código documenta que trabalho
descartado ali custou 9% do tempo de paint. As colunas com `DisplayRole` já são
lidas por um leitor de tela sem nenhuma mudança — o Qt cai no `DisplayRole`
sozinho. A única que perde algo é `CLASSIFICACAO`, hoje `None`: ela passa a
devolver o próprio rótulo (`"+1"`) no `DisplayRole`, **dentro do ramo que já
existe**, sem custo novo no caminho quente. Visualmente nada muda —
`_pinta_fundo` zera `opcao.text` e o `ClassificationDelegate` desenha os
segmentos por conta própria. `CAPA` continua sem texto: uma capa não carrega
informação que valha anunciar.

Sem teste gramatical varrendo o pacote atrás de widgets sem nome — a heurística
("é `QWidget`, tem `paintEvent`, logo precisa de nome") produz falso positivo em
todo container. Um teste por widget, verificando nome e descrição.

## Item 3 — protocolo de medição de performance

Não gera código. É uma sessão de medição contra a biblioteca real do usuário,
porque é a única que tem capas em disco e volume suficiente para o número
significar algo — a verificação da Fase 2 rodou com 9 linhas sintéticas sem
capa, e por isso o ~2,5 ms medido lá não é comparável a nada.

**Duas medidas, não uma.** A primeira antes da Fase 2 e a segunda depois. Sem a
medida de baseline, um número ruim no fim não diz se o culpado é o anel novo, a
coluna CAPA ou o retângulo de fundo da onda.

- Comando: `uv run dj review`, aba Biblioteca, densidade `comfortable`.
- Rodar duas vezes e medir a segunda: na primeira os thumbs de 96px ainda estão
  sendo gravados, e o custo de gerá-los não é o custo de exibi-los.
- O que medir: tempo do primeiro paint da Biblioteca e ms por parada de rolagem
  — a mesma técnica de perfilamento descrita no comentário de `ba53271`.
- Referência: **29,5 ms** no primeiro paint, **5,6 ms** por parada, com 354
  tracks.
- Critério de regressão: acima de 1,5× a referência. Abaixo disso é ruído de
  máquina, não sinal.
- Se regredir, suspeitos em ordem de custo esperado: o retângulo de fundo da
  onda (`WaveformDelegate`), a coluna CAPA, o anel de foco.

O resultado vira um comentário de commit ou uma nota no plano, com os números
crus. Um "medimos e está ok" sem número não fecha esta pendência.

## Fora de escopo

- Legenda de atalhos na Biblioteca (decisão explícita).
- Seek clicando na onda grande. O mockup marca `cursor:pointer` na onda da
  Revisão, mas isso é interação de player, não de barra — mexe em
  `WaveformView` e no `BasePlayer`, e cabe em spec própria.
- Qualquer mudança em `Meter` ou nos widgets que o consomem.
- Modo claro; continua `mode: dark`.
