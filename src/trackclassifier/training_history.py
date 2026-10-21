"""Historico de treinamentos do modelo, persistido em data_dir.

O dashboard da aba Modelo (web) exibe historico de treinos, deltas entre
treinos consecutivos e a versao ativa. A fonte de verdade e este arquivo
JSON: uma entrada por `TrackService.train()`, cap de 50, escrita atomica
(tmp + os.replace) para nao deixar metade de um JSON no disco se o processo
morrer no meio.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CAP = 50

#: `handcrafted-v2` -> era 2. Extrator sem sufixo numerico trava em era 1,
#: que nunca deve acontecer -- a ideia e ter um major por geracao de
#: features, comparavel entre si, sem confundir treinos da mesma era.
_PADRAO_ERA = re.compile(r"-v(\d+)$")


@dataclass(frozen=True)
class TrainingEntry:
    ts: str
    extractor: str
    version: str
    n_examples: int
    accuracy: float
    ordinal_mae: float
    weighted_f1: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> TrainingEntry:
        return cls(
            ts=str(dados["ts"]),
            extractor=str(dados["extractor"]),
            version=str(dados["version"]),
            n_examples=int(dados["n_examples"]),
            accuracy=float(dados["accuracy"]),
            ordinal_mae=float(dados["ordinal_mae"]),
            weighted_f1=float(dados["weighted_f1"]),
        )


def load(path: Path) -> list[TrainingEntry]:
    """Le o historico; arquivo ausente ou corrompido devolve lista vazia.

    Corrompido nao derruba o servico: dashboard sem historico e degradacao
    recuperavel com o proximo treino, crash de boot nao.
    """
    try:
        cru = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as e:
        print(f"historico de treino ilegivel ({e}); comecando vazio", file=sys.stderr)
        return []
    if not isinstance(cru, dict) or not isinstance(cru.get("entries"), list):
        print("historico de treino em formato inesperado; comecando vazio", file=sys.stderr)
        return []
    entradas: list[TrainingEntry] = []
    for item in cru["entries"]:
        try:
            entradas.append(TrainingEntry.from_dict(item))
        except (KeyError, TypeError, ValueError) as e:
            print(f"entrada de historico invalida descartada ({e})", file=sys.stderr)
    return entradas


def era_de(extractor: str) -> int:
    match = _PADRAO_ERA.search(extractor)
    return int(match.group(1)) if match else 1


def next_version(entries: list[TrainingEntry], extractor: str) -> str:
    """Versao do PROXIMO treino na era corrente do extractor.

    Formato v{era}.{indice}.0: `indice` conta treinos JA gravados na MESMA
    era, entao o primeiro treino da era vira v2.0.0 e cada retreino
    incrementa o minor. A versao e gravada NA entrada, nunca derivada da
    posicao: o cap de 50 derruba os mais antigos e deslocaria todo o
    historico se a versao dependesse do indice na lista.
    """
    era = era_de(extractor)
    na_era = sum(1 for e in entries if era_de(e.extractor) == era)
    return f"v{era}.{na_era}.0"


def append(path: Path, entry: TrainingEntry, cap: int = CAP) -> None:
    """Adiciona uma entrada, cortando as mais antigas acima do cap.

    Escrita atomica: writes em tmp no mesmo diretorio e os.replace, para
    um leitor (outro processo do servico) nunca ver JSON pela metade.
    """
    path = Path(path)
    entries = load(path)
    entries.append(entry)
    excedente = max(len(entries) - cap, 0)
    entries = entries[excedente:]
    dados = {"entries": [e.to_dict() for e in entries]}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
