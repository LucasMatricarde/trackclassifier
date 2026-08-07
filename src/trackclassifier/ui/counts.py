"""Contagem barata de arquivos por pasta, para o chip da aba Configuracao.

O chip responde a pergunta que reler o caminho nao responde: "essa pasta e
mesmo a que eu acho que e?". Um numero ancora o campo.

**Nao reutiliza library.scan_labeled nem nada que calcule SHA1.** Aquilo le
o arquivo inteiro para identificar a track; aqui basta o nome. A diferenca e
de ordens de grandeza, e isto roda a cada caminho digitado.

Modulo puro (sem Qt) de proposito: quem o executa fora da thread da GUI e
counts_worker.py, e assim a regra de formatacao continua testavel sem
QApplication.
"""

from pathlib import Path

from ..audio_io import SUPPORTED_SUFFIXES

#: Chip quando o caminho nao aponta para uma pasta existente.
NAO_ENCONTRADA = "NÃO ENCONTRADA"

_UM_MB = 1024 * 1024


def conta_tracks(caminho: str) -> int | None:
    """Quantos arquivos de audio na pasta. None se ela nao existe.

    Sem recursao: as pastas de destino sao planas por construcao (apply move
    o arquivo para a raiz da pasta), e descer a arvore inteira de um acervo
    grande a cada tecla digitada seria justamente o custo que este modulo
    existe para evitar.
    """
    pasta = Path(caminho).expanduser()
    try:
        entradas = list(pasta.iterdir())
    except OSError:
        # Pasta inexistente, caminho que e arquivo, permissao negada: os tres
        # dao no mesmo para a tela -- nao ha numero para mostrar.
        return None
    return sum(1 for item in entradas if item.suffix.lower() in SUPPORTED_SUFFIXES)


def resumo_do_data_dir(caminho: str) -> tuple[int, int] | None:
    """(analises no parquet, bytes em disco). None se a pasta nao existe.

    A contagem de analises vem dos METADADOS do parquet, nao de um
    read_parquet: o arquivo tem uma coluna de vetor de features por track e
    carrega-lo inteiro para descobrir o numero de linhas custaria mais que
    todo o resto desta tela junto.
    """
    pasta = Path(caminho).expanduser()
    if not pasta.is_dir():
        return None

    bytes_totais = 0
    for item in pasta.rglob("*"):
        try:
            if item.is_file():
                bytes_totais += item.stat().st_size
        except OSError:
            # Arquivo removido entre o rglob e o stat (um scan concorrente
            # regravando o parquet, por exemplo). Ignorar um arquivo e
            # melhor que perder o total.
            continue

    return _linhas_do_parquet(pasta / "analyses.parquet"), bytes_totais


def _linhas_do_parquet(caminho: Path) -> int:
    try:
        import pyarrow.parquet as pq

        return pq.ParquetFile(caminho).metadata.num_rows
    except Exception:
        # Parquet ausente (data_dir novo) ou corrompido -- o resto da app
        # trata parquet ilegivel como cache vazio, e aqui nao seria
        # diferente. Zero analises e a resposta honesta.
        return 0


def texto_do_chip(chave: str, caminho: str) -> str:
    """Texto pronto do chip, ja no vocabulario de cada campo.

    Vazio quando nao ha o que dizer (campo em branco): o chip some, em vez
    de virar "0" para um caminho que o usuario nem terminou de digitar.
    """
    if not caminho.strip():
        return ""

    if chave == "data_dir":
        resumo = resumo_do_data_dir(caminho)
        if resumo is None:
            return NAO_ENCONTRADA
        analises, bytes_totais = resumo
        return f"{analises} ANÁLISES · {bytes_totais / _UM_MB:.0f} MB"

    total = conta_tracks(caminho)
    if total is None:
        return NAO_ENCONTRADA
    return f"{total} NOVAS" if chave == "inbox" else f"{total} TRACKS"


def contagens(caminhos: dict[str, str]) -> dict[str, str]:
    """{chave: caminho} -> {chave: texto do chip}, uma passada."""
    return {chave: texto_do_chip(chave, caminho) for chave, caminho in caminhos.items()}
