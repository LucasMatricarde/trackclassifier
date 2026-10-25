# Tela Modelo — fidelidade visual ao mockup

## Context
A aba Modelo do front web (`web/`) já segue a estrutura de `design/mockup/TrackClassifier Model Dashboard.png`, mas diverge em detalhes: o header mostra Scan/ESCANEAR, os KPI cards não têm tile de ícone, o F1 aparece em %, a matriz tem uma legenda inventada, os steppers não existem no mockup etc. O objetivo é replicar o mockup região por região, com evidência de render (valor computado ou px medido) antes de avançar. Revisão e Biblioteca estão congeladas.

Decisões tomadas com o usuário:
- **Matriz**: a cor fora da diagonal segue a **distância** (|real−previsto|=1 âmbar, =2 vinho), como nos pixels do mockup; reaproveita `severityClass` de `web/src/model.ts`.
- **⋮ e "Ver recomendações →"**: só visuais (`<button aria-disabled="true">`, sem handler).
- **"Saiba mais ↗"**: abre a spec da aba no GitHub (`https://github.com/LucasMatricarde/trackclassifier/blob/main/docs/superpowers/specs/2026-10-21-aba-modelo-dashboard-web.md`) fora do app.
- **Escopo extra aprovado**: a ilha do header no layout do mockup, ícones nos títulos dos painéis e ⓘ com tooltip nos inputs.

## Passo 0 — branch e registro
- `rtk git switch -c feat/modelo-fidelidade origin/main` (o fetch já trouxe o `4eeb322`). Os untracked atuais continuam fora do commit.
- Salvar este plano em `docs/superpowers/plans/2026-10-25-modelo-fidelidade-visual.md`.

## Tokens (feito uma vez, antes da região A)
Criar o grupo `color.model.*` em `design/design-tokens.json`, no mesmo molde de `color.library.*`, e rodar `uv run python design/build_tokens.py`, que gera `--color-model-*` em `web/src/styles/tokens.css`:

| token | hex | uso |
|---|---|---|
| kpi-exemplos | #6874F2 | ícone do título, tile e sparkline de Exemplos |
| kpi-acc | #48D878 | Acurácia |
| kpi-erro | #48A8F0 | Erro ordinal |
| kpi-f1 | #F0A848 | F1 |
| delta-good / delta-good-bg | #50C884 / #15332C | badge de melhora |
| class-row-lento / -neutro / -animada | #13246E / #30281C / #241B24 | fill das linhas de Desempenho |
| cm-diag | #162F62 | diagonal da matriz |
| cm-adjacente / cm-extremo | #493723 / #2C212E | erro a 1 e a 2 classes de distância |
| status-active / status-archived | #3CE679 / #8091BA | dots do Histórico e da ilha do header |

`accent.base` já é #6979FB, então RETREINAR AGORA usa o token existente. Para o badge de piora, o pedido não traz cor: uso `state.danger` com tint (o padrão atual).
O `tests/test_tokens.py::test_hex_no_web_existe_no_json` garante que nenhum hex fica fora do JSON.

## Regiões (uma por vez; evidência → commit → próxima)

**A. Header** — `web/src/components/AppHeader.tsx`, `web/src/styles/model.css`
- Com `aba === "modelo"`, não renderizar o bloco scan-status nem o `.btn-scan`. Nas outras abas o header fica byte a byte igual, porque Revisão está congelada (`decide-flow.spec.ts`/`review.spec.ts` procuram "Scan concluído"/Escanear).
- A ilha segue o mockup: ícone + "Último treinamento" (muted) com a data embaixo; dot `status-active` + "Modelo ativo" com a versão embaixo; RETREINAR outline (borda accent) com ícone refresh.

**B. Título + info card** — `ModelTab.tsx`, `model.css`, `shell/main.js`
- Ícone de barras com `--color-model-kpi-exemplos` (~48px) à esquerda do h1.
- Info card com ícone ⓘ, o texto e o link "Saiba mais ↗" à direita.
- `shell/main.js`: adicionar `webContents.setWindowOpenHandler` que manda URLs `https:` para `shell.openExternal` e devolve `{action: "deny"}`. Sem isso, `target=_blank` abre o GitHub numa BrowserWindow dentro do app.

**C. KPI cards** — `MetricCard.tsx`, `ModelTab.tsx`, `model-logic.ts`, `Sparkline.tsx`
- Layout: tile 40×40 (bg = `color-mix` do token do card com a superfície, ícone na cor cheia) à esquerda. Na coluna: label pequeno; valor grande mono + badge de delta **à direita do valor**; descrição. Sparkline na base com a cor do card. A classe `metric-card-<cor>` passa a definir `color` para tile, ícone e sparkline.
- `chipDelta` ganha `menorMelhor` explícito e o número de casas. Hoje "decimal" implica "menor é melhor", o que quebraria o F1 em decimal. Formatos: Acurácia `+2,3%`, Erro `-0,031` (menor = verde), F1 `+0,05`.
- F1 exibido com `decimal(f1, 2)` → "0,71".
- Ícones novos no estilo do mockup: database, alvo, barras, raio.
- Texto do Erro: "Quanto menor, melhor". O "moner" do mockup é typo e não será copiado.

**D. Desempenho por classe** — `PerClassPanel.tsx`, `model.css`
- Cada linha: container arredondado com fill `class-row-*`. À esquerda, o dot com halo + o valor da classe na cor dela + "Energia …". À direita, três colunas Precisão/Recall/F1 (label sans pequeno), valor `decimal(v, 2)` e barra na cor da classe.
- Ícone de barras no título do painel.

**E. Matriz de confusão** — `ConfusionMatrix.tsx`, `model.css`
- Rótulo "Previsto" acima das colunas e "Real" vertical à esquerda. Cabeçalho da coluna neutra em `neutro-base`, +1 em `animada-base`, −1 neutro.
- `corDaCelula`: base `cm-diag` / `cm-adjacente` / `cm-extremo` por distância. A intensidade por contagem continua via `color-mix` com a superfície (mais escuro = mais exemplos). O texto das células segue o mockup: diagonal branco, adjacente âmbar, extremo vermelho.
- Legenda: só o swatch azul + "Quanto mais escuro, maior a quantidade de exemplos.". O bloco acerto/erro leve/erro grave sai.
- Ícone de grade no título.

**F. Distribuição** — `ClassDistribution.tsx`, `model.css`
- Rótulo da classe acima da barra e contagem à direita no formato `71 (15,4%)`, com o % sobre o total (hoje é sobre o máximo).
- Info card: ícone ⓘ, texto e botão outline "Ver recomendações →" (aria-disabled).
- Ícone de pizza no título.

**G. Histórico** — `HistoryPanel.tsx`, `model-logic.ts` (`statusDeHistorico`), `model.css`
- Linha 0: "Ativo" com dot `status-active`. As demais: "Arquivado" com dot `status-archived`.
- Coluna final ⋮ em todas as linhas (aria-disabled).
- Subtítulo do mockup: "Últimos treinamentos realizados e comparação de métricas.".
- Ícone de relógio no título.

**H. Configurações** — `ModelSettingsPanel.tsx`, `model.css`
- Os dois `Stepper` viram inputs lado a lado: label + ⓘ, que usa o `ui/Tooltip.tsx` existente com o hint atual; `input type=number` com sufixo "músicas". Mantêm os testIds `settings-retrain-value`/`settings-min-value`, o debounce de 500ms e o `onSettings`.
- Botões lado a lado: "RETREINAR AGORA" (fill accent, ícone refresh, mantém `model-train-panel` e o guard) e "OPÇÕES AVANÇADAS" (outline, engrenagem), que alterna a visibilidade do `TechDetail` existente.
- Footnote: "O treinamento usa os exemplos rotulados da biblioteca.".
- Subtítulo: "Ajuste parâmetros e inicie um novo treinamento.".
- Ícone de engrenagem no título.

## Evidência por região (definition of done)
1. Parar o app → `rm -rf web/dist web/.vite` → `cd web && npm run build` → `uv run dj serve`.
2. Spec temporária Playwright (scratchpad, com `stubAbaModelo` de `web/tests/fixtures/modelo.ts`) que lê `getComputedStyle` dos elementos da região (cores, tamanhos, display) e tira screenshot recortado da região. Os valores entram no relatório da região junto com o print, comparados aos hex/px do pedido.
3. Só então commit `feat(web): ...` da região e avanço para a próxima.

## Testes a ajustar (com a mudança, não depois)
- `web/tests/model.spec.ts`: F1 em decimal ("91,5%" → decimal), delta do F1, por-classe com 2 casas, "—" → "Arquivado", steppers → inputs, opções avançadas pelo botão novo, ilha do header sem scan.
- `web/tests/fidelity.spec.ts`: o teste das amostras da legenda (l.236) e o da intensidade da matriz (l.203) passam a ler os novos tokens.
- `web/tests/model-unit.spec.ts`: `chipDelta` com `menorMelhor`/casas.
- Baseline `web/tests/screenshot.spec.ts-snapshots/model-baseline-darwin.png` regenerado no fim. `review-baseline-darwin.png` **não pode mudar**: ele prova que a Revisão ficou intacta.

## Verificação final
- `uv run ruff check . && uv run pytest tests/test_tokens.py`
- `cd web && npm run build && npx playwright test` (tudo verde, e só o baseline do modelo atualizado)
- `cd shell && npm run start`: abrir a aba Modelo no Electron, conferir "Saiba mais" abrindo no navegador do sistema e comparar o screenshot final lado a lado com o mockup.
