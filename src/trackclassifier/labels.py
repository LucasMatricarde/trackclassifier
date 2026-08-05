from enum import Enum


class Label(str, Enum):
    UP = "+1"
    NEUTRAL = "neutra"
    DOWN = "-1"


LABEL_ORDER: list[Label] = [Label.DOWN, Label.NEUTRAL, Label.UP]

LABEL_TARGET: dict[Label, float] = {
    Label.DOWN: 0.0,
    Label.NEUTRAL: 0.5,
    Label.UP: 1.0,
}
