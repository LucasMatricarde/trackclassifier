# TrackClassifier

Aprende o criterio pessoal de energia de um DJ a partir das pastas ja organizadas
e pre-classifica novos downloads em `+1`, `neutra` e `-1`.

## Pre-requisitos

```bash
brew install ffmpeg
```

## Instalacao

```bash
cd ProjetosPessoais/TrackClassifier
uv sync --extra dev
cp config.example.toml config.toml
```

Editar `config.toml` com os caminhos reais das tres pastas rotuladas e da pasta
de download.

## Uso

```bash
uv run dj scan     # extrai features das tracks novas
uv run dj train    # retreina e imprime as metricas
uv run dj review   # abre a janela de revisao
```

Na revisao: `1` marca `-1`, `2` marca `neutra`, `3` marca `+1`, espaco toca e pausa.
Cada decisao move o arquivo para a pasta correspondente, e a cada 10 decisoes o
modelo retreina sozinho.

## Testes

```bash
uv run pytest
```
