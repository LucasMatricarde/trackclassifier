"""font.tracking e font.case aplicados em codigo, porque o QSS nao os tem.

A lista de propriedades do Qt Style Sheets nao inclui `letter-spacing` nem
`text-transform`. Gerar as duas familias no app.qss deixaria o arquivo com
duas propriedades que o Qt descarta em silencio -- o mesmo defeito que a
propria v0.2 aponta em `motion.*` ("cinco tokens que mentem sobre existir").

Entao o tracking vira QFont.setLetterSpacing e a caixa alta vira `.upper()`
no texto do widget. Os tokens continuam sendo a fonte: quem chama passa
FONT_TRACKING_* e le FONT_CASE_LABEL, nunca um numero solto.

Ordem importa: a folha de estilo tem precedencia sobre setFont() para as
propriedades que ela declara (familia, tamanho, peso), mas letterSpacing nao
e uma delas -- o Qt monta a fonte final a partir da fonte do widget e sobre
ela aplica o que o QSS especifica. Por isso os dois convivem.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget

from .tokens import FONT_CASE_LABEL, FONT_TRACKING_WIDEST


def _percentual(tracking: str) -> float:
    """'0.09em' -> 109.0. O 100 do Qt e o espacamento natural da fonte."""
    return 100.0 + float(tracking.removesuffix("em")) * 100.0


def aplica_tracking(widget: QWidget, tracking: str = FONT_TRACKING_WIDEST) -> None:
    fonte = widget.font()
    fonte.setLetterSpacing(QFont.SpacingType.PercentageSpacing, _percentual(tracking))
    widget.setFont(fonte)


def texto_de_label(texto: str) -> str:
    """Aplica font.case.label. Le o token em vez de chamar .upper() direto.

    Caixa alta e decisao de sistema: se um dia `label` deixar de ser
    uppercase no JSON, esta funcao muda o app inteiro de uma vez.
    """
    return texto.upper() if FONT_CASE_LABEL == "uppercase" else texto


def estiliza_label(widget: QWidget, texto: str, tracking: str = FONT_TRACKING_WIDEST) -> None:
    """Caixa alta mais tracking: o par que os dois tokens sempre andam junto.

    `font.case.label` no JSON diz "SEMPRE com tracking.widest" -- ter uma
    funcao so evita que metade das chamadas esqueca uma das duas metades.
    """
    widget.setText(texto_de_label(texto))
    aplica_tracking(widget, tracking)


def primeira_familia(familia: str) -> str:
    """'SF Mono, Menlo, monospace' -> 'SF Mono'.

    O token guarda a lista de fallback inteira (formato CSS), mas QFont quer
    uma familia por vez -- ele proprio tem o proprio mecanismo de fallback
    via QFontDatabase, e passar a string toda faria o Qt procurar (sem achar)
    uma fonte chamada literalmente "SF Mono, Menlo, monospace".
    """
    return familia.split(",")[0]


def fonte_de_token(familia: str, tamanho: str) -> QFont:
    """QFont a partir de um par de tokens (familia CSS + tamanho em px).

    Repetido tres vezes no codigo antes de virar funcao (duas em
    track_model.py, uma em delegates.py, cada uma reparseando a mesma
    string) -- um so lugar para consertar se o formato do tamanho mudar.
    """
    fonte = QFont(primeira_familia(familia))
    fonte.setPixelSize(int(tamanho.removesuffix("px")))
    return fonte


def repolir(widget: QWidget) -> None:
    """Forca o Qt a reavaliar seletores de QSS que dependem de setProperty().

    O Qt Style Sheets so re-testa um seletor como `[state="invalid"]` num
    unpolish/polish explicito -- setProperty() sozinho muda o valor mas
    deixa o widget pintado com o estilo antigo ate o proximo evento que
    force um repaint completo (o que pode nunca acontecer, dependendo do
    widget). Compartilhado porque qualquer widget com estado dirigido por
    propriedade dinamica (campo invalido, chip de contagem, ponto de
    status) precisa do mesmo par de chamadas depois de cada setProperty().
    """
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
