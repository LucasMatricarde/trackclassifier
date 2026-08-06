"""Janela principal. Monta as abas e liga os sinais -- nada mais."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
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
        self._registra_atalhos()
        self._thread.start()
        # Dispara sozinho depois da janela aparecer: o scan sincrono do CLI
        # seriam minutos de tela morta aqui. O overload de 3 argumentos e
        # essencial aqui: singleShot(msec, callable) roda o callable na
        # thread de QUEM CHAMOU (a GUI), ignorando a afinidade de thread do
        # objeto -- so o overload (msec, contexto, callable) despacha via
        # fila de eventos do contexto, que e o que manda isto rodar na
        # QThread do worker em vez de travar a janela pela duracao do scan.
        QTimer.singleShot(0, self._worker, self._worker.refresh)
        QTimer.singleShot(0, self._worker, self._worker.scan)

    def _conecta(self) -> None:
        self.review_tab.decide_requested.connect(self._worker.decide)
        self.review_tab.undo_requested.connect(self._worker.undo)
        self.review_tab.bulk_approve_requested.connect(self._worker.bulk_approve)
        self.library_tab.decide_requested.connect(self._worker.decide)
        self.model_tab.train_requested.connect(self._worker.train)

        self._worker.states_changed.connect(self.apply_states)
        self._worker.scan_progress.connect(self._mostra_progresso)
        self._worker.scan_finished.connect(self._scan_concluido)
        self._worker.error.connect(self._mostra_erro)
        self._worker.retrained.connect(self._modelo_retreinado)

    def apply_states(
        self, review: ReviewState, library: LibraryState, model: ModelState
    ) -> None:
        self.review_tab.set_state(review)
        self.library_tab.set_state(library)
        self.model_tab.set_state(model)

    def _mostra_progresso(self, concluidas: int, total: int, nome: str) -> None:
        self.statusBar().showMessage(f"escaneando {concluidas}/{total} · {nome}")

    def _scan_concluido(self) -> None:
        self.statusBar().showMessage("Scan concluido.", 4000)

    def _mostra_erro(self, mensagem: str) -> None:
        self.statusBar().showMessage(mensagem, 6000)

    def _modelo_retreinado(self) -> None:
        self.statusBar().showMessage("Modelo retreinado.", 4000)

    # ---- atalhos de teclado --------------------------------------------
    #
    # Registrados aqui, nao em keyPressEvent das abas: depois que a janela
    # aparece, o foco inicial cai no QTabBar e eventos de tecla sobem a
    # cadeia de pais a partir de quem tem foco, nunca descem para o widget
    # de conteudo da aba. E o QTableView da Biblioteca ainda consome teclas
    # de digito para a busca incremental embutida do QAbstractItemView antes
    # que qualquer keyPressEvent de LibraryTab rode. QShortcut com contexto
    # WindowShortcut entra na etapa de despacho do Qt que roda ANTES da
    # entrega normal de keyPressEvent ao widget focado, entao funciona
    # independente de onde o foco esta dentro da janela.

    _TECLAS_ROTULO = {"1": "-1", "2": "neutra", "3": "+1"}

    def _registra_atalho(self, tecla: str, callback) -> None:
        atalho = QShortcut(QKeySequence(tecla), self)
        atalho.setContext(Qt.ShortcutContext.WindowShortcut)
        atalho.activated.connect(callback)

    def _registra_atalhos(self) -> None:
        for tecla, rotulo in self._TECLAS_ROTULO.items():
            self._registra_atalho(tecla, lambda rotulo=rotulo: self._decide_na_aba_atual(rotulo))
        self._registra_atalho("Space", self._alterna_reproducao)
        self._registra_atalho("Right", self._pular_revisao)
        self._registra_atalho("Left", self._voltar_revisao)
        # "Ctrl+Z" e portavel: no macOS o Qt mapeia o modificador Ctrl da
        # sequencia para Cmd automaticamente (comportamento documentado do
        # QKeySequence), entao nao precisa de uma segunda entrada para Cmd+Z.
        self._registra_atalho("Ctrl+Z", self._desfazer)

    def _decide_na_aba_atual(self, rotulo: str) -> None:
        aba = self.tabs.currentWidget()
        if aba is self.review_tab:
            self.review_tab.decide_atual(rotulo)
        elif aba is self.library_tab:
            self.library_tab.decide_selecionada(rotulo)

    def _alterna_reproducao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self._player.toggle()

    def _pular_revisao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self.review_tab.pular()

    def _voltar_revisao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self.review_tab.voltar()

    def _desfazer(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self.review_tab.undo_requested.emit()

    def closeEvent(self, event) -> None:
        self._player.stop()
        self._thread.stop()
        super().closeEvent(event)
