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
    #: O terceiro `int` extra em `_erro` identifica QUAL contador (checagem
    #: ou instalacao) a geracao pertence -- ver o comentario em
    #: `_roda_checagem`/`_roda_instalacao` sobre por que as duas operacoes
    #: nao podem compartilhar um unico contador.
    _achou = Signal(int, object)
    _nada = Signal(int)
    _erro = Signal(int, int, str)
    _terminou = Signal(int)
    _andou = Signal(int, int, int)

    #: Identificam qual contador uma geracao pertence, para `_erro` (usado
    #: pelas duas operacoes) comparar contra o certo.
    _OP_CHECAGEM = 0
    _OP_INSTALACAO = 1

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
        # Dois contadores, nao um: checar() e instalar_release() podiam
        # roubar o resultado uma da outra porque as duas incrementavam o
        # MESMO self._geracao. Cenario real (achado #3 da revisao final): o
        # usuario clica "Atualizar" (instalar_release comeca, geracao de
        # instalacao = 1) e, enquanto o download roda, aciona o menu
        # "Buscar atualizacoes..." (checar comeca e incrementava o mesmo
        # contador para 2). Quando a instalacao termina e emite _terminou(1),
        # o _atual(1) do worker comparava contra o contador global (agora 2)
        # e descartava o resultado -- a troca do bundle no disco JA tinha
        # acontecido (o trabalho da thread nao e cancelado, so a emissao do
        # resultado), mas a faixa ficava presa em "Baixando..." para sempre e
        # `relanca()` nunca rodava. Contadores separados fazem uma checagem
        # em voo nunca invalidar uma instalacao em voo, e vice-versa.
        self._geracao_checagem = 0
        self._geracao_instalacao = 0

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
        self._geracao_checagem += 1
        geracao = self._geracao_checagem
        QThreadPool.globalInstance().start(_Tarefa(lambda: self._roda_checagem(geracao)))

    def _roda_checagem(self, geracao: int) -> None:
        try:
            release = self.buscar()
        except UpdateError as erro:
            self._emite(self._erro, self._OP_CHECAGEM, geracao, str(erro))
            return
        except Exception as erro:
            # Bug nosso nao pode virar excecao solta numa thread do pool: o
            # pior aceitavel e a faixa dizer que nao deu para verificar.
            self._emite(
                self._erro, self._OP_CHECAGEM, geracao, f"Nao foi possivel verificar: {erro}"
            )
            return

        if release is None or not ha_versao_nova(self.versao_atual, release.version):
            self._emite(self._nada, geracao)
            return
        self._emite(self._achou, geracao, release)

    def instalar_release(self, release: Release, bundle: Path) -> None:
        self._geracao_instalacao += 1
        geracao = self._geracao_instalacao
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
            self._emite(self._erro, self._OP_INSTALACAO, geracao, str(erro))
            return
        except Exception as erro:
            self._emite(
                self._erro, self._OP_INSTALACAO, geracao, f"Falha na atualizacao: {erro}"
            )
            return
        self._emite(self._terminou, geracao)

    def _atual_checagem(self, geracao: int) -> bool:
        """Descarta resultado de pedido antigo: duas checagens em voo podem
        terminar fora de ordem, e a mais velha ofereceria uma versao que ja
        nao e a ultima."""
        return geracao == self._geracao_checagem

    def _atual_instalacao(self, geracao: int) -> bool:
        """Mesma ideia de `_atual_checagem`, mas para o contador de
        instalacao -- ver o comentario em __init__ sobre por que sao dois
        contadores separados."""
        return geracao == self._geracao_instalacao

    @Slot(int, object)
    def _recebe_achou(self, geracao: int, release: object) -> None:
        if self._atual_checagem(geracao):
            self.disponivel.emit(release)

    @Slot(int)
    def _recebe_nada(self, geracao: int) -> None:
        if self._atual_checagem(geracao):
            self.sem_novidade.emit()

    @Slot(int, int, str)
    def _recebe_erro(self, operacao: int, geracao: int, mensagem: str) -> None:
        atual = (
            self._atual_checagem(geracao)
            if operacao == self._OP_CHECAGEM
            else self._atual_instalacao(geracao)
        )
        if atual:
            self.falhou.emit(mensagem)

    @Slot(int)
    def _recebe_terminou(self, geracao: int) -> None:
        if self._atual_instalacao(geracao):
            self.instalado.emit()

    @Slot(int, int, int)
    def _recebe_andou(self, geracao: int, feito: int, total: int) -> None:
        if self._atual_instalacao(geracao):
            self.progresso.emit(feito, total)
