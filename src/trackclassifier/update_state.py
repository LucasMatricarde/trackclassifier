"""Controle de quando checar atualizacao e do que ja foi dispensado.

Mora em data_dir/updates.json, junto do resto do estado do app. Guarda epoch
float e nao data ISO de proposito: comparar dois floats nao tem como errar, e
o arquivo e lido so pela maquina.

Nenhum metodo aqui levanta excecao. Este arquivo e controle acessorio -- se
ele estiver corrompido, ilegivel ou num diretorio sem permissao, o pior
resultado aceitavel e checar atualizacao uma vez a mais. Falhar a abertura do
app por causa dele nao e aceitavel.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

#: Uma vez por dia. Mais frequente nao descobre nada (releases sao manuais) e
#: gasta requisicao do limite anonimo de 60/h da API do GitHub.
INTERVALO_PADRAO_S: float = 24 * 60 * 60


class EstadoDeAtualizacao:
    def __init__(self, path: Path, agora: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        # Injetavel para o teste nao precisar dormir 24h nem mexer no relogio
        # do sistema.
        self._agora = agora

    def _carrega(self) -> dict:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _grava(self, dados: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(dados), encoding="utf-8")
        except OSError:
            # Silencio proposital: ver a docstring do modulo.
            return

    def deve_checar(self, intervalo_s: float = INTERVALO_PADRAO_S) -> bool:
        ultima = self._carrega().get("ultima_checagem")
        if not isinstance(ultima, int | float):
            return True
        return (self._agora() - float(ultima)) >= intervalo_s

    def marca_checagem(self) -> None:
        dados = self._carrega()
        dados["ultima_checagem"] = self._agora()
        self._grava(dados)

    def dispensa(self, versao: str) -> None:
        dados = self._carrega()
        dados["versao_dispensada"] = versao
        self._grava(dados)

    def esta_dispensada(self, versao: str) -> bool:
        return self._carrega().get("versao_dispensada") == versao
