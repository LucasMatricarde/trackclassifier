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


def test_delegate_de_key_pinta_o_fundo_de_selecao(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.KEY)
    delegate = KeyDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_delegate_de_key_pinta_chips_diferentes_para_keys_diferentes(qapp, tmp_path):
    from dataclasses import replace

    from trackclassifier.keys import Key, Mode
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    modelo.set_rows([replace(linha, key=Key(9, Mode.MINOR))])
    oito_a = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    modelo.set_rows([replace(linha, key=Key(3, Mode.MINOR))])
    dois_a = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    assert oito_a != dois_a


def test_delegate_de_key_sem_key_nao_quebra(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    assert modelo.row_at(0).key is None

    imagem = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    assert not imagem.isNull()


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


def test_busca_encontra_por_titulo_e_por_artista(qapp, tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label
    from trackclassifier.ui.library_tab import LibraryTab

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = _servico(config)
    aba = LibraryTab()
    aba.set_state(library_state(servico))

    aba._busca.setText("glue")
    assert aba._model.rowCount() == 1

    aba._busca.setText("bicep")
    assert aba._model.rowCount() == 1

    # O nome do arquivo continua valendo: e a unica pista de uma track sem tag.
    # "r0_0.1" e nao "r0_": `_servico` grava r0_0.1 / r0_0.5 / r0_0.9, entao o
    # prefixo curto casaria tres linhas e o assert nao provaria nada.
    aba._busca.setText("r0_0.1")
    assert aba._model.rowCount() == 1


def test_delegate_de_titulo_pinta_o_fundo_de_selecao(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.TITULO)
    delegate = TitleDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_delegate_de_titulo_desenha_algo_mesmo_sem_capa(qapp, tmp_path):
    # Sem capa a linha ganha um placeholder, nao um buraco: uma coluna que
    # oscila entre ter e nao ter miniatura desalinha o texto de linha para
    # linha.
    from PySide6.QtGui import QColor, QImage

    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo(tmp_path)
    assert modelo.row_at(0).cover_path is None

    index = modelo.index(0, Column.TITULO)
    pintada = _pinta(TitleDelegate(), index, False)

    vazia = QImage(LARGURA, ALTURA, QImage.Format.Format_ARGB32)
    vazia.fill(QColor("#000000"))
    assert pintada != vazia


def _modelo_com_capa(tmp_path):
    """Modelo cuja PRIMEIRA linha tem capa de verdade em disco.

    O `_modelo` comum produz linhas todas sem capa, e um teste de cache sobre
    elas passaria sem provar nada: `_miniatura` sai antes de tocar no disco
    quando `cover_path` e None, entao o contador ficaria em zero dos dois
    lados da comparacao.
    """
    from mutagen.flac import FLAC, Picture

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "aaa_0.9.flac"  # "aaa" para ordenar primeiro
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Com capa"]
    imagem = Picture()
    imagem.type = 3
    imagem.mime = "image/jpeg"
    # Um jpeg minimo de verdade: o QPixmap precisa conseguir decodificar,
    # senao _miniatura cai no placeholder e o cache nunca e alimentado.
    imagem.data = _jpeg_minimo()
    arquivo.add_picture(imagem)
    arquivo.save()

    servico = _servico(config)
    linhas = sorted(library_state(servico).rows, key=lambda linha: linha.filename)
    assert linhas[0].cover_path is not None, "fixture nao produziu capa"
    return TrackTableModel(linhas)


def _jpeg_minimo() -> bytes:
    """Gera um JPEG 1x1 valido usando o proprio Qt, sem dependencia nova."""
    from PySide6.QtCore import QBuffer, QByteArray

    imagem = QImage(1, 1, QImage.Format.Format_RGB32)
    imagem.fill(QColor("#4CC2E0"))
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "JPG")
    buffer.close()
    return bytes(buffer_bytes)


def test_cache_de_capa_evita_reler_o_disco_a_cada_paint(qapp, tmp_path):
    # Rolar a tabela chama paint() dezenas de vezes por segundo. Sem cache,
    # cada uma abriria o jpeg de novo.
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo_com_capa(tmp_path)
    index = modelo.index(0, Column.TITULO)
    delegate = TitleDelegate()

    _pinta(delegate, index, False)
    assert delegate._leituras == 1, "a primeira pintura tem que ler o disco"

    _pinta(delegate, index, False)
    _pinta(delegate, index, False)

    assert delegate._leituras == 1


def test_delegate_de_titulo_desenha_a_capa_quando_ela_existe(qapp, tmp_path):
    # Prova que o ramo da miniatura e distinto do ramo do placeholder.
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    com_capa = _modelo_com_capa(tmp_path)
    # Diretorio proprio: _config cria as pastas de rotulo dentro do caminho que
    # recebe (e com mkdir() sem parents=True, entao ele precisa ja existir).
    outro = tmp_path / "outro"
    outro.mkdir()
    sem_capa = _modelo(outro)

    pintada_com = _pinta(TitleDelegate(), com_capa.index(0, Column.TITULO), False)
    pintada_sem = _pinta(TitleDelegate(), sem_capa.index(0, Column.TITULO), False)

    assert pintada_com != pintada_sem


def test_delegate_da_onda_usa_rgb_quando_ha_buckets(qapp, tmp_path):
    # Prova que o ramo RGB e distinto do mono: as duas imagens da MESMA
    # track precisam diferir quando so o peaks_path muda.
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    caminho = tmp_path / f"{linha.sha1}.npy"
    bandas = np.zeros((64, 3), dtype=np.float16)
    bandas[:, 0] = 1.0  # grave puro: bem diferente do accent do render mono
    np.save(caminho, bandas)

    modelo.set_rows([replace(linha, peaks_path=str(caminho))])
    com_rgb = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    modelo.set_rows([replace(linha, peaks_path=None)])
    com_mono = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    assert com_rgb != com_mono


def test_delegate_da_onda_cai_no_mono_com_npy_corrompido(qapp, tmp_path):
    # O paint() nao pode levantar por causa de um arquivo truncado.
    from dataclasses import replace

    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    caminho = tmp_path / f"{linha.sha1}.npy"
    caminho.write_bytes(b"isto nao e um npy")
    modelo.set_rows([replace(linha, peaks_path=str(caminho))])

    imagem = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    assert not imagem.isNull()


def test_delegate_pede_computo_de_quem_nao_tem_buckets(qapp, tmp_path):
    # E o gatilho preguicoso: pintar uma linha sem buckets enfileira o
    # computo, e a mesma linha nao pode pedir duas vezes.
    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    delegate = WaveformDelegate()
    pedidos = []
    delegate.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    index = modelo.index(0, Column.WAVEFORM)
    _pinta(delegate, index, False)
    _pinta(delegate, index, False)

    assert pedidos == [modelo.row_at(0).sha1]
