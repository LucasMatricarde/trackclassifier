import pytest

from trackclassifier.ui.colors import tinta
from trackclassifier.ui.tokens import COLOR_STATE_DANGER


def test_tinta_deriva_rgba_do_token():
    assert tinta(COLOR_STATE_DANGER, 0.12) == "rgba(240,87,92,0.12)"


def test_tinta_com_alfa_cheio_mantem_a_cor_visivel():
    assert tinta(COLOR_STATE_DANGER, 1.0) == "rgba(240,87,92,1.0)"


def test_tinta_recusa_alfa_fora_da_faixa():
    with pytest.raises(ValueError):
        tinta(COLOR_STATE_DANGER, 1.4)


def test_tinta_recusa_cor_que_nao_e_hex_de_seis_digitos():
    # rgba(...) entra como cor em varios tokens de borda. Passar um deles
    # aqui e erro de chamada, nao caso a tratar -- e o mais provavel.
    with pytest.raises(ValueError):
        tinta("rgba(255,255,255,0.05)", 0.5)
