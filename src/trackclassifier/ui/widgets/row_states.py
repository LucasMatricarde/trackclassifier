"""Estado visual de uma linha da tabela, derivado num lugar so.

Quatro delegates pintam a mesma linha e todos precisam da mesma resposta:
esta track tem analise? esta tocando? falhou? Cada um derivando por conta
propria e como quatro definicoes de "pendente" divergem -- e o sintoma
aparece como uma linha com a onda em caixa vazia mas o BPM preenchido.

Sem Qt: a regra e sobre o dado, nao sobre a pintura.
"""

from enum import StrEnum

from ..viewmodel import TrackRow


class EstadoDaLinha(StrEnum):
    NORMAL = "normal"
    #: Ainda nao analisada. Onda vira caixa vazia; bpm, key e classe viram
    #: travessao. Estado de linha, nao de dialogo: o layout nao pula
    #: quando a analise chega.
    PENDENTE = "pendente"
    #: Analise tentada e falhada. Titulo apagado, motivo no lugar da onda.
    FALHOU = "falhou"
    TOCANDO = "tocando"


def estado_da_linha(
    row: TrackRow, *, sha1_tocando: str | None, motivo_da_falha: str | None
) -> EstadoDaLinha:
    """Precedencia: FALHOU > TOCANDO > PENDENTE > NORMAL.

    FALHOU vem primeiro porque e o mais especifico: uma track que falhou
    tambem parece pendente (nao tem bpm nem curva), e mostrar "pendente"
    deixaria o usuario esperando por uma analise que ja aconteceu e nao
    deu. TOCANDO vem antes de PENDENTE so por completude -- nao da para
    tocar o que nao decodifica, entao os dois juntos sao bug em outro
    lugar, e esconder a falha atrasaria a descoberta.
    """
    if motivo_da_falha is not None:
        return EstadoDaLinha.FALHOU
    if sha1_tocando is not None and sha1_tocando == row.sha1:
        return EstadoDaLinha.TOCANDO
    # bpm 0 e o que uma analise interrompida deixa; a curva sozinha vem do
    # render mono e nao prova que a extracao terminou. Exigir os dois e o
    # que evita uma linha meio preenchida.
    if not row.bpm or not row.energy_curve:
        return EstadoDaLinha.PENDENTE
    return EstadoDaLinha.NORMAL
