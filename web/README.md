# TrackClassifier - frontend React (spike)

Front React/TypeScript do app (a UI Qt/PySide6 original foi removida). O motor
Python (scan, extracao, modelo, apply) e independente da tela; o
`src/trackclassifier/viewmodel.py` e o contrato da API.

Ainda nao e o app final: roda no navegador durante o spike. A decisao entre
Tauri e Electron vem depois.

## Como rodar

Precisa do backend no ar (porta 8765) e do Vite (porta 5173):

```bash
# na raiz do repositorio
uv run dj serve

# em outro terminal
cd web
npm install
npm run dev -- --host 127.0.0.1
```

Abra `http://127.0.0.1:5173`. O frontend descobre o token em
`GET /api/health` e o manda em `X-Auth-Token` (REST) ou `?token=` (audio e
WebSocket). O Vite faz proxy de `/api` e `/ws` para `http://127.0.0.1:8765`.

## Modo producao (um processo so)

```bash
cd web && npm run build
cd .. && uv run dj serve --no-browser
```

Com `web/dist/index.html` presente, o FastAPI monta o build em `/` e o app
inteiro fica em `http://127.0.0.1:8765` -- sem Vite, mesma origem para REST,
audio e WS. E assim que o shell desktop vai abrir o front.

## Testes

```bash
npm run build        # tsc -b + vite build; npx tsc --noEmit NAO segue
                     # as project references e deixa passar erro de build
npx playwright test
```

Os specs usam `baseURL` de `playwright.config.ts` (padrao
`http://127.0.0.1:5173`). Para rodar contra o build servido pelo proprio
FastAPI, sem Vite:

```bash
npm run build
TC_WEB_URL=http://127.0.0.1:8765 npx playwright test
```

Os specs exigem backend rodando (e Vite, no modo dev) e usam a biblioteca
local:

- `tests/review.spec.ts` - carga da aba, ondas, teclado, status do scan e
  toggle de notacao.
- `tests/decide-flow.spec.ts` - fluxo completo; cria uma track sintetica com
  ffmpeg e remove ao final.
- `tests/screenshot.spec.ts` - baseline visual da Revisao e do Modelo
  (`toHaveScreenshot`, `maxDiffPixels: 10`; ambos rodam sobre fixtures, sem
  depender da biblioteca local). O baseline e por plataforma
  (`review-baseline-darwin.png`); regenere com `--update-snapshots=all`.
- `tests/fidelity.spec.ts` - mede o DOM e compara com
  `design/design-tokens.json` (fonte da verdade), alem de checar fontes.

O baseline visual usa os TTFs de `public/fonts/` entao nao depende
de rede.

## Tokens

`src/styles/tokens.css` e **gerado** - nao edite a mao. Rode na raiz:

```bash
uv run python design/build_tokens.py
```

O comando regenera `web/src/styles/tokens.css` a partir de
`design/design-tokens.json`. Ha testes que falham se o CSS sair de sincronia
do JSON, se um alias colidir, se houver ciclo de `var()` ou hex fora do JSON.

## Estrutura

- `src/api/` - cliente REST/WS e tipos do contrato.
- `src/hooks/` - estado da revisao, player, teclado, WebSocket, notacao.
- `src/components/` - header, waveform, player, decision, fila; `ui/` tem os
  primitivos.
- `src/styles/` - `tokens.css` gerado + `globals.css` + `review.css`.
