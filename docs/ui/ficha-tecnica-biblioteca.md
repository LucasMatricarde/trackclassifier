# TrackClassifier — Ficha Técnica: Tela Biblioteca
> Valores medidos no mockup e validados no render (pixel a pixel), sessões de 21–23/10/2026.
> Uso: referência única ao mexer nesta tela. "Alvo" = mockup; "Validado" = medido no app.

## 1. Estrutura de layout

| Região | Especificação | Validado |
|---|---|---|
| Header | 56px, tabs (ativa = pill roxa), "Scan concluído" 2 linhas + ESCANEAR (96×36) | ✓ |
| Título | "Biblioteca" 28px/700 + subtítulo 14px | ✓ |
| Filter bar | **UMA linha, sem wrap** (busca 390px fixa; selects min 100/max 130px; altura única 36px) | ✓ |
| Filter bar gaps | 8px dentro do grupo; **24px entre grupos** (fim dos chips ↔ select "Gênero"). Implementado com `.library-chips + .library-field { margin-left }` (first-of-type por tag NUNCA — seletor morto) | ✓ |
| Card da tabela | border 1px rgba(255,255,255,0.1), radius 14px, header dentro | ✓ |
| Colunas | checkbox · # · Capa · Título · Artista · Onda · Gênero · BPM · Key · Classe · Duração · Arquivo · ⋮ | ✓ |
| Linha | 48px; bg = fundo da página (sem elevação); seleção = tint roxa na `<tr>` | ✓ |
| Painel direito | ~320px, radius 14px, cover com play + ⋮, tabs, info com hairlines, ações rápidas, botão danger | ✓ |
| Player bar | mesma componente da Revisão | ✓ |
| Player: volume | `VolumeIcon` e `VolumeRail` compartilhados com a Revisão; ver seção 8 | ✓ |

## 2. Cores (hex medidos no mockup)

### Base
| Uso | Hex |
|---|---|
| Fundo página | `#0B1118` |
| Fundo header | `#0D1319` |
| Borda de cards | `rgba(255,255,255,0.1)` |
| Linha normal | `#0B1018` (igual ao fundo) |
| **Linha selecionada** | `#192545` (token `library.row-selected`) |
| Input de busca | `#2B3241` |
| Accent global | `#6979FB` |

### Checkbox
| Estado | Spec |
|---|---|
| Unchecked | fill `#0D131C`, border `#2B3241`, radius 4px, `appearance: none` (NUNCA render nativo branco) |
| Checked | fill `#6979FB` + check branco em SVG |

### Chips de filtro (energia)
| Estado | "-1" | "neutra" | "+1" | "Todos" ativo |
|---|---|---|---|---|
| Fill ativo | `#0E1623` | `#584B25` (âmbar) | `#3B181F` (vinho) | `#161B30` |
| Texto ativo | `#91B1FF` | âmbar | vinho | índigo claro |
| Borda ativa | `#638FFF` | âmbar | vinho | índigo |
| Inativo | fill `#141B23`, borda `#2B3241`, **texto mantém cor da classe (sutil)** | | | |
| Contagem | mini-pill interno com count | | | |

> Regra de design: chips usam **fill translúcido colorido**, não fill neutro com borda colorida.

### Badges KEY (Camelot) — escala global
`1:#46917C 2:#469164 3:#5F9146 4:#849A44 5:#B2953C 6:#C37735 7:#D14D30 8:#D13F69 9:#B3479C 10:#7D53B6 11:#536EB6 12:#3F8EAA`
(dourados/vermelhos ~15% mais escuros que a escala antiga; 5A = `#B2953C`)

### Texto na linha selecionada
| Elemento | Hex |
|---|---|
| Título | `#F0F4FF` (branco) |
| Artista sob o título | `#8AA6D7` (muted) |
| Artista na coluna ARTISTA | `#92B8E8` (mais claro — token `library.artist-selected-column`) |

### Tabs do painel
- Ativa: pill fill `#181F2E`, radius 8px, texto branco negrito, **SEM underline**
- Inativa: texto ~60% opacidade, sem destaque

## 3. Geometrias

| Componente | Spec |
|---|---|
| Badge CLASSE | **52×24px fixos**, radius 8px (NÃO cápsula), `line-height: 1`, padding 0, texto centralizado. Classe `.class-chip` (só CLASSE + "Classe atual" — chips da filter bar usam `.library-chip`, sem conflito) |
| Radius | `--radius-sm: 6px` (kbd, badges KEY) · `--radius-md: 10px` (inputs, chips, selects, botões) · `--radius-lg: 14px` (cards, painel) |
| ONDA | mini-waveform espelhada, altura ~40px por célula, renderizador da Revisão em escala |

## 4. Onda — cores
- Mapeamento **RGB por energia**: R = grave, G = médio, B = agudo
- Matiz varia por track (rosa/roxo/laranja aparecem — não forçar paleta única)
- `waveband.saturation: 1.50` (1.25 ficava lavada; alvo s=0.55–0.66 nos picos)

## 5. Tipografia
- UI inteira: sans geométrica (mesma da Revisão), via token `--font-ui`
- Mono **apenas** para: BPM, durações, tempos, contagens
- Hierarquia: título da tela 28/700 · row título 13/700 · artista 12 · labels 12–13

## 6. Estado pendente (dado, não layout)
- Gênero: só 53/463 tracks (11,4%) têm tag real. Binding correto — decisão de produto: melhorar scanner, fallback por pasta, ou aceitar "—".

## 7. Regras de processo (aprendidas nessa sessão)
1. **Definition of done = evidência de render** (computed via devtools ou medição em px do screenshot). CSS escrito não é prova.
2. CSS certo ≠ render certo → seletor não casa com o DOM (3 ocorrências: `:first-of-type` por tag, etc.). Sempre inspecionar o pai real.
3. Cache do Vite: `rm -rf web/dist web/.vite` antes de rebuild após mudar CSS/tokens.
4. Correções visuais em tokens, nunca inline; variantes (`.class-chip`) em vez de alterar componente base.
5. Uma região por iteração; telas aprovadas congeladas.
6. Regressão: `web/tests/fidelity.spec.ts` (manter no repo).

## 8. Player: volume
Valores medidos no render (Playwright, biblioteca mockada, janela 1512×1037, track selecionada);
o alvo do mockup (alto-falante com ondas, trilho fino, knob redondo) está em
[`ficha-tecnica-revisao.md`](ficha-tecnica-revisao.md), item 2.

| Elemento | Medido |
|---|---|
| Botão `.library-volume-btn` | 28×28 em x=1274, y=993, sem padding (com o padding padrão do `<button>` o svg era espremido para 16 px) |
| Ícone (`VolumeIcon`) | **18×18** em x=1279, y=998, `rgb(175, 188, 210)` (`--color-text-secondary`); mesmo desenho da Revisão (corpo + 2 ondas) |
| Trilho `.volume-rail` | 100×12 em x=1306; `.volume-track` 2 px `rgba(255,255,255,0.1)` |
| Fill | `rgb(175, 188, 210)` (cinza, o accent da Biblioteca é do seek); 80 px no padrão |
| Knob `.volume-marker` | **9×9** círculo, `rgb(240, 244, 255)`, `border-radius` 9999px |

- O volume é o do `useAudioPlayer` elevado no `LibraryTab`: padrão 80% (`audio.volume=0.8`), clique
  a 30% → `aria-valuenow=30` e `audio.volume≈0.3`, e o valor sobrevive à troca de track.
- Antes o trilho tinha `value={80}` fixo e o ícone era uma cópia inline do path malformado.
- Testes: `web/tests/volume-player.spec.ts` (RED/GREEN descrito na ficha da Revisão).
