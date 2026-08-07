"""StatusStrip: resumo permanente do acervo, rodape esquerdo da janela."""

from trackclassifier.ui.tokens import COLOR_STATE_SUCCESS, COLOR_STATE_WARNING
from trackclassifier.ui.widgets.status_strip import StatusStrip


def test_resumo_mostra_os_tres_numeros(qapp):
    faixa = StatusStrip()

    faixa.mostra_resumo(tracks=354, analisadas=341, pendentes=13)

    texto = faixa._texto.text()
    assert "354" in texto
    assert "341" in texto
    assert "13" in texto


def test_resumo_pinta_o_ponto_de_sucesso(qapp):
    faixa = StatusStrip()

    faixa.mostra_resumo(tracks=1, analisadas=1, pendentes=0)

    assert faixa._ponto._cor.name() == _hex(COLOR_STATE_SUCCESS)


def test_scan_em_andamento_pinta_o_ponto_de_aviso(qapp):
    """Cor de aviso: o resumo de repouso ainda nao vale enquanto escaneia."""
    faixa = StatusStrip()
    faixa.mostra_resumo(tracks=1, analisadas=1, pendentes=0)

    faixa.mostra_scan(concluidas=5, total=20, nome="track.wav")

    assert faixa._ponto._cor.name() == _hex(COLOR_STATE_WARNING)
    assert "5" in faixa._texto.text()
    assert "20" in faixa._texto.text()
    assert "track.wav" in faixa._texto.text()


def _hex(token: str) -> str:
    """QColor.name() sempre devolve minusculo -- normaliza o token do
    design system (maiusculo) para comparar."""
    return token.lower()
