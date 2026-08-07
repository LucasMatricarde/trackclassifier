"""As fontes do mockup viajam com o app.

Space Grotesk e JetBrains Mono estao em primeiro na pilha de
`font.family.*` dos tokens, com fallback para Inter e SF Mono. O fallback
funciona -- o app nao quebra sem elas -- mas a tela nao se parece com o
mockup, e o CI nunca teria as fontes instaladas. Ambas sao OFL, entao
redistribuir dentro do repo e permitido desde que a licenca va junto (os
dois OFL-*.txt ao lado dos TTF, com teste que falha se sumirem).

QFontDatabase.addApplicationFont exige um QGuiApplication vivo: chamar
antes do QApplication devolve -1 para todos os arquivos, em silencio.
"""

from pathlib import Path

from PySide6.QtGui import QFontDatabase

DIRETORIO = Path(__file__).parent / "fonts"

#: Cache do resultado. Registrar o mesmo arquivo duas vezes devolve um id
#: novo e duplica a familia na lista do Qt; os testes sobem a UI varias
#: vezes na mesma QApplication de sessao e cairiam nisso.
_registradas: list[str] | None = None


def registra_fontes() -> list[str]:
    """Carrega os TTF e devolve as familias registradas, sem repetir.

    Lista vazia quando a pasta sumiu ou nenhum arquivo foi aceito: o app
    sobe assim mesmo, no fallback. Uma instalacao quebrada nao pode
    impedir o usuario de classificar.
    """
    global _registradas
    if _registradas is not None:
        return _registradas

    familias: list[str] = []
    for arquivo in sorted(DIRETORIO.glob("*.ttf")):
        identificador = QFontDatabase.addApplicationFont(str(arquivo))
        if identificador == -1:
            # Arquivo corrompido ou formato recusado. Nao e motivo para
            # derrubar o app -- as outras tres podem ter entrado.
            continue
        for familia in QFontDatabase.applicationFontFamilies(identificador):
            if familia not in familias:
                familias.append(familia)

    _registradas = familias
    return familias
