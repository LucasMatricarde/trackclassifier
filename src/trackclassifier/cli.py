import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .labels import LABEL_ORDER
from .model import NotEnoughClassesError
from .service import TrackService


def _empacotado() -> bool:
    """True quando rodando de dentro do .app gerado pelo PyInstaller.

    PyInstaller define sys.frozen=True no executavel gerado -- e o unico
    jeito confiavel de saber que nao ha terminal nem cwd previsivel por tras
    (clique duplo no Finder), diferente de rodar `uv run dj ...`.
    """
    return bool(getattr(sys, "frozen", False))


def _caminho_config_padrao() -> Path:
    # Empacotado: cwd nao tem sentido (Finder pode abrir de qualquer lugar).
    # Fora do pacote, mantem o comportamento de sempre (relativo ao cwd de
    # quem chamou `dj`).
    if _empacotado():
        return Path.home() / ".trackclassifier" / "config.toml"
    return Path("config.toml")


def _imprime_progresso(concluidas: int, total: int, nome: str) -> None:
    print(f"[{concluidas}/{total}] {nome}")


def _servico(caminho_config: str) -> TrackService:
    # So chamada por scan/train -- review nao passa mais por aqui (ver
    # main()), entao nao precisa de um parametro pra pular o analyze_all.
    config = load_config(Path(caminho_config))
    servico = TrackService(config)
    servico.analyze_all(on_progress=_imprime_progresso)
    return servico


def _imprime_metricas(metricas) -> None:
    print(f"Exemplos rotulados: {metricas.n_examples}")
    print(f"Acuracia (leave-one-out): {metricas.accuracy * 100:.1f}%")
    print(f"Erro ordinal medio: {metricas.ordinal_mae:.3f}")
    print("Matriz de confusao (linha = real, coluna = previsto):")
    cabecalho = "        " + "".join(f"{rotulo.value:>8}" for rotulo in LABEL_ORDER)
    print(cabecalho)
    for rotulo, linha in zip(LABEL_ORDER, metricas.confusion, strict=True):
        print(f"{rotulo.value:>8}" + "".join(f"{valor:>8}" for valor in linha))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if _empacotado() and not argv:
        # Clique duplo no .app chama o executavel sem argumentos -- sem
        # isso o argparse abaixo exigiria um subcomando que ninguem digitou
        # e sairia com erro antes de a janela sequer abrir.
        argv = ["review"]

    parser = argparse.ArgumentParser(prog="dj", description="Classificador de tracks por energia")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    caminho_padrao = str(_caminho_config_padrao())
    for nome, ajuda in (
        ("scan", "Extrai features das tracks ainda nao analisadas"),
        ("train", "Retreina o modelo e imprime as metricas"),
        ("review", "Abre a janela de revisao"),
    ):
        sub = subcomandos.add_parser(nome, help=ajuda)
        sub.add_argument("--config", default=caminho_padrao, help="Caminho do config.toml")
    argumentos = parser.parse_args(argv)

    if argumentos.comando == "review":
        # A janela faz o proprio scan (ver Task 9 da fase 1): construir um
        # TrackService aqui so pra descartar seria reler o parquet inteiro e
        # desempacotar o model.joblib duas vezes -- ui/__main__.py monta o
        # seu proprio.
        #
        # O try/except de ConfigError saiu junto com _prepara_config_padrao:
        # config ausente ou invalido agora abre o FirstRunDialog dentro de
        # ui.__main__, que e o unico lugar com QApplication vivo para exibir
        # qualquer coisa. Copiar o config.example.toml para o home era pior
        # que nao copiar -- transformava "nao tem config" em "config
        # apontando para /Users/SEU_USUARIO", que e justamente a condicao que
        # dispara o dialogo, escondida atras de um arquivo que existe.
        print("Abrindo a janela de revisao...")
        from .ui.__main__ import main as abre_janela

        return abre_janela(str(Path(argumentos.config)))

    try:
        servico = _servico(argumentos.config)
    except ConfigError as erro:
        print(f"Erro de configuracao: {erro}", file=sys.stderr)
        return 1

    falhas = servico.failures()
    if falhas:
        print(f"{len(falhas)} arquivo(s) falharam na analise:", file=sys.stderr)
        for falha in falhas:
            print(f"  {falha.filename}: {falha.reason}", file=sys.stderr)

    if argumentos.comando == "scan":
        print(f"{len(servico.cache)} track(s) analisadas no total.")
        return 0

    try:
        _imprime_metricas(servico.train())
    except NotEnoughClassesError as erro:
        print(str(erro), file=sys.stderr)
        return 1
    return 0
