# UI desktop em PySide6 — design

Data: 2026-08-05

## Objetivo

Substituir a revisão web (`dj review` + FastAPI + `static/`) por um aplicativo
desktop em PySide6 que cobre o ciclo inteiro do TrackClassifier: escanear,
revisar a fila, navegar a biblioteca já rotulada e acompanhar o modelo.

A base visual e de componentes vem de dois materiais de referência já
existentes fora do repositório:

- `~/Downloads/trackclassifier` — design system: `design-tokens.json` como
  fonte única, `build_tokens.py` gerando `tokens.css` / `tokens.py` / `app.qss`,
  e `DESIGN-SYSTEM.md` com os contratos de componente.
- `~/Downloads/trackclassifier2` — esqueleto PySide6 rodando com dados
  mockados: janela, player, render RGB da waveform com cache LRU, delegates,
  modelo de tabela, conversão Camelot.

Os dois entram como **base de componentes**, não como a UI final.

## Decisões que sustentam o resto

| Decisão | Escolha |
|---|---|
| Plataforma | Desktop PySide6. A UI web morre. |
| Escopo | App inteiro: scan, train, review e biblioteca. |
| Dados | Fidelidade total ao design system: key/Camelot, tags, capa e waveform RGB. |
| Comunicação com o backend | In-process. O Qt importa `TrackService` direto; sem HTTP, sem servidor. |
| Layout | Abas por modo: Revisão, Biblioteca, Modelo. |
| Loop de revisão | Após 1/2/3 a próxima track carrega **parada** em `peak_offset_s`; o usuário dá play. |
| Scan | Ação global (botão na barra de abas, progresso na status bar), não uma aba. |

## Arquitetura

### Camadas

```
TrackService (backend atual, síncrono, sem Qt)
      ↕   acessado de dentro de uma QThread dedicada
ui/viewmodel.py       dataclasses puras — não importa Qt nem librosa
      ↕   sinais
ui/                   QMainWindow, abas, widgets, delegates
```

Regra de fronteira: **`viewmodel.py` não importa Qt, e a UI não importa
`TrackService`.** É o que permite testar a lógica de tela — o que aparece na
linha, o que a próxima tecla faz, quando a fila esvazia — com `pytest` puro,
sem `QApplication` e sem áudio.

### Árvore de arquivos

```
src/trackclassifier/
  config.py labels.py library.py cache.py features.py descriptors.py
  audio_io.py extraction.py model.py service.py apply.py     (backend atual)
  presentation.py       NOVO (fase 2) — cache lateral: tags, capa, key, buckets RGB
  cli.py                dj scan / dj train seguem headless; dj review abre a janela
  ui/
    __main__.py         QApplication, carrega app.qss
    viewmodel.py        TrackService -> dataclasses puras
    worker.py           QThread dona do serviço; emite progresso e resultados
    window.py           QMainWindow, barra de abas, status bar, botão de scan
    review_tab.py
    library_tab.py
    model_tab.py
    tokens.py           GERADO por build_tokens.py — não editar
    app.qss             GERADO por build_tokens.py — não editar
    widgets/
      waveform_render.py   portado do ref2
      waveform_view.py     portado do ref2
      delegates.py         portado do ref2
      transport_bar.py     portado do ref2
      now_playing.py       portado do ref2
      player.py            portado do ref2
      keys.py              portado do ref2 (puro, sem Qt)
      track_model.py       portado do ref2, adaptado às colunas reais
design/
  design-tokens.json    fonte única de verdade
  build_tokens.py       emite ui/tokens.py e ui/app.qss
```

### O que é removido

| Alvo | Motivo |
|---|---|
| `web.py`, `static/index.html`, `static/app.js` | substituídos pela janela |
| `streaming.py` | existia porque o navegador não toca `.flac` nem `.aiff` — transcodava com ffmpeg e mantinha cache. `QMediaPlayer` toca ambos direto. Some o módulo e some o diretório `transcoded/`. |
| `tests/test_web.py`, `tests/test_streaming.py` | acompanham os módulos |
| `fastapi`, `uvicorn` em `pyproject.toml` | sem uso após a remoção |
| geração de `tokens.css` em `build_tokens.py` | sem web, sem CSS |

### O que explicitamente NÃO é portado do ref2

`audio/analyzer.py` do ref2 monta um `QThreadPool` com `AnalysisTask` e
`AnalysisService`. Não é portado: `service._analyze` já resolve o mesmo
problema melhor — usa `ProcessPoolExecutor` (processo, não thread, o que
escapa do GIL num trabalho CPU-bound), salva o cache a cada N tracks para
sobreviver a interrupção, e contém tanto falha de worker quanto falha do
próprio pool sem derrubar o scan.

A UI precisa apenas não bloquear: uma `QThread` chama
`analyze_all(on_progress=...)` e o callback vira sinal. O paralelismo segue
sendo o do backend. Dois pools aninhados seriam duplicação e disputa de núcleo.

### Dependências

- `PySide6-Essentials` — dependência obrigatória (widgets, QPainter, threads).
- `PySide6-Addons` — extra opcional `audio`, traz `QtMultimedia`. Fica fora das
  deps obrigatórias justamente para que o CI instale só o Essentials.
- `mutagen` — leitura de tags e capa embutida (fase 2).

O `create_player()` do ref2 detecta a ausência de `QtMultimedia` e devolve um
`SimulatedPlayer` que move o playhead sem emitir som. Esse fallback é mantido:
é o que torna a UI exercitável em CI sem `Addons` e sem dispositivo de áudio.

## Design system

`design-tokens.json` continua sendo a única fonte de verdade.
`build_tokens.py` roda após qualquer edição no JSON e regenera
`ui/tokens.py` e `ui/app.qss` — QSS não tem variáveis, então a expansão é
obrigatória, e esquecer de regenerar é o modo de falha mais provável.

Ambos os arquivos gerados são comitados, com cabeçalho marcando que são
gerados. Os valores no `waveform_render.py` do ref2 (`LOW_GAIN`, `MID_GAIN`,
`HIGH_GAIN`, `FLOOR`, `BACKGROUND`) hoje estão duplicados à mão no módulo;
passam a ser importados de `ui/tokens.py`.

Regras de uso herdadas do `DESIGN-SYSTEM.md`, mantidas: nenhum hex fora do
JSON, dois pesos de fonte (400 e 500), números sempre em mono alinhados à
direita, sentence case, uma cor de accent por tela.

## As três abas

### Revisão

Uma track por vez, ocupando a aba inteira.

- Topo: título · artista · gênero, `KeyChip`, BPM e duração em mono à direita.
- Meio: waveform RGB grande com playhead; clique faz seek.
- Abaixo: palpite do modelo (`ClassificationChip` + confiança) e a legenda das
  três teclas.
- Rodapé: as três próximas da fila em mini-linhas.

Teclado:

| Tecla | Ação |
|---|---|
| `1` `2` `3` | −1 / neutra / +1 — move o arquivo, avança, e a próxima carrega **parada** em `peak_offset_s` |
| `espaço` | play/pause |
| `→` | pular sem decidir |
| `←` | voltar para a anterior |
| `⌘Z` | desfazer a última decisão |

**Desfazer é comportamento novo.** Hoje a decisão move o arquivo e não há
volta sem ir ao Finder. Com três teclas adjacentes e lotes de dezenas de
tracks, o erro de tecla é questão de tempo. Implementação: função nova em
`apply.py` que devolve o arquivo à pasta de origem, mais a remoção do exemplo
do conjunto de treino. Pilha de um nível apenas, não persistida entre
execuções.

Herdado da web sem mudança: aprovação em bloco por confiança ≥ 0.75 (com
diálogo de confirmação, porque move vários arquivos de uma vez), retreino
automático a cada 10 decisões, aviso quando o modelo está em
`low_confidence_mode`, e estado vazio orientando a escanear.

### Biblioteca

Tabela do ref2 com as colunas reais:
`Onda | Título | Artista | Gênero | BPM | Key | Classificação | Duração`.

Ordenável por qualquer coluna — o `_sort_key` do ref2 já empurra `None` para o
fim. Alternador Camelot ↔ clássica vem pronto do ref2. Acrescenta-se filtro por
rótulo (todos / +1 / neutra / −1) e busca por texto.

Reclassificar usa as mesmas três teclas: seleciona a linha, aperta, o arquivo
troca de pasta. Mesmo gesto das duas abas — é o que evita dois modelos mentais
para a mesma ação.

Altura de linha fixa em 46px (densidade confortável). A altura fixa não é
negociável: é o que permite ao `QTableView` calcular o offset do scroll sem
medir cada item.

### Modelo

Métricas que `train()` já devolve: acurácia leave-one-out, erro ordinal médio,
matriz de confusão 3×3 e número de exemplos. Botão **Retreinar**. Abaixo, a
lista de falhas de análise (arquivo + motivo), que hoje só sai em `stderr` e se
perde.

## Scan

Scan não é um modo e não tem tela própria: é ação de fundo com um gatilho e um
progresso.

- Gatilho: botão **⟳ Escanear** na ponta direita da barra de abas, alcançável
  de qualquer aba.
- Progresso: status bar, no formato `escaneando 18/34 · Bicep — Glue.flac`,
  com botão **Cancelar** (o `ProcessPoolExecutor` termina o que já começou e
  para de submeter).
- A janela permanece utilizável durante o scan: dá para revisar o que já foi
  analisado enquanto o resto processa.

**Ao abrir o app**, a janela aparece imediatamente com o que está em cache e o
scan dispara sozinho em segundo plano. Isto contrasta com o comportamento atual
do CLI, em que `_servico()` roda `analyze_all()` de forma síncrona em todo
comando — numa janela, isso seriam minutos de tela morta.

## Dados de apresentação

### Por que um cache separado

`cache.py` invalida seu conteúdo comparando `extractor.name`. Se key e buckets
RGB entrassem em `FEATURE_NAMES`, o nome do extrator mudaria e **toda a
biblioteca seria re-analisada do zero** — HPSS do librosa sobre centenas de
arquivos. Dado de apresentação vive separado, com versão própria.

```
.trackclassifier/
  cache.parquet          intocado — vetor de ML
  presentation.parquet   sha1, title, artist, album, genre, key_pc, key_mode, version
  covers/<sha1>.jpg      capa embutida, extraída uma vez
  peaks/<sha1>.npy       buckets (N,3) float16 para o render RGB
```

Capa e picos ficam em arquivo por track, não em coluna de parquet: o Qt carrega
sob demanda e o parquet não vira um blob de centenas de MB lido inteiro no
boot. Incrementar `version` recalcula apenas apresentação e **nunca toca no
cache de ML**.

A key é gravada em forma canônica — pitch class 0–11 mais modo — e formatada na
exibição. Gravar a string `"8A"` inviabilizaria trocar de notação depois.

### Quando cada dado é computado

| Dado | Custo | Quando |
|---|---|---|
| tags + capa (`mutagen`) | ~1ms, não decodifica áudio | durante o scan, junto com o resto |
| buckets RGB | STFT, caro | preguiçoso: quando a linha entra em tela, na mesma pool |
| key (chroma CQT → correlação Krumhansl-Schmuckler) | ~1–2s | mesmo caminho preguiçoso |

Preguiçoso e priorizado pelo que está visível, em vez de backfill da biblioteca
inteira: o usuário abre o app para revisar dezenas de tracks, não para esperar
centenas serem re-lidas. Enquanto os buckets não existem, a linha mostra um
placeholder liso.

### Cache de sha1

`library.py` calcula `file_sha1` de todo arquivo antes de qualquer outra coisa,
lendo cada um por inteiro. Com centenas de tracks isso significa gigabytes de
I/O e, sozinho, já são minutos de janela morta.

O sha1 passa a ser cacheado por `(path, mtime, size)`. É mudança pequena em
`library.py` e é o que torna verdadeira a promessa de a janela abrir na hora —
sem ela, o resto do design de concorrência não salva o boot.

## Concorrência

Uma regra única: **uma `QThread` é dona do `TrackService`.** Todo acesso ao
serviço acontece nela; a UI envia pedidos e recebe sinais. O
`ProcessPoolExecutor` continua vivendo dentro do serviço, na thread dele.

Consequência: sem lock, sem `TrackService` compartilhado entre threads, sem
parquet escrito de dois lugares.

## Erros e estados

| Situação | Comportamento |
|---|---|
| Track ainda sem análise | Chip de classificação vira skeleton pulsando em `surface-3` |
| Buckets ainda não computados | Waveform mostra placeholder liso |
| Arquivo sumiu entre o scan e a decisão | `FileVanishedError` (já existe em `apply.py`) vira mensagem na status bar; a track sai da fila |
| Análise falhou | Entra na lista de falhas da aba Modelo, com o motivo |
| `QtMultimedia` ausente | `SimulatedPlayer`; a status bar informa que não há áudio |
| Poucos exemplos rotulados | Aviso de `low_confidence_mode` na aba Revisão |

## Testes

| Camada | Como |
|---|---|
| `viewmodel.py` | `pytest` puro, sem `QApplication` — é a razão de ele não importar Qt |
| `presentation.py` | áudio sintético via `soundfile`, já presente nas deps de dev |
| `keys.py` | funções puras do ref2, as 24 tonalidades |
| `waveform_render.py` | numpy → QPixmap, com `QT_QPA_PLATFORM=offscreen` |
| janela e abas | teste de fumaça: abre, carrega, aperta 1/2/3, fecha — com `SimulatedPlayer` |

Os testes atuais somam 1880 linhas; saem 298 (web e streaming) e o restante
continua válido, porque o backend não muda de forma.

O workflow de CI existente ganha `QT_QPA_PLATFORM=offscreen`. Sem
`PySide6-Addons` no runner, o player simulado cobre os caminhos de reprodução.

## Escopo cortado

- Tela de login — o próprio `DESIGN-SYSTEM.md` já duvida dela num app que lê
  arquivos locais.
- Tema claro — a waveform RGB só funciona sobre fundo escuro.
- Colorir a linha inteira por classificação — competiria visualmente com a
  waveform. Fica só o chip.
- Destaque de keys compatíveis (±1 na roda de Camelot e o par A/B) — é feature
  de montar set, não de classificar energia.
- Densidade compacta de 28px — v1 fica só na confortável; densidade só pesa com
  biblioteca grande.

## Entrega em fases

| Fase | Entrega |
|---|---|
| **1** | Remoção da web. Janela com as três abas contra o `TrackService` real. Waveform derivada do `energy_curve` existente (mono, ainda não RGB). Scan global em background, cache de sha1, desfazer. **Revisável de ponta a ponta.** |
| **2** | `mutagen`: artista, título, gênero e capa. A tabela ganha as colunas. |
| **3** | Buckets RGB — `render_peaks` do ref2 ligado ao dado real. |
| **4** | Key/Camelot, `KeyChip`, alternador de notação. |

A fase 1 já substitui o `dj review` atual com folga. As três seguintes são
aditivas e cada uma se justifica sozinha.

**Cada fase recebe seu próprio plano de implementação.** Esta spec cobre as
quatro; o plano a ser escrito agora é o da fase 1. As fases 2 a 4 só ganham
plano quando a anterior estiver entregue — antes disso, planejar em detalhe é
adivinhar contra uma UI que ainda não existe.

`dj scan` e `dj train` continuam disponíveis no terminal, para rodar sem abrir
janela. `dj review` passa a abrir o aplicativo.
