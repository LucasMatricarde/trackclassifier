# Atualização in-app — design

Data: 2026-08-07

## Objetivo

Dar ao `.app` empacotado um caminho próprio para descobrir e instalar uma
versão nova, sem que nada do trabalho de classificação e análise já feito seja
perdido.

Hoje não existe caminho nenhum: o build é local e manual, o repositório tem a
tag `v0.2.0` mas **zero GitHub Releases publicados**, e nada no app sabe qual
versão ele é. Atualizar significa buildar de novo na mão e arrastar o bundle.

Este design cobre três coisas que dependem uma da outra e por isso vão juntas:
a **versão como fonte única de verdade**, o **pipeline que produz o artefato de
release**, e o **motor de atualização dentro do app**.

## O que já existe e este trabalho não pode quebrar

- `packaging/trackclassifier.spec` — spec do PyInstaller escrito à mão, com
  `ffmpeg`/`ffprobe` embutidos e `collect_all` de sklearn/pyarrow/librosa. **A
  estrutura do spec não muda**; só o literal de versão sai.
- `packaging/entry_point.py` — `multiprocessing.freeze_support()` antes de tudo.
  Intocado.
- `cli.py:_empacotado()` — `sys.frozen` é o único sinal confiável de bundle.
  Reaproveitado, não reimplementado.
- `cli.py:_caminho_config_padrao()` — empacotado, config em
  `~/.trackclassifier/config.toml`. O `data_dir` sai daí, **sempre fora do
  bundle**.
- `ui/counts_worker.py:ContadorEmSegundoPlano` — o padrão de trabalho de fundo
  fora da thread do serviço (QThreadPool + contador de geração + callback
  injetável). O verificador de atualização é modelado nele.
- `ui/window.py:MainWindow` — monta as abas e liga sinais. Ganha uma faixa e uma
  barra de menu; a montagem das abas não muda.
- `ui/viewmodel.py` — não importa Qt (há teste que falha se importar). A
  contagem de tracks usada no aviso de recomputo sai de `LibraryState.rows`, que
  a janela **já recebe por sinal**.
- Invariante de thread: só a thread do `ServiceWorker` fala com `TrackService`.
  O caminho de atualização **não chama o serviço em ponto nenhum**.
- Invariante de erro: erro numa borda degrada e reporta, nunca derruba o
  comando. Toda falha de rede, disco ou zip vira `UpdateError` e vira texto na
  tela.

## O que "não perder a classificação e a análise" significa aqui

O estado do app se divide em quatro, com riscos diferentes:

| Estado | Onde mora | Risco no update |
| --- | --- | --- |
| Rótulos (+1 / neutra / -1) | pastas do acervo do usuário | **zero** — são arquivos do usuário, o app só os lê |
| Features extraídas | `data_dir/analyses.parquet`, chave `sha1` + `extractor` | só se a versão nova bumpar `HandcraftedExtractor.name` |
| Apresentação, ondas, capas | `data_dir/presentation.parquet`, `peaks/`, `covers/` | só se a versão nova bumpar `PRESENTATION_VERSION` |
| Modelo treinado | `data_dir/model.joblib` | sobrevive; retreino é barato |

A troca do bundle **em si** não ameaça nada: tudo isso vive em
`~/.trackclassifier/`, fora do `.app`. O risco real é outro — uma versão nova
que mude o cálculo de features invalida o cache legitimamente e força recomputo
de todo o acervo, e hoje o usuário só descobre isso quando o scan seguinte
demora.

A resposta do design é dupla:

1. **Garantia mecânica**: `instala()` toca exclusivamente o `.app`. Nunca abre
   `config.toml` nem nada dentro de `data_dir`. Isso é verificado por teste, não
   prometido em comentário.
2. **Aviso informado**: o release declara se recalcula, e o diálogo diz quantas
   tracks serão reanalisadas **antes** de o usuário decidir atualizar.

O cache antigo nunca é apagado pelo update. Voltar para a versão anterior faz
ela reencontrar as linhas dela no parquet, porque a chave inclui o nome do
extrator.

## Fase 1 — Versão com uma fonte só

Hoje `pyproject.toml` diz `0.1.0`, `trackclassifier.spec` diz `0.1.0`, e a tag
no remote diz `v0.2.0`. Comparar versões exige um número confiável.

- `src/trackclassifier/__init__.py` (hoje vazio) passa a conter
  `__version__ = "0.2.0"`.
- `pyproject.toml` troca `version = "0.1.0"` por `dynamic = ["version"]` e
  `[tool.hatch.version] path = "src/trackclassifier/__init__.py"`.
- `trackclassifier.spec` lê a mesma constante para
  `CFBundleShortVersionString`, em vez do literal.

Nenhum lugar novo guarda versão: o `Info.plist` não pode divergir de
`__version__` porque é gerado a partir dele. O único ponto que ainda pode
divergir é a tag do git, e é o workflow da fase 2 que fecha essa porta.

## Fase 2 — `.github/workflows/release.yml`

O repositório é **público**, então runner `macos-latest` do GitHub Actions é
gratuito. A justificativa de custo no `README.md` não se aplica e é corrigida
junto.

Dispara em `push` de tag `v*`, `runs-on: macos-latest`:

1. **Falha cedo** se a tag não bater com `__version__`. Publicar um release
   dizendo `v0.3.0` com um bundle que se identifica como `0.2.0` quebraria a
   comparação de versão no cliente para sempre — vale abortar.
2. `brew install ffmpeg`, `uv sync --extra build`,
   `uv run pyinstaller packaging/trackclassifier.spec --noconfirm`.
3. Zipa com `ditto -c -k --keepParent`. **Não `zip`**: o `zip` comum não
   preserva os symlinks internos dos frameworks Qt e o bundle chega quebrado do
   outro lado.
4. `shasum -a 256` do zip, gravado num `.sha256` ao lado.
5. `gh release create` anexando os dois arquivos.

O corpo do release carrega, opcionalmente, uma linha declarando o que a versão
invalida:

```
recompute: features, presentation
```

Quem bumpa `HandcraftedExtractor.name` ou `PRESENTATION_VERSION` escreve essa
linha. Ausência da linha significa "nada é recalculado".

O workflow de CI atual (ruff + pytest em push/PR para `main`) fica intocado.

## Fase 3 — `src/trackclassifier/updates.py`

Módulo puro, **sem Qt**, sem dependência nova.

```python
@dataclass(frozen=True)
class Release:
    version: str
    url_zip: str
    sha256: str
    notas: str
    recomputa: frozenset[str]
```

- `busca_ultimo_release(abrir=urlopen) -> Release | None` — GET em
  `/releases/latest` da API do GitHub, timeout curto, `User-Agent` explícito,
  sem token (60 requisições/hora por IP anônimo é folgado para uma checagem
  diária). O `abrir` é injetável pelo mesmo motivo do `contar` em
  `ContadorEmSegundoPlano`: o teste precisa observar a chamada sem tocar a rede.
- Comparação de versão: `X.Y.Z` vira tupla de int. Tag que não parseia é
  ignorada (devolve `None`), em vez de derrubar a checagem — nenhuma dependência
  nova só para comparar três inteiros.
- `recomputa` sai da linha `recompute:` do corpo, parseada com tolerância;
  corpo sem a linha resulta em conjunto vazio.
- `baixa(release, destino, progresso=None) -> Path` — baixa para um temporário,
  confere o SHA-256, `UpdateError` se divergir. Um zip truncado que virasse
  bundle seria pior do que não atualizar.
- `instala(zip, bundle) -> None`:
  1. `ditto -x -k` para um temporário **irmão do bundle** — mesmo volume, para
     que os renames seguintes sejam atômicos.
  2. Valida o extraído: é um `.app`, tem `Contents/MacOS/TrackClassifier`
     executável, e o `Info.plist` traz a versão esperada.
  3. `rename(bundle, bundle.old)` → `rename(novo, bundle)` → remove `.old`.
     Se o segundo rename falhar, desfaz o primeiro; o bundle antigo continua
     sendo o que abre.
  4. Sem permissão de escrita no diretório-pai → `UpdateError` com o caminho na
     mensagem.
- `relanca(bundle)` — `open -n <bundle>`; o chamador fecha a janela.
- `caminho_do_bundle() -> Path | None` — sobe de `sys.executable` até o `.app`,
  `None` fora do bundle.

`UpdateError` é a única exceção que sai deste módulo.

## Fase 4 — Camada Qt

- **`ui/update_worker.py`** — `VerificadorDeAtualizacao(QObject)` sobre
  `QThreadPool`, espelhando `ContadorEmSegundoPlano`: contador de geração para
  descartar resultado antigo, callback injetável, `except RuntimeError` no emit
  para a janela fechada no meio do trabalho. Sinais: `disponivel(Release)`,
  `sem_novidade()`, `falhou(str)`, `progresso(int, int)`, `instalado()`.
- **Menu** — `MainWindow` ganha uma `QMenuBar` com um `QAction` "Buscar
  atualizacoes...", com `MenuRole.ApplicationSpecificRole`, que o Qt coloca no
  menu **TrackClassifier** do macOS. O clique sempre checa: ignora o intervalo
  de 24h e a versão dispensada.
- **Faixa** — widget fino acima do `QTabWidget`, escondido por padrão. Mostra
  "Versao 0.3.0 disponivel", um botão `Atualizar` e um `✕`. Nunca modal, nunca
  bloqueia a janela.
- **Diálogo de update** — versão atual, versão nova, notas do release, barra de
  progresso do download. Quando `recomputa` não é vazio, uma linha a mais:
  *"Esta versao recalcula as features das N tracks — o proximo scan vai
  demorar."* O `N` vem de `len(LibraryState.rows)`, estado que a janela já
  recebe por sinal; nenhum widget chama `TrackService`.
- Ao terminar: `relanca()` e `close()`.

Fora do bundle, `caminho_do_bundle()` devolve `None`: em `uv run dj review` o
menu não é montado e nenhuma requisição sai. A atualização é um recurso do
`.app`, não do repositório em desenvolvimento.

## Fase 5 — Estado da checagem

`data_dir/updates.json`:

```json
{"ultima_checagem": "2026-08-07T14:02:11", "versao_dispensada": "0.3.0"}
```

A checagem no boot só acontece se passaram mais de 24h desde a última. O `✕` na
faixa grava `versao_dispensada` — aquela versão específica não volta a aparecer,
mas a seguinte aparece. Arquivo ausente, ilegível ou com JSON quebrado é tratado
como "nunca checou": degrada para checar, sem erro na tela.

## Erros

Tudo que pode falhar, falha para o mesmo lugar: uma mensagem curta na faixa ou
no diálogo, com a janela intacta.

| Situação | Comportamento |
| --- | --- |
| Sem rede, DNS, timeout | "Nao foi possivel verificar atualizacoes." Faixa some. |
| JSON inesperado da API | Mesmo tratamento — nenhum parse otimista. |
| Tag do release não parseia | Ignorada; equivale a não haver versão nova. |
| SHA-256 divergente | "Download corrompido." Bundle não é tocado. |
| Zip sem `.app` válido | `UpdateError`; bundle não é tocado. |
| Sem permissão de escrita | Mensagem com o caminho, sugerindo mover o app. |
| Rename falha no meio | Desfaz; bundle antigo permanece funcional. |

## Testes

Nenhum teste toca a rede: `abrir` é sempre injetado.

| Arquivo | Cobre |
| --- | --- |
| `tests/test_updates.py` | comparação de versão, tag ilegível, corpo com e sem `recompute:`, SHA-256 divergente, JSON quebrado da API, timeout, zip sem `.app` válido, diretório-pai sem permissão de escrita, e **`data_dir` bit a bit intocado depois de `instala()`** |
| `tests/test_update_worker.py` | geração antiga descartada, exceção não derruba a thread do pool, emit para janela já destruída |
| `tests/test_window.py` | faixa aparece e some, `✕` grava a versão dispensada, item de menu força a checagem |

O teste de `data_dir` intocado é o que carrega o requisito central do usuário:
monta um bundle falso com um `data_dir` irmão populado, roda `instala()` e
afirma que conteúdo e mtimes continuam idênticos.

## Fora de escopo

- Assinatura e notarização do `.app`. O bundle continua não assinado; como o
  download é feito pelo Python e não pelo navegador, o arquivo não recebe o
  atributo `com.apple.quarantine` e o Gatekeeper não barra a troca. Assinar
  continua sendo o caminho certo um dia, mas não é pré-requisito disto.
- Atualização diferencial ou delta. O zip é grande porque o spec usa
  `collect_all` em três pacotes científicos, e encolher isso é problema do
  bundle, não do updater.
- Canal beta / múltiplas trilhas de release. Um canal só, `latest`.
- Rollback pela interface. Voltar de versão é baixar o release anterior à mão;
  o cache antigo continua no disco esperando.
