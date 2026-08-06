"""Ponto de entrada da janela. Carrega o QSS gerado e sobe o QApplication."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ..config import load_config
from ..service import TrackService
from .window import MainWindow

QSS = Path(__file__).parent / "app.qss"


def main(config_path: str = "config.toml") -> int:
    config = load_config(Path(config_path))
    service = TrackService(config)

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))

    janela = MainWindow(service)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
