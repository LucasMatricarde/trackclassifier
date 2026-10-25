# Tela Configuração — reconstrução contra o mockup, 2 fases

## Context

A aba Configuração web (`web/src/components/ConfigTab.tsx` + `web/src/styles/config.css`) é hoje uma coluna única com Salvar manual — port direto do `settings_form.py`. O mockup `design/mockup/TrackClassifier Settings Dashboard.png` (1556×1011) desenha outra tela: título com tile de engrenagem, card de auto-save, 4 cards de seção numerados em coluna esquerda e sidebar "Resumo da configuração". Este plano reconstrói a tela em 2 fases, com evidência de render (valor computado ou medição em px) por item, mesmo método das rodadas do Modelo. **Revisão, Biblioteca e Modelo congeladas** — nenhum arquivo delas muda; os baselines `review-baseline-darwin.png` e `model-baseline-darwin.png` são a prova.

## Passo 0 — branch e tokens

- `rtk git switch -c feat/config-fidelidade` a partir de `feat/modelo-fidelidade` (empilhada no PR #55, decisão do usuário): reaproveita `font.weight.bold`, a moldura de 1520px e o gerador de tokens corrigido.
- Salvar este plano em `docs/superpowers/plans/2026-10-25-config-fidelidade-visual.md`.
- Criar o grupo `color.settings.*` em `design/design-tokens.json` (molde de `color.model.*`) e rodar `uv run python design/build_tokens.py`:

| token | hex | uso |
|---|---|---|
| title-tile-bg / title-gear | #19223B / #6670F6 | tile 48px do título |
| section-badge | #5268C9 | badge circular numerado dos cards |
| pill-count | #425577 | badge-pill de contagem (6 NOVAS, 71 TRACKS) |
| dot-lento / dot-neutro / dot-animada | #48A5FC / #F6BB37 / #F4647C | dots de energia das linhas de destino |
| toggle-on / toggle-off / toggle-knob | #5D6DFC / #38424F / #FBFAFF | trilhos e knob dos toggles |
| storage-icon | #6780F5 | ícone do "Uso de armazenamento" |
| status-on / status-off | #2BDE6E / #5E6F85 | dots Ativado/Desativado do Sistema |
| scan-btn | #5B6CFD | fill do "ESCANEAR NOVAS MÚSICAS" |

`accent.base` (#6979FB) cobre RETREINAR/outline gerais. O `tests/test_tokens.py` garante nenhum hex fora do JSON.

## FASE A — esqueleto (itens 1–6)

1. **Layout 2 colunas** — `.config-tab` vira grid: coluna esquerda ~1130px + sidebar ~370px, gap 16px, mesma moldura do Modelo (`width:100%; max-width:1556px; margin:0 auto; padding 25px/18`, `min-height:0; overflow-y:auto`). O `.app-main` não muda.
2. **Título** — tile 48px (bg `title-tile-bg`, radius 12) com engrenagem `title-gear` + "Configurações" 28px/`--font-weight-bold` + subtítulo "Configure pastas, organização, modelo e preferências do TrackClassifier." O modo setup mantém "Primeiro uso" (o mockup não cobre primeiro uso).
3. **Card de info** — à direita do título: ⓘ + "Todas as configurações são salvas automaticamente. As alterações são aplicadas na próxima operação." (reuso do padrão `.model-banner` adaptado; só no modo normal, não no setup).
4. **Cards de seção** — 4 cards com badge circular 24px (`section-badge`, número branco) + título 16/700 + subtítulo 13px. Conteúdo ainda é o atual (migra na fase B).
5. **Sidebar** — card com título "Resumo da configuração", corpo vazio na fase A.
6. **Remover SALVAR → auto-save** — `useConfig`: o apply passa a sair sozinho, debounced, quando o rascunho valida sem erro e difere do salvo (a validação com debounce de 300ms já existe; o auto-save reusa o mesmo ciclo). Banner "Configuração salva." continua como feedback. **Setup mantém o botão explícito "Começar"**: o apply cria o config.toml, não existe auto-save do que não existe.

Evidência da fase A: spec temporária Playwright (mesmo padrão das rodadas do Modelo, viewport 1556×1011, `getComputedStyle` + bounding boxes + recortes) medindo moldura, tile, badge e grid. Rebuild limpo (`rm -rf web/dist web/.vite`) antes de medir.

**CHECKPOINT: apresentar evidência da fase A e aguardar aprovação antes da fase B.**

## FASE B — conteúdos (itens 7–11), um commit por item

Backend primeiro (fase B precisa dele):

- **Draft web ganha os toggles existentes**: `configDraft.ts` + `ConfigDraftValues` passam a ler/escrever `model.auto_move_enabled` e o modo `create_under_root` do draft (`config.py` já tem os dois; hoje nem chegam ao front). Testes Python de round-trip já existem para esses campos.
- **`GET /api/config/stats`** novo em `serve.py`: tamanho do `data_dir` (soma recursiva, em MB), nº de análises realizadas (do banco), nº de arquivos novos na inbox e contagens por pasta de destino. Erro de leitura de pasta degrada para 0 + não derruba o endpoint (invariante do projeto).
- **`POST /api/config/reset`**: reseta `retrain_every=10`, `min_examples=15`, `auto_move_enabled=false`, `create_under_root=false` e preserva pastas/data_dir (não têm padrão sensato). Salva e recria o serviço como o apply atual.

7. **Seção 1 "Pastas e organização"** — pasta de entrada com pill "N NOVAS" (do stats) + input + botão-ícone pasta + ESCOLHER outline; hairline; "Pastas de destino" com badge de tracks por linha; 3 linhas com dot de energia (`dot-*`) + nome + energia em coluna fixa ~200px + input + ícone + ESCOLHER.
8. **Seção 2 "Organização automática"** — 3 toggles lado a lado (componente novo `ui/Toggle.tsx`: trilho `toggle-on`/`toggle-off`, knob `toggle-knob`), label + descrição. "Mover arquivos após classificação" e "Criar pastas automaticamente" ligados nos campos reais; "Manter uma cópia na entrada" só visual (`aria-disabled`, sem handler).
9. **Seção 3 "Dados do aplicativo"** — pasta de dados com pill "ANÁLISES · MB" + input + ícone + ESCOLHER; bloco "Uso de armazenamento" à direita dentro do card: ícone `storage-icon`, "X MB utilizados" / "de 2 GB" (2 GB é a referência fixa do mockup), barra de progresso e "ABRIR PASTA" outline que usa o `revealItem` já exposto no preload do Electron (no navegador, sem Electron, o botão fica `aria-disabled`).
10. **Seção 4 "Modelo de classificação"** — inputs "Retreinar a cada N músicas classificadas" e "Mínimo de exemplos por classe N músicas" (valores reais atuais, sem forçar os 30/20 do mockup); card "Recomendação" com ⓘ à direita (texto estático do mockup).
11. **Sidebar** — grupos Pastas/Modelo/Dados/Sistema com ícone + título; linhas label-esquerda/valor-direita alimentadas pelo state real; Sistema com dots `status-on`/`status-off` refletindo os toggles; rodapé com "ESCANEAR NOVAS MÚSICAS" (fill `scan-btn`, chama o `scan()` existente) e "RESTAURAR PADRÕES" (outline, chama o endpoint novo, com `ConfirmDialog` antes).

## Testes junto com a mudança

- `web/tests/config.spec.ts`: reescrito para o novo layout — auto-save (fill + espera o POST sem clicar em Salvar), setup continua com "Começar", toggles reais fazem round-trip, toggle de cópia é `aria-disabled`, botões do rodapé.
- `web/tests/model-unit.spec.ts`-style: testes puros de `configDraft.ts` com os campos novos.
- Python: `tests/test_serve.py` ganha casos de `/api/config/stats` e `/api/config/reset`.
- Baselines: `review-` e `model-baseline-darwin.png` não podem mudar; criar baseline novo da Configuração no fim da fase B.
- Specs temporárias de evidência (`_tmp-`) deletadas ao fim de cada fase.

## Verificação final

1. `uv run ruff check $(git ls-files '*.py')` e `uv run pytest tests/test_tokens.py tests/test_serve.py tests/test_config*.py -q`.
2. `cd web && rm -rf dist .vite && npm run build` e `npx playwright test` completo contra `dj serve` da **raiz do repo** (o `toggle de notacao` segue ambiental com fila vazia).
3. `cd shell && npm test && npm run smoke`.
4. Push da branch + PR empilhado com base em `feat/modelo-fidelidade` (texto completo do corpo mostrado inline antes de postar).

## Fora de escopo (reportar, não fazer)

- Toggle "Manter uma cópia na entrada" de verdade (mudança mover→copiar no backend) — fica visual.
- Multi-perfil na UI da Configuração (o backend suporta; o mockup não desenha).
