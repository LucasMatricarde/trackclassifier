# TrackClassifier — Ficha Técnica: Tela Modelo
> Valores medidos no mockup e validados no render (pixel a pixel), sessões de 25/10/2026.
> Branch: feat/modelo-fidelidade · PR #55. Revisão e Biblioteca: congeladas (baseline byte a byte).

## 1. Estrutura de layout

| Região | Especificação | Validado |
|---|---|---|
| Header | Global, MAS **sem Scan/ESCANEAR** nesta tela. Direita: cadeado + "Último treinamento" (2 linhas) + "Modelo ativo" (dot verde + versão) + RETREINAR (outline roxo, ícone refresh) | ✓ |
| Título | Ícone de barras roxo ~48px + "Modelo de Classificação" 28/700 + subtítulo | ✓ |
| Card de info | Texto explicativo + link "Saiba mais ↗" (abre no browser do sistema via setWindowOpenHandler) | ✓ |
| Moldura | Conteúdo centrado, margens simétricas; painéis do meio **1.31 : 1 : 0.87** (608/468/410 no mock) | ✓ (593/454/395) |
| Painéis inferiores | Histórico/Configuração = **59.5 : 40.5** (893/610 no mock) | ✓ (878/596) |
| Rolagem | `.model-tab { min-height: 0; overflow-y: auto }` (mesmo padrão da config-tab) | ✓ |

## 2. KPI cards (4, larguras iguais)

Estrutura: tile de ícone → label → valor grande → delta badge → descrição → sparkline na base.

| Card | Tile (53×53) | Sparkline |
|---|---|---|
| Exemplos rotulados | roxo `#6874F2` | `#6874F2` |
| Acurácia (leave-one-out) | verde `#48D878` | `#2FA868` |
| Erro ordinal médio | azul `#48A8F0` | `#2E86D8` |
| Score F1 (ponderado) | âmbar `#F0A848` | `#C08A38` |

- **Valor: sans negrito ~28px (NUNCA mono)**; F1 sempre **decimal "0,71"**, nunca percentual
- **Delta badge**: verde `#50C884` (bg `#15332C`) quando melhora · vermelho quando piora · **cinza `#8091BA` quando Δ=0** · erro ordinal tem semântica invertida (menor = melhor = verde)
- **Sparkline**: container próprio 32px, `position:absolute; bottom:0; overflow:hidden`, stroke 2px, fill ≤15% — **nunca cobrir a descrição**

## 3. Desempenho por classe

- Cada linha = bloco esquerdo arredondado com fill tint + dot com glow + nome + label de energia
- `-1`: fill dominante `#142236`, glow `#13246E` só ao redor do dot · `neutra`: `#30281C` · `+1`: `#241B24`
- Métricas PRECISÃO/RECALL/F1: **2 casas decimais** + barra na cor da classe

## 4. Matriz de confusão

- Headers de coluna **coloridos por classe** (neutra âmbar, +1 vermelho); rótulo "Previsto" acima, "Real" à esquerda (vertical)
- Escala: diagonal azul `#162F62` (quanto **mais escuro/saturado, mais exemplos**); off-diagonal âmbar `#493723` / vinho `#2C212E` conforme distância real×previsto
- **Legenda única**: "Quanto mais escuro, maior a quantidade de exemplos." (sem legenda acerto/erro inventada)

## 5. Distribuição das classes

- Contagem à direita da barra: `71 (15,4%)`
- Barras: -1 `#6E92F2` · neutra `#F0B848` · +1 `#F06E78`
- Info card com ⓘ + texto dinâmico + botão outline **"Ver recomendações →"**

## 6. Histórico de treinamentos

- Status: **Ativo** dot `#3CE679` · **Arquivado** dot `#8091BA` (nunca "—")
- Coluna final com ⋮ em todas as linhas

## 7. Configurações do modelo

- 2 inputs ** lado a lado** (não steppers): `appearance: none` (sem spinners nativos), sufixo "músicas"
- Botões lado a lado: **RETREINAR AGORA** (fill accent `#6979FB`) + **OPÇÕES AVANÇADAS** (outline, ícone engrenagem)
- Footnote: "O treinamento usa os exemplos rotulados da biblioteca."

## 8. Decisões registradas (fora de escopo, acompanhar)

| Item | Status |
|---|---|
| Fundo dos painéis: mock `#111A24` × app `surface.panel #09131A` | Mantido token global — diferença conhecida; se fidelidade absoluta, criar `model.panel` |
| Licença OFL das fontes web embarcadas | Pendente de verificação (due diligence, não é layout) |

## 9. Processo

- Cores novas via tokens `color.model.*` em `design/design-tokens.json`; **nenhuma cor fixa em componente**
- Evidências de render por região: `render-A.png … render-H.png` (+ recortes mk-*.png do mockup)
- Suite: test_tokens.py 19/19 · Playwright completo 86 passados (1 falha pré-existente: toggle de notação)
- Prova de congelamento: review-baseline-darwin.png byte a byte igual à main
