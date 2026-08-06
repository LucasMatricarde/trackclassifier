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


def _prepara_config_padrao(caminho: Path) -> None:
    """So roda quando empacotado. Sem terminal visivel, um ConfigError
    lancado no stderr nunca chegaria ao usuario -- copiar o exemplo embutido
    no .app pro local padrao na primeira execucao e a unica forma pratica
    dele conseguir editar os caminhos e reabrir o app.
    """
    if caminho.exists():
        return
    origem = Path(getattr(sys, "_MEIPASS", "")) / "config.example.toml"
    if not origem.is_file():
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(origem.read_text(encoding="utf-8"), encoding="utf-8")


def _mostra_erro_grafico(titulo: str, mensagem: str) -> None:
    # So chamado quando empacotado (ver main()): sem isso o erro de
    # configuracao ficaria so no stderr, que ninguem ve num app de clique
    # duplo sem terminal.
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(None, titulo, mensagem)
    del app


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
        # A janela faz o proprio scan (ver Task 9): construir um TrackService
        # aqui so pra descartar seria reler o parquet inteiro e desempacotar
        # o model.joblib duas vezes -- ui/__main__.py monta o seu proprio.
        # O try/except continua aqui (nao dentro de _servico) porque e
        # ui.__main__.main que agora chama load_config, e ele pode levantar
        # o mesmo ConfigError.
        print("Abrindo a janela de revisao...")
        from .ui.__main__ import main as abre_janela

        caminho_config = Path(argumentos.config)
        if _empacotado():
            _prepara_config_padrao(caminho_config)

        try:
            return abre_janela(str(caminho_config))
        except ConfigError as erro:
            print(f"Erro de configuracao: {erro}", file=sys.stderr)
            if _empacotado():
                _mostra_erro_grafico(
                    "Track classifier",
                    f"{erro}\n\nEdite {caminho_config} e abra o app de novo.",
                )
            return 1

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
