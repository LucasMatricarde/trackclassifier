"""Conversao entre notacao Camelot e classica.

Funcoes puras, sem dependencia de Qt nem de mutagen. A key e guardada em
forma canonica (pitch class + modo) e formatada so na hora de exibir --
gravar a string "8A" no parquet inviabilizaria trocar de notacao depois, que
e exatamente o alternador que esta fase entrega.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final


class Mode(Enum):
    """Modo da tonalidade. Camelot usa A para menor e B para maior."""

    MAJOR = "B"
    MINOR = "A"


class KeyNotation(Enum):
    """Como a key e exibida. Preferencia global, alternavel na Biblioteca."""

    CAMELOT = "camelot"
    CLASSIC = "classic"


#: pitch class: 0 = C, 1 = C#/Db, ... 11 = B
_CAMELOT_PARA_PITCH: Final[dict[tuple[int, Mode], int]] = {
    (1, Mode.MINOR): 8,   (1, Mode.MAJOR): 11,
    (2, Mode.MINOR): 3,   (2, Mode.MAJOR): 6,
    (3, Mode.MINOR): 10,  (3, Mode.MAJOR): 1,
    (4, Mode.MINOR): 5,   (4, Mode.MAJOR): 8,
    (5, Mode.MINOR): 0,   (5, Mode.MAJOR): 3,
    (6, Mode.MINOR): 7,   (6, Mode.MAJOR): 10,
    (7, Mode.MINOR): 2,   (7, Mode.MAJOR): 5,
    (8, Mode.MINOR): 9,   (8, Mode.MAJOR): 0,
    (9, Mode.MINOR): 4,   (9, Mode.MAJOR): 7,
    (10, Mode.MINOR): 11, (10, Mode.MAJOR): 2,
    (11, Mode.MINOR): 6,  (11, Mode.MAJOR): 9,
    (12, Mode.MINOR): 1,  (12, Mode.MAJOR): 4,
}

_PITCH_PARA_CAMELOT: Final[dict[tuple[int, Mode], int]] = {
    (pitch, modo): numero for (numero, modo), pitch in _CAMELOT_PARA_PITCH.items()
}

#: Grafia usada por Rekordbox/Mixed In Key: bemois no menor, exceto F#m.
_NOMES_MENOR: Final[tuple[str, ...]] = (
    "Cm", "Dbm", "Dm", "Ebm", "Em", "Fm",
    "F#m", "Gm", "Abm", "Am", "Bbm", "Bm",
)
_NOMES_MAIOR: Final[tuple[str, ...]] = (
    "C", "Db", "D", "Eb", "E", "F",
    "F#", "G", "Ab", "A", "Bb", "B",
)

#: Enarmonicos aceitos na leitura de tag: ID3 nao segue padrao nenhum, e o
#: mesmo tom aparece como C#m ou Dbm conforme a ferramenta que gravou.
_ALIASES: Final[dict[str, str]] = {
    "c#m": "Dbm", "d#m": "Ebm", "gbm": "F#m", "g#m": "Abm", "a#m": "Bbm",
    "c#": "Db", "d#": "Eb", "gb": "F#", "g#": "Ab", "a#": "Bb",
}

SEM_KEY: Final[str] = "—"


@dataclass(frozen=True, slots=True)
class Key:
    """Tonalidade canonica. `pitch_class` 0-11 com 0 = C."""

    pitch_class: int
    mode: Mode

    def __post_init__(self) -> None:
        if not 0 <= self.pitch_class <= 11:
            raise ValueError(f"pitch_class fora de 0-11: {self.pitch_class}")

    @property
    def camelot(self) -> str:
        """Ex.: '8A'."""
        return f"{_PITCH_PARA_CAMELOT[(self.pitch_class, self.mode)]}{self.mode.value}"

    @property
    def classic(self) -> str:
        """Ex.: 'Am'."""
        tabela = _NOMES_MENOR if self.mode is Mode.MINOR else _NOMES_MAIOR
        return tabela[self.pitch_class]

    @property
    def camelot_number(self) -> int:
        """1-12. E o que define a cor do chip na roda de Camelot."""
        return _PITCH_PARA_CAMELOT[(self.pitch_class, self.mode)]

    def format(self, notation: KeyNotation) -> str:
        return self.camelot if notation is KeyNotation.CAMELOT else self.classic


def parse_key(text: str) -> Key | None:
    """Le '8A', 'Am', 'C#m' ou 'F'. Devolve None se nao reconhecer.

    Best-effort de proposito: a tag pode conter qualquer coisa (inclusive
    texto livre de quem catalogou a mao), e quem chama decide o que fazer
    com None -- aqui, mostrar travessao.
    """
    bruto = text.strip()
    if not bruto:
        return None

    # Camelot: numero seguido de A ou B.
    if len(bruto) >= 2 and bruto[:-1].isdigit() and bruto[-1].upper() in ("A", "B"):
        numero = int(bruto[:-1])
        modo = Mode.MINOR if bruto[-1].upper() == "A" else Mode.MAJOR
        pitch = _CAMELOT_PARA_PITCH.get((numero, modo))
        return Key(pitch, modo) if pitch is not None else None

    # Classica, com enarmonicos tolerados.
    nome = _ALIASES.get(bruto.lower(), bruto)
    normalizado = nome[0].upper() + nome[1:].replace("M", "m")
    if normalizado in _NOMES_MENOR:
        return Key(_NOMES_MENOR.index(normalizado), Mode.MINOR)
    if normalizado in _NOMES_MAIOR:
        return Key(_NOMES_MAIOR.index(normalizado), Mode.MAJOR)
    return None


def format_key(key: Key | None, notation: KeyNotation) -> str:
    """Formata para exibicao. Track sem key mostra travessao."""
    return key.format(notation) if key is not None else SEM_KEY


ALL_KEYS: Final[tuple[Key, ...]] = tuple(
    Key(pitch, modo)
    for (pitch, modo) in sorted(
        _PITCH_PARA_CAMELOT, key=lambda k: (_PITCH_PARA_CAMELOT[k], k[1].value)
    )
)
