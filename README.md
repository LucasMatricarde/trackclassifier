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

## Download

[**Baixar TrackClassifier (macOS)**](https://github.com/LucasMatricarde/trackclassifier/releases/latest/download/TrackClassifier-latest.zip)

O link baixa direto o `.zip` do app, sempre da versao mais recente -- nao
precisa passar pela pagina de releases nem escolher entre os assets. Depois
de baixar: descompacte e abra `TrackClassifier.app`. Da segunda vez em
diante o proprio app se auto-atualiza (menu de atualizacao na janela).

**Primeira abertura:** o app nao e assinado com Developer ID nem notarizado
pela Apple (exige conta paga), entao o Gatekeeper bloqueia com "'TrackClassifier'
Not Opened -- Apple could not verify...". O zip vem com um `abrir.command` do
lado do `.app`: da duplo-clique nele em vez do app na primeira vez -- ele tira
a quarentena e abre sozinho. Se preferir Terminal, o equivalente e:

```bash
xattr -cr TrackClassifier.app
```

So precisa fazer isso uma vez; da segunda abertura em diante o Finder abre
normal.

Pra conferir integridade do download ou pegar uma versao antiga especifica,
use a [pagina de releases](https://github.com/LucasMatricarde/trackclassifier/releases) --
cada release tem, alem do `TrackClassifier-latest.zip`, um
`TrackClassifier-X.Y.Z.zip` fixo daquela versao com `.sha256` ao lado. Os
dois "Source code" que o GitHub adiciona sozinho sao so o codigo-fonte, nao
o app -- ignore.

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

## Empacotamento e release (macOS)

Build local, para testar:

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

Gera `dist/TrackClassifier.app`, um app standalone com ffmpeg embutido que
abre a janela de revisao ao ser clicado no Finder.

Release publico: bumpe `__version__` em `src/trackclassifier/__init__.py` e
comite pra `main` (direto ou via PR). O workflow
`.github/workflows/release.yml` roda em todo push pra `main`; se
`__version__` mudou (a tag `vX.Y.Z` correspondente ainda nao existe), ele
cria a tag sozinho e segue pro build em `macos-latest` (gratuito neste
repositorio por ele ser publico) -- zipa com `ditto`, gera o `.sha256` e
publica o GitHub Release. Se a versao nao mudou, o job de build nem chega a
acordar o runner macOS.

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
