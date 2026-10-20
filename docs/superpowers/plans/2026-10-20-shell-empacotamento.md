# Empacotamento do shell desktop

Data: 2026-10-20

## Objetivo

Transformar `shell/` (hoje so roda do checkout) no app distribuivel: Electron
com o backend PyInstaller embutido, build do React servido em `/`, e o mesmo
modelo de release (zip no GitHub) usado hoje.

Estado de partida: shell dev validado (`npm run smoke` → `SMOKE OK`), backend
servindo `web/dist` em `/`, decisao Electron registrada em
`2026-10-20-shell-desktop-decisao.md`.

## Ordem de build

1. `cd web && npm ci && npm run build` → `web/dist`
2. `uv run --extra build pyinstaller packaging/trackclassifier.spec` →
   `dist/TrackClassifier/` (onedir; o spec ja inclui `web/dist` quando
   existe)
3. `cd shell && npm ci && npm run dist` → Electron em `shell/out/`, com o
   onedir copiado para `Contents/Resources/backend`

O passo 2 precisa vir antes do 3: o `extraResources` aponta para
`../dist/TrackClassifier` e o electron-builder falha se a pasta nao existir.
Quando o shell virar o app oficial, a condicional do spec vira erro (bundle
sem `index.html` abriria vazio).

## Primeiro uso (resolvido)

`run_server` carregava `~/.trackclassifier/config.toml` e saia com
`SystemExit` se ele nao existisse. **Resolvido em 2026-10-20** (commits
`e7f5a32` e `d0a7641`):

- A aba Configuracao foi portada e o mesmo formulario serve de setup
  (`ConfigTab setup`), sem header, com botao "Comecar".
- Config ausente nao e mais fatal: `run_server` sobe com `_service=None`,
  `_config=None` e `_config_path` definido. Config existente e invalido
  continua saindo com erro -- abrir setup mascararia um arquivo quebrado.
- `/api/health` expoe `configured`; `/api/config` sem config devolve raw
  vazio com `data_dir` sugerido ao lado do arquivo; os endpoints de estado
  seguem 503.
- O `apply` cria o config e o servico; o App detecta `configured:false`,
  mostra o setup e, ao salvar, dispara o scan inicial e entra na Revisao.
- Verificado de ponta a ponta com `--config /tmp/tc-setup/config.toml`:
  health `false`, formulario, "Comecar", config gravado e health `true`.

Falta o seletor nativo de pasta no Electron (hoje sao campos de texto).
Biblioteca pode vir depois, pois nao bloqueia o primeiro uso.

## Config do electron-builder (rascunho)

```json
{
  "appId": "com.lucasmatricarde.trackclassifier",
  "productName": "TrackClassifier",
  "directories": { "output": "out" },
  "files": ["main.js", "package.json"],
  "extraResources": [
    { "from": "../dist/TrackClassifier", "to": "backend" }
  ],
  "mac": { "category": "public.app-category.music", "target": ["zip"] },
  "win": { "target": ["zip"] }
}
```

O `main.js` ja procura `process.resourcesPath/backend/<TrackClassifier|
TrackClassifier.exe>` e roda `serve --no-browser`. O icone deve ser o mesmo
`packaging/TrackClassifier.icns` (mac) e um `.ico` novo (Windows), ambos
derivados de `packaging/TrackClassifier.png`.

## Atualizacao

O updater atual (`updates.py`) assume o zip do PyInstaller com
`TrackClassifier.app` na raiz. Com o Electron o zip passa a conter o `.app`
do shell (que por dentro leva o backend). Ajustes:

- `caminho_do_bundle()` e a troca do `.app` continuam valendo (o shell e um
  `.app` normal).
- O shasum e o nome do asset (`TrackClassifier-<versao>-macos.zip`) nao
  mudam.
- No Windows o zip passa a ser a pasta do Electron (com `TrackClassifier.exe`
  na raiz), mantendo a atualizacao manual.

## CI

No job de release (macos-latest e windows-latest):

1. setup Node + `npm ci` + `npm run build` em `web/`
2. PyInstaller como hoje
3. `npm ci` + `npm run dist` em `shell/`
4. smoke empacotado: rodar o app com `--smoke` (backend incluso, sem Vite)
5. zipar `shell/out/*.app` (mac, via ditto) ou a pasta do Windows

O smoke do shell precisa da config do usuario no runner; para o CI, criar um
`config.toml` temporario apontando para pastas vazias e um inbox vazio.

## Verificacao

- `npm run smoke` no checkout: ja passa.
- `npm run dist` + abrir o `.app` empacotado: janela, scan e decisao.
- Matar o app: nenhum processo `TrackClassifier` resta na porta 8765.
- Tamanho do zip final: comparar com os 187MB/276MB atuais e registrar.
- `uv run pytest -q` e Playwright contra o build servido em 8765.
