"""Aba Modelo: metricas, retreino e a lista de falhas de analise."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .viewmodel import LABELS_EM_ORDEM, ModelState


class ModelTab(QWidget):
    train_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._metricas = QLabel("Modelo ainda nao treinado.")
        self._confusao = QLabel("")
        self._confusao.setObjectName("Numeric")
        self._falhas = QListWidget()

        botao = QPushButton("Retreinar")
        botao.setProperty("variant", "primary")
        botao.clicked.connect(self.train_requested)

        rotulo_falhas = QLabel("Falhas de analise")
        rotulo_falhas.setObjectName("SectionLabel")

        layout = QVBoxLayout(self)
        layout.addWidget(self._metricas)
        layout.addWidget(self._confusao)
        layout.addWidget(botao)
        layout.addWidget(rotulo_falhas)
        layout.addWidget(self._falhas, 1)

    def set_state(self, state: ModelState) -> None:
        if state.accuracy is None:
            self._metricas.setText("Modelo ainda nao treinado.")
            self._confusao.setText("")
        else:
            self._metricas.setText(
                f"Exemplos rotulados: {state.n_examples}\n"
                f"Acuracia (leave-one-out): {state.accuracy * 100:.1f}%\n"
                f"Erro ordinal medio: {state.ordinal_mae:.3f}"
            )
            cabecalho = "        " + "".join(f"{r:>8}" for r in LABELS_EM_ORDEM)
            linhas = [
                f"{rotulo:>8}" + "".join(f"{valor:>8}" for valor in linha)
                for rotulo, linha in zip(LABELS_EM_ORDEM, state.confusion, strict=True)
            ]
            self._confusao.setText(
                "Matriz de confusao (linha = real, coluna = previsto):\n"
                + "\n".join([cabecalho, *linhas])
            )

        self._falhas.clear()
        for nome, motivo in state.failures:
            self._falhas.addItem(f"{nome}: {motivo}")
