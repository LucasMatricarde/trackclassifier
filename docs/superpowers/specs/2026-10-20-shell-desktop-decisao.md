# Shell desktop: Tauri ou Electron

Data: 2026-10-20

## Contexto

O spike provou o front React servido pelo FastAPI (`dj serve` entrega o build
em `/`). Falta escolher o invólucro desktop. O criterio nao e "qual e mais
moderno", e sim o que custa menos para este projeto: um app pessoal,
distribuido por GitHub Releases em macOS e Windows, sem assinatura Apple, com
atualizacao propria ja funcionando.

## Numeros medidos

| | macOS | Windows |
|---|---:|---:|
| Download atual (v0.3.2, Qt) | 187MB | 276MB |
| Remocao do Qt (comprimido) | ~-30MB | ~-30MB |
| Shell Tauri | ~+5MB | ~+5MB |
| Shell Electron | ~+100MB | ~+100MB |

O bundle desempacotado tem 528MB; PySide6 sao 89MB dele (llvmlite 123MB e
pyarrow 110MB dominam). Ou seja: o shell nao decide o tamanho do app, mas
Electron anula boa parte da economia do Qt.

## Matriz

| Criterio | Tauri | Electron |
|---|---|---|
| Download final | ~160MB / ~250MB | ~260MB / ~350MB |
| Toolchain nova | Rust (rustup) no dev e no CI | nenhuma (Node ja instalado) |
| Engine de render | WKWebView (mac) / WebView2 (win) | Chromium nos dois |
| Paridade com os testes | exige projeto `webkit` no Playwright | identica ao testado |
| Dependencia de runtime | WebView2 no Windows | nenhuma |
| Empacotamento do backend | resources + spawn (onedir) | extraResources + spawn (onedir) |
| Maturidade de updater | plugin proprio (nao exige assinatura Apple) | autoUpdater exige assinatura; manteriamos o updater Python |

## Decisao: Electron

Pelo contexto deste projeto:

1. **Fidelidade visual e o criterio que guiou o spike inteiro.** O waveform e
   canvas, as fontes sao self-hosted e o baseline e gerado no Chromium. Electron
   entrega exatamente o engine testado nos dois sistemas; Tauri exigiria manter
   dois engines verdes (WKWebView no mac, WebView2 no win).
2. **Zero toolchain nova.** Node ja esta no projeto e no CI. Rust adicionaria
   instalacao local e mais um passo de build no release.
3. **O updater continua sendo o nosso.** Nao usamos o autoUpdater do Electron;
   o mecanismo atual (baixar o zip e trocar o `.app`) segue valendo, o que
   torna a assinatura Apple irrelevante para a decisao.

O custo aceito e o download ~50% maior. Se isso virar problema, a troca para
Tauri e contida: o front nao sabe quem o hospeda (fala HTTP/WS com
`127.0.0.1:8765`), entao so o diretorio `shell/` muda.

## Forma do shell

- `shell/main.js` sobe o backend (dev: `uv run dj serve`; empacotado:
  `resources/backend/TrackClassifier serve --no-browser`), espera
  `GET /api/health` e abre uma `BrowserWindow` em `http://127.0.0.1:8765`.
- Uma instancia por vez; o backend morre junto com a janela.
- Sem `nodeIntegration`; a janela so fala HTTP com o backend local.
- Modo `--smoke` esconde a janela e falha se a aba Revisao nao renderizar --
  e o teste de fumaca do shell no CI.

## O que ainda falta para distribuir

> **Status (2026-10-25):** os quatro itens abaixo entram no release 0.5.0 (PR #50;
> so valem depois do merge e da tag):
> `release.yml` builda o front antes do PyInstaller e empacota o shell nos dois
> sistemas, o smoke roda sobre o artefato empacotado, e o updater virou
> `update_service.py` + menu/dialogos nativos em `shell/updater.js` (sem tela
> React, porque o mockup nao tem esse elemento). O texto original segue abaixo
> como registro.

1. `extraResources` do electron-builder apontando para `dist/TrackClassifier/`
   (o onedir do PyInstaller), com o `run_server` como entry point.
2. Build do front (`npm run build`) antes do PyInstaller no workflow.
3. Smoke do shell no CI do macOS; no Windows, o mesmo com `--smoke`.
4. Migrar o updater para trocar o `.app`/pasta do Electron (o formato do zip
   muda; o codigo de `updates.py` precisa de um alvo novo).
