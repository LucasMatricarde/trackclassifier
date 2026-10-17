---
name: trackclassifier-ui
description: Use ao mexer em qualquer coisa dentro de src/trackclassifier/ui/ ou em config.py do trackclassifier - janela PySide6, abas Revisao/Biblioteca/Modelo, delegates, viewmodel, worker, first run, tela de configuracoes. Cobre as camadas (viewmodel sem Qt -> worker -> widgets), a regra de uma so thread dona do TrackService, quem pede o computo das ondas olhando o viewport, o thumb da capa e a separacao validar/aplicar do config. Gatilhos: "widget", "delegate", "paint", "QThread", "sinal/slot", "janela travando", "tabela lenta", "tela de settings".
---

# Camadas e regras da UI

## `ui/viewmodel.py` nao importa Qt

E a fronteira entre o dominio e a tela: `viewmodel.py` traduz `TrackService` em
dataclasses puras (`TrackRow`, `ReviewState`, `LibraryState`, `ModelState`) que
os widgets consomem, e nada nele sabe o que e um `QWidget`. Isso e o que permite
testar a logica de tela -- o que aparece, quantas faltam, quando a fila esvazia
-- com pytest puro, sem `QApplication`. Ha um teste
(`tests/test_viewmodel.py`) que garante isso gramaticalmente, lendo o modulo e
falhando se aparecer um import de PySide6 -- nao adicione um import de Qt aqui,
mesmo que pareca inofensivo.

## Camadas

`viewmodel.py` (sem Qt, dados puros) -> `worker.py` (`ServiceWorker`, os slots que
rodam na thread do servico, so fala com `TrackService` e com o viewmodel) ->
`window.py`/`review_tab.py`/`library_tab.py`/`model_tab.py`/`widgets/` (widgets
Qt, so falam com o worker por sinal/slot, nunca com `TrackService` direto). Cada
camada so conhece a de baixo; um widget que chamasse `TrackService` direto
quebraria a regra de "uma so thread dona do servico" (ver
`trackclassifier-concorrencia`).

## Quem pede o computo de uma onda e a aba, olhando o viewport -- nunca o delegate

`WaveformDelegate.paint()` so desenha; ele nao tem sinal `peaks_requested`
nenhum. A versao anterior emitia dali, com dedup por sha1 -- parecia suficiente e
nao era: `paint()` nao sabe o que mais esta na tela, so a celula que esta pintando
naquele instante. Rolar a biblioteca real (354 tracks, a maioria sem buckets
ainda) pintava ~300 linhas sem onda colorida uma vez cada e enfileirava ~300
computos de `ensure_peaks` (~0,4 s cada) na MESMA thread que atende
`decide`/`undo`/`train` -- depois de um scroll ate o fim, teclar 1/2/3 ficava sem
resposta por ~2 minutos, porque os slots dessa thread sao servidos em ordem de
chegada.

`LibraryTab._pede_peaks_visiveis` corrige isso perguntando ao `QTableView` quais
linhas o viewport cobre AGORA: um `QTimer` de `ATRASO_PEAKS_MS` (250ms),
reiniciado a cada rolagem, absorve o arrasto (so a parada final vira pedido), e
`MAX_PEAKS_EM_VOO` (3) limita quantos `compute_peaks` ficam pendentes na thread
do servico ao mesmo tempo -- e o que garante que uma decisao pelo teclado nunca
espere mais que ~1s atras da fila. `ServiceWorker.peaks_failed` existe so por
causa desse teto: sem avisar uma falha, a vaga dela nunca seria liberada e a aba
pararia de pedir qualquer onda depois de tres falhas.

## A miniatura da capa vem de um thumb reduzido em disco

`ui/widgets/thumbs.py` grava `covers/<sha1>.thumb.png` (96px) na primeira vez que
a linha e pintada, e toda pintura seguinte le esse arquivo pequeno em vez de
decodificar o jpeg embutido inteiro (720x720 a 1280x720 numa biblioteca real) so
para reduzi-lo a 34px. Medido: decodificar a capa cheia e escalar custava
4,25 ms; ler o thumb, 0,22 ms. Era 72% do tempo de paint da aba Biblioteca -- o
primeiro paint caia de 482 ms para ~60 ms so com isso, e para ~30 ms depois que o
thumb ja existe em disco (toda abertura a partir da segunda).

A geracao mora em `ui/` e nao em `presentation.py`: `dj scan` e `dj train` rodam
headless e nao importam Qt (ver `trackclassifier-empacotamento`), e reduzir um
jpeg precisa de um decodificador de imagem -- a tela e a unica camada que tem um.
A invalidacao do thumb esta em `trackclassifier-apresentacao`.

## `config.py` cresceu para servir a tela

Alem de `load_config`, ele expoe `read_raw` (parse sem validar, para preencher o
formulario quando o config esta quebrado), `SettingsDraft` (o texto cru dos
campos), `validate_settings` (puro, roda a cada tecla) e `apply_draft` (cria as
pastas, roda uma vez ao salvar). A separacao entre validar e aplicar e o que
permite validar a cada tecla sem criar uma pasta a cada tecla -- e o que mantem
toda a regra testavel sem `QApplication`.

## Cores

Nenhum hex fora de `design/design-tokens.json`; `ui/tokens.py` e `ui/app.qss` sao
gerados por `uv run python design/build_tokens.py`. Ha teste que varre `ui/` atras
de hex literal (`tests/test_tokens.py::test_nenhum_hex_fora_do_json`).
