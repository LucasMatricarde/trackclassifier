# Performance da janela — plano de implementacao

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar da thread da GUI o trabalho que faz a aba Biblioteca engasgar
(primeiro paint de 482 ms, 21,6 ms por parada de rolagem) e impedir que a
rolagem afogue a thread do servico com computo de ondas, que hoje deixa uma
decisao pelo teclado sem resposta por ~2 minutos.

**Architecture:** Nada de novo entra em cena — as duas correcoes movem trabalho
para onde ele ja podia estar. A miniatura da capa deixa de ser derivada da capa
original dentro de `paint()` e passa a ser lida de um thumb reduzido em disco,
gerado pela propria tela na primeira vez e reaproveitado em toda abertura
seguinte. E a decisao de "quais ondas computar" sobe do delegate (que so
enxerga a celula que esta pintando) para a aba (que sabe perguntar ao
`QTableView` o que o viewport cobre agora), ganhando de graca um teto de
concorrencia e um atraso que descarta o que passou voando durante um arrasto.

**Tech Stack:** `QImageReader` (decodificacao escalada, ja disponivel via
PySide6), `QTimer` single-shot. Nenhuma dependencia nova.

---

## Medicoes que motivam o plano

Biblioteca real do usuario: 354 tracks rotuladas, 349 capas embutidas
(720x720 a 1280x720), 51 tracks com buckets de banda ja computados.

Paint da aba Biblioteca, offscreen, viewport de 638x441 (15 linhas visiveis):

| | medido |
|---|---|
| 1o paint (cache de pixmap frio) | **482,6 ms** |
| scroll ate o fim (78 paradas) | 1687,6 ms — **21,6 ms/parada** |
| uma tecla no campo de busca | 49–58 ms |
| paint com o cache quente | 2,8 ms |

`cProfile` do primeiro paint mais um scroll completo (1,761 s no total):

| funcao | tottime | fatia |
|---|---|---|
| `delegates.TitleDelegate._miniatura` | 1,270 s | **72%** |
| `track_model.TrackTableModel.data` (88.196 chamadas) | 0,089 s cum | 5% |
| `delegates._DelegateComFundo._pinta_fundo` (5.188 chamadas) | 0,073 s cum | 4% |
| `waveform_render.render_curve` (299 chamadas) | 0,039 s cum | 2% |

Dentro de `_miniatura`, `QPixmap.scaled` responde por apenas 0,042 s: **o custo
e o decode do jpeg em resolucao cheia**, nao a reducao.

Tres caminhos ate a miniatura de 34px, medidos sobre as mesmas 60 capas:

| caminho | ms/capa |
|---|---|
| `QPixmap(capa)` + `scaled` (o que rodava em `paint()`) | 4,25 |
| `QImageReader.setScaledSize` | 2,07 |
| thumb de 96px em disco + `scaled` | **0,22** |

Gerar os thumbs custa ~5,8 ms por capa, uma vez, e ~14 KB cada (≈5 MB para o
acervo inteiro).

Fila de peaks: `compute_bands` custa ~0,4 s por track (medido em tres tracks
reais, descartada a primeira por conta do import a frio). Rolar a biblioteca
inteira pintava as 303 linhas sem buckets e enfileirava 303 computos —
**~2 minutos** de thread do servico ocupada, com `decide`/`undo`/`train`
esperando atras na mesma fila de slots.

---

## Global Constraints

- **`presentation.py` continua sem importar Qt.** `dj scan` e `dj train` rodam
  headless (ver CLAUDE.md); por isso a GERACAO do thumb mora em `ui/`, e o que
  o dominio faz e apenas apagar o thumb obsoleto — um `unlink`, sem Qt.
- **`ui/viewmodel.py` continua sem importar Qt.** Nada deste plano o toca;
  `tests/test_viewmodel.py` falha gramaticalmente se isso mudar.
- **Nenhuma camada nova, e a direcao das existentes nao inverte.**
  `viewmodel` → `worker` → widgets continua valendo: a aba fala com o worker
  por sinal/slot, e nunca com `TrackService`.
- **`PRESENTATION_VERSION` nao e bumpado.** O thumb e derivado da capa, e a
  capa e chaveada por sha1 do CONTEUDO do audio — capa nova so aparece com
  sha1 novo, ou com um `put()` que ja apaga o thumb velho. Nada do que este
  plano produz entra em `presentation.parquet`.
- **O thumb e cache descartavel, igual a `peaks/`.** Apagar `covers/*.thumb.png`
  a mao e sempre seguro; falhar ao grava-lo nao pode quebrar o paint.
- **`paint()` nao pode levantar.** Vale para o caminho novo do thumb tanto
  quanto para `load_peaks`: arquivo corrompido, sumido ou em formato
  desconhecido vira placeholder, nunca traceback.
- **Comportamento visual identico.** A miniatura continua sendo o mesmo
  recorte `KeepAspectRatioByExpanding` de 34px que a linha ja mostrava. Este
  plano e sobre custo, nao sobre aparencia.
- **Portugues sem acentos** no codigo, como no resto de `src/`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/ui/widgets/thumbs.py` | Nova. Le/gera a miniatura: thumb em disco quando existe, decode escalado da capa quando nao. |
| `src/trackclassifier/presentation.py` | Modificado. `THUMB_SUFFIX`; `put()` apaga o thumb obsoleto ao gravar capa nova. |
| `src/trackclassifier/ui/widgets/delegates.py` | Modificado. `TitleDelegate` usa `thumbs` e cache maior; `WaveformDelegate` para de pedir computo e expoe `tem_peaks`. |
| `src/trackclassifier/ui/library_tab.py` | Modificado. Passa a ser quem pede computo, olhando o viewport, com atraso e teto. |
| `src/trackclassifier/ui/worker.py` | Modificado. Sinal `peaks_failed`, para o teto da aba nao vazar. |
| `src/trackclassifier/ui/window.py` | Modificado. Liga `peaks_failed` a aba Biblioteca. |
| `src/trackclassifier/ui/widgets/track_model.py` | Modificado. `data()` sai antes de construir `Column` para os roles que nao usa. |
| `tests/test_thumbs.py` | Nova. Comportamento do thumb: cria, reusa, invalida, degrada. |
| `tests/test_delegates.py` | Modificado. O teste do gatilho preguicoso sai do delegate e vira teste de viewport na aba. |
| `tests/test_presentation.py` | Modificado. Capa nova apaga o thumb velho. |
| `tests/test_worker.py` | Modificado. `peaks_failed` dispara quando o computo nao produz caminho. |
| `CLAUDE.md` | Modificado. Documenta as duas decisoes e a armadilha do thumb sem versao. |

---

### Task 1: `thumbs.py` — miniatura barata

**Files:**
- Create: `src/trackclassifier/ui/widgets/thumbs.py`
- Modify: `src/trackclassifier/presentation.py`
- Modify: `src/trackclassifier/ui/widgets/delegates.py` (`TitleDelegate`)
- Test: `tests/test_thumbs.py`, `tests/test_presentation.py`

**Interfaces:**
- Consumes: `presentation.THUMB_SUFFIX`, `TrackRow.cover_path`
- Produces:
  - `thumbs.THUMB_SIZE: int` = 96
  - `thumbs.thumb_path(cover_path: str | Path) -> Path` — irmao da capa,
    `<sha1>.thumb.png`. Nao garante existencia.
  - `thumbs.load_thumbnail(cover_path: str | Path, side: int) -> QPixmap | None`
    — miniatura quadrada de `side` px; `None` quando a capa nao abre.
  - `presentation.THUMB_SUFFIX: str` = `".thumb.png"`

**Decisoes e o porque:**

- **O sufixo e composto (`.thumb.png`), nao `.png`.** `PresentationCache` grava
  `covers/<sha1><sufixo do mime>`; um acervo com capa em PNG produziria
  `<sha1>.png` dos dois lados e o thumb sobrescreveria a capa.
- **A constante mora em `presentation.py`, nao em `thumbs.py`.** Quem apaga o
  thumb obsoleto e o `put()` do dominio, e o dominio nao pode importar `ui/`.
  `ui/` importando do dominio e a direcao permitida.
- **96px, e nao 34px exatos.** A mesma miniatura serve densidades de tela
  diferentes e uma linha mais alta sem voltar a capa original.
- **`setScaledSize` com `max()`, nao `min()`.** E o que corresponde ao
  `KeepAspectRatioByExpanding` do recorte final; com `min()` a imagem chegaria
  menor que o lado pedido num dos eixos e teria que ser AMPLIADA de volta.
- **Thumb ruim volta para a capa original e reescreve.** Um PNG truncado por
  interrupcao nao pode condenar a linha ao placeholder para sempre.
- **Gravar falha em silencio.** Disco cheio ou pasta somente leitura custam
  desempenho, nao correcao: a miniatura ja esta em memoria.

- [x] **Step 1: Escrever os testes que falham** (`tests/test_thumbs.py`)

Casos:
- `load_thumbnail` de uma capa sem thumb cria `<stem>.thumb.png` ao lado e
  devolve pixmap de `side x side`.
- Segunda chamada nao toca mais a capa original — provado apagando a capa
  entre as duas chamadas e verificando que a segunda ainda devolve pixmap.
- Capa corrompida devolve `None` e nao cria thumb.
- Thumb corrompido cai na capa original, devolve pixmap e REESCREVE o thumb.
- Pasta somente leitura: devolve pixmap mesmo sem conseguir gravar.
- `thumb_path` nunca colide com a capa quando a capa e `.png`.

- [x] **Step 2: Implementar `thumbs.py`**
- [x] **Step 3: `presentation.put()` apaga o thumb obsoleto** + teste em
      `tests/test_presentation.py` (grava capa A, cria thumb a mao, grava capa
      B, thumb sumiu).
- [x] **Step 4: `TitleDelegate._miniatura` chama `load_thumbnail`**, capacidade
      do `PixmapCache` de 256 para 1024 (uma miniatura de 34px ocupa ~4 KB; com
      256 o cache nao cabia as 354 linhas do acervo real e uma segunda passada
      de scroll redecodificava tudo).
      `test_cache_de_capa_evita_reler_o_disco_a_cada_paint` continua valendo
      sem alteracao — `_leituras` segue contando as idas ao disco.
- [x] **Step 5: Verificar** — `uv run pytest tests/test_thumbs.py
      tests/test_delegates.py tests/test_presentation.py`

---

### Task 2: computo de ondas so do que esta no viewport

**Files:**
- Modify: `src/trackclassifier/ui/widgets/delegates.py` (`WaveformDelegate`)
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `src/trackclassifier/ui/worker.py`
- Modify: `src/trackclassifier/ui/window.py`
- Test: `tests/test_delegates.py`, `tests/test_worker.py`, `tests/test_window.py`

**Interfaces:**
- Removed: `WaveformDelegate.peaks_requested`, `WaveformDelegate._pede_computo`
- Produces:
  - `WaveformDelegate.tem_peaks(sha1: str) -> bool`
  - `library_tab.MAX_PEAKS_EM_VOO: int` = 3
  - `library_tab.ATRASO_PEAKS_MS: int` = 250
  - `LibraryTab.peaks_falharam(sha1: str) -> None`
  - `ServiceWorker.peaks_failed = Signal(str)`
- `LibraryTab.peaks_requested` continua existindo com a mesma assinatura, e
  `window.py` continua ligando-o a `worker.compute_peaks` — o que muda e so
  quem, dentro da aba, decide emitir.

**Decisoes e o porque:**

- **A dedup por sha1 do delegate nao era suficiente, e nao tinha como ser.**
  Ela impedia pedir a MESMA track duas vezes, mas nao impedia pedir 303 tracks
  diferentes: `paint()` nao tem como saber o que continua na tela. Por isso a
  decisao sobe de camada em vez de ganhar mais um filtro.
- **Atraso de 250 ms reiniciado a cada rolagem.** Um arrasto longo nao deixa
  rastro: so a parada final vira pedido. Um debounce sobre "o que foi pintado"
  nao serviria — acumularia o rastro do arrasto inteiro.
- **Teto de 3 em voo.** A thread do servico serve os slots em ordem de chegada,
  entao o teto e o que garante que uma tecla 1/2/3 nunca espere mais que ~1 s.
- **`peaks_failed` existe pelo teto, nao pela mensagem.** Continua sem virar
  aviso na status bar (uma track sem onda colorida segue classificavel), mas
  sem o sinal uma falha ocuparia uma vaga do teto para sempre e depois de tres
  a aba pararia de pedir qualquer onda.
- **`_peaks_sem_sucesso` e limpo em `set_state`, `_peaks_em_voo` nao.** Um scan
  novo pode ter resolvido a causa da falha; ja um pedido em voo continua na
  fila do worker e a resposta ainda vai chegar — limpa-lo deixaria o teto
  contando errado.
- **`showEvent`/`resizeEvent` tambem agendam.** Trocar de aba e esticar a
  janela revelam linhas novas sem mexer na barra de rolagem, entao
  `valueChanged` nao dispara.
- **`valueChanged` conecta a um metodo, nao a `QTimer.start`.** O sinal carrega
  um `int` e o overload `QTimer.start(msec)` o aceitaria: a posicao da barra
  viraria o intervalo do timer.
- **A aba Revisao nao muda.** Ela pede uma track por vez — a exibida, que e a
  prioridade real — e a dedup dela ja e correta para esse caso.

- [x] **Step 1: Escrever os testes que falham**

`tests/test_delegates.py` (substituindo
`test_delegate_pede_computo_de_quem_nao_tem_buckets`):
- Pintar uma linha sem buckets NAO emite nada (o delegate nao pede mais).
- `LibraryTab` com N linhas e viewport curto pede apenas as visiveis, nunca as
  de baixo.
- Rolagem nao pede antes do timer disparar.
- Nunca mais que `MAX_PEAKS_EM_VOO` pedidos simultaneos.
- `peaks_prontos` libera a vaga e o proximo pedido sai.
- `peaks_falharam` libera a vaga e a mesma sha1 nao e pedida de novo.
- `set_state` reabre as sha1 que falharam.

`tests/test_worker.py`:
- `compute_peaks` emite `peaks_failed` quando `ensure_peaks` devolve `None`.
- `compute_peaks` emite `peaks_failed` quando `ensure_peaks` levanta.

- [x] **Step 2: `WaveformDelegate` perde o sinal e ganha `tem_peaks`**
- [x] **Step 3: `LibraryTab` ganha o timer, o teto e `_pede_peaks_visiveis`**
- [x] **Step 4: `worker.compute_peaks` emite `peaks_failed`**
- [x] **Step 5: `window.py` liga `peaks_failed` a `library_tab.peaks_falharam`**
- [x] **Step 6: Verificar** — `uv run pytest tests/test_delegates.py
      tests/test_worker.py tests/test_window.py`

---

### Task 3: `data()` sai cedo

**Files:**
- Modify: `src/trackclassifier/ui/widgets/track_model.py`
- Test: `tests/test_delegates.py` (cobertura existente ja exercita todos os
  roles; nenhum teste novo — e refatoracao sem mudanca de contrato)

**Decisao:** `data()` e chamado 88.196 vezes num scroll da biblioteca — o Qt
pede varios roles por celula (decoracao, fonte, tooltip, check state) e a
versao atual constroi `Column(index.column())` antes de descobrir que nao vai
usar nenhum deles. Reordenar para responder `TRACK_ROLE` e `TextAlignmentRole`
primeiro, sair em `role != DisplayRole`, e so entao construir o enum.

- [x] **Step 1: Reordenar `data()`**
- [x] **Step 2: Verificar** — `uv run pytest tests/test_delegates.py`

**Nao incluido, e por que:** `_pinta_fundo` estava na lista de otimizacoes
menores, mas o profile mostra que os 4% dele sao `initStyleOption`
(0,056 s) e `drawControl` (0,006 s) — trabalho inerente do Qt. A copia do
`QStyleOptionViewItem`, unica parte evitavel, mede ~0,010 s de 1,761 s (0,6%),
e reusar uma instancia exigiria mutar o `option` do chamador. Nao compensa o
risco.

---

### Task 4: verificacao e documentacao

- [x] **Step 1:** `uv run pytest` (suite completa)
- [x] **Step 2:** `uv run ruff check .`
- [x] **Step 3:** Re-medir com o mesmo bench de paint sobre a biblioteca real e
      registrar aqui o antes/depois de: 1o paint, ms por parada de scroll, e
      tecla na busca.
- [x] **Step 4:** `CLAUDE.md` — documentar (a) que a miniatura vem de um thumb
      em disco gerado pela tela e que `covers/*.thumb.png` e cache descartavel
      sem versao dentro, igual a `peaks/`; (b) que quem pede computo de ondas e
      a aba pelo viewport, com o motivo medido; (c) que `presentation.py`
      continua sem Qt e por isso a geracao mora em `ui/`.

---

## Resultado medido

Mesmo bench de paint (offscreen, `viewport 638x441`, 15 linhas visiveis),
biblioteca real: 354 tracks, 349 capas, 51 com peaks. Duas colunas de
"depois" porque o thumb muda o comportamento entre a primeira abertura pos-
upgrade e todas as seguintes -- a segunda e o caso comum do dia a dia.

| | antes | depois, 1a abertura (thumbs inexistentes) | depois, abertura seguinte (thumbs em disco) |
|---|---|---|---|
| 1o paint da aba Biblioteca | 482,6 ms | 57–62 ms (**~8x**) | 29,5 ms (**~16x**) |
| scroll ate o fim, por parada | 21,6 ms | 17,8–18,0 ms | 5,6 ms (**~3,9x**) |
| tecla na busca | 49–58 ms | 4,4–7,1 ms | 4,9–7,1 ms |
| computos de onda enfileirados por um scroll completo | 303 (~2 min de thread do servico) | 0–`MAX_PEAKS_EM_VOO` por vez, so o que o viewport pediu | idem |

A primeira abertura pos-upgrade decodifica cada capa uma vez (caminho
`QImageReader` escalado, ~2 ms) e grava o thumb; e o que explica scroll ainda
proximo do numero antigo nessa passada -- cada linha revelada e nova.
Da segunda abertura em diante, todo `_miniatura` bate no thumb de 96px
(~0,22 ms), e e onde o ganho aparece de verdade.

**Efeito colateral do benchmark:** rodar o bench sobre `.trackclassifier/`
real (nao um fixture) gravou os 349 `covers/*.thumb.png` de producao -- e o
comportamento pretendido (o mesmo que `dj review` faria na primeira
abertura), nao um artefato de teste a limpar.
