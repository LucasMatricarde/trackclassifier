"""A QThread dona do TrackService.

Regra unica de concorrencia desta UI: o servico vive inteiro nesta thread.
A janela nunca chama TrackService direto -- manda um pedido por slot e
recebe o resultado por sinal. E o que dispensa lock, evita duas escritas
concorrentes no parquet e mantem o ProcessPoolExecutor rodando onde ele
sempre rodou, dentro do proprio servico.
"""

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..labels import Label
from ..model import NotEnoughClassesError
from ..service import TrackService
from .viewmodel import library_state, model_state, review_state


class ServiceWorker(QObject):
    """Slots que rodam na thread do servico. Nenhum toca em widget."""

    scan_progress = Signal(int, int, str)
    scan_finished = Signal()
    states_changed = Signal(object, object, object)
    retrained = Signal()
    error = Signal(str)

    def __init__(self, service: TrackService) -> None:
        super().__init__()
        self._service = service
        self._cancelar = False

    # ---- leitura ------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        try:
            estados = (
                review_state(self._service),
                library_state(self._service),
                model_state(self._service),
            )
        except Exception as erro:
            # library_state percorre _labeled chamando service._analysis, que
            # tem `assert analise is not None`. Uma track rotulada sem entrada
            # no cache -- parquet truncado por interrupcao, ou extractor.name
            # bumpado sem rescan das pastas ja rotuladas -- vira AssertionError
            # aqui dentro. Este slot roda na QThread do worker, onde uma
            # excecao que escapa nao tem quem a capture: a janela simplesmente
            # para de receber estado, sem mensagem nenhuma. Toda a UI degrada
            # por mensagem na status bar; refresh nao pode ser a excecao.
            self.error.emit(f"Falha ao montar a tela: {erro}")
            return
        self.states_changed.emit(*estados)

    # ---- acoes --------------------------------------------------------

    @Slot()
    def scan(self) -> None:
        self._cancelar = False

        def _progresso(concluidas: int, total: int, nome: str) -> None:
            self.scan_progress.emit(concluidas, total, nome)

        try:
            self._service.analyze_all(on_progress=_progresso)
        except Exception as erro:
            # O servico ja contem falha de item e falha de pool; chegar aqui
            # significa algo fora disso (config quebrada, disco cheio no save).
            # Vira mensagem na status bar, nunca derruba a janela.
            self.error.emit(str(erro))
        self.refresh()
        self.scan_finished.emit()

    @Slot()
    def cancel_scan(self) -> None:
        self._cancelar = True

    @Slot(str, str)
    def decide(self, sha1: str, label: str) -> None:
        # As duas abas emitem o mesmo sinal, mas a operacao e diferente:
        # decide() so age sobre a inbox, reclassify() so sobre a biblioteca.
        # path_for e o que decide qual das duas -- ele levanta KeyError
        # exatamente quando a sha1 nao esta na inbox. Nao da para deixar o
        # proprio decide() resolver: ele devolve o mesmo False para "nao esta
        # na inbox" e para "arquivo sumiu entre o scan e a decisao", e o
        # usuario ficaria com um refresh mudo em vez de mensagem.
        try:
            self._service.path_for(sha1)
            na_inbox = True
        except KeyError:
            na_inbox = False

        try:
            if na_inbox:
                retreinou = self._service.decide(sha1, Label(label))
            else:
                retreinou = self._service.reclassify(sha1, Label(label))
        except KeyError:
            # reclassify levanta KeyError quando a sha1 tambem nao esta na
            # biblioteca: estado obsoleto na tela (a track saiu por fora entre
            # o ultimo refresh e o atalho de teclado).
            self.error.emit("Track nao esta mais na fila nem na biblioteca.")
            self.refresh()
            return
        except Exception as erro:
            self.error.emit(str(erro))
            self.refresh()
            return
        if retreinou:
            self.retrained.emit()
        self.refresh()

    @Slot()
    def undo(self) -> None:
        if not self._service.undo_last():
            self.error.emit("Nada para desfazer.")
        self.refresh()

    @Slot()
    def train(self) -> None:
        try:
            self._service.train()
        except NotEnoughClassesError as erro:
            self.error.emit(str(erro))
            return
        self.retrained.emit()
        self.refresh()

    @Slot(float)
    def bulk_approve(self, min_confidence: float) -> None:
        try:
            self._service.bulk_approve(min_confidence)
        except Exception as erro:
            self.error.emit(str(erro))
        self.refresh()


class ServiceThread:
    """Embrulha QThread + ServiceWorker para a janela nao lidar com os dois."""

    def __init__(self, service: TrackService) -> None:
        self._thread = QThread()
        self.worker = ServiceWorker(service)
        self.worker.moveToThread(self._thread)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._thread.quit()
        # Espera de verdade: sair com a thread viva enquanto o servico
        # escreve o parquet deixaria o arquivo pela metade. Mas quit() so
        # faz efeito quando o worker volta pro loop de eventos -- se um scan
        # (minutos, potencialmente) esta em andamento, ele so volta quando
        # analyze_all() termina. Um timeout limitado evita travar o fechar
        # da janela para sempre; terminate() nao e opcao, porque matar a
        # thread no meio de uma escrita de parquet corrompe o arquivo, o que
        # e pior do que a janela demorar pra fechar. Cancelamento de verdade
        # do scan fica fora do escopo desta fase (sem botao de cancelar
        # funcional ainda) -- isto so limita o dano, nao resolve a UX.
        if not self._thread.wait(5000):
            pass  # scan ainda rodando: nao ha o que fazer alem de esperar.
