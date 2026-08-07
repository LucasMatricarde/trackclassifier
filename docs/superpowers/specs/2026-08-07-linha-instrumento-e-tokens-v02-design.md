# Linha "instrumento" e design tokens v0.2 — design

Data: 2026-08-07

## Objetivo

Dar identidade visual ao app e fechar as duas lacunas que a auditoria do design
system expôs: **estados de componente** e **navegação por teclado**.

A direção estética é *instrumento*, não *aplicativo de consumo* — a referência
é equipamento de estúdio (Elektron, Bitwig, a serigrafia de um mixer), não
"neon/rave". Isso se traduz em superfícies com matiz frio, um único signal
color quente, tipografia monoespaçada nos números, micro-labels em caixa alta
com tracking largo e raio de canto quase zero.

Referência visual: `design/mockups/linha-instrumento.html` (protótipo estático,
abrir no navegador). Ele mostra a aba **Biblioteca**, mas o componente de linha
é compartilhado com a **Revisão**.

## O que já existe e este trabalho não pode quebrar

- `design/design-tokens.json` v0.1 + `design/build_tokens.py` gerando
  `ui/tokens.py` e `ui/app.qss`. **Fonte única — nada é editado à mão.**
- `ui/tokens.py` expõe, além das constantes, as helpers `camelot_color(n)` e
  `classification_colors(label)`, que resolvem as famílias dinâmicas. Qualquer
  renomeação de token precisa passar por elas.
- `ui/widgets/delegates.py` — `TRACK_ROLE`, `_DelegateComFundo`,
  `WaveformDelegate`, `TitleDelegate`, `ClassificationDelegate`. O
  `_DelegateComFundo` existe porque um `paint()` que não chama a base apaga o
  fundo de seleção; **manter esse contrato**.
- `ui/widgets/waveform_render.py` — `render_curve`, `render_bands`,
  `PixmapCache` (LRU por `(sha1, largura, altura)`).
- `ui/viewmodel.py` — dataclasses puras, **não importa Qt** (há teste
  gramatical que falha se importar).
- `presentation.py` — `PresentationCache`, `extract_cover`, `cover_path(sha1)`,
  versionado por `PRESENTATION_VERSION`.
- `service.py` — `failures() -> list[FailedItem]`, hoje exibido só na aba
  Modelo.

## Decisões de design

### A linha tem duas faixas, não uma

`comfortable` passa de 36px para **44px**: faixa de metadado (16px) sobre a
onda (22px), com a capa à esquerda ocupando a altura das duas.

O motivo é que a onda é a feature diferenciada do app e hoje está espremida
numa coluna de 18px de altura. Ao ocupar a largura da linha, ela deixa de ser
acessório e vira o corpo do componente. Custo aceito: ~20% menos linhas por
tela.

`compact` (32px) mantém a faixa única de hoje, com a capa em 28px.

### A capa é bloco âncora, não coluna

38px de altura cheia, à esquerda, alinhada às duas faixas. Se fosse coluna
dentro da faixa de metadado ficaria com 16px, tamanho em que uma capa não
comunica nada.

Três estados obrigatórios:

| Estado | Visual | Por quê |
|---|---|---|
| Com capa | miniatura 38px, `radius.xs` | — |
| Sem capa | inicial do título em `font.family.mono`, `text.disabled` sobre `surface.2` | Um ícone genérico repetido em 341 linhas vira ruído e compete com as capas reais |
| Carregando | caixa vazia `surface.1`, mesmas dimensões | Sem a caixa reservada, o layout pula quando as capas chegam durante o scroll |

**Não tingir o placeholder com a cor de Camelot.** Fica bonito e quebra a regra
`$regra-de-uso.cor-pertence-ao-dado`: pareceria que a capa carrega significado
quando ela só está ausente.

### Foco e seleção são visualmente distintos

Na v0.2 `accent.base` e `classification.animada.base` são **a mesma cor**
(`#FF6B3D`). Isso é deliberado, mas cria ambiguidade na linha selecionada de
uma track classificada como animada.

Resolução: nenhum dos dois usa preenchimento colorido.

| Estado | Tratamento |
|---|---|
| Default | transparente |
| Hover | `surface.1` |
| Selected | `surface.2` + barra de 2px em `surface.selection-bar` na borda esquerda |
| Focus (teclado) | tudo de Selected + anel interno de 2px em `accent.base` |
| Pendente | onda substituída por caixa vazia; sem BPM, key ou classe |
| Falhou | título em `text.muted`, motivo inline em `state.danger` no lugar da onda |

Pendente e Falhou como estado **de linha**, não de diálogo: o layout não pula
quando a análise chega, e o usuário vê qual track falhou sem trocar de aba.
`service.failures()` já tem o dado.

### Teclado é a interação primária, não acessibilidade

Classificar centenas de tracks com o mouse é inviável. A barra de atalhos no
rodapé documenta e serve de affordance.

| Tecla | Ação | Tela |
|---|---|---|
| ↑ / ↓ | navegar | ambas |
| 1 / 2 / 3 | classificar em -1 / neutra / +1 | Revisão |
| 1 / 2 / 3 | reclassificar | Biblioteca |
| Z | desfazer (`undo_last`) | ambas |
| Espaço | play/pause | ambas |

Na Biblioteca a barra deve dizer "RECLASSIFICAR", não "CLASSIFICAR" — a ação
roteia por `worker.decide`, que já distingue `decide` de `reclassify` via
`path_for`.

## Fases

Ordem obrigatória — cada fase depende da anterior. Fases 1 e 2 são pequenas;
o volume está na 3.

**Fase 1 — tokens v0.2 e o gerador.** Substituir `design-tokens.json`, ensinar
`build_tokens.py` a lidar com as famílias novas (`font.tracking` e `font.case`
viram `letter-spacing` e `text-transform` no QSS) e com o aninhamento a mais em
`size.*` (a v0.1 era plana). Verificar que os nomes gerados continuam batendo
com o que `camelot_color` e `classification_colors` esperam. Rodar
`uv run python design/build_tokens.py` e revisar o diff de `tokens.py` e
`app.qss` antes de commitar.

**Fase 2 — decidir os órfãos.** 19 tokens da v0.1 nunca são consumidos. A v0.2
dá papel documentado à maioria; os que sobram (`size.sidebar`, `radius.pill`)
precisam de decisão explícita: usar ou apagar. A família `motion.*` está
marcada `$deprecated` porque **QSS não suporta `transition`** — ou vira
`QPropertyAnimation` no código, ou sai.

**Fase 3 — o delegate de linha.** Um delegate parametrizado por densidade,
usado pela Biblioteca e pela Revisão. Inclui capa, duas faixas e os seis
estados. O pré-escalonamento das miniaturas **saiu do escopo** — já foi
entregue em 08d21a2, ver a seção de performance abaixo.

**Fase 4 — teclado e acessibilidade.** Atalhos, `setFocusPolicy`,
`setAccessibleName`/`setAccessibleDescription` nos widgets pintados à mão —
hoje há **zero** ocorrências no pacote `ui/widgets/`.

## Performance: miniaturas de capa — RESOLVIDO em 08d21a2

> Esta seção descrevia um problema real e propunha uma solução que **não é
> implementável**. O problema foi corrigido por outro caminho antes desta spec
> entrar em execução. Mantida com a correção à vista porque o raciocínio
> descartado é o que impede alguém de reintroduzi-lo.

O diagnóstico estava certo: `TitleDelegate._miniatura` decodificava a capa
embutida inteira (720×720 a 1280×720 na biblioteca real) a cada `paint()`, e
isso era **72% do tempo de paint** — 482,6 ms no primeiro paint da Biblioteca,
21,6 ms por parada de rolagem.

A proposta original era escalar dentro de `PresentationCache.put()`, gerando
miniaturas de 28px e 38px, com `cover_path_for()` recebendo o tamanho e bump de
`PRESENTATION_VERSION`. **Isso não pode ser feito:** `presentation.py` é
importado por `dj scan` e `dj train`, que rodam headless e não importam Qt (ver
CLAUDE.md, seção do executável). Reduzir uma imagem exige um decodificador —
escalar em `put()` obrigaria Pillow a virar dependência do scan, para produzir
dado que só a tela consome.

**O que foi feito** (`ui/widgets/thumbs.py`): a miniatura é gerada pela TELA, na
primeira vez que a linha é pintada, e gravada como `covers/<sha1>.thumb.png` a
96px. Um tamanho só, não dois — qualquer lado ≤96 sai dele por `scaled()` em
memória, sem tocar o disco. Sem bump de `PRESENTATION_VERSION`: o thumb é
derivado da capa, e a capa é chaveada pelo sha1 do conteúdo do áudio, então capa
nova implica sha1 novo. `PresentationCache.put()` apaga o thumb obsoleto ao
gravar uma capa nova — um `unlink`, sem Qt.

Medido, biblioteca real de 354 tracks:

| caminho até a miniatura de 34px | ms/capa |
|---|---|
| `QPixmap(capa)` + `scaled` (o que rodava em `paint()`) | 4,25 |
| `QImageReader.setScaledSize` (1ª vez, thumb ainda ausente) | 2,07 |
| thumb de 96px em disco | **0,22** |

Primeiro paint: 482,6 ms → 29,5 ms. Rolagem: 21,6 ms → 5,6 ms por parada.

**Consequência para a Fase 3:** o pré-escalonamento de miniaturas sai do escopo
dela — já existe. O que a Fase 3 precisa é apenas pedir o lado certo a
`load_thumbnail()`; nenhuma variante nova de arquivo é criada por tamanho.

## Fora de escopo

- **Qualquer coisa do scan v2 / `handcrafted-v2`.** Trabalho independente, não
  misturar no mesmo commit — se algo regredir, é preciso saber qual dos dois.
- Progresso de scan por track na tabela. O estado "Pendente" existe no
  componente, mas para aparecer de verdade `analyze_all` teria que emitir por
  track e o `TrackModel` atualizar linha a linha. Trabalho de arquitetura,
  outra spec.
- Modo claro. O sistema é `mode: dark` e continua sendo.

## Testes

- Teste gramatical existente (`viewmodel` não importa Qt) continua valendo.
- `build_tokens.py`: teste de que toda família nova gera constante em
  `tokens.py` e que `camelot_color`/`classification_colors` resolvem todos os
  valores da paleta.
- Delegate: um teste por estado, verificando o que foi pintado via
  `QStyleOptionViewItem` — os testes de `test_delegates.py` já fazem isso.
- Capa ausente e capa carregando não devem levantar exceção nem alterar a
  altura da linha.
- Atalhos: `QTest.keyClick` na tabela dispara o sinal esperado, incluindo o
  roteamento decide vs. reclassify.
