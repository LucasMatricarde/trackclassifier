import argparse
import signal
import sys
import threading
from pathlib import Path

from .config import ConfigError, load_config
from .labels import LABEL_ORDER
from .model import NotEnoughClassesError
from .service import KeyBatchReport, TrackService


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
    # So chamada por scan/train -- serve monta o proprio servico (ver main()),
    # entao nao precisa de um parametro pra pular o analyze_all.
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


def _imprime_relatorio_de_keys(relatorio: KeyBatchReport) -> None:
    if relatorio.calibrar:
        _imprime_calibracao(relatorio)
        return
    print(
        f"Tonalidade pelo audio: {relatorio.detected} detectada(s), "
        f"{relatorio.none} sem resultado, {relatorio.skipped} pulada(s) "
        f"(ja tinham key, ja tentadas ou sem registro)."
    )
    if relatorio.cancelled:
        restantes = relatorio.total - relatorio.detected - relatorio.none
        print(
            f"Cancelado: o parcial foi salvo e {restantes} track(s) seguem pendentes. "
            "Rode `dj keys` de novo para continuar."
        )


def _imprime_calibracao(relatorio: KeyBatchReport) -> None:
    """Tabela da estimativa pelo audio contra as tags. Nada foi gravado."""
    print("Calibracao da tonalidade (nada foi gravado)")
    print(f"  Tracks com tag de key:     {relatorio.com_tag}")
    tentadas = relatorio.detected + relatorio.none
    if tentadas == 0:
        print("  Nenhuma track comparada.")
        return
    sufixo = " (cancelado)" if relatorio.cancelled else ""
    print(f"  Comparadas contra a tag:   {tentadas}{sufixo}")
    print(f"  Sem resultado (none):      {relatorio.none:>5}  {relatorio.taxa_none * 100:5.1f}%")
    print(
        f"  Acerto exato:              {relatorio.acerto_exato:>5}  "
        f"{relatorio.taxa_acerto_exato * 100:5.1f}%"
    )
    print(
        f"  Acerto vizinho:            {relatorio.acerto_vizinho:>5}  "
        f"{relatorio.taxa_acerto_vizinho * 100:5.1f}%"
    )
    print("  (vizinho = exato, relativa maior/menor ou +-1 na roda de Camelot;")
    print("   percentuais sobre as comparadas, contando 'none' como erro)")


def _executa_keys(servico: TrackService, calibrar: bool) -> int:
    """Roda o lote de keys; Ctrl-C cancela de forma cooperativa e salva o parcial.

    O primeiro Ctrl-C so levanta o flag: as tracks em voo terminam, o parcial
    e gravado e o comando sai com 130. Devolver o handler padrao ja na
    primeira vez deixa um segundo Ctrl-C matar o processo de verdade se o
    usuario nao quiser esperar a track em andamento.
    """
    cancelar = threading.Event()
    anterior = None

    def _ao_interromper(*_):
        cancelar.set()
        print("\nCancelando: aguardando as tracks em andamento e salvando o parcial...")
        if anterior is not None:
            signal.signal(signal.SIGINT, anterior)

    try:
        anterior = signal.signal(signal.SIGINT, _ao_interromper)
    except ValueError:
        # Fora da thread principal nao da para instalar handler; sem Ctrl-C
        # cooperativo, mas o lote roda igual.
        anterior = None
    try:
        relatorio = servico.detect_keys_batch(
            on_progress=_imprime_progresso,
            should_cancel=cancelar.is_set,
            calibrar=calibrar,
        )
    finally:
        if anterior is not None:
            signal.signal(signal.SIGINT, anterior)
    _imprime_relatorio_de_keys(relatorio)
    return 130 if relatorio.cancelled else 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if _empacotado() and not argv:
        # Clique duplo no .app chama o executavel sem argumentos -- sem
        # isso o argparse abaixo exigiria um subcomando que ninguem digitou
        # e sairia com erro antes de o servidor sequer subir.
        argv = ["serve"]

    parser = argparse.ArgumentParser(prog="dj", description="Classificador de tracks por energia")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    caminho_padrao = str(_caminho_config_padrao())
    for nome, ajuda in (
        ("scan", "Extrai features das tracks ainda nao analisadas"),
        ("train", "Retreina o modelo e imprime as metricas"),
        ("keys", "Estima pelo audio a tonalidade das tracks sem key (Ctrl-C salva o parcial)"),
    ):
        sub = subcomandos.add_parser(nome, help=ajuda)
        sub.add_argument("--config", default=caminho_padrao, help="Caminho do config.toml")
        if nome == "keys":
            sub.add_argument(
                "--calibrar",
                action="store_true",
                help="Mede a estimativa contra as tags existentes e NAO grava nada",
            )

    # Subcomando serve: API + WebSocket para o front React
    serve_parser = subcomandos.add_parser("serve", help="Sobe API + WebSocket para o front web")
    serve_parser.add_argument("--config", default=caminho_padrao, help="Caminho do config.toml")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host para bind")
    serve_parser.add_argument("--port", default=8765, type=int, help="Porta")
    serve_parser.add_argument("--no-browser", action="store_true", help="Nao abre o browser")

    argumentos = parser.parse_args(argv)

    if argumentos.comando == "serve":
        from .serve import run_server

        run_server(
            argumentos.config,
            host=argumentos.host,
            port=argumentos.port,
            open_browser=not argumentos.no_browser,
        )
        return 0

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

    if argumentos.comando == "keys":
        return _executa_keys(servico, argumentos.calibrar)

    try:
        _imprime_metricas(servico.train())
    except NotEnoughClassesError as erro:
        print(str(erro), file=sys.stderr)
        return 1
    return 0
