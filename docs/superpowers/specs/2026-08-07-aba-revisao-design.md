# Aba Revisão — design

Data: 2026-08-07

## Objetivo

Redesenhar a aba Revisão sobre os tokens v0.2 e a linguagem "instrumento",
tornando visível a informação que já existe no modelo e hoje não chega à tela.

A fila de revisão é uma fila de **active learning**: `TrackService.queue()`
ordena por `confidence` crescente, ou seja, mostra primeiro o que o modelo
menos sabe. Nada na tela atual comunica isso — o usuário assume ordem
alfabética ou de importação e não entende por que uma track obscura veio na
frente. Metade deste redesign é tornar essa lógica legível.

Referência visual: `design/mockups/revisao-instrumento.html`.

Depende de: `docs/superpowers/specs/2026-08-07-linha-instrumento-e-tokens-v02-design.md`
(fases 1 e 2 — tokens e gerador — precisam estar entregues).

## O que já existe e este trabalho não pode quebrar

- `ui/review_tab.py` — `ReviewTab` com os sinais `decide_requested(str, str)`,
  `undo_requested()`, `bulk_approve_requested(float)`, `peaks_requested`,
  `scan_requested`. **Os sinais não mudam.**
- `ui/viewmodel.py` — `ReviewState`, `TrackRow`. Dataclasses puras, **não
  importam Qt** (teste gramatical falha se importarem).
- `service.py` — `QueueItem` já carrega `label`, `score`, `confidence`, `bpm`,
  `duration_s`, `energy_curve`, `peak_offset_s`.
- `model.py` — `TrackModel.thresholds_: tuple[float, float]` (calibrados por
  `_calibrate`), `Prediction.score`, `Prediction.confidence`,
  `low_confidence_mode`.
- `presentation.py` — `read_tags` já lê `album` e `genre`; `PresentationRecord`
  já os armazena. **Nenhum dos dois é exibido hoje.**
- `ui/widgets/waveform_view.py` — `WaveformView`, com playhead e seek.
- `ui/widgets/player_bar.py`, `ui/widgets/key_chip.py`,
  `ui/widgets/empty_state.py`.
- `BULK_MIN_CONFIDENCE` e o botão de aprovar em bloco.

## Decisões de design

### Cabeçalho: capa 72px + três níveis de texto

Título (`font.size.large`), artista (`font.size.small`, `text.secondary`),
e uma terceira linha com **álbum · gênero** (`font.size.caption`,
`text.muted`). Os dois campos já são lidos e persistidos e nunca apareceram.
Quando ausentes, a linha inteira some — não mostrar rótulo vazio nem "—".

Chips métricos abaixo, em `font.family.mono`: BPM, key (colorida por Camelot),
duração. LUFS fica de fora: é dado de análise, não de decisão.

### A onda marca o pico

`peak_offset_s` está no `QueueItem` e hoje não aparece em lugar nenhum.
Desenhar um marcador vertical de 1px em `rgba(255,255,255,0.22)` na posição do
pico, com legenda `▲ PICO mm:ss` abaixo da onda, e um controle "ir ao pico" na
barra de transporte que faz seek direto.

Motivo: animada vs. lento se decide no drop, não na intro. Sem isso o usuário
arrasta o playhead procurando o ponto toda vez.

O playhead segue branco sólido (`waveband.playhead`); o trecho já tocado fica
em opacidade cheia, o restante em 42%.

### A confiança é medidor, não texto

Hoje mora dentro de um `QLabel` de palpite. Vira: rótulo mono + valor + barra
de 3px de 56px de largura, preenchida proporcionalmente. Cor da barra segue a
faixa — `state.warning` abaixo de 0.4, `text.secondary` acima.

É a informação mais acionável da tela porque explica a posição na fila.

### Zona de decisão: três alvos com o palpite pré-marcado

Grid de três colunas iguais. O alvo do palpite recebe `classification.<x>.bg`
de fundo e borda em `classification.<x>.base`; os outros dois ficam com borda
`border.default` e texto `text.secondary`.

O número do atalho vive **dentro** do alvo, num chip pequeno. Isso faz do botão
e da tecla a mesma affordance visual, em vez de uma legenda separada que o
usuário precisa correlacionar.

### Painel "por que este palpite" — recolhível, fechado por padrão

Régua de score de 0 a 1 com:

- três zonas de fundo separadas pelos limiares `t1`/`t2` de `model.thresholds_`,
  tintadas com `classification.<x>.bg`;
- traços de 1px, opacidade 0.5, para o score de cada track já rotulada,
  coloridos pela classe em que caem;
- linhas de 1px em `rgba(255,255,255,0.30)` nos dois limiares;
- marcador de 2px em `text.primary` com seta, no score da track atual.

Abaixo, uma linha de texto explicando a distância até o limiar mais próximo.

**Por que não um histograma:** o histograma responde "como é a distribuição
geral"; a pergunta do usuário na tela é "por que o modelo está inseguro nesta
track". A régua responde a segunda, custa menos para desenhar, e usa dado que
já existe.

Fechado por padrão — quem classifica rápido não precisa disso em 90% das
tracks. Atalho `D`.

**Dado novo necessário:** os scores das tracks já rotuladas. `ReviewState`
precisa carregar `scores_rotulados: list[tuple[float, Label]]` e
`thresholds: tuple[float, float]`. `viewmodel.review_state()` os obtém de
`service.model`. Nenhum cálculo novo — `model.score()` sobre `_labeled` já
existe.

### Fila "a seguir" usa o delegate de linha

As próximas 3 tracks, com capa, nome, artista e confiança. Mesmo componente da
Biblioteca em densidade `compact`, não um `QLabel` de texto corrido como hoje.

Miniatura em `size.art.row-compact` (28px) — **não** criar um terceiro tamanho
de capa, porque cada tamanho é uma variante a mais no cache de pixmap.

### Teclado

| Tecla | Ação | Sinal |
|---|---|---|
| 1 / 2 / 3 | classificar em -1 / neutra / +1 | `decide_requested` |
| Espaço | play/pause | player |
| D | abrir/fechar o painel de detalhe | local |
| Z | desfazer | `undo_requested` |

A barra de atalhos no rodapé documenta e serve de affordance; à direita dela,
o botão de aprovar em bloco, com o limiar visível.

## Estados

| Estado | Tratamento |
|---|---|
| Fila vazia, biblioteca vazia | `empty_state` atual, com ação "escanear" (`scan_requested`) |
| Fila vazia, biblioteca cheia | Mensagem distinta: tudo classificado. Não oferecer escanear como ação primária |
| Modelo não treinado | Zona de decisão sem palpite pré-marcado, medidor de confiança oculto, painel de detalhe desabilitado. Os três alvos continuam ativos — classificar é justamente o que treina |
| `low_confidence_mode` | Já existe no modelo (menos de `min_examples`). Mostrar aviso discreto de que o palpite ainda não é confiável |
| Onda ainda não computada | `peaks` é preguiçoso; cai no render mono do `energy_curve`, como hoje. Sem salto de layout |
| Arquivo sumiu entre scan e decisão | `decide` devolve `False`; avançar para a próxima com mensagem na status bar |

## Fora de escopo

- Qualquer coisa do scan v2 / `handcrafted-v2`.
- Progresso de scan por track.
- Reordenar a fila por outro critério que não confiança. A ordem por incerteza
  é a tese do produto; expor um seletor de ordenação a enfraqueceria.

## Testes

- `viewmodel` continua sem importar Qt.
- `review_state()` carrega `thresholds` e `scores_rotulados`; com modelo não
  treinado, ambos vêm vazios e a tela não quebra.
- Régua: com `t1 == t2` (limiares degenerados de uma biblioteca minúscula) não
  levanta divisão por zero nem desenha zona de largura negativa.
- Marcador de pico em `peak_offset_s == 0.0` e em `peak_offset_s > duration_s`
  (dado inconsistente de cache antigo) fica dentro dos limites da onda.
- `QTest.keyClick` de 1/2/3 emite `decide_requested` com o label correto;
  `D` alterna o painel; `Z` emite `undo_requested`.
- Cabeçalho sem álbum e sem gênero não deixa linha vazia ocupando altura.
