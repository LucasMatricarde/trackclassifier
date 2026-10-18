---
name: trackclassifier-empacotamento
description: Use ao gerar, alterar ou depurar o executavel do trackclassifier - packaging/trackclassifier.spec, packaging/entry_point.py, PyInstaller, dist/TrackClassifier.app, dist/TrackClassifier/TrackClassifier.exe - e ao mexer em audio_io.py ou cli.py, que so quebram empacotados. Cobre o comando de build, o workflow de release, o que diverge no Windows, as quatro armadilhas do bundle (freeze_support, ffmpeg embutido, config fora do cwd, FirstRunDialog) e o teste obrigatorio com PATH minimo. Gatilhos: "gerar o .app", "gerar o .exe", "PyInstaller", "abriu pelo Finder e falhou", "bundle", "release", "windows", "assinar app".
---

# Executavel (macOS e Windows)

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

Uma spec so; o passo final e escolhido por `sys.platform`. macOS: `BUNDLE` fecha
em `dist/TrackClassifier.app`. Windows: o proprio `COLLECT` ja e o artefato,
`dist/TrackClassifier/TrackClassifier.exe`. Nao duplique a spec por plataforma --
tudo que costuma quebrar (datas das fontes, `collect_all` das libs cientificas,
ffmpeg embutido) e identico nas duas, e duas copias divergiriam.

Release e por workflow (`.github/workflows/release.yml`), disparado por bump de
`__version__` em `main`: job `build-app` (macOS) cria o release, `build-windows`
sobe os assets dele depois -- nessa ordem, senao dois `gh release create` na
mesma tag correm um contra o outro.

## Quatro coisas so quebram no app empacotado, nunca em `uv run dj`

Todas ja morderam uma vez.

- **`multiprocessing.freeze_support()` em `packaging/entry_point.py`.** O pool do
  scan cria workers relancando o proprio executavel; sem a chamada, cada worker
  cai no argparse com os argumentos internos do multiprocessing e o pool inteiro
  morre.
- **`ffmpeg`/`ffprobe` vao dentro do bundle** (via `binaries` no spec, que faz o
  PyInstaller reescrever os install_name das dylibs do homebrew). App aberto pelo
  Finder nao herda o PATH do shell: sem eles embutidos, `/opt/homebrew/bin` fica
  invisivel e toda track falha. `audio_io._ffmpeg_embutido` prefere o do bundle e
  cai no PATH fora dele.
- **Config nao pode ser relativo ao cwd.** Empacotado (`sys.frozen`), o default
  vira `~/.trackclassifier/config.toml`. Quando ele nao existe -- ou existe
  apontando para uma pasta que sumiu -- a janela abre o `FirstRunDialog`
  (`ui/first_run.py`), que grava o arquivo pela primeira vez. Nao ha mais copia do
  `config.example.toml` para o home: ela transformava "nao tem config" em "config
  apontando para /Users/SEU_USUARIO", escondendo do app a unica condicao que
  dispara o dialogo. `dj scan` e `dj train` seguem headless, com `ConfigError` no
  stderr e sem importar Qt.
- **Teste o bundle com `env -i ... PATH=/usr/bin:/bin:/usr/sbin:/sbin`** depois de
  qualquer mudanca no spec ou em `audio_io.py`/`cli.py`: e o que reproduz o PATH
  minimo que o Finder da, e e onde a classe de bug acima aparece. Rodar com o PATH
  normal do shell mascara justamente isso.

## O que diverge no Windows

- **O binario embutido tem sufixo.** O PyInstaller preserva o nome do arquivo,
  entao la ele e `ffmpeg.exe`. `audio_io._nome_no_bundle` poe o `.exe` antes de
  procurar; sem isso a busca falha e cai no PATH -- exatamente a dependencia que
  o embutido existe para remover.
- **Nunca instale o ffmpeg de build por gerenciador com "shim"** (chocolatey). O
  `shutil.which` da spec devolveria o lancador, nao o ffmpeg, e o pacote sairia
  com um stub que procura um caminho inexistente na maquina do usuario. O
  workflow baixa um build estatico do gyan.dev, com URL versionada e sha256
  conferido.
- **Sem auto-update.** `updates.py` inteiro e macOS (ditto, Info.plist, `.app`) e
  `caminho_do_bundle` devolve `None` fora do darwin -- a janela nao monta o menu.
  Se um dia houver update no Windows, e codigo novo, nao adaptacao daquele.
- **`os.replace` nao e o mesmo.** No POSIX substitui por cima de arquivo aberto;
  no Windows estoura `PermissionError` se outro processo estiver com o destino
  aberto. Todo cache do projeto grava assim (`cache.py`, `library.py`,
  `presentation.py`, `ui/widgets/thumbs.py`) e o `counts_worker` le o parquet em
  paralelo -- ainda nao tratado, e o primeiro lugar a olhar se aparecer falha de
  escrita so no Windows.

## Relacionado

O gate `_empacotado()` em `service.py` (que forca pool no bundle por causa de um
SIGSEGV do numpy) esta em `trackclassifier-concorrencia`.
