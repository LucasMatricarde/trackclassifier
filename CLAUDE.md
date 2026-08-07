# CLAUDE.md

Guia do repositorio para o Claude Code. O detalhe de cada area mora numa skill em
`.claude/skills/` -- invoque a skill antes de mexer na area, em vez de deduzir do
codigo.

## Comandos

```bash
uv sync --extra dev            # instala deps (roda antes de qualquer coisa)
uv run pytest                  # suite completa (~70s, usa ffmpeg de verdade)
uv run pytest tests/test_service.py::test_treina_e_reporta_metricas   # um teste
uv run pytest -k paralelo      # por substring do nome
uv run ruff check .            # lint (gate do CI)
uv run ruff check --fix .
```

CLI (precisa de `config.toml`, copiado de `config.example.toml`, gitignored):

```bash
uv run dj scan     # extrai features das tracks ainda nao analisadas
uv run dj train    # retreina e imprime metricas
uv run dj review   # abre a janela de revisao PySide6
uv run python design/build_tokens.py   # regenera ui/tokens.py e ui/app.qss
```

`ffmpeg` e `ffprobe` precisam estar no PATH (`brew install ffmpeg`) -- nao ha
fallback puro-Python. Sem eles a maioria dos testes falha com `AudioDecodeError`.

Python `>=3.11,<3.14`. CI (`.github/workflows/ci.yml`) roda ruff + pytest em
push/PR para `main`.

## Skills deste repositorio

| Skill | Use quando mexer em |
| --- | --- |
| `trackclassifier-arquitetura` | pipeline, cache/SHA-1, modelo ordinal, erros contidos, estado em disco |
| `trackclassifier-audio-features` | `audio_io.py`, `spectral.py`, `descriptors.py`, `features.py` |
| `trackclassifier-concorrencia` | `service._analyze`, pool do scan, cancelamento, thread do servico |
| `trackclassifier-empacotamento` | `packaging/`, PyInstaller, o `.app`, qualquer bug que so aparece empacotado |
| `trackclassifier-apresentacao` | `presentation.py`, `keys.py`, `peaks.py`, tags, capa, thumbs |
| `trackclassifier-ui` | `src/trackclassifier/ui/**`, `config.py` |

## Invariantes (valem sempre, o porque esta na skill)

- Mudou o calculo de features: **bumpe `HandcraftedExtractor.name`**
  (`features.py`). Mudou o que `presentation.py` produz: **bumpe
  `PRESENTATION_VERSION`** -- e apague `peaks/` a mao se o formato dos buckets
  mudou.
- Criou outro caminho que move um arquivo: chame `sha1_cache.rename(origem,
  destino)` junto.
- Erro numa borda **degrada e reporta** em `service.failures()`; nunca derruba o
  comando.
- So a thread do `ServiceWorker` fala com `TrackService`. Widget nao chama
  servico direto.
- `ui/viewmodel.py` nao importa Qt (ha teste que falha se importar).
- Nenhum hex fora de `design/design-tokens.json` (ha teste que varre `ui/`).

## Convencoes

- **Portugues sem acentos** em tudo: nomes de variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. Todo `src/` esta
  livre de acentos (ha tres escapes isolados em comentarios de teste) -- escreva
  sem acento.
- API publica (dataclasses, metodos de classe, campos JSON, nomes de features) em
  ingles; o interior das funcoes, em portugues.
- Comentarios explicam **por que**, nao o que -- e sao longos quando a decisao nao
  e obvia (qual excecao, qual race, qual limite). Siga esse tom.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores. Consulte antes de reescrever essas areas.
