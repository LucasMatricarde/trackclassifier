# Desenvolvimento

Guia tecnico do TrackClassifier -- rodar do codigo-fonte, testar, empacotar e
publicar release. Se voce so quer usar o app, veja o [README](../README.md).

## Pre-requisitos

- Python `>=3.11,<3.14`
- [`uv`](https://docs.astral.sh/uv/) pra gerenciar dependencias e o venv
- `ffmpeg`/`ffprobe` no PATH -- toda decodificacao de audio passa por
  subprocesso ffmpeg, nao ha fallback puro-Python

```bash
brew install ffmpeg uv
```

No Windows:

```powershell
winget install Gyan.FFmpeg astral-sh.uv
```

## Instalacao

```bash
git clone <url-do-repositorio>
cd trackclassifier
uv sync --extra dev
cp config.example.toml config.toml
```

Edite o `config.toml` com os caminhos reais das suas pastas:

```toml
[folders]
up = "/Users/SEU_USUARIO/Music/Tracks +1"       # energia alta
neutral = "/Users/SEU_USUARIO/Music/Tracks"      # energia neutra
down = "/Users/SEU_USUARIO/Music/Tracks -1"      # energia baixa
inbox = "/Users/SEU_USUARIO/Downloads/DJ"        # faixas novas, ainda nao classificadas

[model]
retrain_every = 10   # retreina sozinho a cada N decisoes na revisao
min_examples = 15    # minimo de exemplos rotulados pra treinar

[paths]
data_dir = ".trackclassifier"   # onde ficam cache de features e o modelo salvo
```

Copiar o `config.toml` a mao so e necessario pra rodar `dj scan`/`dj train`
sem nunca ter aberto a janela -- na primeira vez que voce abre `dj review`
sem config, um dialogo guia o preenchimento e grava o arquivo sozinho.

## Uso via CLI

```bash
uv run dj scan      # extrai features das tracks novas (nas 4 pastas)
uv run dj train      # retreina o modelo e imprime as metricas
uv run dj review     # abre a janela de revisao (PySide6)
```

## Como funciona por baixo

TrackClassifier extrai um vetor de features de audio (espectro, HPSS, onset,
loudness etc.), treina um modelo de regressao ordinal (`RidgeCV` com limiares
ajustados por leave-one-out) e usa isso pra sugerir onde cada faixa nova da
pasta de downloads deveria entrar.

## Estrutura do projeto

```
src/trackclassifier/
  audio_io.py, spectral.py, descriptors.py, features.py   pipeline de audio -> vetor de features
  cache.py, library.py, extraction.py                      cache por SHA-1 e orquestracao do scan
  model.py                                                  regressao ordinal e metricas
  service.py                                                unico ponto que fala com a UI
  presentation.py, keys.py, peaks.py                        metadados de exibicao (tags, capa, waveform)
  apply.py, labels.py, config.py, cli.py                    aplicacao de decisoes, config, CLI (`dj`)
  ui/                                                        janela PySide6 (Revisao / Biblioteca / Modelo)
packaging/        empacotamento em app macOS / .exe do Windows (PyInstaller)
design/            tokens de design e gerador de QSS
```

Guia completo de arquitetura, convencoes e decisoes de design mora em
`AGENTS.md` (e nas skills de `.claude/skills/`, lidas por Claude Code, OpenCode
e Kimi Code) e em `docs/superpowers/`.

## Empacotamento e release

O app distribuido e o **shell Electron** (`shell/`) com o front React (`web/`)
e o backend Python empacotado dentro dele. O app Qt (`dj review`) continua no
repositorio, mas nao e mais o que o release entrega.

Build local, nesta ordem (cada passo alimenta o proximo; pular o primeiro abre
um app vazio e pular o segundo faz o empacotamento nao achar o backend):

```bash
cd web && npm ci && npm run build && cd ..          # front -> web/dist
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm   # backend -> dist/TrackClassifier/
cd shell && npm ci && npm test && npm run pack      # .app/.exe -> shell/out/
```

O PyInstaller embute `web/dist` no backend (`trackclassifier/web`), e o
`electron-builder` embute `dist/TrackClassifier/` em `Resources/backend`. A
mesma spec serve as duas plataformas: no macOS o resultado e
`shell/out/mac-arm64/TrackClassifier.app`, no Windows
`shell/out/win-unpacked/` (com `TrackClassifier.exe`). Nos dois casos e
standalone, com ffmpeg embutido. Para conferir o artefato de verdade, rode o
proprio executavel empacotado com `--smoke` (esconde a janela, sobe o backend
embutido e falha se a aba nao renderizar).

Release publico: bumpe `__version__` em `src/trackclassifier/__init__.py`,
`shell/package.json` e a raiz de `shell/package-lock.json` (os tres juntos; o
teste de pacote falha se divergirem) e comite pra `main` (direto ou via PR). O workflow
`.github/workflows/release.yml` roda em todo push pra `main`; se
`__version__` mudou (a tag `vX.Y.Z` correspondente ainda nao existe), ele
cria a tag sozinho e segue pro build em `macos-latest` (gratuito neste
repositorio por ele ser publico) -- zipa com `ditto`, gera o `.sha256` e
publica o GitHub Release. Se a versao nao mudou, o job de build nem chega a
acordar o runner macOS.

Cada job builda o front, empacota o backend, empacota o shell e roda o smoke
do artefato antes de zipar: um release que abre vazio falha no CI em vez de
chegar ao usuario.

O job `build-windows` roda depois, em `windows-latest`, e sobe
`TrackClassifier-<versao>-windows.zip` no release que o job do macOS acabou
de criar. Ele depende de `build-app` de proposito: dois jobs chamando `gh
release create` na mesma tag em paralelo dariam corrida.

### Ensaio do release (sem publicar nada)

O workflow roda os dois builds inteiros e sobe os zips como artefato do run
(`macos-dry-run` e `windows-dry-run`, 3 dias), **sem** criar tag nem release,
em dois casos: (1) automaticamente em todo PR que mexe em
`.github/workflows/release.yml`, `packaging/` ou `shell/`; (2) a pedido, em
Actions > Release > Run workflow (`workflow_dispatch`, que o GitHub so aceita
depois que o workflow esta na branch padrao). O workflow so se testa de verdade
rodando, por isso o ensaio existe.

### Atualizacao dentro do app

Quem checa, baixa e troca o `.app` e o backend (`/api/update/*`, em
`update_service.py`, sem Qt); o shell so mostra o menu "TrackClassifier >
Buscar atualizacoes..." e os dialogos nativos (`shell/updater.js`). Nao ha tela
React para isso de proposito: o mockup nao tem esse elemento. O zip novo troca
o `.app` inteiro, entao o `CFBundleShortVersionString` do Electron (que vem de
`shell/package.json`) tem que ser igual a `__version__` -- o teste
`test_versao_do_shell_acompanha_o_backend` e o `release.yml` garantem isso.

### O que muda no Windows

- **Sem auto-update.** Todo o `updates.py` e macOS (`ditto` pra restaurar os
  symlinks do bundle, `Info.plist` pra conferir a versao, `.app` pra trocar de
  lugar). `caminho_do_bundle` devolve `None` fora do darwin, e o backend
  responde `supported: false` em `/api/update/check`.
- **ffmpeg embutido tem sufixo.** O PyInstaller preserva o nome do arquivo,
  entao no pacote ele e `ffmpeg.exe` -- `audio_io._nome_no_bundle` poe o
  sufixo antes de procurar. Cuidado ao instalar ffmpeg por gerenciador que
  usa "shim" (chocolatey): `shutil.which` devolveria o lancador e o pacote
  sairia com um stub inutil. O workflow baixa um build estatico por isso.
- **Nao ha `abrir.command`.** O equivalente do Gatekeeper la e o SmartScreen,
  que se resolve na propria tela ("Mais informacoes" -> "Executar assim
  mesmo") sem script nenhum.

`git tag vX.Y.Z && git push origin vX.Y.Z` continua funcionando como
escape-hatch manual -- o mesmo workflow reage a push de tag direto. Em
qualquer um dos dois caminhos a tag tem que bater com `__version__`: o
workflow falha de proposito se divergirem.

Se a versao nova mudar `HandcraftedExtractor.name` ou `PRESENTATION_VERSION`,
acrescente ao corpo do release a linha:

```
recompute: features, presentation
```

E o que faz o app avisar, antes de atualizar, que a analise de toda a
biblioteca sera refeita.

## Testes e lint

```bash
uv run pytest                  # suite completa (usa ffmpeg de verdade, ~70s)
uv run pytest -k paralelo      # filtra por substring do nome do teste
uv run ruff check .            # lint (gate do CI)
```

CI (`.github/workflows/ci.yml`) roda ruff + pytest em todo push/PR pra
`main`.
