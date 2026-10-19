"""Render offscreen da aba Biblioteca com o acervo real. Somente leitura.

Nao chama analyze_all (nao grava nada em ~/.trackclassifier/data) e desconecta
peaks_requested antes de mostrar a janela, para nao computar buckets durante o
render. Uso:

    uv run python design/render_biblioteca.py saida.png [largura] [altura]
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyleFactory  # noqa: E402

from trackclassifier.config import load_config  # noqa: E402
from trackclassifier.library import scan_labeled  # noqa: E402
from trackclassifier.service import TrackService  # noqa: E402
from trackclassifier.ui.fonts import registra_fontes  # noqa: E402
from trackclassifier.ui.viewmodel import (  # noqa: E402
    library_state,
    model_state,
    review_state,
)
from trackclassifier.ui.window import MainWindow  # noqa: E402

SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "biblioteca.png"
LARGURA = int(sys.argv[2]) if len(sys.argv) > 2 else 1512
ALTURA = int(sys.argv[3]) if len(sys.argv) > 3 else 982


def _pump(app: QApplication, ciclos: int = 8) -> None:
    """Gira o loop de eventos o bastante para a tela assentar.

    O sendPostedEvents(DeferredDelete) nao e detalhe: processEvents() NAO
    processa deleteLater -- e o HintBar troca a legenda com removeWidget +
    deleteLater. Sem ele, os rotulos da aba anterior continuam filhos do
    HintBar (fora do layout, no geometry antigo) e saem pintados na imagem,
    o que parece bug do app e e so do render.
    """
    for _ in range(ciclos):
        app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def main() -> int:
    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))
    registra_fontes()
    app.setStyleSheet((RAIZ / "src/trackclassifier/ui/app.qss").read_text(encoding="utf-8"))

    config = load_config(RAIZ / "config.toml")
    servico = TrackService(config)
    # _labeled sai da varredura no disco: scan_labeled so identifica os arquivos,
    # nao extrai feature nenhuma (isso e analyze_all, que grava cache).
    servico._labeled = scan_labeled(config, servico.sha1_cache)
    servico._inbox = []
    print(f"rotuladas: {len(servico._labeled)}")

    TrackService.analyze_all = lambda self, *a, **k: False
    # O scan do boot pintaria "✕ CANCELAR" no lugar de ESCANEAR e trocaria o
    # resumo do cabecalho por "Escaneando N/M". A tela que interessa aqui e a
    # de repouso.
    MainWindow._inicia_scan = lambda self: None

    janela = MainWindow(servico, config_path=RAIZ / "config.toml")
    # Sem isto cada linha visivel sem buckets enfileira um compute_peaks de ~0,4 s
    # na thread do servico e o render fica esperando o disco a toa.
    janela.library_tab.peaks_requested.disconnect(janela._worker.compute_peaks)
    janela.tabs.setCurrentWidget(janela.library_tab)
    janela.resize(LARGURA, ALTURA)
    janela.show()
    _pump(app)
    janela.apply_states(
        review_state(servico), library_state(servico), model_state(servico)
    )
    _pump(app)
    janela.grab().save(str(SAIDA))
    print(f"salvo em {SAIDA}")
    # close() roda o closeEvent: para o player e para a QThread do worker. Sem
    # isto o interpretador sai com "QThread: Destroyed while thread is still
    # running" e o processo pode demorar a morrer.
    janela.close()
    _pump(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
