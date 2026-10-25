"""Backend descartavel para os E2E do Playwright que decidem/movem arquivos.

Sobe a API real (serve.app, que entrega o web/dist) sobre pastas e data_dir
temporarios, com o ExtratorFalso dos testes de servico: o E2E nao toca no
acervo, no config.toml nem no data_dir do app. Uso:

    python -m tests.e2e_backend --dir <tmp> --port 8799

Nao e um teste (o nome nao casa com test_*.py): o pytest nao o coleta. Quem o
inicia e o decide-flow.spec.ts, que gera o arquivo de teste na inbox depois
que /api/health responde.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import uvicorn

from trackclassifier.config import Config
from trackclassifier.labels import Label
from trackclassifier.service import TrackService

from .test_service import ExtratorFalso

# Seis por classe, como os testes de servico: o modelo precisa de exemplos
# em todas as classes para ajustar, e sem modelo ajustado a fila e vazia.
_POR_CLASSE = 6


def _mp3_de_um_segundo(destino: Path) -> None:
    """mp3 real e curto: a apresentacao (peaks/capa) decodifica o arquivo de
    verdade, entao bytes soltos gerariam falha de decodificacao."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:a", "libmp3lame", "-q:a", "9", str(destino),
        ],
        check=True,
    )


def monta_servico(raiz: Path) -> TrackService:
    pastas = {}
    for chave, rotulo in (("up", Label.UP), ("neutral", Label.NEUTRAL), ("down", Label.DOWN)):
        destino = raiz / chave
        destino.mkdir(parents=True, exist_ok=True)
        pastas[rotulo] = destino
    inbox = raiz / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    data_dir = raiz / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # retrain_every alto: a decisao do E2E nao pode disparar retreino em
    # segundo plano no meio do teste.
    config = Config.from_folders(
        folders=pastas, inbox=inbox, data_dir=data_dir, retrain_every=1000, min_examples=1
    )
    for rotulo, energia in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for i in range(_POR_CLASSE):
            valor = energia + i * 0.001
            _mp3_de_um_segundo(pastas[rotulo] / f"t{i}_{valor:.3f}.mp3")

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    servico.train()
    return servico


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument(
        "--pos-lenta",
        type=float,
        default=0.0,
        metavar="N",
        help="atrasa N s a passada de tags/capa/tonalidade de cada scan",
    )
    args = parser.parse_args()

    import trackclassifier.serve as serve_mod

    servico = monta_servico(args.dir)
    if args.pos_lenta > 0:
        # Instala depois de monta_servico: o scan de montagem nao deve pagar o
        # atraso. Com o ExtratorFalso e tudo em cache a "analise" e instantanea;
        # sem este atraso a fase "processando" dura milissegundos e o E2E nao
        # teria como enxergar o header nela.
        original = servico._preenche_apresentacao

        def _preenche_lento(*a, **kw):
            time.sleep(args.pos_lenta)
            return original(*a, **kw)

        servico._preenche_apresentacao = _preenche_lento
    serve_mod._service = servico
    serve_mod._config = servico.config
    # Caminho dentro do tmp: sem isto um apply gravaria o config.toml do cwd.
    serve_mod._config_path = args.dir / "config.toml"

    uvicorn.run(serve_mod.app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
