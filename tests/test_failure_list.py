from trackclassifier.ui.widgets.failure_list import FailureList, agrupa

FALHAS = (
    ("promo_04.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("set_rip_b.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    ("rip_side_a.flac", "Falha ao decodificar rip_side_a.flac: x", "falha ao decodificar"),
)


def test_agrupa_por_categoria_e_nao_por_razao():
    grupos = agrupa(FALHAS)

    # As razoes de decode diferem (trazem o nome do arquivo e o stderr);
    # a categoria e a mesma. Sem isso, dez arquivos viram dez grupos.
    assert [categoria for categoria, _ in grupos] == [
        "ffmpeg nao encontrado",
        "falha ao decodificar",
    ]


def test_grupo_maior_vem_primeiro():
    grupos = agrupa(FALHAS)

    assert len(grupos[0][1]) == 2


def test_agrupa_dez_do_mesmo_tipo_em_um_grupo():
    dez = tuple(
        (f"arq_{i}.m4a", f"Falha ao decodificar arq_{i}.m4a: x", "falha ao decodificar")
        for i in range(10)
    )

    grupos = agrupa(dez)

    assert len(grupos) == 1
    assert len(grupos[0][1]) == 10


def test_sem_falhas_esconde_a_secao(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)
    lista.set_failures(())

    # Secao some inteira. Nao mostrar lista vazia com "nenhuma falha".
    assert lista.isHidden()


def test_cabecalho_conta_arquivos_e_motivos(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)

    assert lista.resumo.text() == "3 ARQUIVOS · 2 MOTIVOS"


def test_badge_mostra_a_contagem_do_grupo(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)

    assert lista.badge(0).text() == "2"


def test_lista_de_arquivos_resume_depois_de_cinco(qapp):
    sete = tuple(
        (f"arq_{i}.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado") for i in range(7)
    )

    lista = FailureList()
    lista.set_failures(sete)

    assert lista.arquivos(0).text().endswith("· +2")


def test_lista_curta_nao_ganha_sufixo(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)

    assert "+" not in lista.arquivos(0).text()


def test_trocar_de_conjunto_nao_acumula_cards(qapp):
    lista = FailureList()
    lista.set_failures(FALHAS)
    lista.set_failures(FALHAS[:1])

    # set_failures roda a cada atualizacao de estado da aba: sem limpar,
    # os cards antigos empilhariam a cada scan.
    assert lista.total_de_grupos() == 1
