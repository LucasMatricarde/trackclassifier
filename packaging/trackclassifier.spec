# Spec do PyInstaller para o .app do macOS. Gerado a mao (nao pelo
# `pyinstaller --onedir ...` inicial) porque o app.qss gerado e o
# config.example.toml embutido (bootstrap do primeiro uso, ver cli.py)
# precisam de --add-data explicito -- nenhum dos dois e descoberto pela
# analise automatica de imports.
#
# Rodar da raiz do repo: uv run --extra build pyinstaller packaging/trackclassifier.spec

import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# spec roda com exec(), sem __file__ -- SPECPATH e a variavel que o
# PyInstaller injeta no namespace do spec com o caminho deste arquivo.
raiz = Path(SPECPATH).parent

# Importa o pacote so para ler __version__. Cabe aqui porque
# trackclassifier/__init__.py nao importa nada -- se um dia importar, este
# import passa a arrastar numpy/librosa para dentro do processo que ANALISA
# o bundle, e o build fica lento sem motivo.
sys.path.insert(0, str(raiz / "src"))
from trackclassifier import __version__  # noqa: E402

# Os tres pacotes abaixo tem descoberta de plugin/hook em runtime (sklearn
# decide o solver a usar, pyarrow carrega extensoes C++ por nome, librosa
# importa submodulos so quando a funcao correspondente e chamada) que a
# analise estatica do PyInstaller nao segue sozinha. collect_all() pega
# tudo (codigo + dados + binarios) em vez de tentar listar hidden imports um
# a um -- infla o bundle, mas e o jeito confiavel de nao faltar nada numa
# combinacao de libs cientificas + Qt.
datas = [
    (str(raiz / "src" / "trackclassifier" / "ui" / "app.qss"), "trackclassifier/ui"),
    (str(raiz / "config.example.toml"), "."),
]
# ffmpeg/ffprobe entram como binarios do bundle porque o app aberto pelo
# Finder nao herda o PATH do shell -- sem eles embutidos, /opt/homebrew/bin
# fica invisivel e toda track falha em audio_io._require_ffmpeg. Passar por
# `binaries` (e nao copiar a mao) e o que faz o PyInstaller seguir a arvore
# de dylibs do homebrew e reescrever os install_name para dentro do .app.
binaries = []
for ferramenta in ("ffmpeg", "ffprobe"):
    caminho = shutil.which(ferramenta)
    if caminho is None:
        raise SystemExit(
            f"{ferramenta} nao encontrado no PATH da maquina de build. "
            "Instale com: brew install ffmpeg"
        )
    binaries.append((caminho, "."))

hiddenimports = []
for pacote in ("sklearn", "pyarrow", "librosa"):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h

bloco = Analysis(
    [str(raiz / "packaging" / "entry_point.py")],
    pathex=[str(raiz / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(bloco.pure)

exe = EXE(
    pyz,
    bloco.scripts,
    [],
    exclude_binaries=True,
    name="TrackClassifier",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

colecao = COLLECT(
    exe,
    bloco.binaries,
    bloco.datas,
    strip=False,
    upx=False,
    name="TrackClassifier",
)

app = BUNDLE(
    colecao,
    name="TrackClassifier.app",
    icon=None,
    bundle_identifier="com.lucasmatricarde.trackclassifier",
    info_plist={
        "CFBundleShortVersionString": __version__,
        "NSHighResolutionCapable": True,
    },
)
