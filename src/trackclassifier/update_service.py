"""Atualizacao do app dentro do `dj serve`, sem Qt.

Porta de `ui/update_worker.py` e do trecho de `ui/window.py` que decide quando
checar, quando oferecer e o que mostrar. Existe porque o app que o usuario abre
passa a ser o shell Electron: a janela Qt (e o QThreadPool dela) nao esta mais
no processo, entao quem checa, baixa e instala e o backend, e o shell so
mostra os dialogos. Toda a logica de verdade continua em `updates.py` -- este
modulo so a orquestra.

Nada aqui conhece HTTP. `serve.py` expoe os metodos; os testes exercitam a
classe direto, com os mesmos seams (`buscar`, `baixar`, `instalar`,
`verificar`) que o worker do Qt tinha.
"""

import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .ui.viewmodel import texto_de_atualizacao
from .update_state import EstadoDeAtualizacao
from .updates import (
    Release,
    UpdateError,
    baixa,
    busca_ultimo_release,
    ha_versao_nova,
    instala,
    verifica_instalavel,
)

#: Estados de `status()`. "done" e "failed" ficam ate a proxima instalacao: o
#: shell consulta por polling e nao pode perder o resultado por ter chegado
#: um instante depois do fim.
OCIOSO = "idle"
BAIXANDO = "downloading"
INSTALANDO = "installing"
CONCLUIDO = "done"
FALHOU = "failed"


class InstalacaoEmAndamento(Exception):
    """Ja ha um download ou troca de bundle em curso."""


class ServicoDeAtualizacao:
    def __init__(
        self,
        bundle: Path | None,
        estado: Callable[[], EstadoDeAtualizacao | None],
        n_tracks: Callable[[], int],
        versao_atual: str = __version__,
        buscar: Callable[[], Release | None] = busca_ultimo_release,
        baixar: Callable = baixa,
        instalar: Callable = instala,
        verificar: Callable = verifica_instalavel,
    ) -> None:
        # `estado` e uma funcao, e nao o objeto, porque o data_dir so existe
        # depois do primeiro uso (o servidor sobe sem config no setup). Quem
        # chama devolve None enquanto nao ha onde gravar, e o servico segue
        # funcionando, so sem lembrar da checagem nem da versao dispensada.
        self._bundle = bundle
        self._estado = estado
        self._n_tracks = n_tracks
        self._versao_atual = versao_atual
        self._buscar = buscar
        self._baixar = baixar
        self._instalar = instalar
        self._verificar = verificar

        self._lock = threading.Lock()
        self._release: Release | None = None
        self._situacao = OCIOSO
        self._feito = 0
        self._total = 0
        self._erro: str | None = None

    @property
    def suportado(self) -> bool:
        """So ha o que trocar dentro de um .app: em dev e no Windows e False."""
        return self._bundle is not None

    def checa(self, manual: bool) -> dict:
        """Procura versao nova. `manual` e o pedido explicito do menu.

        O pedido explicito ignora o intervalo de um dia e a versao dispensada,
        e deixa o erro de rede subir: quem clicou quer saber que falhou. A
        checagem automatica do boot faz o contrario, porque erro de rede sem
        ninguem ter pedido nada e ruido.
        """
        if not self.suportado:
            return {"supported": False, "available": False}

        estado = self._estado()
        if not manual and estado is not None:
            if not estado.deve_checar():
                return {"supported": True, "available": False}
            # Marca ANTES de buscar, como a janela Qt fazia: com a rede fora,
            # marcar so no sucesso faria cada boot repetir a requisicao ate
            # estourar o limite anonimo de 60/h do GitHub.
            estado.marca_checagem()

        try:
            release = self._buscar()
        except UpdateError:
            if manual:
                raise
            return {"supported": True, "available": False}

        if release is None or not ha_versao_nova(self._versao_atual, release.version):
            with self._lock:
                self._release = None
            return {"supported": True, "available": False}

        if not manual and estado is not None and estado.esta_dispensada(release.version):
            return {"supported": True, "available": False}

        with self._lock:
            self._release = release
        # So conta as tracks quando a versao recalcula a analise: e o unico
        # caso em que o texto usa o numero, e contar monta a biblioteca toda.
        n = self._n_tracks() if release.recomputa else 0
        return {
            "supported": True,
            "available": True,
            "version": release.version,
            "text": texto_de_atualizacao(release, self._versao_atual, n),
        }

    def dispensa(self) -> None:
        with self._lock:
            release = self._release
        estado = self._estado()
        if release is not None and estado is not None:
            estado.dispensa(release.version)

    def instala_pendente(self) -> None:
        """Dispara download + troca numa thread; o progresso vem de `status()`."""
        with self._lock:
            if self._situacao in (BAIXANDO, INSTALANDO):
                raise InstalacaoEmAndamento()
            if self._release is None or self._bundle is None:
                raise UpdateError("Nao ha atualizacao pendente para instalar.")
            release = self._release
            self._situacao = BAIXANDO
            self._feito = 0
            self._total = 0
            self._erro = None
        threading.Thread(target=self._roda, args=(release,), daemon=True).start()

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._situacao,
                "done": self._feito,
                "total": self._total,
                "error": self._erro,
            }

    def _roda(self, release: Release) -> None:
        bundle = self._bundle
        assert bundle is not None  # instala_pendente() ja garantiu
        try:
            # Antes do download, como no worker do Qt: um bundle somente leitura
            # falha em segundos em vez de depois de baixar o zip inteiro.
            self._verificar(bundle)
            with tempfile.TemporaryDirectory(prefix="trackclassifier-dl-") as pasta:
                destino = Path(pasta) / f"TrackClassifier-{release.version}.zip"
                zip_baixado = self._baixar(release, destino, progresso=self._andou)
                with self._lock:
                    self._situacao = INSTALANDO
                self._instalar(zip_baixado, bundle, release.version)
        except UpdateError as erro:
            self._termina(FALHOU, str(erro))
            return
        except Exception as erro:
            self._termina(FALHOU, f"Falha na atualizacao: {erro}")
            return
        self._termina(CONCLUIDO, None)

    def _andou(self, feito: int, total: int) -> None:
        with self._lock:
            self._feito = feito
            self._total = total

    def _termina(self, situacao: str, erro: str | None) -> None:
        with self._lock:
            self._situacao = situacao
            self._erro = erro
