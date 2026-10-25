---
name: trackclassifier-arquitetura
description: Use ao mexer no pipeline (library, cache, extraction, model, service, apply) ou ao decidir onde uma logica nova mora. Gatilhos: "onde fica", "cache invalida", "adicionar feature", "FailedItem", "retreino".
---

# Arquitetura do trackclassifier

## Pipeline

Um comando `dj`: `library` varre as pastas -> `cache` decide o que ja foi
analisado -> `extraction` roda em `ProcessPoolExecutor` -> `cache` persiste em
parquet -> `model` treina/prediz -> `service.queue()` ordena por confianca ->
`serve` entrega a revisao ao front web (React/Electron) -> `apply` move o arquivo -> retreino
automatico.

## Identidade e invalidacao de cache

Uma track e identificada pelo SHA-1 do conteudo (`cache.file_sha1`), nunca pelo
caminho -- renomear ou mover nao reprocessa. O cache e chaveado por
`(sha1, extractor.name)`: **mudou o calculo de features, bumpe
`HandcraftedExtractor.name`** (`"handcrafted-v2"` em `features.py`). Sem o bump,
vetores velhos e novos se misturam silenciosamente.

## O modelo e regressao ordinal, nao classificacao

`LABEL_TARGET` mapeia `-1/neutra/+1` para `0.0/0.5/1.0`; `RidgeCV` prediz um
escore continuo em `[0,1]`; dois limiares (`thresholds_`) fatiam o escore de
volta em rotulos. Os limiares sao calibrados por busca exaustiva sobre predicoes
leave-one-out -- e a mesma passada LOO que produz `Metrics`, entao acuracia
relatada e fora de amostra. Confianca = distancia ao limiar mais proximo,
cortada pela metade enquanto `low_confidence_mode` (menos de `min_examples`
exemplos).

## Os erros sao contidos por design, em cada camada

Parquet corrompido -> cache vazio; `model.joblib` ilegivel (drift de versao do
pickle) -> modelo novo; worker morto ou pool que nem construiu -> `FailedItem`
para os pendentes, scan segue; extracao que falha -> `extract_one` devolve
`(None, mensagem)`. O padrao e sempre degradar e reportar em
`service.failures()`, nunca derrubar o comando. Preserve isso ao mexer nessas
bordas -- os comentarios longos no codigo explicam qual excecao especifica cada
bloco cobre.

## Estado em disco

Fica em `data_dir` (default `.trackclassifier/`, gitignored):
`analyses.parquet` (escrita atomica via `os.replace`, salvo a cada 10
extracoes), `model.joblib`, `sha1.json` (`library.Sha1Cache` -- evita reler o
arquivo inteiro a cada scan quando `(mtime, size)` nao mudou).

`analyses.parquet` nunca e sobrescrito as cegas. Se ele existe mas nao le
(bump de pyarrow/pandas, schema novo -- o caso do update de versao), o
`AnalysisCache` **move** o arquivo para `analyses.parquet.corrupt` (`-2`, `-3`
se ja houver) e enche `load_error`, que `analyze_all` publica em
`service.failures()`. Sem esse desvio o cache abriria vazio e o primeiro save
do scan escreveria por cima -- horas de extracao perdidas em silencio. Alem
disso o primeiro `save()` de cada processo copia o parquet como estava na
abertura para `analyses.parquet.prev`: uma vez por processo, nao por chamada,
senao o backup ficaria 10 extracoes atras do arquivo atual. Nenhuma das duas
protecoes existe em `presentation.parquet` -- ali reler custa ~1ms por track.

A chave do `Sha1Cache` e o caminho, e toda decisao move o arquivo de pasta: por
isso `decide`, `reclassify` e `undo_last` chamam
`sha1_cache.rename(origem, destino)`. **Se voce criar outro caminho que mova um
arquivo, chame `rename` tambem** -- sem isso a track vira cache-miss garantido
no scan seguinte, relendo o arquivo inteiro por nada. A poda em `save()` e so a
rede para o que foi movido por fora.

O cache de apresentacao (`presentation.parquet`, `covers/`, `peaks/`) e
separado e tem versao propria: ver a skill `trackclassifier-apresentacao`.

## Fronteira de tela: `viewmodel.py` e `config.py`

`viewmodel.py` traduz `TrackService` em dataclasses puras (`TrackRow`,
`ReviewState`, `LibraryState`, `ModelState`) que o `serve.py` serializa para a
web; nada nele conhece toolkit de UI. Isso e o que deixa testar a logica de tela
-- o que aparece, quantas faltam, quando a fila esvazia -- com pytest puro. Ha um
teste (`tests/test_viewmodel.py`) que le o modulo e falha se aparecer um import de
PySide6/Qt: nao adicione um, mesmo que pareca inofensivo.

`config.py` alem de `load_config` expoe `read_raw` (parse sem validar, para
preencher o formulario quando o config esta quebrado), `SettingsDraft` (o texto
cru dos campos de UM perfil), `validate_settings` (puro, roda a cada tecla) e
`apply_all_drafts` (cria o `Config` multi-perfil e o `data_dir`, roda uma vez ao
salvar). A separacao entre validar e aplicar e o que permite validar a cada tecla
sem criar uma pasta a cada tecla.

## Testes

Injetam um extrator falso (`ExtratorFalso`, que deriva o vetor do nome do
arquivo) pelo parametro `extractor` de `TrackService`, e passam `max_workers=1`
para evitar o pool. Os testes que exercitam o pool ou o extrator real sao
explicitos sobre isso no nome.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e
planos das mudancas maiores (o design original e a paralelizacao do scan).
Consulte antes de reescrever essas areas.
