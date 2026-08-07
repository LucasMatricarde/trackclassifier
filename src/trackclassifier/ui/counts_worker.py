"""Roda counts.contagens fora da thread da GUI.

Contar arquivo e I/O, e o formulario revalida a cada tecla digitada: numa
pasta de rede, um iterdir na thread da GUI congela a janela enquanto o
usuario digita. O debounce (no proprio formulario) reduz a frequencia; esta
classe tira o custo restante do caminho de desenho.

Por que QThreadPool e nao a QThread do servico, como o resto da UI faz: a
contagem nao toca no TrackService -- ela le nomes de arquivo e os metadados
do parquet, e o parquet e gravado com os.replace (atomico), entao ler nunca
pega um arquivo pela metade. Nao ha estado compartilhado para proteger, e a
regra de "uma so thread dona do servico" continua valendo para tudo que
realmente fala com ele. Alem disso o FirstRunDialog roda ANTES de existir
qualquer TrackService, e ele precisa dos mesmos chips.
"""

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .counts import contagens


class _Tarefa(QRunnable):
    def __init__(self, geracao: int, caminhos: dict[str, str], dono: "ContadorEmSegundoPlano"):
        super().__init__()
        self._geracao = geracao
        self._caminhos = caminhos
        self._dono = dono

    def run(self) -> None:
        try:
            resultado = self._dono.contar(self._caminhos)
        except Exception:
            # Nenhuma contagem vale derrubar a thread do pool. Sem chip e um
            # estado previsto pela tela; excecao vazando aqui nao e.
            return
        try:
            self._dono.resultado.emit(self._geracao, resultado)
        except RuntimeError:
            # A tela fechou enquanto a contagem rodava e o objeto C++ ja foi
            # destruido. Emitir para um dono morto e o unico jeito real de
            # esta thread quebrar a janela -- e ela nao tem mais quem ouca.
            return


class ContadorEmSegundoPlano(QObject):
    """Pede contagens e devolve so a mais recente."""

    #: (chave -> texto do chip), so da ultima geracao pedida.
    pronto = Signal(dict)
    #: Interno: atravessa a thread do pool de volta para a thread da GUI.
    resultado = Signal(int, dict)

    def __init__(
        self,
        parent: QObject | None = None,
        contar: Callable[[dict[str, str]], dict[str, str]] | None = None,
    ) -> None:
        super().__init__(parent)
        # Injetavel pelo mesmo motivo do escolher_pasta do formulario: o
        # teste precisa observar SE e QUANTAS vezes a contagem foi pedida
        # sem depender do disco.
        self.contar = contar or contagens
        self._geracao = 0
        self.resultado.connect(self._recebe)

    def pedir(self, caminhos: dict[str, str]) -> None:
        self._geracao += 1
        QThreadPool.globalInstance().start(_Tarefa(self._geracao, dict(caminhos), self))

    @Slot(int, dict)
    def _recebe(self, geracao: int, resultado: dict) -> None:
        # Descarta resultado de pedido antigo: duas contagens em voo podem
        # terminar fora de ordem, e a mais velha sobrescreveria a nova --
        # o chip mostraria a contagem de um caminho que o campo nao tem
        # mais.
        if geracao != self._geracao:
            return
        self.pronto.emit(resultado)
