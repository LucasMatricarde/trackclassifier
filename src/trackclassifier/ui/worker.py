"""A QThread dona do TrackService.

Regra unica de concorrencia desta UI: o servico vive inteiro nesta thread.
A janela nunca chama TrackService direto -- manda um pedido por slot e
recebe o resultado por sinal. E o que dispensa lock, evita duas escritas
concorrentes no parquet e mantem o ProcessPoolExecutor rodando onde ele
sempre rodou, dentro do proprio servico.
"""

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..config import Config
from ..labels import Label
from ..model import NotEnoughClassesError
from ..service import TrackService
from .viewmodel import library_state, model_state, review_state


class ServiceWorker(QObject):
    """Slots que rodam na thread do servico. Nenhum toca em widget."""

    scan_progress = Signal(int, int, str)
    #: True quando o scan terminou por cancelamento, nao por ter acabado.
    scan_finished = Signal(bool)
    states_changed = Signal(object, object, object)
    retrained = Signal()
    error = Signal(str)
    #: (sha1, caminho do .npy) -- computo teve sucesso. Carrega o resultado
    #: direto, ao contrario de decide/undo/train/scan: um refresh() completo
    #: aqui resetaria a selecao inteira da tabela da Biblioteca a cada
    #: computo em segundo plano, e o computo pode disparar dezenas de vezes
    #: numa unica sessao de scroll.
    peaks_ready = Signal(str, str)

    def __init__(self, service: TrackService) -> None:
        super().__init__()
        self._service = service
        self._cancelar = threading.Event()

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

    @Slot(object)
    def reload_config(self, config: Config) -> None:
        """Troca o TrackService por um construido sobre a config nova.

        Roda na thread do worker, como todo o resto: recriar o servico na
        thread da GUI colocaria dois donos no mesmo parquet, que e
        exatamente o que a arquitetura desta UI existe para evitar.

        Limitacao conhecida, tratada na tela e nao aqui: durante um scan o
        loop de eventos desta thread esta parado dentro de analyze_all, entao
        este slot -- enfileirado -- so rodaria quando o scan terminasse. A
        aba Configuracao desabilita Salvar enquanto escaneia, com o motivo
        dito ao lado do botao.
        """
        try:
            self._service = TrackService(config)
        except Exception as erro:
            # Mesma politica do resto do worker: degrada e reporta, nunca
            # derruba a janela. O servico antigo continua de pe.
            self.error.emit(f"Falha ao aplicar a configuracao: {erro}")
            return
        self.refresh()

    # ---- acoes --------------------------------------------------------

    @Slot()
    def scan(self) -> None:
        self._cancelar.clear()

        def _progresso(concluidas: int, total: int, nome: str) -> None:
            self.scan_progress.emit(concluidas, total, nome)

        cancelado = False
        try:
            cancelado = self._service.analyze_all(
                on_progress=_progresso, should_cancel=self._cancelar.is_set
            )
        except Exception as erro:
            # O servico ja contem falha de item e falha de pool; chegar aqui
            # significa algo fora disso (config quebrada, disco cheio no save).
            # Vira mensagem na status bar, nunca derruba a janela.
            self.error.emit(str(erro))
        self.refresh()
        self.scan_finished.emit(cancelado)

    def request_cancel(self) -> None:
        """Pede o fim do scan. Chamado DIRETO da thread da GUI, sem a fila.

        Este e o unico ponto em que a GUI toca este objeto sem passar por
        sinal/slot, e a excecao e deliberada: durante um scan o loop de
        eventos desta thread esta parado dentro de analyze_all, entao um slot
        em fila so rodaria DEPOIS que o scan terminasse -- justamente o que se
        quer interromper. Um @Slot aqui seria codigo morto com aparencia de
        funcionar.

        threading.Event e o que torna a travessia segura: set/is_set sao
        thread-safe por construcao, e o flag e de mao unica dentro de um scan
        (so clear() no inicio do proximo o rearma). E o unico estado
        compartilhado entre as duas threads.

        Corrida conhecida e aceita: se o cancelamento chegar entre o
        QTimer.singleShot que enfileira scan() e o proprio scan() comecar, o
        clear() apaga o pedido e o scan roda inteiro. A janela so mostra o
        botao "Cancelar" depois de enfileirar, e o usuario pode clicar de
        novo.
        """
        self._cancelar.set()

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

    @Slot(str, str)
    def compute_peaks(self, sha1: str, path: str) -> None:
        """Computa os buckets de uma track e avisa quem pediu, sem refresh completo.

        peaks_ready carrega o resultado direto (sha1, caminho); quem pediu
        atualiza so a propria linha/track, sem tocar no resto do estado --
        ver o comentario em peaks_ready para o motivo de nao chamar refresh().

        Falha nao emite nada: ficar sem onda colorida nao merece a status
        bar, porque o fallback mono ja aparece e a track continua
        classificavel.
        """
        try:
            caminho = self._service.ensure_peaks(sha1, Path(path))
        except Exception:
            # ensure_peaks ja contem o que sabe conter; chegar aqui e algo
            # fora dele. Silencioso pelo mesmo motivo do docstring.
            return
        if caminho is not None:
            self.peaks_ready.emit(sha1, str(caminho))


class ServiceThread:
    """Embrulha QThread + ServiceWorker para a janela nao lidar com os dois."""

    def __init__(self, service: TrackService) -> None:
        self._thread = QThread()
        self.worker = ServiceWorker(service)
        self.worker.moveToThread(self._thread)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        # Pede o cancelamento ANTES do quit: quit() so faz efeito quando o
        # worker volta ao loop de eventos, e durante um scan ele nao volta.
        # Com o pedido feito primeiro, analyze_all sai na proxima extracao e o
        # quit encontra a thread ociosa em segundos, em vez de esperar o lote.
        self.worker.request_cancel()
        self._thread.quit()
        # Espera de verdade: sair com a thread viva enquanto o servico escreve
        # o parquet deixaria o arquivo pela metade. Com o request_cancel
        # acima, o caso normal e a thread sair em poucos segundos -- o teto e
        # uma extracao em voo, que nao da para interromper sem matar um
        # processo no meio de ffmpeg/librosa.
        #
        # O timeout continua existindo porque nem toda demora e cancelavel: um
        # extract_one travado num arquivo patologico, ou uma escrita de parquet
        # lenta, nao consultam o flag. terminate() nao e alternativa -- matar a
        # thread durante a escrita corrompe o parquet, que e pior do que a
        # janela demorar a fechar.
        if not self._thread.wait(30_000):
            pass  # extracao presa: sair mesmo assim e melhor que travar a UI.
