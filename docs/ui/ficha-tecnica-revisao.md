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
| 2 | Player: volume (trilho) | trilho 2 px, fill accent até o knob, knob circular branco | `.volume-rail` 100×12 em x=288; `.volume-track` 2 px `rgba(255,255,255,0.1)`; `.volume-fill` `rgb(105, 121, 251)` (`--color-accent-base`) de 0 até o knob; knob **9×9** círculo `rgb(240, 244, 255)` (`--color-text`), `border-radius` 9999px (`--radius-full`) |
| 2 | Player: volume (estado) | — | nasce em **80%**: fill 80 px, knob centrado em x=80 do trilho, `aria-valuenow=80` e `audio.volume=0.8`; clique a 30% → `aria-valuenow=30` e `audio.volume=0.3` |
| 2 | Player: loop + velocidade | ícone de repetir + chip "1x" entre o tempo e "Ações" | repetir 32×32 em x=505 · chip 31×24 em x=561 · `Ações` à direita (ordem testada) |
| 2 | Player: "Ações" | sentence case | `Ações`, `text-transform: none` |
| 3 | Classificação | seção compacta (~205), cards hug, onda absorve a folga | seção **193 px** (cards **94**, iguais; título a 9 px do topo); onda 400 px de painel / canvas 310 a 1512×1037 (284 a 1556×1011; mínimo 240); gaps header↔onda↔player↔classificação↔fila = **16 px** |
| 4 | Capa | 133×131 px (header de 62 px, escala 1:1) | **132×132**; header 150 px de altura (mockup: 152) |
| 5 | Chip da tonalidade | "6A" âmbar; sem tom, "—" | com tom: badge Camelot (8A/6A…); sem tom: "—"; nenhum texto "Camelot" na linha de chips |
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
| Ícone de repetir | Segue o SVG antigo de `PlayerIcons.tsx`, sem a revisão de desenho que o volume recebeu (fora do escopo do bug de volume). |
| Largura do trilho de volume | Mockup: ~240 px (x 307–547). Render: **100 px** — o `width` inline do `VolumeRail` (padrão 100) vence o `width: 120px` do CSS, cujo comentário "120px no mockup" está desatualizado. Não alterado aqui: mexer na largura desloca tempo, repetir e "Ações". |
| Posição do knob | O mockup mostra o player a ~50% (knob em x=428); o render nasce em 80%, o padrão do app. É estado, não layout. |
| Onda mais alta que o mockup em janela alta | O mockup é uma janela exata; aqui a altura sobrante vai para a onda, elemento principal da tela (pedido de 25/10). |

## 4. Testes

- `web/tests/revisao-fidelidade.spec.ts`: nunca mostra seletor de perfil (1 × 2 perfis: 0 nós `.profile-bar` e `top` do header igual), tonalidade vazia, rótulos (texto, caixa,
  família), ordem do player, `loop`/`playbackRate` no `<audio>`, Aprovar em bloco presente, painel
  compacto e fila no rodapé, capa 132. RED provado: dos 8 testes, 7 falham sem a correção; o de Aprovar em
  bloco passa nos dois estados, de propósito.
- `fidelity.spec.ts`: capa 96 → 132. `review.spec.ts`: o toggle de notação clica o badge.
- Baseline `review-baseline-darwin.png` regenerado (mudança visual intencional).
- `volume-player.spec.ts` (Revisão e Biblioteca, fila/biblioteca mockadas, `new Audio()` espiado por
  `addInitScript`): clique a 30% → `aria-valuenow=30` e `audio.volume≈0.3`; padrão 80/0,8; volume
  sobrevive à troca de track; ícone com 3 traços e idêntico nas duas telas; knob 9×9 circular;
  ícone 18×18 na Biblioteca. RED provado: sem a correção os 8 falham (`aria-valuenow` 80 em vez de 30,
  `audio.volume` 1 em vez de 0,8, 1 traço em vez de 3, knob 2×10, ícone 16 px).
  O `<audio>` vivo é o último criado: o StrictMode do dev monta o efeito duas vezes.
