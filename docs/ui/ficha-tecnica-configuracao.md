# TrackClassifier — Ficha Técnica: Tela Configuração
> Valores medidos no mockup e validados no render, sessões de 25/10/2026.
> Merge: PR #57 → main (1b59cfb) · branch fix/config-menores preservada.
> Revisão, Biblioteca e Modelo: congeladas (suíte verde, 105 passed).

## 1. Estrutura de layout

| Região | Especificação | Validado |
|---|---|---|
| Header | Global, **COM Scan/ESCANEAR** (diferente do Modelo, que não tem) | ✓ |
| Título | Tile 48px bg `#19223B` radius 12 + gear `#6670F6` + "Configurações" **24/700** (medido igual ao título do Modelo; NÃO 28) + subtítulo "Configure pastas, organização, modelo e preferências do TrackClassifier." | ✓ |
| Card de info | ⓘ + "Todas as configurações são salvas automaticamente. As alterações são aplicadas na próxima operação." | ✓ |
| Moldura | 2 colunas: esquerda **1086px** (4 seções) + sidebar **374px** (medido a 1512px de largura), gap 16px, margens simétricas de 18px | ✓ |
| Cards de seção | Badge circular 24px fill `#5268C9` + número branco; título 16/700 + subtítulo 13px; conteúdo recuado alinhando com o título (badge+gap) | ✓ |
| Persistência | **Auto-save, sem botão SALVAR** (persistência no onChange) | ✓ |

## 2. Seção 1 — Pastas e organização

- "Pasta de entrada" + badge-pill count bg `#425577` ("0 NOVAS") + input + botão-ícone pasta + ESCOLHER outline
- Hairline; "Pastas de destino" + badge "TRACKS" (`#425577`)
- 3 linhas: dot energia + nome + energia (coluna fixa ~200px) + input + botão-ícone + ESCOLHER
- Dots: -1 `#48A5FC` · neutra `#F6BB37` · +1 `#F4647C`

## 3. Seção 2 — Organização automática

- 3 toggles lado a lado, **52×28px**, knob 22px (medido no render a 1512px): ON trilho `#5D6DFC` knob `#FBFAFF` (token `color.settings.toggle-knob`) · OFF trilho `#38424F`
- Cada toggle: label + descrição
- **Ruling registrado**: "Manter uma cópia na entrada" é fixo ON, só visual (issue #59)

## 4. Seção 3 — Dados do aplicativo

- Pasta de dados: label + badge "ANÁLISES · MB" (`#425577`) + input + ícone + ESCOLHER
- Dentro do card, à direita: "Uso de armazenamento" com ícone `#6780F5`, "utilizados de 2 GB", barra de progresso com **proporção real** (~5,5%), botão outline "ABRIR PASTA"

## 5. Seção 4 — Modelo de classificação

- "Retreinar a cada [input] músicas classificadas" + "Mínimo de exemplos por classe [input] músicas" — inputs limpos (`appearance: none`, sem spinners)
- Card "Recomendação": ⓘ + título + texto estático

## 6. Sidebar — Resumo da configuração

- Grupos com ícone + título: Pastas (pasta) · Modelo (gráfico) · Dados (database) · Sistema (engrenagem)
- Linhas label-esquerda / valor-direita; caminhos truncam preservando +2 segmentos
- Sistema com status dots: `#2BDE6E` Ativado · `#5E6F85` Desativado
- Rodapé: botão largo accent "ESCANEAR NOVAS MÚSICAS" `#5B6CFD` + outline "RESTAURAR PADRÕES"
- Hairlines entre grupos

## 7. Componentes compartilhados (novos, reutilizáveis)

| Componente | Spec |
|---|---|
| ConfirmDialog | Props opcionais: `error` (mensagem em `role="alert"`, cor `--color-state-danger`, `--font-size-small`; só aparece no estado de falha) e `busyLabel` (default "Aprovando…", retrocompat; reset usa "Restaurando…") |
| Toggle | 52×28px, knob 22px, trilho accent/cinza, knob `#FBFAFF` |
| Badge-pill count | bg `#425577`, texto claro |
| ConfirmDialog.error | Nunca renderiza em estado normal — telas aprovadas não mudam |

## 8. Diferenças conhecidas (registradas, não bugs)

| Item | Status |
|---|---|
| Campo `create_under_root` persiste em Config, mas não existe no mockup | Feature real — decisão: manter (diff conhecida) |
| Fundo dos painéis: token global `surface.panel` ≠ mockup `#111A24` | Mantido token global (mesma decisão do Modelo) |
| Valores 10/50 ≠ mockup 30/20 | Dados reais, não forçar |

## 9. Testes e infraestrutura

- **Suíte: 105 passed / 0 failed / 1 skip** (library.spec — precisa de coleção real, 3 rodadas)
- `fidelity.spec` **determinístico**: fila mockada (mockApi + fakeWebSocket, fixture `mockRevisaoCompleta` em review-fixtures.ts), sem backend, 10/10 em 3 rodadas + isolado contra dj serve
- `decide-flow.spec`: backend descartável próprio (tests/e2e_backend.py, porta 8799, data_dir temporário); **hash do data_dir real idêntico antes/depois**
- `toggle de notação`: fila mockada com track tonalizada, confere chip 8A→Am
- Resíduos TESTFLOW reais removidos (backup em scratchpad/backup-data_dir/): 2 sha1, 2 analyses.parquet (+.prev), 2 presentation.parquet, 1 peaks, 1 capa — nenhum batia com track real
- CI lint-and-test verde no commit final

## 10. Dívidas registradas (issues)

| # | Item |
|---|---|
| #58 | /api/config/stats sem cache (stats síncrono pesado) |
| #59 | Toggle "Manter cópia na entrada" só visual |
| #60 | useConfig.recarrega() engole o erro |
| #61 | Stubs de capa/audio duplicados em screenshot.spec |
| #62 / #63 | Race reset × auto-save e floor vs precisão — fechadas, corrigidas no PR #57 |
| PR #64 | Teste "onda espectral" passava sem canvas — agora com peaks mockados (`fixtures/peaks.ts`), falha se não renderizar |

## 11. Processo

- Cores via tokens `color.settings.*` em design/design-tokens.json; nenhuma cor inline
- Badge única de tracks na Seção 1 (mockup ambíguo: 186/286 em posições diferentes → seguiu a badge)
- Barramento: rebuild em fases (A: esqueleto → B: conteúdos) — 1 rodada de construção + 2 de fechamento
