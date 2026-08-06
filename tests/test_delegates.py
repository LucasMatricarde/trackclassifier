"""Os delegates pintam a celula inteira, entao precisam pintar o fundo tambem.

Um paint() sobrescrito que nunca chama a base perde selecao, hover e linha
alternada -- e como Onda e Classificacao sao pintadas assim, a linha
selecionada some sob elas. O teste compara os pixels de uma mesma celula
pintada selecionada e nao selecionada: se o fundo nao for desenhado, as duas
imagens saem identicas.
"""

from dataclasses import replace

import numpy as np
import soundfile as sf
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from tests.test_viewmodel import ExtratorFalso, _config, _servico
from trackclassifier.labels import Label
from trackclassifier.service import TrackService
from trackclassifier.ui.viewmodel import library_state
from trackclassifier.ui.widgets.delegates import ClassificationDelegate, WaveformDelegate
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel

LARGURA = 150
ALTURA = 46


def _pinta(delegate, index, selecionado: bool) -> QImage:
    imagem = QImage(LARGURA, ALTURA, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#000000"))

    opcao = QStyleOptionViewItem()
    opcao.rect = QRect(0, 0, LARGURA, ALTURA)
    opcao.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
    if selecionado:
        opcao.state |= QStyle.StateFlag.State_Selected

    painter = QPainter(imagem)
    delegate.paint(painter, opcao, index)
    painter.end()
    return imagem


def _modelo(tmp_path) -> TrackTableModel:
    servico = _servico(_config(tmp_path))
    return TrackTableModel(list(library_state(servico).rows))


def test_delegate_da_onda_pinta_o_fundo_de_selecao(qapp, tmp_path):
    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.WAVEFORM)
    delegate = WaveformDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_delegate_de_classificacao_pinta_o_fundo_de_selecao(qapp, tmp_path):
    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.CLASSIFICACAO)
    delegate = ClassificationDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_fundo_e_pintado_mesmo_sem_conteudo_para_desenhar(qapp, tmp_path):
    """Linha sem rotulo nem palpite: o chip nao aparece, o fundo sim.

    Os delegates saiam por `return` antes de qualquer desenho quando nao
    havia o que pintar -- o que apagava a selecao justamente nas linhas sem
    dado.
    """
    modelo = _modelo(tmp_path)
    sem_rotulo = replace(modelo.row_at(0), label=None, predicted=None)
    modelo.set_rows([sem_rotulo])
    index = modelo.index(0, Column.CLASSIFICACAO)
    delegate = ClassificationDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def _servico_com_bpms_distintos(tmp_path):
    """Servico onde as 9 tracks rotuladas tem BPM diferente entre si.

    O `_servico` compartilhado grava np.zeros(100) em todas: identidade e o
    sha1 do CONTEUDO, entao as 9 colidem numa unica entrada de cache e saem
    todas com o mesmo BPM -- qualquer assert de ordenacao vira tautologia.
    Aqui cada arquivo recebe amplitude propria (dentro de [-1, 1], senao o
    PCM16 satura e colide de novo) e nome com energia propria, que e de onde
    ExtratorFalso tira o BPM.
    """
    config = _config(tmp_path)
    for grupo, (rotulo, base) in enumerate(
        ((Label.UP, 0.9), (Label.NEUTRAL, 0.5), (Label.DOWN, 0.1))
    ):
        for i in range(3):
            sinal = np.full(100, (grupo * 3 + i + 1) / 20.0, dtype=np.float32)
            sf.write(config.folders[rotulo] / f"r{i}_{base + i / 100:.2f}.wav", sinal, 22050)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    return servico


def test_ordenacao_da_tabela_sobrevive_ao_filtro(qapp, tmp_path):
    """setSortingEnabled nao reordena sozinho depois de um reset de modelo.

    O indicador do cabecalho continua apontando para a coluna escolhida, mas
    as linhas voltam para a ordem de insercao -- o usuario ordena por BPM,
    digita na busca e a tabela embaralha sem o indicador mudar.
    """
    from trackclassifier.ui.library_tab import LibraryTab

    servico = _servico_com_bpms_distintos(tmp_path)
    aba = LibraryTab()
    aba.set_state(library_state(servico))

    bpms_naturais = [aba._model.row_at(i).bpm for i in range(aba._model.rowCount())]
    assert bpms_naturais != sorted(bpms_naturais, reverse=True)  # senao nao prova nada

    aba._table.sortByColumn(Column.BPM, Qt.SortOrder.DescendingOrder)
    aba._busca.setText("r")  # bate em todas as 9 tracks: so o reset importa

    bpms = [aba._model.row_at(i).bpm for i in range(aba._model.rowCount())]
    assert bpms == sorted(bpms, reverse=True)
