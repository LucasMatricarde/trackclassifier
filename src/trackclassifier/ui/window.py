"""Janela principal. Monta as abas e liga os sinais -- nada mais."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QPushButton, QTabWidget

from ..service import TrackService
from .library_tab import LibraryTab
from .model_tab import ModelTab
from .review_tab import ReviewTab
from .viewmodel import LibraryState, ModelState, ReviewState
from .widgets.player import MULTIMEDIA_AVAILABLE, create_player
from .worker import ServiceThread


class MainWindow(QMainWindow):
    def __init__(self, service: TrackService) -> None:
        super().__init__()
        self.setWindowTitle("Track classifier")
        self.resize(1180, 760)

        self._player = create_player(self)
        self._thread = ServiceThread(service)
        self._worker = self._thread.worker

        self.review_tab = ReviewTab(self._player)
        self.library_tab = LibraryTab()
        self.model_tab = ModelTab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.review_tab, "Revisao")
        self.tabs.addTab(self.library_tab, "Biblioteca")
        self.tabs.addTab(self.model_tab, "Modelo")

        self._botao_scan = QPushButton("⟳ Escanear")
        self._botao_scan.clicked.connect(self._worker.scan)
        self.tabs.setCornerWidget(self._botao_scan, Qt.Corner.TopRightCorner)

        self.setCentralWidget(self.tabs)

        if not MULTIMEDIA_AVAILABLE:
            self.statusBar().showMessage(
                "Sem QtMultimedia: player simulado. Instale o extra audio para ouvir."
            )

        self._conecta()
        self._thread.start()
        # Dispara sozinho depois da janela aparecer: o scan sincrono do CLI
        # seriam minutos de tela morta aqui.
        QTimer.singleShot(0, self._worker.refresh)
        QTimer.singleShot(0, self._worker.scan)

    def _conecta(self) -> None:
        self.review_tab.decide_requested.connect(self._worker.decide)
        self.review_tab.undo_requested.connect(self._worker.undo)
        self.review_tab.bulk_approve_requested.connect(self._worker.bulk_approve)
        self.library_tab.decide_requested.connect(self._worker.decide)
        self.model_tab.train_requested.connect(self._worker.train)

        self._worker.states_changed.connect(self.apply_states)
        self._worker.scan_progress.connect(self._mostra_progresso)
        self._worker.scan_finished.connect(
            lambda: self.statusBar().showMessage("Scan concluido.", 4000)
        )
        self._worker.error.connect(
            lambda mensagem: self.statusBar().showMessage(mensagem, 6000)
        )
        self._worker.retrained.connect(
            lambda: self.statusBar().showMessage("Modelo retreinado.", 4000)
        )

    def apply_states(
        self, review: ReviewState, library: LibraryState, model: ModelState
    ) -> None:
        self.review_tab.set_state(review)
        self.library_tab.set_state(library)
        self.model_tab.set_state(model)

    def _mostra_progresso(self, concluidas: int, total: int, nome: str) -> None:
        self.statusBar().showMessage(f"escaneando {concluidas}/{total} · {nome}")

    def closeEvent(self, event) -> None:
        self._player.stop()
        self._thread.stop()
        super().closeEvent(event)
