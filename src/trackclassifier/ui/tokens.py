"""Gerado por build_tokens.py a partir de design-tokens.json. Nao edite a mao."""

from typing import Final

# --- color ---
COLOR_SURFACE_0: Final = "#0A1119"
COLOR_SURFACE_1: Final = "#111C28"
COLOR_SURFACE_2: Final = "#1A293A"
COLOR_SURFACE_3: Final = "#24364A"
COLOR_SURFACE_WAVEFORM: Final = "#0C151F"
COLOR_SURFACE_SELECTION_BAR: Final = "#7187FF"
COLOR_SURFACE_PANEL: Final = "#121E2B"
COLOR_SURFACE_PANEL_RAISED: Final = "#192737"
COLOR_TEXT_PRIMARY: Final = "#F0F4FF"
COLOR_TEXT_SECONDARY: Final = "#AFBCD2"
COLOR_TEXT_MUTED: Final = "#8292AA"
COLOR_TEXT_DISABLED: Final = "#536176"
COLOR_TEXT_INVERSE: Final = "#0A1119"
COLOR_BORDER_SUBTLE: Final = "rgba(255,255,255,0.05)"
COLOR_BORDER_DEFAULT: Final = "rgba(255,255,255,0.10)"
COLOR_BORDER_STRONG: Final = "rgba(255,255,255,0.18)"
COLOR_BORDER_PANEL: Final = "rgba(164,188,224,0.14)"
COLOR_ACCENT_BASE: Final = "#7887FF"
COLOR_ACCENT_HOVER: Final = "#9AA7FF"
COLOR_ACCENT_BG: Final = "#202B52"
COLOR_ACCENT_TEXT: Final = "#C7CEFF"
COLOR_CLASSIFICATION_ANIMADA_BASE: Final = "#FF6576"
COLOR_CLASSIFICATION_ANIMADA_BG: Final = "#3B202C"
COLOR_CLASSIFICATION_ANIMADA_TEXT: Final = "#FF8795"
COLOR_CLASSIFICATION_NEUTRO_BASE: Final = "#FFC652"
COLOR_CLASSIFICATION_NEUTRO_BG: Final = "#3B3021"
COLOR_CLASSIFICATION_NEUTRO_TEXT: Final = "#FFD478"
COLOR_CLASSIFICATION_LENTO_BASE: Final = "#638FFF"
COLOR_CLASSIFICATION_LENTO_BG: Final = "#1A2E50"
COLOR_CLASSIFICATION_LENTO_TEXT: Final = "#91B1FF"
COLOR_STATE_DANGER: Final = "#FF6576"
COLOR_STATE_SUCCESS: Final = "#36D68D"
COLOR_STATE_WARNING: Final = "#FFC652"
COLOR_CAMELOT_1: Final = "#3FBFA8"
COLOR_CAMELOT_2: Final = "#3FBF7F"
COLOR_CAMELOT_3: Final = "#5CBF3F"
COLOR_CAMELOT_4: Final = "#95C63F"
COLOR_CAMELOT_5: Final = "#D6C13F"
COLOR_CAMELOT_6: Final = "#E09B3F"
COLOR_CAMELOT_7: Final = "#E8703F"
COLOR_CAMELOT_8: Final = "#E84F6B"
COLOR_CAMELOT_9: Final = "#D14FA8"
COLOR_CAMELOT_10: Final = "#9B5FD1"
COLOR_CAMELOT_11: Final = "#5F72D1"
COLOR_CAMELOT_12: Final = "#3F9BD1"
COLOR_WAVEBAND_LOW_GAIN: Final = "1.00"
COLOR_WAVEBAND_MID_GAIN: Final = "0.92"
COLOR_WAVEBAND_HIGH_GAIN: Final = "1.00"
COLOR_WAVEBAND_FLOOR: Final = "0.06"
COLOR_WAVEBAND_PLAYHEAD: Final = "#FFFFFF"
COLOR_WAVEBAND_GRID: Final = "rgba(255,255,255,0.08)"

# --- font ---
FONT_FAMILY_SANS: Final = "Space Grotesk, Inter, -apple-system, Segoe UI, Roboto, sans-serif"
FONT_FAMILY_MONO: Final = "JetBrains Mono, SF Mono, Consolas, monospace"
FONT_SIZE_MICRO: Final = "10px"
FONT_SIZE_CAPTION: Final = "11px"
FONT_SIZE_SMALL: Final = "12px"
FONT_SIZE_BODY: Final = "13px"
FONT_SIZE_LARGE: Final = "15px"
FONT_SIZE_TITLE: Final = "18px"
FONT_SIZE_DISPLAY: Final = "22px"
FONT_TRACKING_NORMAL: Final = "0"
FONT_TRACKING_WIDE: Final = "0.06em"
FONT_TRACKING_WIDEST: Final = "0.09em"
FONT_CASE_LABEL: Final = "uppercase"
FONT_CASE_BODY: Final = "none"
FONT_WEIGHT_REGULAR: Final = "400"
FONT_WEIGHT_MEDIUM: Final = "500"
FONT_LEADING_TIGHT: Final = "1.25"
FONT_LEADING_NORMAL: Final = "1.5"

# --- space ---
SPACE_1: Final = 2
SPACE_2: Final = 4
SPACE_3: Final = 6
SPACE_4: Final = 8
SPACE_5: Final = 12
SPACE_6: Final = 16
SPACE_7: Final = 24
SPACE_8: Final = 32

# --- radius ---
RADIUS_XS: Final = 2
RADIUS_SM: Final = 3
RADIUS_MD: Final = 3
RADIUS_LG: Final = 6
RADIUS_PANEL: Final = 10

# --- size ---
SIZE_ROW_COMPACT: Final = 32
SIZE_ROW_COMFORTABLE: Final = 44
SIZE_ART_ROW_COMPACT: Final = 28
SIZE_ART_ROW_COMFORTABLE: Final = 38
SIZE_ART_PLAYER: Final = 56
SIZE_ART_REVIEW: Final = 112
SIZE_WAVE_ROW: Final = 24
SIZE_WAVE_PLAYER: Final = 96
SIZE_WAVE_BAR: Final = 2
SIZE_WAVE_GAP: Final = 1
SIZE_WAVE_BUCKETS: Final = 2000
SIZE_CONTROL_BASE: Final = 28
SIZE_CONTROL_ACTION: Final = 32
SIZE_CONTROL_PRIMARY: Final = 36
SIZE_CONTROL_HEADER: Final = 62
SIZE_CONTROL_TRANSPORT: Final = 64
SIZE_FOCUS_RING: Final = 2

# --- motion ---
MOTION_FAST: Final = 120
MOTION_BASE: Final = 180
MOTION_SLOW: Final = 320
MOTION_EASE: Final = "cubic-bezier(0.2, 0, 0.2, 1)"
MOTION_PLAYHEAD_FPS: Final = 60


def classification_colors(label: str) -> tuple[str, str]:
    """Devolve (bg, text) do chip para 'animada' | 'neutro' | 'lento'."""
    table = {
        "animada": (COLOR_CLASSIFICATION_ANIMADA_BG, COLOR_CLASSIFICATION_ANIMADA_TEXT),
        "neutro": (COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT),
        "lento": (COLOR_CLASSIFICATION_LENTO_BG, COLOR_CLASSIFICATION_LENTO_TEXT),
    }
    return table[label.lower()]


def classification_base(label: str) -> str:
    """Cor cheia da classe para 'animada' | 'neutro' | 'lento'.

    Separada de classification_colors porque o par (bg, text) serve ao
    chip da lista, e o ponto de cor da aba Configuracao precisa do
    matiz cheio -- o bg do chip sobre o fundo do formulario some.
    """
    return {
        "animada": COLOR_CLASSIFICATION_ANIMADA_BASE,
        "neutro": COLOR_CLASSIFICATION_NEUTRO_BASE,
        "lento": COLOR_CLASSIFICATION_LENTO_BASE,
    }[label.lower()]


def camelot_color(number: int) -> str:
    """Cor da posicao 1-12 na roda de Camelot. Levanta fora da faixa."""
    return {
        1: COLOR_CAMELOT_1,
        2: COLOR_CAMELOT_2,
        3: COLOR_CAMELOT_3,
        4: COLOR_CAMELOT_4,
        5: COLOR_CAMELOT_5,
        6: COLOR_CAMELOT_6,
        7: COLOR_CAMELOT_7,
        8: COLOR_CAMELOT_8,
        9: COLOR_CAMELOT_9,
        10: COLOR_CAMELOT_10,
        11: COLOR_CAMELOT_11,
        12: COLOR_CAMELOT_12,
    }[number]
