---
name: trackclassifier-empacotamento
description: Use ao gerar, alterar ou depurar o app macOS do trackclassifier - packaging/trackclassifier.spec, packaging/entry_point.py, PyInstaller, dist/TrackClassifier.app - e ao mexer em audio_io.py ou cli.py, que so quebram empacotados. Cobre o comando de build, por que nao ha workflow de release, as quatro armadilhas do bundle (freeze_support, ffmpeg embutido, config fora do cwd, FirstRunDialog) e o teste obrigatorio com PATH minimo. Gatilhos: "gerar o .app", "PyInstaller", "abriu pelo Finder e falhou", "bundle", "release", "assinar app".
---

# Executavel do macOS

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm   # gera dist/TrackClassifier.app
```

Nao ha workflow de release: runner macOS hospedado no GitHub conta minuto a 10x,
e um build (~15min) estoura a cota gratis rapido. O build e sempre local, rodado
a mao quando quiser uma versao nova.

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

## Relacionado

O gate `_empacotado()` em `service.py` (que forca pool no bundle por causa de um
SIGSEGV do numpy) esta em `trackclassifier-concorrencia`.
