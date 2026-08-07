"""font.tracking, font.case e QFont-a-partir-de-token aplicados em codigo.

primeira_familia/fonte_de_token existem porque o mesmo idioma
(`familia.split(",")[0]` + tamanho em px) aparecia repetido em
track_model.py (duas vezes) e delegates.py (uma vez) -- achado do code
review da biblioteca 3a.
"""

from trackclassifier.ui.typography import fonte_de_token, primeira_familia


def test_primeira_familia_corta_na_primeira_virgula():
    assert primeira_familia("JetBrains Mono, SF Mono, Consolas, monospace") == "JetBrains Mono"


def test_primeira_familia_sem_virgula_devolve_a_string_inteira():
    assert primeira_familia("Arial") == "Arial"


def test_fonte_de_token_usa_a_primeira_familia_e_o_tamanho_em_px(qapp):
    fonte = fonte_de_token("JetBrains Mono, SF Mono, monospace", "11px")

    assert fonte.family() == "JetBrains Mono"
    assert fonte.pixelSize() == 11
