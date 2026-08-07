# Spec do PyInstaller, uma so para macOS e Windows. Gerado a mao (nao pelo
# `pyinstaller --onedir ...` inicial) porque o app.qss gerado e o
# config.example.toml embutido (bootstrap do primeiro uso, ver cli.py)
# precisam de --add-data explicito -- nenhum dos dois e descoberto pela
# analise automatica de imports.
#
# So o passo final diverge por plataforma: no macOS o COLLECT vira um
# BUNDLE (.app, com Info.plist e identificador); no Windows o proprio
# COLLECT ja e a pasta distribuivel, com TrackClassifier.exe dentro. Uma
# spec so, e nao duas, porque tudo que costuma quebrar no pacote (datas das
# fontes, collect_all das libs cientificas, ffmpeg embutido) e identico nas
# duas e duplicar convidaria as duas copias a divergirem.
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
# As fontes sao dado, nao modulo: a analise de imports nao as descobre, e
# sem elas o .app cai no fallback do sistema enquanto a versao rodada do
# repo fica certa -- o tipo de divergencia que so aparece depois de
# distribuir. Mesmo motivo do app.qss estar aqui em cima.
datas += [
    (str(caminho), "trackclassifier/ui/fonts")
    for caminho in sorted((raiz / "src" / "trackclassifier" / "ui" / "fonts").iterdir())
]
# ffmpeg/ffprobe entram como binarios do bundle porque o app aberto pelo
# Finder (ou pelo Menu Iniciar) nao herda o PATH do shell -- sem eles
# embutidos, /opt/homebrew/bin fica invisivel e toda track falha em
# audio_io._require_ffmpeg. Passar por `binaries` (e nao copiar a mao) e o
# que faz o PyInstaller seguir a arvore de dylibs do homebrew (ou de DLLs, no
# Windows) e reescrever os install_name para dentro do pacote.
#
# O nome do arquivo copiado e preservado, entao no Windows ele chega como
# ffmpeg.exe -- e por isso que audio_io._nome_no_bundle poe o sufixo antes de
# procurar. Cuidado no Windows com gerenciador que instala por "shim" (o
# chocolatey faz isso): shutil.which devolveria o lancador, nao o ffmpeg, e o
# pacote sairia com um stub que procura um caminho que nao existe na maquina
# do usuario. O workflow de release baixa um build estatico justamente para
# nao cair nisso.
binaries = []
for ferramenta in ("ffmpeg", "ffprobe"):
    caminho = shutil.which(ferramenta)
    if caminho is None:
        dica = "brew install ffmpeg"
        if sys.platform == "win32":
            dica = "winget install Gyan.FFmpeg"
        elif sys.platform not in ("darwin", "win32"):
            dica = "sudo apt install ffmpeg"
        raise SystemExit(
            f"{ferramenta} nao encontrado no PATH da maquina de build. "
            f"Instale com: {dica}"
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

# BUNDLE so existe no macOS: e ele que embrulha a colecao no .app com
# Info.plist. No Windows o artefato distribuivel ja e a pasta que o COLLECT
# acabou de escrever (dist/TrackClassifier/, com TrackClassifier.exe dentro),
# e chamar BUNDLE ali seria erro do PyInstaller. A versao, que no macOS vai
# no CFBundleShortVersionString e e o que o updater compara, no Windows nao
# tem onde morar -- e por isso que updates.caminho_do_bundle devolve None
# fora do macOS e o menu de atualizacao nao aparece.
if sys.platform == "darwin":
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
