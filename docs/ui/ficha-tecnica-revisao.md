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
| 1 | Pill "DEFAULT" sob o header | não existe | `.profile-bar` só com 2+ perfis; com 1 perfil, 0 nós |
| 2 | Player: volume | ícone de alto-falante | `svg` 18×18 em `.player-volume-icon`, sem o texto "Volume" |
| 2 | Player: loop + velocidade | ícone de repetir + chip "1x" entre o tempo e "Ações" | repetir 32×32 em x=505 · chip 31×24 em x=561 · `Ações` à direita (ordem testada) |
| 2 | Player: "Ações" | sentence case | `Ações`, `text-transform: none` |
| 3 | Classificação | título colado no topo do painel | título a 9 px do topo do painel (padding 8 + borda 1); 0 px de vazio acima |
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
- Painel de classificação: `flex: 0 1 auto; align-items: flex-start; margin-bottom: auto`. A folga do
  viewport vai entre o painel e a fila (84 px a 1556×1011), e a fila continua colada no rodapé.
  Em 1280×720 o painel já nasce cortado (alturas fixas do contrato do mockup), como antes.

## 3. Diferenças conhecidas entre mockup e render

| Diferença | Motivo |
|---|---|
| Botão **Aprovar em bloco** no player | Feature de produto (`POST /api/review/bulk`, `service.bulk_approve`, Qt, `review-hardening.spec`); o mockup não a tem. Mantida e registrada aqui por decisão do item 2. |
| Barra de perfil com 2+ perfis | Sem ela, um perfil sem pendências prenderia o usuário no estado vazio. O mockup mostra um perfil só. |
| Loop e chip de velocidade funcionais | O mockup só os desenha. Na Biblioteca o botão de repetir não tem ação e o chip "1x" não existe. |
| Divisor vertical antes de "Ações" | O mockup tem; o app não (fora dos 6 itens). |
| Ícones de volume e repetir | Mesmo desenho da Biblioteca (`PlayerIcons.tsx` repete o SVG; `LibraryTransport` é tela congelada e fica como está). |
| Folga entre painel e fila em janela alta | O mockup é uma janela exata e não tem folga. |

## 4. Testes

- `web/tests/revisao-fidelidade.spec.ts`: um perfil × dois, tonalidade vazia, rótulos (texto, caixa,
  família), ordem do player, `loop`/`playbackRate` no `<audio>`, Aprovar em bloco presente, painel
  compacto e fila no rodapé, capa 132. RED provado: dos 8 testes, 7 falham sem a correção; o de Aprovar em
  bloco passa nos dois estados, de propósito.
- `fidelity.spec.ts`: capa 96 → 132. `review.spec.ts`: o toggle de notação clica o badge.
- Baseline `review-baseline-darwin.png` regenerado (mudança visual intencional).
