"""O chip de tonalidade. Roda com QT_QPA_PLATFORM=offscreen (conftest)."""

from trackclassifier.keys import Key, KeyNotation, Mode
from trackclassifier.ui.widgets.key_chip import KeyChip


def test_chip_mostra_camelot_por_padrao(qapp):
    chip = KeyChip()
    chip.set_key(Key(9, Mode.MINOR))

    assert chip.text() == "8A"


def test_chip_troca_para_notacao_classica(qapp):
    chip = KeyChip()
    chip.set_key(Key(9, Mode.MINOR))
    chip.set_notation(KeyNotation.CLASSIC)

    assert chip.text() == "Am"


def test_chip_sem_key_mostra_travessao(qapp):
    chip = KeyChip()
    chip.set_key(None)

    assert chip.text() == "—"


def test_trocar_notacao_sem_key_nao_quebra(qapp):
    chip = KeyChip()
    chip.set_notation(KeyNotation.CLASSIC)

    assert chip.text() == "—"


def test_chip_pinta_cores_diferentes_para_posicoes_diferentes_da_roda(qapp):
    # A cor E a informacao: duas keys distantes na roda nao podem sair iguais.
    oito_a = KeyChip()
    oito_a.set_key(Key(9, Mode.MINOR))  # 8A
    dois_a = KeyChip()
    dois_a.set_key(Key(3, Mode.MINOR))  # 2A

    assert oito_a.grab().toImage() != dois_a.grab().toImage()
