# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos

```bash
uv sync --extra dev            # instala deps (roda antes de qualquer coisa)
uv run pytest                  # suite completa (~70s, usa ffmpeg de verdade)
uv run pytest tests/test_service.py::test_treina_e_reporta_metricas   # um teste
uv run pytest -k paralelo      # por substring do nome
uv run ruff check .            # lint (gate do CI)
uv run ruff check --fix .
```

`ffmpeg` e `ffprobe` precisam estar no PATH (`brew install ffmpeg`) — nao ha
fallback puro-Python. Sem eles a maioria dos testes falha com `AudioDecodeError`.

CLI (precisa de `config.toml`, copiado de `config.example.toml`, gitignored):

```bash
uv run dj scan     # extrai features das tracks ainda nao analisadas
uv run dj train    # retreina e imprime metricas
uv run dj review   # servidor de revisao em http://127.0.0.1:8000
```

Python `>=3.11,<3.14`. CI (`.github/workflows/ci.yml`) roda ruff + pytest em
push/PR para `main`.

## Arquitetura

Pipeline de um comando `dj`: `library` varre as pastas → `cache` decide o que ja
foi analisado → `extraction` roda em `ProcessPoolExecutor` → `cache` persiste em
parquet → `model` treina/prediz → `service.queue()` ordena por confianca → `web`
serve a revisao → `apply` move o arquivo → retreino automatico.

**Identidade e invalidacao de cache.** Uma track e identificada pelo SHA-1 do
conteudo (`cache.file_sha1`), nunca pelo caminho — renomear ou mover nao
reprocessa. O cache e chaveado por `(sha1, extractor.name)`: **mudou o calculo de
features, bumpe `HandcraftedExtractor.name`** (`"handcrafted-v1"` em
`features.py`). Sem o bump, vetores velhos e novos se misturam silenciosamente.

**O modelo e regressao ordinal, nao classificacao.** `LABEL_TARGET` mapeia
`-1/neutra/+1` para `0.0/0.5/1.0`; `RidgeCV` prediz um escore continuo em
`[0,1]`; dois limiares (`thresholds_`) fatiam o escore de volta em rotulos. Os
limiares sao calibrados por busca exaustiva sobre predicoes leave-one-out — e a
mesma passada LOO que produz `Metrics`, entao acuracia relatada e fora de
amostra. Confianca = distancia ao limiar mais proximo, cortada pela metade
enquanto `low_confidence_mode` (menos de `min_examples` exemplos).

**Todo audio passa por subprocesso ffmpeg** (`audio_io.decode`), nao por
`librosa.load`. `librosa` so e usado sobre arrays ja decodificados
(`descriptors.py`, beat tracking). Toda chamada de subprocesso tem timeout.

**Os erros sao contidos por design, em cada camada.** Parquet corrompido → cache
vazio; `model.joblib` ilegivel (drift de versao do pickle) → modelo novo; worker
morto ou pool que nem construiu → `FailedItem` para os pendentes, scan segue;
extracao que falha → `extract_one` devolve `(None, mensagem)`. O padrao e sempre
degradar e reportar em `service.failures()`, nunca derrubar o comando. Preserve
isso ao mexer nessas bordas — os comentarios longos no codigo explicam qual
excecao especifica cada bloco cobre.

**Concorrencia tem duas formas distintas.** O scan usa processos
(`ProcessPoolExecutor`, workers limitados a 8 por causa do pico de memoria de
ffmpeg+librosa por worker; `extract_one` fixa BLAS em 1 thread via
`threadpool_limits` para nao multiplicar threads). Ja o servidor web usa threads:
as rotas do FastAPI sao sincronas e o Starlette as executa num thread pool, e e
por isso que `apply._destino_livre` reserva o nome de destino atomicamente com
`os.open(O_CREAT|O_EXCL)` em vez de checar `exists()`.

`_analyze` reordena o resultado pela ordem original de entrada — `as_completed`
devolve fora de ordem e a estabilidade entre execucoes e garantida.

**Estado em disco** fica em `data_dir` (default `.trackclassifier/`, gitignored):
`analyses.parquet` (escrita atomica via `os.replace`, salvo a cada 10 extracoes),
`model.joblib`, `transcoded/<sha1>/` (cache de transcode para o player — chaveado
por sha1 justamente para dois arquivos de mesmo nome nao colidirem).

**Testes** injetam um extrator falso (`ExtratorFalso`, que deriva o vetor do nome
do arquivo) pelo parametro `extractor` de `TrackService`, e passam
`max_workers=1` para evitar o pool. Os testes que exercitam o pool ou o extrator
real sao explicitos sobre isso no nome.

## Convencoes

- **Portugues sem acentos** em tudo: nomes de variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. Todo `src/` esta
  livre de acentos (ha tres escapes isolados em comentarios de teste) — escreva
  sem acento.
- API publica (dataclasses, metodos de classe, campos JSON, nomes de features)
  em ingles; o interior das funcoes, em portugues.
- Comentarios explicam **por que**, nao o que — e sao longos quando a decisao nao
  e obvia (qual excecao, qual race, qual limite). Siga esse tom.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores (o design original e a paralelizacao do scan). Consulte
antes de reescrever essas areas.
