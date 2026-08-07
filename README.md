# TrackClassifier

Ferramenta pessoal de DJ que aprende seu criterio de energia a partir de
pastas ja organizadas e pre-classifica novos downloads em tres niveis:
`+1` (sobe a pista), `neutra` e `-1` (desce a pista).

Voce mantem tres pastas com faixas ja rotuladas manualmente. O TrackClassifier
extrai um vetor de features de audio (espectro, HPSS, onset, loudness etc.),
treina um modelo de regressao ordinal (`RidgeCV` com limiares ajustados por
leave-one-out) e usa isso pra sugerir onde cada faixa nova da pasta de
downloads deveria entrar. Uma janela de revisao toca a faixa, mostra a
sugestao e deixa voce confirmar ou corrigir com um atalho de teclado -- cada
correcao move o arquivo pra pasta certa e realimenta o modelo.

## Pre-requisitos

- Python `>=3.11,<3.14`
- [`uv`](https://docs.astral.sh/uv/) pra gerenciar dependencias e o venv
- `ffmpeg`/`ffprobe` no PATH -- toda decodificacao de audio passa por
  subprocesso ffmpeg, nao ha fallback puro-Python

```bash
brew install ffmpeg uv
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

## Uso

```bash
uv run dj scan      # extrai features das tracks novas (nas 4 pastas)
uv run dj train      # retreina o modelo e imprime as metricas
uv run dj review     # abre a janela de revisao (PySide6)
```

Na janela de revisao:

| Tecla | Acao |
| --- | --- |
| `1` | marca `-1` (desce) |
| `2` | marca `neutra` |
| `3` | marca `+1` (sobe) |
| `espaco` | toca / pausa a faixa |

Cada decisao move o arquivo de audio pra pasta correspondente no disco. A
cada `retrain_every` decisoes o modelo retreina sozinho, entao a sugestao
melhora enquanto voce revisa.

A janela tambem tem abas de Biblioteca (visao geral das faixas e metadados:
capa, BPM, tonalidade Camelot) e Modelo (metricas de acuracia e matriz de
confusao do treino atual).

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
packaging/        empacotamento em app macOS (PyInstaller)
design/            tokens de design e gerador de QSS
```

Guia completo de arquitetura, convencoes e decisoes de design mora em
`.claude/skills/` (para uso com Claude Code) e em `docs/superpowers/`.

## Empacotamento (macOS)

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

Gera `dist/TrackClassifier.app`, um app standalone com ffmpeg embutido que
abre a janela de revisao ao ser clicado no Finder. Nao ha workflow de release
(runner macOS hospedado custa caro em minutos de CI) -- build sempre local, a
mao, quando quiser gerar uma versao nova.

## Testes e lint

```bash
uv run pytest                  # suite completa (usa ffmpeg de verdade, ~70s)
uv run pytest -k paralelo      # filtra por substring do nome do teste
uv run ruff check .            # lint (gate do CI)
```

CI (`.github/workflows/ci.yml`) roda ruff + pytest em todo push/PR pra
`main`.
