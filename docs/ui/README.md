# Fichas tecnicas de UI

Uma ficha por tela: hex, geometrias, tipografia e tokens medidos no mockup e
validados no render. E a referencia numerica ao mexer na tela -- "Alvo" e o
mockup, "Validado" e o valor medido no app (`getComputedStyle` ou pixels do
screenshot, nunca o CSS escrito).

| Tela | Ficha | Estado |
|---|---|---|
| Biblioteca | [ficha-tecnica-biblioteca.md](ficha-tecnica-biblioteca.md) | congelada |
| Modelo | [ficha-tecnica-modelo.md](ficha-tecnica-modelo.md) | congelada (PR #55) |
| Configuracao | [ficha-tecnica-configuracao.md](ficha-tecnica-configuracao.md) | congelada (PR #57) |
| Revisao | [ficha-tecnica-revisao.md](ficha-tecnica-revisao.md) | revisao de fidelidade de 25/10 (6 itens); resto no baseline de pixel |

A ficha da Revisao cobre so a revisao de fidelidade de 25/10; o resto da tela
segue no baseline de pixel em `web/tests/screenshot.spec.ts-snapshots/`. Os mockups ficam em `design/mockup/`
e os tokens em `design/design-tokens.json`.

## Testes e infraestrutura de fidelidade

| O que | Onde |
|---|---|
| Invariantes medidos no DOM contra os tokens (Revisao e Modelo) | `web/tests/fidelity.spec.ts`, `web/tests/revisao-fidelidade.spec.ts` |
| Regressao visual da Revisao (baseline de pixel) | `web/tests/screenshot.spec.ts` |
| Fila mockada da Revisao (`mockRevisaoCompleta`, `mockApi`, `fakeWebSocket`) | `web/tests/review-fixtures.ts` |
| Estado fixo das abas Modelo e Configuracao | `web/tests/fixtures/modelo.ts`, `web/tests/fixtures/config.ts` |
| Peaks sinteticos para a onda espectral | `web/tests/fixtures/peaks.ts` (PR #64) |
| Backend descartavel do E2E que decide/move arquivo (porta 8799, `data_dir` temporario) | `tests/e2e_backend.py` + `web/tests/decide-flow.spec.ts` |

As regras de processo (medir no render, tokens, escopo por iteracao, testes sem
estado real, backend descartavel, isolamento por hash, uma ficha por tela) estao
em [`AGENTS.md`](../../AGENTS.md), secao "Regras de fidelidade visual".
