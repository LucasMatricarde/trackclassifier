"""Janela principal. Monta as abas e liga os sinais -- nada mais."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..service import TrackService
from ..update_state import EstadoDeAtualizacao
from ..updates import Release, relanca
from .library_tab import LibraryTab
from .model_tab import ModelTab
from .review_tab import ReviewTab
from .settings_tab import SettingsTab
from .tokens import SIZE_CONTROL_BASE, SPACE_4
from .typography import aplica_tracking, texto_de_label
from .update_banner import UpdateBanner
from .update_worker import VerificadorDeAtualizacao
from .viewmodel import LibraryState, ModelState, ReviewState, texto_de_atualizacao
from .widgets.hint_bar import HintBar
from .widgets.player import MULTIMEDIA_AVAILABLE, create_player
from .widgets.status_strip import StatusStrip
from .worker import ServiceThread

# texto_de_label so na palavra, nao no glifo: .upper() num simbolo unicode
# como "⟳" e "✕" e uma troca de glifo por acidente do Unicode Case Folding
# em famílias de simbolo raras -- o risco nao vale a pena por um caractere
# que ja e todo maiusculo visualmente.
TEXTO_ESCANEAR = "⟳ " + texto_de_label("Escanear")
TEXTO_CANCELAR = "✕ " + texto_de_label("Cancelar")

# Legenda por aba da HintBar (rodape de atalhos, chrome da janela --
# ver ui/widgets/hint_bar.py). (texto, destacado); destacado sobe de
# text.muted para text.secondary, reservado para a acao PRINCIPAL da aba.
#
# Revisao mantem a mesma legenda que a DecisionBar carregava antes desta
# faixa existir (ctrl+Z, nao "Z" -- ver o motivo no proprio atalho
# registrado em MainWindow._registra_atalhos). O digito 1/2/3 nao entra
# aqui: ele ja vive DENTRO de cada alvo da DecisionBar, uma legenda
# separada para ele duplicaria a informacao.
_HINTS_REVISAO: tuple[tuple[str, bool], ...] = (
    ("espaco tocar", False),
    ("← → navegar", False),
    ("ctrl+Z desfazer", False),
)

# Biblioteca segue o mockup 3a ao pe da letra, inclusive onde ele promete
# teclas que a aba nao cumpre: "Z" (o atalho real e ctrl+Z, mesmo motivo do
# comentario acima) e "espaco tocar" (so a Revisao toca). Decisao deliberada
# do design, nao lacuna esquecida -- ver a decisao no plano desta mudanca.
_HINTS_BIBLIOTECA: tuple[tuple[str, bool], ...] = (
    ("↑↓ navegar", False),
    ("1 / 2 / 3 reclassificar", True),
    ("Z desfazer", False),
    ("espaco tocar", False),
)

_HINTS_VAZIO: tuple[tuple[str, bool], ...] = ()


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: TrackService,
        config_path: Path | None = None,
        bundle: Path | None = None,
        atualizacoes: EstadoDeAtualizacao | None = None,
        verificador: VerificadorDeAtualizacao | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Track classifier")
        self.resize(1180, 760)

        self._player = create_player(self)
        self._thread = ServiceThread(service)
        self._worker = self._thread.worker

        self.review_tab = ReviewTab(self._player)
        self.library_tab = LibraryTab()
        self.model_tab = ModelTab()
        # config_path opcional: os testes de fumaca da janela montam um
        # TrackService direto, sem arquivo de config em disco. Sem caminho,
        # a aba nao aparece -- e melhor que uma aba que grava num lugar
        # inventado.
        self.settings_tab = SettingsTab(config_path) if config_path is not None else None

        self.tabs = QTabWidget()
        self.tabs.addTab(self.review_tab, "Revisao")
        self.tabs.addTab(self.library_tab, "Biblioteca")
        self.tabs.addTab(self.model_tab, "Modelo")
        if self.settings_tab is not None:
            self.tabs.addTab(self.settings_tab, "Configuracao")

        self._escaneando = False
        self._botao_scan = QPushButton(TEXTO_ESCANEAR)
        self._botao_scan.clicked.connect(self._clique_no_botao_scan)
        self._botao_scan.setProperty("variant", "ghost")
        aplica_tracking(self._botao_scan)
        # Altura fixa e nao maximumHeight: sem isto o botao herdaria a
        # altura natural do cornerWidget, encostado na borda direita da
        # janela, esticando sem respiro nenhum -- o container abaixo e o
        # que da a margem e centraliza o botao na faixa. (A regra generica
        # de QPushButton em app.qss ja fecha em size.control.base
        # descontada a borda -- ver sem_borda em design/build_tokens.py --
        # entao nao precisa mais de folha de instancia repetindo o calculo
        # aqui; setFixedHeight so reforca o mesmo numero.)
        self._botao_scan.setFixedHeight(SIZE_CONTROL_BASE)
        canto = QWidget()
        canto_layout = QHBoxLayout(canto)
        canto_layout.setContentsMargins(0, 0, SPACE_4, 0)
        canto_layout.setSpacing(0)
        canto_layout.addWidget(self._botao_scan, 0, Qt.AlignmentFlag.AlignVCenter)
        self.tabs.setCornerWidget(canto, Qt.Corner.TopRightCorner)

        # A faixa entra num container acima das abas, e nao como widget de
        # canto da tab bar: ela precisa da largura inteira e nao pode
        # competir com o botao Escanear, que ja ocupa o canto.
        self.banner = UpdateBanner()
        self._hint_bar = HintBar()
        central = QWidget()
        caixa = QVBoxLayout(central)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(0)
        caixa.addWidget(self.banner)
        caixa.addWidget(self.tabs)
        caixa.addWidget(self._hint_bar)
        self.setCentralWidget(central)

        # Widget "normal" (addWidget, nao addPermanentWidget): fica a
        # esquerda e uma showMessage() temporaria (scan, erro, "Configuracao
        # aplicada") o cobre por cima enquanto dura -- e o comportamento que
        # StatusStrip.__doc__ conta com, nao um efeito colateral.
        self._status = StatusStrip()
        self.statusBar().addWidget(self._status)

        if not MULTIMEDIA_AVAILABLE:
            self.statusBar().showMessage(
                "Sem QtMultimedia: player simulado. Instale o extra audio para ouvir."
            )

        self._bundle = bundle
        self._atualizacoes = atualizacoes
        self._release_pendente: Release | None = None
        # True enquanto a checagem em voo for a do boot. O menu zera isto:
        # pedido explicito ignora a versao dispensada e merece resposta
        # mesmo quando nao ha novidade.
        self._checagem_automatica = True
        self._n_tracks = 0
        self.acao_atualizar: QAction | None = None
        self._verificador: VerificadorDeAtualizacao | None = None
        if bundle is not None:
            self._monta_atualizacao(verificador)

        self._conecta()
        self._registra_atalhos()
        self.tabs.currentChanged.connect(self._atualiza_atalhos_de_revisao)
        self.tabs.currentChanged.connect(self._muda_hint_bar)
        # currentChanged nao dispara para o estado inicial (a aba 0 ja esta
        # current antes de qualquer um se conectar ao sinal) -- sem esta
        # chamada explicita, Space/Right/Left ficariam desabilitados (e a
        # HintBar mostraria a legenda errada) ate a primeira troca de aba,
        # mesmo com Revisao sendo a aba inicial.
        self._atualiza_atalhos_de_revisao(self.tabs.currentIndex())
        self._muda_hint_bar(self.tabs.currentIndex())
        self._thread.start()
        # Dispara sozinho depois da janela aparecer: o scan sincrono do CLI
        # seriam minutos de tela morta aqui. O overload de 3 argumentos e
        # essencial aqui: singleShot(msec, callable) roda o callable na
        # thread de QUEM CHAMOU (a GUI), ignorando a afinidade de thread do
        # objeto -- so o overload (msec, contexto, callable) despacha via
        # fila de eventos do contexto, que e o que manda isto rodar na
        # QThread do worker em vez de travar a janela pela duracao do scan.
        QTimer.singleShot(0, self._worker, self._worker.refresh)
        self._inicia_scan()

    def _conecta(self) -> None:
        self.review_tab.decide_requested.connect(self._worker.decide)
        self.review_tab.undo_requested.connect(self._worker.undo)
        self.review_tab.bulk_approve_requested.connect(self._worker.bulk_approve)
        self.library_tab.decide_requested.connect(self._worker.decide)
        self.model_tab.train_requested.connect(self._worker.train)
        self.review_tab.peaks_requested.connect(self._worker.compute_peaks)
        self.library_tab.peaks_requested.connect(self._worker.compute_peaks)
        self.review_tab.scan_requested.connect(self._pede_scan)
        self.library_tab.scan_requested.connect(self._pede_scan)
        self._worker.peaks_ready.connect(self.review_tab.recebe_peaks)
        self._worker.peaks_ready.connect(self.library_tab.peaks_prontos)
        self._worker.peaks_failed.connect(self.library_tab.peaks_falharam)

        self._worker.states_changed.connect(self.apply_states)
        self._worker.scan_progress.connect(self._mostra_progresso)
        self._worker.scan_finished.connect(self._scan_concluido)
        self._worker.error.connect(self._mostra_erro)
        self._worker.retrained.connect(self._modelo_retreinado)
        self.library_tab.notation_changed.connect(self.review_tab.set_notation)
        if self.settings_tab is not None:
            self.settings_tab.config_saved.connect(self._aplica_config)

    def apply_states(
        self, review: ReviewState, library: LibraryState, model: ModelState
    ) -> None:
        self.review_tab.set_state(review)
        self.library_tab.set_state(library)
        self.model_tab.set_state(model)
        # O aviso de recomputo precisa de quantas tracks serao reanalisadas.
        # Sai do estado que a janela ja recebe por sinal -- nenhum widget
        # chama o TrackService.
        self._n_tracks = len(library.rows)
        # library.rows ja e so o classificado (ver LibraryTab/TrackService) --
        # somado ao que falta revisar, fecha o total do acervo sem pedir mais
        # nada ao servico.
        self._status.mostra_resumo(
            tracks=len(library.rows) + review.remaining,
            analisadas=len(library.rows),
            pendentes=review.remaining,
        )

    def _mostra_progresso(self, concluidas: int, total: int, nome: str) -> None:
        self._status.mostra_scan(concluidas, total, nome)

    def _muda_hint_bar(self, indice: int) -> None:
        aba = self.tabs.widget(indice)
        if aba is self.review_tab:
            self._hint_bar.set_atalhos(_HINTS_REVISAO)
        elif aba is self.library_tab:
            self._hint_bar.set_atalhos(_HINTS_BIBLIOTECA)
        else:
            self._hint_bar.set_atalhos(_HINTS_VAZIO)

    def _aplica_config(self, config) -> None:
        # Overload de 3 argumentos pelo mesmo motivo do refresh e do scan:
        # e o unico que despacha via fila de eventos do worker em vez de
        # rodar na thread de quem chamou.
        QTimer.singleShot(0, self._worker, lambda: self._worker.reload_config(config))
        self.statusBar().showMessage("Configuracao aplicada.", 4000)

    def _clique_no_botao_scan(self) -> None:
        """Um botao so: inicia o scan quando parado, cancela quando rodando.

        Ser o mesmo botao e o que impede disparar um segundo scan por cima do
        primeiro -- enquanto ha um em andamento, nao existe controle na tela
        que inicie outro.
        """
        if self._escaneando:
            self._botao_scan.setEnabled(False)  # pedido feito; evita duplo clique
            self._worker.request_cancel()
            self.statusBar().showMessage("Cancelando o scan...")
            return
        self._inicia_scan()

    def _pede_scan(self) -> None:
        """Caminho so-de-inicio para o botao do empty state, achado da
        revisao final.

        Diferente do botao do canto (_clique_no_botao_scan, um toggle
        escanear/cancelar), o botao dentro do EmptyState so mostra um
        rotulo: "Escanear". O auto-scan de abertura (fim do __init__)
        comeca ANTES de qualquer aba receber estado — nesse intervalo o
        empty state ja esta na tela mostrando "Escanear" enquanto ha, de
        fato, um scan em andamento. Ligar scan_requested ao toggle faria
        esse clique cancelar o scan que acabou de comecar, o oposto do que
        o rotulo promete. Ignorar o pedido quando ja escaneando (em vez de
        desabilitar o botao, que exigiria um hook tipo
        SettingsTab.set_scanning que o EmptyState nao tem) e suficiente:
        nada aqui precisa saber que perdeu a corrida.
        """
        if self._escaneando:
            return
        self._inicia_scan()

    def _inicia_scan(self) -> None:
        self._escaneando = True
        self._botao_scan.setText(TEXTO_CANCELAR)
        if self.settings_tab is not None:
            self.settings_tab.set_scanning(True)
        # Overload de 3 argumentos, pelo mesmo motivo do refresh acima: e o
        # unico que despacha via fila de eventos do worker em vez de rodar na
        # thread de quem chamou.
        QTimer.singleShot(0, self._worker, self._worker.scan)

    def _scan_concluido(self, cancelado: bool) -> None:
        self._escaneando = False
        self._botao_scan.setText(TEXTO_ESCANEAR)
        self._botao_scan.setEnabled(True)
        if self.settings_tab is not None:
            self.settings_tab.set_scanning(False)
        self.statusBar().showMessage(
            "Scan cancelado." if cancelado else "Scan concluido.", 4000
        )

    def _mostra_erro(self, mensagem: str) -> None:
        self.statusBar().showMessage(mensagem, 6000)

    def _modelo_retreinado(self) -> None:
        self.statusBar().showMessage("Modelo retreinado.", 4000)

    def _monta_atualizacao(
        self, verificador: VerificadorDeAtualizacao | None = None
    ) -> None:
        """So existe dentro do .app: fora dele nao ha bundle para trocar.

        `verificador` e um seam de injecao puramente aditivo: None (o
        default de todo chamador de producao) mantem o comportamento de
        sempre, construindo o VerificadorDeAtualizacao real. Testes que
        precisam evitar a checagem automatica de boot batendo na rede
        passam um fake aqui em vez de monkeypatchar busca_ultimo_release.
        """
        self._verificador = (
            verificador if verificador is not None else VerificadorDeAtualizacao(self)
        )
        self._verificador.disponivel.connect(self._atualizacao_disponivel)
        self._verificador.sem_novidade.connect(self._sem_atualizacao)
        self._verificador.falhou.connect(self._atualizacao_falhou)
        self._verificador.progresso.connect(self.banner.mostra_progresso)
        self._verificador.instalado.connect(self._atualizacao_instalada)

        self.banner.atualizar_clicado.connect(self._confirma_atualizacao)
        self.banner.dispensar_clicado.connect(self._dispensa_atualizacao)

        self.acao_atualizar = QAction("Buscar atualizacoes...", self)
        # ApplicationSpecificRole e o que faz o Qt colocar o item no menu
        # "TrackClassifier" do macOS, junto de Sobre e Sair, em vez de criar
        # um menu solto na barra. Mas o merge so acontece para acoes que
        # vivem DENTRO de um QMenu -- uma QAction solta adicionada direto
        # via menuBar().addAction() e descartada pelo plugin cocoa do Qt e
        # nunca aparece em [NSApp mainMenu] (confirmado lendo o menu nativo
        # em runtime). addMenu("TrackClassifier") cria o menu que o Qt
        # reconhece e funde no menu do app; nenhum menu solto sobra na barra
        # porque toda acao dentro dele tem role de app-menu.
        self.acao_atualizar.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        self.acao_atualizar.triggered.connect(self._checa_a_pedido)
        menu = self.menuBar().addMenu("TrackClassifier")
        menu.addAction(self.acao_atualizar)

        if self._atualizacoes is not None and self._atualizacoes.deve_checar():
            self._atualizacoes.marca_checagem()
            self._verificador.checar()

    def _checa_a_pedido(self) -> None:
        """Pedido explicito: ignora o intervalo e a versao dispensada."""
        self._checagem_automatica = False
        if self._verificador is not None:
            self._verificador.checar()

    def _atualizacao_disponivel(self, release: Release) -> None:
        dispensada = (
            self._checagem_automatica
            and self._atualizacoes is not None
            and self._atualizacoes.esta_dispensada(release.version)
        )
        if dispensada:
            return
        self._release_pendente = release
        self.banner.mostra(release.version)

    def _sem_atualizacao(self) -> None:
        self.banner.esconde()
        if not self._checagem_automatica:
            # So avisa quando o usuario perguntou. Silencio na checagem
            # automatica e o comportamento correto: nao ha noticia.
            self.statusBar().showMessage("Voce ja esta na versao mais recente.", 4000)

    def _atualizacao_falhou(self, mensagem: str) -> None:
        self.banner.esconde()
        self.statusBar().showMessage(mensagem, 6000)

    def _confirma_atualizacao(self) -> None:
        if self._release_pendente is None or self._bundle is None:
            return
        corpo = texto_de_atualizacao(
            self._release_pendente,
            versao_atual=self._verificador.versao_atual,
            n_tracks=self._n_tracks,
        )
        resposta = QMessageBox.question(
            self,
            "Atualizar o TrackClassifier",
            corpo,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if resposta != QMessageBox.StandardButton.Ok:
            return
        self._verificador.instalar_release(self._release_pendente, self._bundle)

    def _dispensa_atualizacao(self) -> None:
        if self._release_pendente is not None and self._atualizacoes is not None:
            self._atualizacoes.dispensa(self._release_pendente.version)
        self.banner.esconde()

    def _atualizacao_instalada(self) -> None:
        QMessageBox.information(
            self,
            "Atualizado",
            "A versao nova foi instalada. O app vai reabrir.",
        )
        if self._bundle is not None:
            relanca(self._bundle)
        self.close()

    # ---- atalhos de teclado --------------------------------------------
    #
    # Registrados aqui, nao em keyPressEvent das abas: depois que a janela
    # aparece, o foco inicial cai no QTabBar e eventos de tecla sobem a
    # cadeia de pais a partir de quem tem foco, nunca descem para o widget
    # de conteudo da aba. E o QTableView da Biblioteca ainda consome teclas
    # de digito para a busca incremental embutida do QAbstractItemView antes
    # que qualquer keyPressEvent de LibraryTab rode. QShortcut com contexto
    # WindowShortcut entra na etapa de despacho do Qt que roda ANTES da
    # entrega normal de keyPressEvent ao widget focado, entao funciona
    # independente de onde o foco esta dentro da janela.

    _TECLAS_ROTULO = {"1": "-1", "2": "neutra", "3": "+1"}

    def _registra_atalho(self, tecla: str, callback) -> QShortcut:
        atalho = QShortcut(QKeySequence(tecla), self)
        atalho.setContext(Qt.ShortcutContext.WindowShortcut)
        atalho.activated.connect(callback)
        return atalho

    def _registra_atalhos(self) -> None:
        for tecla, rotulo in self._TECLAS_ROTULO.items():
            self._registra_atalho(tecla, lambda rotulo=rotulo: self._decide_na_aba_atual(rotulo))
        # Guardamos as referencias destes tres porque _atualiza_atalhos_de_revisao
        # precisa liga-los/desliga-los conforme a aba atual -- ver o comentario
        # la para o motivo (eles brigam com widgets nativos do Qt fora da Revisao).
        self._atalho_espaco = self._registra_atalho("Space", self._alterna_reproducao)
        self._atalho_direita = self._registra_atalho("Right", self._pular_revisao)
        self._atalho_esquerda = self._registra_atalho("Left", self._voltar_revisao)
        # "Ctrl+Z" e portavel: no macOS o Qt mapeia o modificador Ctrl da
        # sequencia para Cmd automaticamente (comportamento documentado do
        # QKeySequence), entao nao precisa de uma segunda entrada para Cmd+Z.
        self._registra_atalho("Ctrl+Z", self._desfazer)

    def _atualiza_atalhos_de_revisao(self, indice: int) -> None:
        """Liga Space/Right/Left so quando a Revisao e a aba atual.

        Diferente de 1/2/3/Ctrl+Z (que nao colidem com nada), estes tres tem
        contrapartida nativa no Qt fora da Revisao: QTabBar usa Left/Right
        para trocar de aba e QPushButton (o botao "Escanear" no canto) usa
        Space para se ativar quando tem foco. Como QShortcut com contexto
        WindowShortcut roda ANTES da entrega normal de evento, deixa-los
        sempre ligados rouba essas teclas dos widgets nativos em qualquer
        aba. QShortcut desabilitado e pulado inteiramente pelo despacho do
        Qt, entao desliga-los fora da Revisao devolve a tecla ao fluxo normal
        -- nao "simplifique" isto de volta pra sempre-ligado.
        """
        ativo = self.tabs.widget(indice) is self.review_tab
        self._atalho_espaco.setEnabled(ativo)
        self._atalho_direita.setEnabled(ativo)
        self._atalho_esquerda.setEnabled(ativo)

    def _decide_na_aba_atual(self, rotulo: str) -> None:
        aba = self.tabs.currentWidget()
        if aba is self.review_tab:
            self.review_tab.decide_atual(rotulo)
        elif aba is self.library_tab:
            self.library_tab.decide_selecionada(rotulo)

    def _alterna_reproducao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self._player.toggle()

    def _pular_revisao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self.review_tab.pular()

    def _voltar_revisao(self) -> None:
        if self.tabs.currentWidget() is self.review_tab:
            self.review_tab.voltar()

    def _desfazer(self) -> None:
        """Vale em qualquer aba, diferente de Space/Left/Right.

        O que da para desfazer e estado do servico (_ultima_decisao), nao da
        tela: undo_last devolve uma decisao da inbox para a fila de revisao e
        uma reclassificacao para a biblioteca com o rotulo antigo, olhando a
        origem_label que ele mesmo guardou.

        A Biblioteca nao anuncia a tecla em lugar nenhum -- ela nao tem
        rodape de atalhos. E divida conhecida, nao esquecimento: a legenda
        da Revisao (DecisionBar) continua sendo a unica que a documenta.

        Overload de 3 argumentos, mesmo motivo do refresh/scan/reload_config
        acima: e o unico que despacha via fila de eventos do worker em vez de
        chamar TrackService.undo_last direto na thread da GUI. So a thread do
        ServiceWorker pode falar com TrackService -- Ctrl+Z nao e desabilitado
        durante um scan (so Space/Left/Right sao), entao uma chamada direta
        aqui mutaria Sha1Cache/parquet em paralelo com o scan mutando as
        mesmas estruturas, alem de rodar undo_last+refresh (que percorre a
        biblioteca inteira) sincronamente dentro do evento de tecla.
        """
        QTimer.singleShot(0, self._worker, self._worker.undo)

    def closeEvent(self, event) -> None:
        self._player.stop()
        self._thread.stop()
        super().closeEvent(event)
