"""Ponto de entrada da janela. Carrega o QSS gerado e sobe o QApplication."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from ..config import Config, ConfigError, load_config
from ..service import TrackService
from .first_run import FirstRunDialog
from .fonts import registra_fontes
from .window import MainWindow

QSS = Path(__file__).parent / "app.qss"


def _tenta_carregar(caminho: Path) -> Config | None:
    """None quando nao da para usar -- ausente, ilegivel ou pasta sumida.

    Nao distingue os casos de proposito: os tres levam ao mesmo lugar, o
    dialogo, que se preenche sozinho com o que houver de aproveitavel.
    """
    try:
        return load_config(caminho)
    except ConfigError:
        return None


def main(config_path: str = "config.toml") -> int:
    caminho = Path(config_path)

    # QApplication PRECISA existir antes do dialogo. Ate a fase anterior o
    # load_config rodava aqui em cima e um ConfigError abortava o programa
    # antes de haver Qt -- por isso o erro so podia virar texto no stderr.
    app = QApplication(sys.argv)
    # Antes do QSS: a folha nomeia "Space Grotesk" e "JetBrains Mono" na
    # frente da pilha de fallback, e o Qt resolve a familia no momento em
    # que aplica o estilo. Depois do QApplication porque
    # addApplicationFont devolve -1 em silencio sem um QGuiApplication.
    registra_fontes()
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))

    config = _tenta_carregar(caminho)
    if config is None:
        dialogo = FirstRunDialog(caminho)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            # Cancelar fecha o app sem gravar nada. Sai com 0: desistir da
            # configuracao nao e falha do programa.
            return 0
        config = dialogo.config
        assert config is not None  # accept() so acontece com config carregado

    janela = MainWindow(TrackService(config), config_path=caminho)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
