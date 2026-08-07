"""Roda a checagem e a instalacao de atualizacao fora da thread da GUI.

Por que QThreadPool e nao a QThread do servico, como a maioria da UI faz: o
mesmo motivo de counts_worker.py -- nada aqui toca o TrackService. Este
codigo fala com a rede e com o diretorio do .app, e nao ha estado
compartilhado com o servico para proteger. A regra de "uma so thread dona do
servico" continua valendo para tudo que realmente fala com ele.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .. import __version__
from ..updates import (
    Release,
    UpdateError,
    baixa,
    busca_ultimo_release,
    ha_versao_nova,
    instala,
)


class _Tarefa(QRunnable):
    def __init__(self, funcao: Callable[[], None]):
        super().__init__()
        self._funcao = funcao

    def run(self) -> None:
        self._funcao()


class VerificadorDeAtualizacao(QObject):
    """Checa e instala; emite tudo de volta na thread da GUI."""

    #: Release mais novo que o atual. `object` porque Release e um dataclass
    #: Python, nao um tipo registrado no meta-objeto do Qt.
    disponivel = Signal(object)
    sem_novidade = Signal()
    falhou = Signal(str)
    #: (bytes baixados, total em bytes). total e 0 quando o servidor nao
    #: manda Content-Length.
    progresso = Signal(int, int)
    instalado = Signal()

    #: Internos: atravessam a thread do pool de volta para a da GUI. Levam a
    #: geracao junto para o resultado de um pedido velho ser descartado.
    _achou = Signal(int, object)
    _nada = Signal(int)
    _erro = Signal(int, str)
    _terminou = Signal(int)
    _andou = Signal(int, int, int)

    def __init__(
        self,
        parent: QObject | None = None,
        versao_atual: str = __version__,
        buscar: Callable[[], Release | None] = busca_ultimo_release,
        baixar: Callable = baixa,
        instalar: Callable = instala,
    ) -> None:
        super().__init__(parent)
        # Injetaveis pelo mesmo motivo do `contar` de ContadorEmSegundoPlano:
        # o teste precisa observar o caminho inteiro sem tocar a rede nem o
        # diretorio do .app.
        self.versao_atual = versao_atual
        self.buscar = buscar
        self.baixar = baixar
        self.instalar = instalar
        self._geracao = 0

        self._achou.connect(self._recebe_achou)
        self._nada.connect(self._recebe_nada)
        self._erro.connect(self._recebe_erro)
        self._terminou.connect(self._recebe_terminou)
        self._andou.connect(self._recebe_andou)

    def _emite(self, sinal, *args) -> None:
        try:
            sinal.emit(*args)
        except RuntimeError:
            # A janela fechou enquanto a tarefa rodava e o objeto C++ ja
            # morreu. Emitir para um dono morto e o unico jeito real desta
            # thread quebrar a janela -- e ela nao tem mais quem ouca.
            return

    def checar(self) -> None:
        self._geracao += 1
        geracao = self._geracao
        QThreadPool.globalInstance().start(_Tarefa(lambda: self._roda_checagem(geracao)))

    def _roda_checagem(self, geracao: int) -> None:
        try:
            release = self.buscar()
        except UpdateError as erro:
            self._emite(self._erro, geracao, str(erro))
            return
        except Exception as erro:
            # Bug nosso nao pode virar excecao solta numa thread do pool: o
            # pior aceitavel e a faixa dizer que nao deu para verificar.
            self._emite(self._erro, geracao, f"Nao foi possivel verificar: {erro}")
            return

        if release is None or not ha_versao_nova(self.versao_atual, release.version):
            self._emite(self._nada, geracao)
            return
        self._emite(self._achou, geracao, release)

    def instalar_release(self, release: Release, bundle: Path) -> None:
        self._geracao += 1
        geracao = self._geracao
        QThreadPool.globalInstance().start(
            _Tarefa(lambda: self._roda_instalacao(geracao, release, bundle))
        )

    def _roda_instalacao(self, geracao: int, release: Release, bundle: Path) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="trackclassifier-dl-") as pasta:
                destino = Path(pasta) / f"TrackClassifier-{release.version}.zip"
                zip_baixado = self.baixar(
                    release,
                    destino,
                    progresso=lambda feito, total: self._emite(
                        self._andou, geracao, feito, total
                    ),
                )
                self.instalar(zip_baixado, bundle, release.version)
        except UpdateError as erro:
            self._emite(self._erro, geracao, str(erro))
            return
        except Exception as erro:
            self._emite(self._erro, geracao, f"Falha na atualizacao: {erro}")
            return
        self._emite(self._terminou, geracao)

    def _atual(self, geracao: int) -> bool:
        """Descarta resultado de pedido antigo: duas checagens em voo podem
        terminar fora de ordem, e a mais velha ofereceria uma versao que ja
        nao e a ultima."""
        return geracao == self._geracao

    @Slot(int, object)
    def _recebe_achou(self, geracao: int, release: object) -> None:
        if self._atual(geracao):
            self.disponivel.emit(release)

    @Slot(int)
    def _recebe_nada(self, geracao: int) -> None:
        if self._atual(geracao):
            self.sem_novidade.emit()

    @Slot(int, str)
    def _recebe_erro(self, geracao: int, mensagem: str) -> None:
        if self._atual(geracao):
            self.falhou.emit(mensagem)

    @Slot(int)
    def _recebe_terminou(self, geracao: int) -> None:
        if self._atual(geracao):
            self.instalado.emit()

    @Slot(int, int, int)
    def _recebe_andou(self, geracao: int, feito: int, total: int) -> None:
        if self._atual(geracao):
            self.progresso.emit(feito, total)
