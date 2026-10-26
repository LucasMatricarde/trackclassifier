# TrackClassifier — Ficha Técnica: Tela Revisão
> Escopo: a revisão de fidelidade de 25/10/2026 (6 itens). O resto da tela (waveform, minimapa,
> fila, painel de previsão/confiança/progresso) segue no baseline de pixel
> `web/tests/screenshot.spec.ts-snapshots/review-baseline-darwin.png` e nos invariantes de
> `web/tests/fidelity.spec.ts`.
> Valores "Validado" medidos no render (Playwright, fila mockada, janela 1512×1037 do shell e
> 1556×1011 do mockup); "Alvo" medido por pixel em `design/mockup/TrackClassifier Music Review Dashboard.png`.

## 1. Itens desta revisão

| # | Região | Alvo (mockup) | Validado (render) |
|---|---|---|---|
| 1 | Pill "DEFAULT" sob o header | não existe | sem barra de perfil: `.profile-bar` tem 0 nós com 1 ou N perfis e o `top` de `.review-header` é o mesmo nos dois casos (a troca de perfil mora no dropdown da Configuração) |
| 2 | Player: volume (ícone) | alto-falante com ondas, contorno claro, ~17×16 px (x 271–287, y 629–644) | `VolumeIcon` (corpo + 2 ondas, traço 1,5): `svg` **18×18** em x=246, y=671, `rgb(175, 188, 210)` (`--color-text-secondary`), sem o texto "Volume" |
| 2 | Player: volume (trilho) | trilho 2 px, fill accent até o knob, knob circular branco; **240 px** (x 307–547, medido por pixel em y=636) | `.volume-rail` **240×12** em x=288 (x 288–528; era 100); `.volume-track` 2 px `rgba(255,255,255,0.1)`; `.volume-fill` `rgb(105, 121, 251)` (`--color-accent-base`) de 0 até o knob; knob **9×9** círculo `rgb(240, 244, 255)` (`--color-text`), `border-radius` 9999px (`--radius-full`) |
| 2 | Player: volume (estado) | — | nasce em **80%**: fill 192 px (80% de 240), knob centrado em x=192 do trilho, `aria-valuenow=80` e `audio.volume=0.8`; clique a 30% → `aria-valuenow=30` e `audio.volume=0.3` |
| 2 | Player: loop + velocidade | ícone de repetir (duas setas curvas em círculo, ~17×16 px em x 668–684, y 629–644) + chip "1x" (**38×28**, x 696–733, y 623–650) entre o tempo e "Ações"; gaps de tinta entre vizinhos: volume→trilho **18**, trilho→tempo **33**, tempo→repetir **23**, repetir→chip **11** | `RepeatIcon` `svg` **18×18** (viewBox 18, 2 `path` em `<g>` traço 1,5, pontas e juntas redondas) em x=638 dentro do botão **28×28** (`.player-icon-btn`) em x=631 · chip **39×28** em x=663 (padding `--space-3` `--space-5`) · tempo 63 px em x=552 · `Ações` em x=983 (ordem testada). Gaps de tinta no render: volume→trilho **17**, trilho→tempo **33**, tempo→repetir **22**, repetir→chip **10** (±2 do mockup). Grupos `.player-volume` (ícone + trilho, gap `--space-6`) e `.player-readout` (tempo + repetir + chip, `margin-left: --space-4` sobre o gap de 24 da barra). Medido com o tempo em "2:35 / 7:13", como no mockup (a fixture não carrega o `<audio>` e mostra `Infinity:NaN`) |
| 2 | Player: "Ações" | sentence case | `Ações`, `text-transform: none` |
| 3 | Classificação | seção compacta (~205), cards hug, onda absorve a folga | seção **193 px** (cards **94**, iguais; título a 9 px do topo); onda 400 px de painel / canvas 310 a 1512×1037 (284 a 1556×1011; mínimo 240); gaps header↔onda↔player↔classificação↔fila = **16 px** |
| 4 | Capa | 133×131 px (header de 62 px, escala 1:1) | **132×132**; header 150 px de altura (mockup: 152) |
| 5 | Chip da tonalidade | "6A" âmbar; sem tom, "—" | com tom: badge Camelot (8A/6A…) **37×24 px**, fundo `rgb(209, 63, 105)` (8A), texto `rgb(10, 17, 25)`, JetBrains Mono 11px, raio 2px — **idêntico** quando o tom vem da tag e quando é estimado pelo áudio (medido nas duas fontes); estimado: `title="Tonalidade estimada pelo áudio"` no badge; sem tom: "—"; nenhum texto "Camelot" na linha de chips |
| 6 | Rótulos | sentence case sans; valores mono | `Previsão do modelo`, `Confiança`, `Progresso da revisão`, `Atalhos do teclado`, `Ações`: Inter 12px, `text-transform: none`, `letter-spacing: normal` |

Cap-height dos rótulos no mockup: 8–9 px → 12px (`--font-size-small`); 11px daria 8 e 13px, 9,5.
Valores seguem mono: confiança (`0.82`), progresso (`1 / 2`), tempo do player, BPM.

## 2. Decisões de implementação

- `.micro-label` (mono, caixa alta) continua valendo na Biblioteca e no Modelo; a Revisão usa a
  variante `.label-sentence`, sem alterar o componente base.
- A troca de notação Camelot/Tom passa a ser o clique no próprio badge da tonalidade
  (`.key-chip-trigger`, botão nu em volta do `KeyChip`). `KeyChip` não mudou (a Biblioteca usa).
  O `.key-notation-toggle` (chip tracejado "CAMELOT") sai da Revisão e continua na Biblioteca.
- Loop e velocidade são funcionais: `useAudioPlayer` expõe `loop/setLoop` e `rate/cycleRate`
  (0,75 → 1 → 1,25 → 1,5 → 0,75…). `defaultPlaybackRate` acompanha `playbackRate` porque o
  `audio.src = …` de `load()` devolve a taxa ao default a cada track.
- Tonalidade por áudio (decisão reaberta; ver o plano da fase 4): sem tag, a Revisão pede
  `POST /api/key/{sha1}/detect` uma vez por track (`requestKey`, só se `key == null` e
  `key_source != "none"`) e o `key_ready` por WebSocket preenche o chip. A tag continua tendo
  prioridade. O chip **não ganha visual novo** (regra 5 de `fidelidade.md`): a única marca da
  estimativa é o `title` do badge. Enquanto a detecção roda (alguns segundos) o chip mostra "—".
- Gap da página: 8 → 16 px (`--space-6`), como no mockup (~16–17 px).
- Estrutura: `.review-tab` (flex column) tem como filhos diretos `review-header`, `wave-panel`,
  `player-bar`, `decision-bar`, `queue-strip` (travado em teste). Não havia div envolvendo
  onda + player + classificação; o vazio vinha do CSS.
- Quem absorve a folga é a **onda**: `.wave-panel { flex: 1 1 0 }` com mínimo de 330 px (onda 240 +
  minimapa 64 + gap e padding) e `WaveformCanvas fillHeight` (canvas absoluto dentro do container,
  `height` vira o mínimo, a Biblioteca não usa). A classificação é hug (`flex: 0 1 auto`), com o
  título no topo; em janela baixa ela encolhe antes da onda. Tentativas anteriores descartadas:
  `flex: 1` na classificação (cards de 194 px) e `margin-bottom: auto` (vazio de ~250 px).
  Em 1280×720 a onda fica no mínimo e a fila sai da janela, como antes.
- Volume: fill accent (`--color-accent-base`) da origem até o knob e trilho cinza no restante,
  só na Revisão (`.player-bar .volume-fill`). Na Biblioteca o `VolumeRail` segue com fill cinza (o
  accent dela está no polegar do seek).
- Volume é **estado do `useAudioPlayer`** (`volume` em 0..1, padrão `DEFAULT_VOLUME` = 0,8): é
  aplicado ao `<audio>` na criação e reaplicado em `load()`, e o `VolumeRail` é controlado. A
  conversão 0..1 ↔ 0–100 fica só no `PlayerBar`/`LibraryTransport`. Antes o trilho tinha
  `value={80}` fixo e o clique chegava como 0–100 num setter que limitava a 0..1 (o `<audio>`
  ia sempre ao máximo). O `VolumeRail` arredonda o valor exibido: `0.3 * 100` é `30.000000000000004`.
- Knob: círculo de 9 px (`.volume-marker`), medido no mockup em x 424–432 e y 633–640; era uma barra
  2×10 que o mockup não tem.
- `VolumeIcon` é um componente só, usado na Revisão e na Biblioteca (a cópia inline saiu).

## 3. Diferenças conhecidas entre mockup e render

| Diferença | Motivo |
|---|---|
| Botão **Aprovar em bloco** no player | Feature de produto (`POST /api/review/bulk`, `service.bulk_approve`, `review-hardening.spec`); o mockup não a tem. Mantida e registrada aqui por decisão do item 2. |
| Loop e chip de velocidade funcionais | O mockup só os desenha. Na Biblioteca o botão de repetir não tem ação e o chip "1x" não existe. |
| Divisor vertical antes de "Ações" | O mockup tem; o app não (fora dos 6 itens). |
| Chip de tonalidade estimada pelo áudio | O mockup só desenha tom vindo de tag. A estimativa (chroma + Krumhansl-Kessler) pode errar; o app a mostra com o mesmo visual e avisa só pelo `title` ("Tonalidade estimada pelo áudio"), por decisão de produto (25/10). Se o aviso precisar ser visível, é decisão de design nova. |
| ~~Largura do trilho de volume~~ (resolvida) | Mockup 240 px (x 307–547); render **240 px** (x 288–528). O `width` inline padrão do `VolumeRail` saiu: só há `style` quando a tela passa `width` (a Biblioteca passa 100) e `.volume-rail` (240 px, `review.css`) manda no resto. Teste: `volume-player.spec.ts`. |
| ~~Ícone de repetir~~ (resolvido) | Antes o SVG antigo (dois "L" soltos). Agora duas setas curvas em círculo (arco de raio 7, a segunda é a primeira girada 180°), no padrão do `VolumeIcon`. Mockup: ~17×16 px; render: 18×18 de caixa, traço de 16×16 px medido no render (x 647–662). Teste: `revisao-fidelidade.spec.ts`. |
| Cor do ícone de repetir | Pixel mais claro do ícone no mockup: `rgb(242, 254, 255)` (o do volume, `rgb(251, 254, 255)`); o render usa `--color-text-secondary` (`rgb(175, 188, 210)`) nos dois ícones, como já registrado para o volume. Não alterado. |
| ~~Espaçamentos do player depois do trilho de 240~~ (resolvido) | Antes: o gap único de 24 px (`--space-7`) do `.player-bar` dava volume→trilho 25 (mockup 18), repetir→chip 32 (mockup 11) e o chip 31×24. Medido de novo por pixel de tinta (distância entre vizinhos, não posição absoluta: o container do mockup é 44 px mais largo): hoje volume→trilho 17, trilho→tempo 33, tempo→repetir 22, repetir→chip 10, chip 39×28 (mockup 38×28; a altura é 28, não os 24 do registro anterior). Teste: `revisao-fidelidade.spec.ts` (gaps ±2). |
| Posições do player antes do volume | Mapa do mockup (x de tinta): play 45–105 (anel de 61 px em volta do botão), anterior 136–153, próximo 200–214, divisor ~245, ícone de volume 269–288 (**20×17**). Render: play 45–84 (40 px, sem anel), anterior 109–140, próximo 165–196, divisor 221, ícone de volume 248–262 (**15×12**). Os glifos ⏮/⏭ e o ícone de volume são menores que os do mockup e ficam ~25 px mais à esquerda; o ícone de volume é compartilhado com a Biblioteca. Fora do escopo desta rodada; registrado, não corrigido. |
| `Ações` mais à esquerda que no mockup | Render x=983, mockup x=1139 (≈1116 na janela de 1512). Quem empurra é o botão **Aprovar em bloco** (acima), que ocupa o último slot do grupo à direita; a largura do trilho não participa (o `.player-spacer` absorve a folga). |
| Posição do knob | O mockup mostra o player a ~50% (knob em x=428); o render nasce em 80%, o padrão do app. É estado, não layout. |
| Onda mais alta que o mockup em janela alta | O mockup é uma janela exata; aqui a altura sobrante vai para a onda, elemento principal da tela (pedido de 25/10). |

## 4. Testes

- `web/tests/revisao-fidelidade.spec.ts`: gaps volume→trilho / trilho→tempo / tempo→repetir / repetir→chip e tamanho do chip contra o mockup (±2; RED provado: sem o ajuste volume→trilho mede 25 contra 18); ícone de repetir (viewBox 18, 2 `path` com arco, `<g>` traço 1,5 redondo, 18×18); nunca mostra seletor de perfil (1 × 2 perfis: 0 nós `.profile-bar` e `top` do header igual), tonalidade vazia, rótulos (texto, caixa,
  família), ordem do player, `loop`/`playbackRate` no `<audio>`, Aprovar em bloco presente, painel
  compacto e fila no rodapé, capa 132. RED provado: dos 8 testes, 7 falham sem a correção; o de Aprovar em
  bloco passa nos dois estados, de propósito.
- `web/tests/review-key.spec.ts`: track sem tom pede a detecção e o `key_ready` preenche o chip
  (e o alternador de notação continua valendo); `key_ready` de outra track é ignorado; tom da tag
  e `key_source: "none"` não disparam pedido; `key_failed` não gera loop de pedidos; o chip estimado
  tem a mesma geometria e cor do chip da tag. RED provado: sem `requestKey` os 2 testes positivos
  falham, e removendo cada guarda do hook (tag, `none`, falha) o teste correspondente falha.
- `fidelity.spec.ts`: capa 96 → 132. `review.spec.ts`: o toggle de notação clica o badge.
- Baseline `review-baseline-darwin.png` regenerado (mudança visual intencional).
- `volume-player.spec.ts` (Revisão e Biblioteca, fila/biblioteca mockadas, `new Audio()` espiado por
  `addInitScript`): clique a 30% → `aria-valuenow=30` e `audio.volume≈0.3`; padrão 80/0,8; volume
  sobrevive à troca de track; ícone com 3 traços e idêntico nas duas telas; knob 9×9 circular;
  ícone 18×18 na Biblioteca. RED provado: sem a correção os 8 falham (`aria-valuenow` 80 em vez de 30,
  `audio.volume` 1 em vez de 0,8, 1 traço em vez de 3, knob 2×10, ícone 16 px).
  O `<audio>` vivo é o último criado: o StrictMode do dev monta o efeito duas vezes.
  Também: trilho da Revisão = 240 ±2 px e o da Biblioteca segue 100. RED provado: sem a correção o trilho mede 100 (diferença de 140 contra ≤2) e o `RepeatIcon` tem 1 `path` em vez de 2.
