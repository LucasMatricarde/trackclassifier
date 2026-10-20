# Spike: aba Revisao em React

Data: 2026-10-19

## Objetivo

Validar, com escopo pequeno e descartavel, se a migracao do frontend PySide6
para React/Typescript e viavel sem reescrever o motor. A pergunta nao era "como
fica o app final", e sim: o `viewmodel.py` aguenta ser contrato de uma API? O
design system sobrevive fora do Qt? O fluxo de teclado continua fluido num
navegador?

Escopo: **somente a aba Revisao**, no navegador. Tauri/Electron ficou para
depois do spike. O app Qt continua intacto e e o app de verdade ate a decisao.

## O que foi construido

### Backend (`src/trackclassifier/serve.py`, comando `dj serve`)

FastAPI + WebSocket no mesmo processo do `TrackService`:

- REST para estado (`/api/review/state`, `/api/library/state`,
  `/api/model/state`), decisoes (`decide`, `undo`, `remove`, `bulk`), scan
  (`/api/scan`, `/api/scan/cancel`), midia (`audio`, `cover`, `thumb`, `peaks`)
  e config/perfis.
- WebSocket `/ws` empurra o estado depois de cada comando e o progresso do
  scan; o front nao faz polling.
- Auth por token local: `X-Auth-Token` no REST, `?token=` em midia e WS (o
  browser nao deixa setar header nesses dois). O token sai de `GET /api/health`.
- Audio com Range (seek sem baixar a faixa inteira), peaks com
  `Semaphore(3)` (mesma contencao do Qt), scan em `asyncio.to_thread` com
  guarda `_scan_running` e scan inicial no startup.
- 16 testes, incluindo regressao do mapeamento de rotulos das classes.

### Frontend (`web/`)

Vite + React + TypeScript. Port da tela: header com capa/chips/palpite,
waveform espectral em tres bandas, mini-onda com janela e botoes de passo,
player, barra de decisao, fila em strip horizontal e atalhos de teclado.

- `tokens.css` e **gerado** por `design/build_tokens.py` a partir de
  `design/design-tokens.json` - o mesmo comando gera `tokens.py` e `app.qss`.
- Fontes self-hosted em `public/fonts/` (os mesmos TTFs que o Qt empacota).
- Notacao de tonalidade em Context + `localStorage`.
- Waveform em canvas empilhado (low rosa embaixo, mid verde, high ciano em
  cima), cores vindas dos tokens.

## O que o spike provou

1. **O `viewmodel.py` funciona como contrato.** As dataclasses viraram JSON
   sem adaptador torto; o mapeamento de rotulo (`-1`/`neutro`/`+1`) foi o
   unico ponto que precisou de teste de regressao.
2. **O design system sobrevive fora do Qt.** Tokens gerados, mesmas fontes,
   mesmas medidas - e o teste de fidelidade mede isso no DOM, nao no olho.
3. **O fluxo de teclado e fluido.** 1/2/3 decidem, Space toca, setas
   navegam; sem lag perceptivel no navegador.
4. **WebSocket simplifica o estado.** Nenhum polling, nenhuma invalidacao
   manual: o servidor manda o estado depois de cada comando.

## O que o spike expos (e foi corrigido)

- **Fallback de fonte virou serif.** Ao apagar o CSS do template do Vite,
  o `font-family` sumiu e o navegador caiu no serif. Corrigido no
  `globals.css`; o teste de fidelidade agora verifica que Space Grotesk e
  JetBrains Mono estao carregadas.
- **Aliases de token colidiam.** Nomes legados apontavam para outros aliases
  e um `var()` apontava para si mesmo; `--space-1` virava `32px` em todo
  lugar. Os consumidores foram renomeados para os nomes canonicos do JSON e
  o gerador ganhou guardas (colisao, ciclo, var indefinida, hex fora do JSON).
- **Card de decisao com 106px em vez de 94.** O `kbd` era item de flex e
  somava altura; virou absoluto no canto, como no mockup.
- **Flake no E2E.** O teste interagia antes do scan terminar. Agora espera
  "Scan concluido" e usa `expect.poll` para a assercao de tempo.

## Como a fidelidade e verificada

Duas camadas, nenhuma delas diff de pixel contra o mockup:

- `tests/fidelity.spec.ts` mede o DOM e compara com
  `design/design-tokens.json`: header 62, capa 136, card de decisao 94, play
  64, capa da fila 52, acento e superficies resolvidos, fontes carregadas.
- `tests/screenshot.spec.ts` guarda um baseline do proprio app
  (`toHaveScreenshot`, 2% de tolerancia) com mascara nas contagens do scan e
  na fila, que dependem da biblioteca local. Baseline por plataforma
  (`review-baseline-darwin.png`).

Diff contra o mockup foi descartado de proposito: o mockup tem outra track,
outra capa e o chrome do macOS; mediria conteudo, nao layout.

## Numeros no fechamento

- 868 testes Python verdes (suite inteira, inclui `serve.py`).
- 11 testes Playwright verdes: carga/teclado/notacao (4), fluxo de decisao
  (1), screenshots (2), fidelidade (3).
- `tsc --noEmit` limpo.

## Decisoes pendentes

- **Tauri vs Electron.** **Decidido em 2026-10-20: Electron** (ver
  `2026-10-20-shell-desktop-decisao.md`). O criterio decisivo foi a paridade
  exata com o Chromium dos testes de fidelidade e nao adicionar Rust ao
  dev/CI; o custo aceito e ~+100MB no download. Tauri fica como fallback
  caso o tamanho vire problema -- o front fala HTTP/WS e nao sabe quem o
  hospeda, entao a troca fica contida em `shell/`.
- **Onde fica a preferencia de notacao.** No Qt ela mora na Biblioteca. No
  spike o toggle ficou no header da Revisao para validar o Context; na
  migracao completa ele volta para Configuracao/Biblioteca.
- **Abas restantes.** Biblioteca, Modelo e Configuracao ainda sao PySide6.
  A ordem sugerida e Biblioteca (mais densa e mais parecida com a Revisao),
  depois Configuracao, depois Modelo.

## Caminho de migracao

1. Decidir o shell (Tauri/Electron) e empacotar o spike com o backend
   embutido, para medir instalacao e assinatura antes de portar mais telas.
2. Portar a Biblioteca reaproveitando os mesmos primitivos e tokens.
3. Portar Modelo e Configuracao; so entao o PySide6 sai do projeto.
4. Manter `viewmodel.py` como contrato durante toda a migracao - e o que
   permitiu o spike rodar em paralelo sem tocar no motor.
