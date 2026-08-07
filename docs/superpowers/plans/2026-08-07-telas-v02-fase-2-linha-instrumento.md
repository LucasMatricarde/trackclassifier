# Telas v0.2 — Fase 2: a linha instrumento — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para implementar task a task. Steps usam checkbox (`- [ ]`).

**Goal:** Trocar a linha generica da Biblioteca pela anatomia fechada na rodada
3a do pack: faixa unica de 44px, capa como coluna ancora, onda de 480, escala
ordinal de tres segmentos no lugar do chip de texto, cabecalho micro-label e os
sete estados de linha.

**Architecture:** **Nao** vira um delegate de linha monolitico. O mockup 3a e
colunar, e a tabela ja e colunar com um delegate por coluna -- a mudanca e de
colunas e de pintura dentro de cada delegate, nao de arquitetura. Isso preserva
`_DelegateComFundo`, o `PixmapCache` e o gate de peaks por viewport, que sao os
tres pontos onde a perf da aba foi conquistada (`ba53271`).

**Tech Stack:** PySide6, pytest, ruff. Nada novo.

Depende de: `docs/superpowers/specs/2026-08-07-telas-v02-instrumento-design.md`
e da Fase 1 (fontes, `MicroLabel`, `colors.para_qcolor`, `Meter`).

## Global Constraints

- Portugues sem acentos em nomes locais, comentarios, docstrings e testes. API
  publica em ingles.
- Nenhum `#RRGGBB` fora de `design/design-tokens.json` — inclusive em docstring
  (a varredura e por linha).
- `ui/viewmodel.py` nao importa Qt.
- `_DelegateComFundo._pinta_fundo` continua sendo chamado **antes de qualquer
  `return`** em todo `paint()`. Um paint que desiste sem pintar o fundo apaga a
  selecao sob aquela coluna.
- `WaveformDelegate` **nao pede** computo de buckets. Quem pede e
  `LibraryTab._pede_peaks_visiveis`, olhando o viewport. Ver o docstring do
  delegate para os numeros que justificam.
- ruff `line-length = 100`, regras `E,F,I,UP,B`.

---

## Decisoes que este plano fecha

### As colunas mudam, e uma some

| Hoje | 3a |
|---|---|
| `WAVEFORM, TITULO, ARTISTA, GENERO, BPM, KEY, CLASSIFICACAO, CONFIANCA, DURACAO` | `CAPA, TITULO, ONDA, GENERO, BPM, KEY, CLASSE, DURACAO` |

- **`CAPA` vira coluna propria.** Hoje a capa e desenhada dentro do
  `TitleDelegate`, o que faz o titulo comecar em x variavel quando a capa falha
  ao carregar. Coluna separada de largura fixa resolve por construcao.
- **`TITULO` e `ARTISTA` viram uma coluna so**, com titulo em
  `font.weight.medium` e artista em `text.secondary` na mesma baseline, gap 8.
  A ordenacao por artista continua existindo (o `_sort_key` nao depende de a
  coluna existir na tela) mas perde o cabecalho clicavel — registrar como perda
  aceita, nao como esquecimento.
- **`CONFIANCA` sai.** E a unica coluna do mockup que some, e a decisao e de
  produto, nao de layout: na Biblioteca a track ja esta classificada, e a
  confianca do modelo sobre uma decisao **humana** ja tomada nao muda nenhuma
  acao. Onde ela e acionavel — explicando a posicao na fila de active learning
  — e na Revisao, e la ela vira medidor na Fase 3. O dado continua no
  `TrackRow`; so nao ocupa coluna.

### Larguras (LEIA-ME do pack, secao "A linha da Biblioteca")

    capa 38 · titulo flex (min 220) · onda 480 · genero 96 · bpm 52 ·
    key 56 · classe 72 · dur 52
    gap 10 · padding 12 esquerda / 20 direita (8 reservados pro scrollbar)

Compacta (32px): mesmas colunas, capa 28, onda 20 de altura.

### O chip de classe vira escala ordinal

Tres segmentos de 9x9, gap 3, na ordem de `LABEL_ORDER`. O ativo em
`classification.<x>.base`; os inativos so com `inset 1px border.default`, sem
preenchimento. Tres classes ordenadas leem melhor como escala que como rotulo,
e o chip de texto competia com o chip de Camelot ao lado.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `ui/widgets/delegates.py` | `CoverDelegate` (nova), `TitleDelegate` (so texto agora), `WaveformDelegate` (caixa de fundo + alturas), `ClassificationDelegate` (segmentos), `KeyDelegate` (raio e padding da v0.2). |
| `ui/widgets/row_states.py` | **Criar.** `EstadoDaLinha` — deriva o estado (default/pendente/falhou/tocando) de uma `TrackRow`, sem Qt no calculo. Um lugar so, consultado por todos os delegates. |
| `ui/widgets/track_model.py` | `Column` nova, larguras, headers, alinhamentos. |
| `ui/library_tab.py` | Aplica larguras, densidade, delegate de capa, cabecalho micro-label. |
| `ui/app.qss` (via `build_tokens.py`) | Estados de linha: hover, selecao com barra de 2px, anel de foco. |

---

### Task 1: o estado da linha vira um lugar so

**Files:**
- Create: `src/trackclassifier/ui/widgets/row_states.py`
- Test: `tests/test_row_states.py`

**Interfaces:**
- Produces: `EstadoDaLinha` (`StrEnum`): `NORMAL`, `PENDENTE`, `FALHOU`,
  `TOCANDO`.
- Produces: `estado_da_linha(row: TrackRow, *, sha1_tocando: str | None,
  motivo_da_falha: str | None) -> EstadoDaLinha`.

Quatro delegates precisam da mesma resposta ("esta linha tem analise?"). Cada um
derivando por conta propria e como quatro definicoes de pendente divergem.

- [ ] **Step 1: Escrever o teste que falha**

```python
from trackclassifier.ui.widgets.row_states import EstadoDaLinha, estado_da_linha


def _linha(**mudancas):
    from trackclassifier.ui.viewmodel import TrackRow

    base = dict(
        sha1="abc", filename="a.wav", label="+1", predicted=None, score=None,
        confidence=None, bpm=128.0, duration_s=300.0, energy_curve=(0.1, 0.2),
        peak_offset_s=1.0, path_hint="/tmp/a.wav",
    )
    return TrackRow(**{**base, **mudancas})


def test_linha_com_analise_e_normal():
    assert estado_da_linha(_linha(), sha1_tocando=None, motivo_da_falha=None) is (
        EstadoDaLinha.NORMAL
    )


def test_sem_bpm_e_sem_curva_e_pendente():
    linha = _linha(bpm=0.0, energy_curve=())

    assert estado_da_linha(linha, sha1_tocando=None, motivo_da_falha=None) is (
        EstadoDaLinha.PENDENTE
    )


def test_motivo_de_falha_vence_pendente():
    linha = _linha(bpm=0.0, energy_curve=())

    # Falhou e mais especifico que pendente: a track nao esta esperando
    # analise, ela ja tentou e nao deu. Mostrar "pendente" esconderia isso.
    assert estado_da_linha(
        linha, sha1_tocando=None, motivo_da_falha="ffmpeg nao encontrado"
    ) is EstadoDaLinha.FALHOU


def test_tocando_vence_normal():
    assert estado_da_linha(_linha(), sha1_tocando="abc", motivo_da_falha=None) is (
        EstadoDaLinha.TOCANDO
    )


def test_tocando_nao_vence_falhou():
    # Nao da para tocar o que nao decodifica. Se os dois aparecerem, o
    # estado tocando e um bug em outro lugar -- e esconder a falha
    # atrasaria a descoberta.
    linha = _linha(bpm=0.0, energy_curve=())

    assert estado_da_linha(
        linha, sha1_tocando="abc", motivo_da_falha="x"
    ) is EstadoDaLinha.FALHOU
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/test_row_states.py -v`
- [ ] **Step 3: Implementar.** Ordem de precedencia: `FALHOU` > `TOCANDO` >
      `PENDENTE` > `NORMAL`. "Pendente" = `not row.energy_curve and not row.bpm`.
- [ ] **Step 4: Rodar e ver passar**
- [ ] **Step 5: Commit** — `feat(trackclassifier): estado de linha vira funcao unica`

---

### Task 2: a capa sai do TitleDelegate

**Files:**
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Test: `tests/test_delegates.py`

**Interfaces:**
- Produces: `CoverDelegate(_DelegateComFundo)` com `clear_cache()` e o mesmo
  `PixmapCache(capacity=1024)` que o `TitleDelegate` tinha.
- Produces: `TitleDelegate` sem capa — pinta titulo + artista.

Tres estados obrigatorios da capa, todos na MESMA caixa de 38x38 (ou 28 em
compacta), `radius.sm`:

| Estado | Visual |
|---|---|
| Com capa | miniatura |
| Sem capa | inicial do titulo em `font.family.mono` / `text.disabled` sobre `surface.2` |
| Carregando | caixa vazia `surface.1` |

**Nao tingir o placeholder com a cor de Camelot** — pareceria que a capa carrega
significado quando ela so esta ausente.

- [ ] **Step 1: Escrever os testes que falham**

Um por estado, comparando a imagem pintada de dois estados entre si (nao contra
cor absoluta — ver Riscos):

```python
def test_capa_ausente_desenha_a_inicial_do_titulo(qapp):
    ...
    # A inicial e do titulo exibido, nao do arquivo: numa biblioteca de
    # promos metade dos arquivos comeca com "01_" e a inicial viraria "0"
    # em metade das linhas.


def test_capa_ausente_difere_de_capa_carregando(qapp):
    ...
    # Sem a caixa reservada o layout pula quando as capas chegam durante o
    # scroll; sem a diferenca de cor, "nao tem" e "ainda nao chegou"
    # parecem a mesma coisa.


def test_placeholder_nao_usa_a_cor_de_camelot(qapp):
    ...
```

- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: Implementar `CoverDelegate`**, movendo `_miniatura` e o contador
      `_leituras` do `TitleDelegate` para ele.
- [ ] **Step 4: `TitleDelegate` perde a capa** e ganha o artista: titulo em
      `font.weight.medium` elidido, artista em `text.secondary` `font.size.caption`
      a 8px de distancia, ambos na mesma baseline. Quando o artista e None, o
      travessao — nao string vazia, que pareceria bug de render.
- [ ] **Step 5: Rodar** — `uv run pytest tests/test_delegates.py -v`
- [ ] **Step 6: Commit** — `feat(trackclassifier): capa vira coluna propria`

---

### Task 3: a classe vira escala ordinal de tres segmentos

**Files:**
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Test: `tests/test_delegates.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_tres_segmentos_na_ordem_ordinal(qapp):
    ...
    # LABEL_ORDER: -1, neutra, +1. A posicao acesa E a informacao -- se a
    # ordem variasse, a escala nao teria leitura.


def test_so_o_segmento_da_classe_fica_aceso(qapp):
    ...


def test_linha_sem_classe_deixa_os_tres_apagados(qapp):
    ...
    # Pendente e "nenhum aceso", nao "coluna vazia": a caixa reservada
    # mantem o alinhamento das colunas seguintes.
```

- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: Implementar.** Segmento 9x9, gap 3 (`SPACE_1` e 2, `SPACE_2` e
      4 — usar 3 exige constante local; anotar o motivo). Aceso:
      `classification_base`. Apagado: contorno `border.default` de 1px, sem
      preenchimento — `drawRect` com pen, nao brush.
- [ ] **Step 4: Rodar e ver passar**
- [ ] **Step 5: Commit** — `feat(trackclassifier): classe vira escala ordinal de tres segmentos`

---

### Task 4: a onda ganha caixa, altura e o estado pendente

**Files:**
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Test: `tests/test_delegates.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_onda_pendente_desenha_a_caixa_vazia(qapp):
    ...
    # Sem a caixa, a coluna vazia parece erro de render e o layout pula
    # quando a analise chega.


def test_onda_falhou_mostra_o_motivo_no_lugar_da_onda(qapp):
    ...
    # Estado de linha, nao de dialogo: o usuario ve qual track falhou sem
    # trocar de aba.


def test_altura_da_onda_segue_a_densidade(qapp):
    ...
```

- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: Implementar.** Fundo `surface.waveform` + `radius.xs` **sempre**,
      antes do pixmap. Altura 28 (comfortable) / 20 (compact), parametro do
      construtor. `EstadoDaLinha.FALHOU` desenha o motivo em `state.danger`
      elidido no lugar da onda.
- [ ] **Step 4: Rodar e ver passar**
- [ ] **Step 5: Commit** — `feat(trackclassifier): onda com caixa de fundo e estados pendente/falhou`

---

### Task 5: as colunas novas

**Files:**
- Modify: `src/trackclassifier/ui/widgets/track_model.py`
- Modify: `src/trackclassifier/ui/library_tab.py`
- Test: `tests/test_library_tab.py`, `tests/test_delegates.py`

- [ ] **Step 1: Escrever os testes que falham** — ordem das colunas, larguras,
      `CONFIANCA` ausente, `CAPA` presente, header em micro-label.
- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: `Column` nova** — `CAPA, TITULO, WAVEFORM, GENERO, BPM, KEY,
      CLASSIFICACAO, DURACAO`. Larguras do LEIA-ME. `TITULO` com
      `setSectionResizeMode(Stretch)` e minimo 220; as outras `Fixed`.
- [ ] **Step 4: Ajustar `_sort_key`** — some `CONFIANCA`, `ARTISTA` continua
      existindo como chave mas sem coluna (ordenar por artista deixa de ser
      alcancavel pelo cabecalho; registrar).
- [ ] **Step 5: Rodar a suite inteira** — `tests/test_library_tab.py` faz
      aritmetica de viewport com a altura de linha; conferir se continua valendo.
- [ ] **Step 6: Commit** — `feat(trackclassifier): colunas da Biblioteca seguem a rodada 3a`

---

### Task 6: os estados de linha no QSS

**Files:**
- Modify: `design/build_tokens.py`
- Modify: `src/trackclassifier/ui/app.qss` (**gerado**)
- Test: `tests/test_tokens.py`

| Estado | Tratamento |
|---|---|
| Default | transparente |
| Hover | `surface.1` |
| Selected | `surface.2` + barra de 2px em `surface.selection-bar` na borda esquerda |
| Focus | Selected + anel interno de `size.focus-ring` em `accent.base` |

Selecao e foco **nunca** usam preenchimento colorido: `accent.base` e
`classification.animada.base` sao a mesma cor, e o preenchimento confundiria
selecao com classe.

- [ ] **Step 1: Escrever o teste que falha** — o QSS tem as quatro regras.
- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: Implementar no template.** A barra de 2px sai de
      `border-left` no `QTableView::item:selected` — e a unica das quatro que o
      QSS alcanca sem pintar a mao. **Conferir no Qt real** se `border-left` no
      item desloca o conteudo; se deslocar, vira pintura no
      `_DelegateComFundo` e o QSS fica so com hover e selecao.
- [ ] **Step 4: Regerar e revisar o diff** de `app.qss`
- [ ] **Step 5: Commit** — `feat(trackclassifier): estados de linha da v0.2 no QSS`

---

### Task 7: ver com os proprios olhos

- [ ] **Step 1:** Screenshot offscreen da `LibraryTab` real com linhas cobrindo
      os sete estados, nas duas densidades.
- [ ] **Step 2:** Comparar contra `design/mockups/03-biblioteca-exploracao.html`,
      rodada **3a** (a fechada — as outras estao no arquivo so como registro).
- [ ] **Step 3:** Medir o paint e comparar com o numero de `ba53271` — 29,5 ms
      no primeiro paint, 5,6 ms por parada de rolagem. A anatomia nova tem mais
      elementos por linha; se regrediu, e agora que se descobre.
- [ ] **Step 4:** Registrar aqui o que destoou.
- [ ] **Step 5: Commit**

---

## Fora de escopo

- **Teclado e acessibilidade** (1/2/3, Z, foco, `setAccessibleName`) — Fase 4.
- **Aba Revisao** — Fase 3, consome estes delegates em `compact`.
- **Progresso de scan por track.** O estado `PENDENTE` existe no componente, mas
  para aparecer de verdade `analyze_all` teria que emitir por track e o
  `TrackModel` atualizar linha a linha. Outra spec.
- **Orfaos do design system** (`radius.pill`, `size.sidebar`,
  `size.art.review-header`, `motion.*`) — Fase 4.

## Riscos

- **Os testes de delegate comparam imagens.** A linha muda de anatomia inteira;
  quase todos vao quebrar. Reescrever comparando "estado A difere de estado B",
  nao cor absoluta — e a unica forma de sobreviverem a proxima mudanca de
  paleta. Um teste que quebra por trocar de tom esta errado; um que quebra por
  hover e selecao ficarem iguais esta certo.
- **Perf.** `ba53271` derrubou o paint de 482,6 ms para 29,5 ms. A anatomia nova
  tem uma coluna a mais e um retangulo de fundo por onda. Medir na Task 7 antes
  de dar a fase por fechada, nao depois de a Fase 3 empilhar por cima.
- **Larguras validadas com dado ficticio.** "Kernel Panic" tem 12 caracteres;
  nomes reais de promo passam de 60. A coluna de titulo e flex com minimo 220 —
  conferir com a biblioteca real antes de fechar.
