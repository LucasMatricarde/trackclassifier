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
`.claude/skills/` (para uso com Claude Code) e em `docs/superpowers/`.

## Empacotamento e release

Build local, para testar:

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

A mesma spec serve as duas plataformas e o passo final e escolhido por
`sys.platform`: no macOS gera `dist/TrackClassifier.app`, no Windows a pasta
`dist/TrackClassifier/` com `TrackClassifier.exe` dentro. Nos dois casos e
standalone, com ffmpeg embutido.

Release publico: bumpe `__version__` em `src/trackclassifier/__init__.py` e
comite pra `main` (direto ou via PR). O workflow
`.github/workflows/release.yml` roda em todo push pra `main`; se
`__version__` mudou (a tag `vX.Y.Z` correspondente ainda nao existe), ele
cria a tag sozinho e segue pro build em `macos-latest` (gratuito neste
repositorio por ele ser publico) -- zipa com `ditto`, gera o `.sha256` e
publica o GitHub Release. Se a versao nao mudou, o job de build nem chega a
acordar o runner macOS.

O job `build-windows` roda depois, em `windows-latest`, e sobe
`TrackClassifier-<versao>-windows.zip` no release que o job do macOS acabou
de criar. Ele depende de `build-app` de proposito: dois jobs chamando `gh
release create` na mesma tag em paralelo dariam corrida.

### O que muda no Windows

- **Sem auto-update.** Todo o `updates.py` e macOS (`ditto` pra restaurar os
  symlinks do Qt, `Info.plist` pra conferir a versao, `.app` pra trocar de
  lugar). `caminho_do_bundle` devolve `None` fora do darwin, e sem bundle a
  janela nao monta o menu de atualizacao.
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
