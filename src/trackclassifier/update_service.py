"""Atualizacao do app dentro do `dj serve`.

Decide quando checar, quando oferecer e o que mostrar. O app que o usuario
abre e o shell Electron, com o backend Python embutido, entao quem checa, baixa
e instala e o backend, e o shell so mostra os dialogos. Toda a logica de
verdade continua em `updates.py` -- este modulo so a orquestra.

Nada aqui conhece HTTP. `serve.py` expoe os metodos; os testes exercitam a
classe direto, com os mesmos seams (`fetch`, `download`, `install`, `verify`)
que o fluxo de update sempre teve.
"""

import logging
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from . import __version__
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
from .viewmodel import texto_de_atualizacao

_log = logging.getLogger(__name__)

#: Estados de `status()`. "done" e "failed" ficam ate a proxima instalacao: o
#: shell consulta por polling e nao pode perder o resultado por ter chegado
#: um instante depois do fim.
IDLE = "idle"
DOWNLOADING = "downloading"
INSTALLING = "installing"
DONE = "done"
FAILED = "failed"


class InstallInProgress(Exception):
    """Ja ha um download ou troca de bundle em curso."""


class AlreadyInstalled(UpdateError):
    """A versao nova ja foi instalada; so falta reabrir o app.

    Subclasse de UpdateError de proposito: quem trata UpdateError continua
    tratando. Mas o servidor a distingue (409) para o shell dizer "reabra o
    app" em tom informativo, em vez do dialogo de "Falha na atualizacao".
    """


class UpdateService:
    def __init__(
        self,
        bundle: Path | None,
        state: Callable[[], EstadoDeAtualizacao | None],
        n_tracks: Callable[[], int],
        current_version: str = __version__,
        fetch: Callable[[], Release | None] = busca_ultimo_release,
        download: Callable = baixa,
        install: Callable = instala,
        verify: Callable = verifica_instalavel,
    ) -> None:
        # `state` e uma funcao, e nao o objeto, porque o data_dir so existe
        # depois do primeiro uso (o servidor sobe sem config no setup). Quem
        # chama devolve None enquanto nao ha onde gravar.
        self._bundle = bundle
        self._state = state
        self._n_tracks = n_tracks
        self._current_version = current_version
        self._fetch = fetch
        self._download = download
        self._install = install
        self._verify = verify

        self._lock = threading.Lock()
        self._release: Release | None = None
        self._situacao = IDLE
        self._feito = 0
        self._total = 0
        self._erro: str | None = None

    @property
    def supported(self) -> bool:
        """So ha o que trocar dentro de um .app: em dev e no Windows e False."""
        return self._bundle is not None

    def check(self, manual: bool) -> dict:
        """Procura versao nova. `manual` e o pedido explicito do menu.

        O pedido explicito ignora o intervalo de um dia e a versao dispensada,
        e deixa o erro de rede subir: quem clicou quer saber que falhou. A
        checagem automatica do boot faz o contrario, porque erro de rede sem
        ninguem ter pedido nada e ruido.
        """
        if not self.supported:
            return {"supported": False, "available": False}

        # Durante e depois de uma instalacao a resposta do GitHub deixa de
        # valer: este processo ainda roda a versao antiga (entao a mesma
        # versao seria oferecida de novo) e uma segunda oferta em cima de um
        # download vira 409 na cara do usuario. O shell usa estes campos para
        # dizer o que esta acontecendo em vez de oferecer.
        with self._lock:
            situacao = self._situacao
        if situacao in (DOWNLOADING, INSTALLING):
            return {"supported": True, "available": False, "in_progress": True}
        if situacao == DONE:
            return {"supported": True, "available": False, "installed": True}

        estado = self._state()
        if not manual:
            if estado is None:
                # Sem data_dir e o primeiro uso: nao ha onde lembrar a checagem
                # nem a dispensa, e oferecer update durante o setup seria
                # repetir o dialogo a cada abertura.
                return {"supported": True, "available": False}
            if not estado.deve_checar():
                return {"supported": True, "available": False}
            # Marca ANTES de buscar, de proposito: com a rede fora,
            # marcar so no sucesso faria cada boot repetir a requisicao ate
            # estourar o limite anonimo de 60/h do GitHub.
            estado.marca_checagem()

        try:
            release = self._fetch()
        except UpdateError:
            if manual:
                raise
            return {"supported": True, "available": False}

        # A busca roda fora do lock e pode demorar ate 10s: nesse intervalo um
        # install_pending() pode ter comecado. Gravar `_release` por cima de um
        # download em curso deixaria, depois de uma falha, uma oferta pendente
        # que o usuario nunca viu. Quem ficou para tras so devolve o estado.
        if release is None or not ha_versao_nova(self._current_version, release.version):
            ocupado = self._grava_oferta(None)
            return ocupado or {"supported": True, "available": False}

        if not manual and estado is not None and estado.esta_dispensada(release.version):
            return {"supported": True, "available": False}

        ocupado = self._grava_oferta(release)
        if ocupado:
            return ocupado
        texto = texto_de_atualizacao(
            release, self._current_version, self._conta_tracks(release)
        )
        return {
            "supported": True,
            "available": True,
            "version": release.version,
            "text": texto,
        }

    def _grava_oferta(self, release: Release | None) -> dict | None:
        """Grava a oferta pendente, a menos que uma instalacao tenha comecado.

        Devolve a resposta de "ocupado" nesse caso (e nao grava), ou None.
        """
        with self._lock:
            if self._situacao in (DOWNLOADING, INSTALLING):
                return {"supported": True, "available": False, "in_progress": True}
            if self._situacao == DONE:
                return {"supported": True, "available": False, "installed": True}
            self._release = release
        return None

    def _conta_tracks(self, release: Release) -> int:
        """So conta quando a versao recalcula a analise, que e quando o texto usa o numero.

        Falhar aqui nao pode derrubar a checagem: o numero e so a frase "recalcula
        a analise das N tracks". Sem servico (primeiro uso) ou com a biblioteca
        indisponivel, a oferta sai com 0 em vez de um 503 que o shell engoliria.
        """
        if not release.recomputa:
            return 0
        try:
            return self._n_tracks()
        except Exception:
            # Sem servico (primeiro uso) o 0 e a resposta certa e nao chega
            # aqui. Qualquer outra coisa e bug de verdade na biblioteca: o texto
            # sai com 0 para a oferta nao morrer, mas o erro fica registrado em
            # vez de sumir.
            _log.warning("nao consegui contar as tracks para o texto do update", exc_info=True)
            return 0

    def dismiss(self) -> None:
        with self._lock:
            release = self._release
        estado = self._state()
        if release is not None and estado is not None:
            estado.dispensa(release.version)

    def install_pending(self, version: str | None = None) -> None:
        """Dispara download + troca numa thread; o progresso vem de `status()`.

        `version` e a que o usuario viu no dialogo. Sem ela, um `check` posterior
        (outro clique no menu, outra checagem) poderia trocar o release pendente
        e instalar uma versao cujo texto ele nunca leu.
        """
        with self._lock:
            if self._situacao in (DOWNLOADING, INSTALLING):
                raise InstallInProgress()
            if self._situacao == DONE:
                raise AlreadyInstalled("A atualizacao ja foi instalada. Feche e abra o app.")
            if self._release is None or self._bundle is None:
                raise UpdateError("Nao ha atualizacao pendente para instalar.")
            if version is not None and version != self._release.version:
                raise UpdateError(
                    f"A versao oferecida ({version}) mudou para {self._release.version}. "
                    "Busque atualizacoes de novo."
                )
            release = self._release
            self._situacao = DOWNLOADING
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
        assert bundle is not None  # install_pending() ja garantiu
        try:
            # Antes do download: um bundle somente leitura
            # falha em segundos em vez de depois de baixar o zip inteiro.
            self._verify(bundle)
            with tempfile.TemporaryDirectory(prefix="trackclassifier-dl-") as pasta:
                destino = Path(pasta) / f"TrackClassifier-{release.version}.zip"
                zip_baixado = self._download(release, destino, progresso=self._andou)
                with self._lock:
                    self._situacao = INSTALLING
                self._install(zip_baixado, bundle, release.version)
        except UpdateError as erro:
            self._termina(FAILED, str(erro))
            return
        except Exception as erro:
            self._termina(FAILED, f"Falha na atualizacao: {erro}")
            return
        self._termina(DONE, None)

    def _andou(self, feito: int, total: int) -> None:
        with self._lock:
            self._feito = feito
            self._total = total

    def _termina(self, situacao: str, erro: str | None) -> None:
        with self._lock:
            self._situacao = situacao
            self._erro = erro
