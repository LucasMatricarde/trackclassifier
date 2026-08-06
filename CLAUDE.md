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
uv run dj review   # abre a janela de revisao PySide6
uv run python design/build_tokens.py   # regenera ui/tokens.py e ui/app.qss
```

Python `>=3.11,<3.14`. CI (`.github/workflows/ci.yml`) roda ruff + pytest em
push/PR para `main`.

## Arquitetura

Pipeline de um comando `dj`: `library` varre as pastas → `cache` decide o que ja
foi analisado → `extraction` roda em `ProcessPoolExecutor` → `cache` persiste em
parquet → `model` treina/prediz → `service.queue()` ordena por confianca → `ui`
serve a revisao numa janela PySide6 → `apply` move o arquivo → retreino
automatico.

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
`threadpool_limits` para nao multiplicar threads). Ja a UI usa uma QThread unica
dona do `TrackService` (`ui/worker.py`): a janela manda pedidos por slot e
recebe sinais, entao nao ha lock nem parquet escrito de dois lugares.
`apply._destino_livre` segue reservando o nome de destino atomicamente com
`os.open(O_CREAT|O_EXCL)` — o desfazer e o scan podem disputar a mesma pasta.

`_analyze` reordena o resultado pela ordem original de entrada — `as_completed`
devolve fora de ordem e a estabilidade entre execucoes e garantida.

**O cancelamento do scan atravessa as threads fora do Qt, de proposito.**
`analyze_all(should_cancel=...)` consulta o flag entre extracoes, e
`ServiceWorker.request_cancel()` e um metodo **normal, nao um `@Slot`**: durante
um scan o loop de eventos da thread do worker esta parado dentro de
`analyze_all`, entao um slot enfileirado so rodaria depois do scan acabar — o
oposto do que se quer. Um `threading.Event` e o unico estado compartilhado entre
as duas threads. Cancelar nao e falhar: o que nao foi extraido continua pendente
para o proximo scan e **nao** entra em `failures()`. O teto de latencia e uma
extracao em voo (`shutdown(cancel_futures=True)` descarta so o que nao comecou),
porque matar um worker no meio de ffmpeg/librosa nao e opcao.

**Estado em disco** fica em `data_dir` (default `.trackclassifier/`, gitignored):
`analyses.parquet` (escrita atomica via `os.replace`, salvo a cada 10 extracoes),
`model.joblib`, `sha1.json` (`library.Sha1Cache` — evita reler o arquivo inteiro
a cada scan quando `(mtime, size)` nao mudou). A chave do `Sha1Cache` e o
caminho, e toda decisao move o arquivo de pasta: por isso `decide`, `reclassify`
e `undo_last` chamam `sha1_cache.rename(origem, destino)`. **Se voce criar outro
caminho que mova um arquivo, chame `rename` tambem** — sem isso a track vira
cache-miss garantido no scan seguinte, relendo o arquivo inteiro por nada. A
poda em `save()` e so a rede para o que foi movido por fora.

`presentation.parquet` e `covers/<sha1>.<ext>` sao o cache de **apresentacao**
(`presentation.py`): titulo, artista, album, genero e capa embutida, lidos com
`mutagen` durante o scan. Ele existe separado do cache de ML por um motivo so:
o de ML invalida tudo quando `extractor.name` muda, entao acrescentar um campo
de apresentacao la dispararia re-analise de features da biblioteca inteira.
Aqui a versao e propria — **bumpe `PRESENTATION_VERSION` quando mudar o que
este modulo produz**, e o custo e ~1ms por track, sem decodificar audio. A capa
fica em arquivo por track, nao em coluna de parquet, para o pandas nao carregar
centenas de MB de blob no boot da janela.

Armadilha do `mutagen`: `mutagen.File(...)` devolve um objeto **falsy** para um
arquivo sem tags, e `None` so quando nao reconhece o formato. Teste sempre com
`is None` — `if arquivo:` descarta em silencio toda track sem metadado.

**`ui/viewmodel.py` nao importa Qt.** E a fronteira entre o dominio e a tela:
`viewmodel.py` traduz `TrackService` em dataclasses puras (`TrackRow`,
`ReviewState`, `LibraryState`, `ModelState`) que os widgets consomem, e nada
nele sabe o que e um `QWidget`. Isso e o que permite testar a logica de tela —
o que aparece, quantas faltam, quando a fila esvazia — com pytest puro, sem
`QApplication`. Ha um teste (`tests/test_viewmodel.py`) que garante isso
gramaticalmente, lendo o modulo e falhando se aparecer um import de PySide6 —
nao adicione um import de Qt aqui, mesmo que pareca inofensivo.

**Camadas de `ui/`.** `viewmodel.py` (sem Qt, dados puros) → `worker.py`
(`ServiceWorker`, os slots que rodam na thread do servico, so fala com
`TrackService` e com o viewmodel) → `window.py`/`review_tab.py`/
`library_tab.py`/`model_tab.py`/`widgets/` (widgets Qt, so falam com o worker
por sinal/slot, nunca com `TrackService` direto). Cada camada so conhece a de
baixo; um widget que chamasse `TrackService` direto quebraria a regra de "uma
so thread dona do servico" da secao de concorrencia acima.

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
- **Nenhum hex fora de `design/design-tokens.json`.** E a fonte unica de cor,
  tipografia, espaco, raio e tamanho. `ui/tokens.py` e `ui/app.qss` sao gerados
  a partir dele por `design/build_tokens.py` — nunca escreva um literal de cor
  direto num widget ou no QSS; edite o JSON e rode
  `uv run python design/build_tokens.py`. Ha um teste
  (`tests/test_tokens.py::test_nenhum_hex_fora_do_json`) que varre `ui/` atras
  de hex literal e falha se achar um fora dos dois arquivos gerados.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores (o design original e a paralelizacao do scan). Consulte
antes de reescrever essas areas.
