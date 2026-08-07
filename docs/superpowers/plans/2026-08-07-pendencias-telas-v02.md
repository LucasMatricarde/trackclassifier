# Pendências das telas v0.2 — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as três pendências das telas v0.2 — a barra do player em v0.1, o anel de foco de teclado que nunca entrou e a medição de performance que nunca foi feita contra o número de referência.

**Architecture:** Um widget novo de volume pintado à mão (`VolumeRail`) substitui o `QSlider` da `PlayerBar`; o anel de foco vira `paintEvent` de uma subclasse do `QTableView` da Biblioteca, e não de delegate; o Ctrl+Z deixa de checar a aba e chama o worker direto. A medição é manual, com uma leitura antes e outra depois do anel.

**Tech Stack:** Python 3.11+, PySide6, pytest com `QT_QPA_PLATFORM=offscreen` (`tests/conftest.py`), uv, ruff.

**Spec:** `docs/superpowers/specs/2026-08-07-pendencias-telas-v02-design.md`

## Global Constraints

- **Português sem acentos** em código: variáveis locais, funções internas, comentários, docstrings, mensagens de erro e nomes de teste. API pública (dataclasses, métodos de classe, campos JSON) em inglês.
- Comentários explicam **por que**, não o quê — e são longos quando a decisão não é óbvia.
- **Nenhum literal `#RRGGBB` fora de `design/design-tokens.json`.** `tests/test_tokens.py::test_nenhum_hex_fora_do_json` varre `ui/` por linha, docstrings inclusive. Cor sempre via token; cor com alfa via `ui/colors.tinta`.
- `ui/viewmodel.py` não importa Qt (teste gramatical falha se importar).
- Nenhum token novo neste plano. Dimensões sem token viram constante de módulo no widget, com comentário — padrão de `_ALTURA_ALVO` em `decision_bar.py`.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` é gate do CI.
- Commits: conventional commits com escopo, ex.: `feat(trackclassifier): ...`.
- Rodar `uv run pytest` inteiro antes de cada commit que toque `ui/` — a suíte leva ~70s.

---

### Task 0: Medida de baseline da Biblioteca (manual, antes de qualquer código)

Sem esta leitura, um número ruim no fim do plano não diz se o culpado é o anel novo, a coluna CAPA ou o fundo da onda. **Esta task não altera nenhum arquivo.**

**Files:**
- Create: nenhum (o resultado é anotado, e vai para a mensagem de commit da Task 7)

- [ ] **Step 1: Confirmar que a biblioteca real está configurada**

Run: `uv run dj scan`
Expected: termina sem erro e reporta o total de tracks. Se reportar menos de ~100 tracks, esta medição não vale — anote isso e siga para a Task 1; o critério de regressão pressupõe volume comparável às 354 tracks da referência.

- [ ] **Step 2: Aquecer os thumbs**

Run: `uv run dj review`
Abra a aba Biblioteca, role a lista de ponta a ponta, feche a janela. Esta passada existe só para gravar os `covers/<sha1>.thumb.png` de 96px — o custo de gerá-los não é o custo de exibi-los, e medir a primeira passada mediria a coisa errada.

- [ ] **Step 3: Medir**

Run: `uv run dj review`
Abra a aba Biblioteca (densidade `comfortable`) e meça, com a técnica de perfilamento descrita no comentário do commit `ba53271`:
- tempo do primeiro paint da Biblioteca
- ms por parada de rolagem (rolar, parar, ler; repetir umas cinco vezes e tomar a mediana)

- [ ] **Step 4: Anotar os dois números**

Guarde os valores em texto (eles entram na mensagem de commit da Task 7). Referência de `ba53271`, para comparação: **29,5 ms** no primeiro paint e **5,6 ms** por parada, com 354 tracks.

---

### Task 1: `VolumeRail` — o trilho de volume da v0.2

**Files:**
- Create: `src/trackclassifier/ui/widgets/volume_rail.py`
- Test: `tests/test_volume_rail.py`

**Interfaces:**
- Consumes: `ui.colors.para_qcolor`, tokens `COLOR_BORDER_DEFAULT`, `COLOR_TEXT_SECONDARY`, `COLOR_TEXT_PRIMARY`
- Produces: `VolumeRail(valor: int = 80, parent: QWidget | None = None)`, sinal `valor_mudou(int)`, métodos `valor() -> int` e `set_valor(valor: int) -> None`. A Task 2 consome os três.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_volume_rail.py`:

```python
"""O trilho de volume: 2px de traco, faixa de clique mais alta que ele."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from trackclassifier.ui.widgets.volume_rail import VolumeRail


def test_nasce_no_valor_pedido(qapp):
    trilho = VolumeRail(80)

    assert trilho.valor() == 80


def test_set_valor_clampa_fora_da_faixa(qapp):
    trilho = VolumeRail(80)

    trilho.set_valor(140)
    assert trilho.valor() == 100

    trilho.set_valor(-5)
    assert trilho.valor() == 0


def test_clique_no_meio_do_trilho_vai_para_metade(qapp):
    trilho = VolumeRail(0)
    recebidos = []
    trilho.valor_mudou.connect(recebidos.append)

    meio = QPoint(trilho.width() // 2, trilho.height() // 2)
    QTest.mouseClick(trilho, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, meio)

    assert 45 <= trilho.valor() <= 55
    assert recebidos and 45 <= recebidos[-1] <= 55


def test_a_faixa_de_clique_e_mais_alta_que_o_traco(qapp):
    """Um trilho desenhado com 2px e intocavel com o mouse -- e por isso
    que este widget existe em vez de um QSlider vestido por QSS."""
    trilho = VolumeRail(0)

    assert trilho.height() >= 10


def test_o_valor_aparece_para_um_leitor_de_tela(qapp):
    """O valor so existe como largura de pixel: sem descricao acessivel,
    um leitor de tela anuncia "Volume" e nada mais."""
    trilho = VolumeRail(30)

    assert trilho.accessibleName() == "Volume"
    assert "30" in trilho.accessibleDescription()
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_volume_rail.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets.volume_rail'`

- [ ] **Step 3: Escrever o widget**

Criar `src/trackclassifier/ui/widgets/volume_rail.py`:

```python
"""Trilho de volume: traco de 2px com marcador, clicavel e arrastavel.

Nao herda de Meter, apesar de os dois serem trilhos pintados a mao. Meter e
read-only, preenche a altura inteira e se anuncia como "Medidor"; aqui os
tres pontos mudam, e sobreviveria so o nome da classe.

O que obriga o widget a existir e a diferenca entre a altura DESENHADA e a
altura CLICAVEL: o mockup pede um traco de 2px, e 2px sao intocaveis com o
mouse. O widget tem altura de _ALTURA, pinta o traco centrado nela e aceita
o clique em qualquer ponto da faixa -- um QSlider vestido por QSS nao
consegue separar as duas alturas.
"""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_BORDER_DEFAULT, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY

#: Do mockup. Nao esticam com a janela: um medidor de volume de 400px nao
#: le melhor que um de 100, so ocupa mais.
_LARGURA = 100
_ALTURA = 12
_ALTURA_TRILHO = 2
_LARGURA_MARCADOR = 2
_ALTURA_MARCADOR = 10


class VolumeRail(QWidget):
    valor_mudou = Signal(int)

    def __init__(self, valor: int = 80, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._valor = 0
        self.setFixedSize(_LARGURA, _ALTURA)
        # NoFocus de proposito: 1/2/3 sao QShortcut de janela e rodam ANTES
        # da entrega normal do evento, entao nem com foco este widget os
        # receberia -- focavel aqui so acrescentaria uma parada no Tab.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Volume")
        self.set_valor(valor)

    def valor(self) -> int:
        return self._valor

    def set_valor(self, valor: int) -> None:
        # Clampa aqui e nao em quem chama: o valor vem de uma coordenada de
        # mouse, que passa das bordas em qualquer arrasto um pouco largo.
        self._valor = min(100, max(0, int(valor)))
        # O valor so existe como largura de pixel.
        self.setAccessibleDescription(f"{self._valor}%")
        self.update()
        self.valor_mudou.emit(self._valor)

    # ---- mouse ---------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        self._valor_do_x(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        self._valor_do_x(event.position().x())

    def _valor_do_x(self, x: float) -> None:
        self.set_valor(round(x / max(1, self.width()) * 100))

    # ---- pintura -------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)

        topo = (self.height() - _ALTURA_TRILHO) // 2
        painter.setBrush(para_qcolor(COLOR_BORDER_DEFAULT))
        painter.drawRect(QRect(0, topo, self.width(), _ALTURA_TRILHO))

        preenchido = round(self.width() * self._valor / 100)
        painter.setBrush(para_qcolor(COLOR_TEXT_SECONDARY))
        painter.drawRect(QRect(0, topo, preenchido, _ALTURA_TRILHO))

        # Marcador preso na borda direita no volume maximo: centrado no
        # preenchimento, metade dele sairia do widget e sumiria.
        x = min(preenchido, self.width() - _LARGURA_MARCADOR)
        painter.setBrush(para_qcolor(COLOR_TEXT_PRIMARY))
        painter.drawRect(
            QRect(
                x,
                (self.height() - _ALTURA_MARCADOR) // 2,
                _LARGURA_MARCADOR,
                _ALTURA_MARCADOR,
            )
        )
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_volume_rail.py -v`
Expected: PASS nos cinco.

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/widgets/volume_rail.py tests/test_volume_rail.py
git commit -m "feat(trackclassifier): trilho de volume da v0.2, pintado a mao"
```

---

### Task 2: `PlayerBar` passa a falar v0.2

**Files:**
- Modify: `src/trackclassifier/ui/widgets/player_bar.py` (troca do `QSlider`, altura, botão, micro-label)
- Test: `tests/test_player_bar.py` (acrescentar; os quatro testes que já existem continuam valendo)

**Interfaces:**
- Consumes: `VolumeRail` da Task 1 (`valor_mudou`, `set_valor`), tokens `SIZE_CONTROL_BASE` (28) e `SIZE_CONTROL_PRIMARY` (36), `ui.typography.estiliza_label`
- Produces: `PlayerBar.volume` (o `VolumeRail`, atributo público, usado pelos testes)

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_player_bar.py`:

```python
def test_o_volume_inicial_chega_ao_player(qapp):
    from trackclassifier.ui.widgets.player_bar import _VOLUME_INICIAL

    player = SimulatedPlayer()
    barra = PlayerBar(player)

    assert barra.volume.valor() == _VOLUME_INICIAL
    assert player.volume() == _VOLUME_INICIAL / 100


def test_mudar_o_trilho_muda_o_volume_do_player(qapp):
    player = SimulatedPlayer()
    barra = PlayerBar(player)

    barra.volume.set_valor(25)

    assert player.volume() == 0.25


def test_a_barra_tem_a_altura_de_controle_primario(qapp):
    """36px vem do mockup e ja existe como token -- e a altura da BARRA.
    O botao usa o token de controle base; usar o mesmo nos dois faria o
    botao encostar nas duas bordas."""
    from trackclassifier.ui.tokens import SIZE_CONTROL_BASE, SIZE_CONTROL_PRIMARY

    barra = PlayerBar(SimulatedPlayer())

    assert barra.height() == SIZE_CONTROL_PRIMARY
    assert barra.altura_do_botao() == SIZE_CONTROL_BASE
```

Se `SimulatedPlayer` não expuser `volume()`, acrescentar o getter em `src/trackclassifier/ui/widgets/player.py` na classe `SimulatedPlayer` (ela já guarda o valor em `set_volume`) — sem isso não há como afirmar que o valor chegou ao player.

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_player_bar.py -v`
Expected: FAIL — `AttributeError: 'PlayerBar' object has no attribute 'volume'`

- [ ] **Step 3: Reescrever a barra**

Em `src/trackclassifier/ui/widgets/player_bar.py`:

Trocar os imports:

```python
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..tokens import SIZE_CONTROL_BASE, SIZE_CONTROL_PRIMARY, SPACE_3, SPACE_5
from ..typography import estiliza_label
from ..viewmodel import format_duration
from .volume_rail import VolumeRail
```

Substituir o corpo do `__init__` entre `self._duracao_ms = 0` e a ligação dos sinais:

```python
        # Altura da BARRA, nao do botao: o botao usa o token de controle
        # base. Ate a v0.1 os dois usavam SIZE_CONTROL_PRIMARY, e o botao
        # de 36px numa barra de 36px encostava nas duas bordas.
        self.setFixedHeight(SIZE_CONTROL_PRIMARY)

        self._botao = QPushButton(_PLAY)
        self._botao.setFixedSize(SIZE_CONTROL_BASE, SIZE_CONTROL_BASE)
        self._botao.clicked.connect(self._player.toggle)

        self._tempo = QLabel("")
        self._tempo.setObjectName("Numeric")

        self._rotulo_volume = QLabel()
        self._rotulo_volume.setObjectName("MicroLabel")
        estiliza_label(self._rotulo_volume, "Volume")

        self.volume = VolumeRail(_VOLUME_INICIAL)
        self.volume.valor_mudou.connect(self._muda_volume)

        layout = QHBoxLayout(self)
        # Margem vertical menor que a horizontal: a barra tem 36px de altura
        # fixa e o botao ocupa 28 deles.
        layout.setContentsMargins(SPACE_5, SPACE_3, SPACE_5, SPACE_3)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._botao)
        layout.addWidget(self._tempo)
        layout.addStretch(1)
        layout.addWidget(self._rotulo_volume)
        layout.addWidget(self.volume)
```

Acrescentar à superfície de teste, junto de `texto_do_botao`:

```python
    def altura_do_botao(self) -> int:
        return self._botao.height()
```

`_muda_volume` continua idêntico — recebe 0..100 e passa `/100` ao player.

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_player_bar.py -v`
Expected: PASS nos sete (os quatro antigos inclusive — em especial `test_botao_reflete_o_estado_do_player`, que protege o contrato de o rótulo vir de `playing_changed`).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: tudo verde. Falha esperada aqui seria em `tests/test_review_widgets.py` ou `tests/test_window.py`, que montam a Revisão inteira.

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/player_bar.py src/trackclassifier/ui/widgets/player.py tests/test_player_bar.py
git commit -m "feat(trackclassifier): a barra do player fala v0.2"
```

---

### Task 3: Anel de foco de teclado na Biblioteca

**Files:**
- Create: `src/trackclassifier/ui/widgets/library_table.py`
- Modify: `src/trackclassifier/ui/library_tab.py:175` (`_monta_tabela` troca `QTableView()` por `LibraryTable()`)
- Test: `tests/test_library_table.py`

**Interfaces:**
- Consumes: tokens `COLOR_ACCENT_BASE` e `SIZE_FOCUS_RING` (2), `ui.colors.para_qcolor`
- Produces: `LibraryTable(parent: QWidget | None = None)`, subclasse de `QTableView`, com `tem_foco_de_teclado() -> bool`. Nenhuma outra task consome.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_library_table.py`:

```python
"""O anel de foco: 'o teclado age NESTA linha agora'.

A tabela e SingleSelection + SelectRows, entao selecao e linha atual sao
sempre a mesma -- o anel nao distingue as duas. Ele responde a pergunta que
hoje nao tem resposta visual: com o foco no campo de busca, a linha continua
pintada como selecionada, mas digitar 1/2/3 nao a reclassifica.

O foco e estado explicito do widget (focusInEvent/focusOutEvent) e nao uma
consulta a hasFocus() no meio do paint: em QT_QPA_PLATFORM=offscreen o foco
real de janela nao e confiavel, e o QTableView nao repinta o viewport quando
o foco entra ou sai.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFocusEvent, QImage

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.viewmodel import library_state
from trackclassifier.ui.widgets.library_table import LibraryTable
from trackclassifier.ui.widgets.track_model import TrackTableModel


def _tabela(tmp_path) -> LibraryTable:
    servico = _servico(_config(tmp_path))
    tabela = LibraryTable()
    tabela.setModel(TrackTableModel(list(library_state(servico).rows)))
    tabela.resize(600, 200)
    tabela.setCurrentIndex(tabela.model().index(0, 0))
    return tabela


def _imagem(tabela: LibraryTable) -> QImage:
    imagem = QImage(tabela.viewport().size(), QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#000000"))
    tabela.viewport().render(imagem)
    return imagem


def _foco(tabela: LibraryTable, entrando: bool) -> None:
    evento = QFocusEvent(
        QFocusEvent.Type.FocusIn if entrando else QFocusEvent.Type.FocusOut,
        Qt.FocusReason.OtherFocusReason,
    )
    if entrando:
        tabela.focusInEvent(evento)
    else:
        tabela.focusOutEvent(evento)


def test_sem_foco_nao_ha_anel(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, False)

    assert tabela.tem_foco_de_teclado() is False


def test_com_foco_a_linha_atual_muda_de_pintura(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, False)
    sem_anel = _imagem(tabela)
    _foco(tabela, True)
    com_anel = _imagem(tabela)

    assert tabela.tem_foco_de_teclado() is True
    assert sem_anel != com_anel


def test_o_anel_some_quando_o_foco_sai(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, True)
    com_anel = _imagem(tabela)
    _foco(tabela, False)
    depois = _imagem(tabela)

    assert com_anel != depois


def test_sem_linha_atual_nao_quebra(qapp, tmp_path):
    """Biblioteca vazia (ou antes da primeira selecao) tem currentIndex
    invalido -- visualRect de um index invalido e um retangulo vazio."""
    tabela = LibraryTable()
    tabela.setModel(TrackTableModel([]))
    tabela.resize(600, 200)

    _foco(tabela, True)

    _imagem(tabela)  # nao levanta
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_library_table.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets.library_table'`

- [ ] **Step 3: Escrever a subclasse**

Criar `src/trackclassifier/ui/widgets/library_table.py`:

```python
"""QTableView da Biblioteca. O anel de foco de teclado mora aqui.

Por que aqui e nao num delegate: tres das oito colunas (GENERO, BPM,
DURACAO) nao tem delegate proprio -- usam o padrao do Qt. Pintar o anel por
celula obrigaria a dar delegate as tres, espalhar a pintura pelas cinco
subclasses de _DelegateComFundo e ainda emendar cinco retangulos num so sem
costura visivel. No paintEvent da view e um retangulo unico, num lugar so.

O anel usa accent.base, que na v0.2 e a MESMA cor de surface.selection-bar.
Isso e aproveitado, nao contornado: com foco, a barra de 2px que o
CoverDelegate ja pinta na borda esquerda vira o lado esquerdo do anel e o
retangulo fecha continuo; sem foco, sobra a barra sozinha.
"""

from PySide6.QtCore import QRect
from PySide6.QtGui import QFocusEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QTableView, QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_ACCENT_BASE, SIZE_FOCUS_RING


class LibraryTable(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._com_foco = False

    def tem_foco_de_teclado(self) -> bool:
        return self._com_foco

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().focusInEvent(event)
        self._muda_foco(True)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().focusOutEvent(event)
        self._muda_foco(False)

    def _muda_foco(self, tem_foco: bool) -> None:
        self._com_foco = tem_foco
        # O QTableView nao repinta o viewport quando o foco entra ou sai --
        # sem este update o anel so apareceria (ou sumiria) na proxima
        # rolagem, que e pior que nao ter anel nenhum.
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().paintEvent(event)
        if not self._com_foco:
            return
        index = self.currentIndex()
        if not index.isValid():
            return
        linha = self.visualRect(index)
        if linha.isEmpty():
            return

        # Largura do viewport, e nao da celula: o anel e da LINHA. visualRect
        # devolve so a celula da coluna atual.
        alvo = QRect(0, linha.top(), self.viewport().width(), linha.height())
        cor = para_qcolor(COLOR_ACCENT_BASE)
        painter = QPainter(self.viewport())
        # Quatro retangulos cheios em vez de um contorno com QPen: a caneta
        # centra o traco na borda e metade dos 2px sairia da linha, invadindo
        # a linha vizinha.
        painter.fillRect(QRect(alvo.left(), alvo.top(), alvo.width(), SIZE_FOCUS_RING), cor)
        painter.fillRect(
            QRect(
                alvo.left(),
                alvo.bottom() - SIZE_FOCUS_RING + 1,
                alvo.width(),
                SIZE_FOCUS_RING,
            ),
            cor,
        )
        painter.fillRect(QRect(alvo.left(), alvo.top(), SIZE_FOCUS_RING, alvo.height()), cor)
        painter.fillRect(
            QRect(
                alvo.right() - SIZE_FOCUS_RING + 1,
                alvo.top(),
                SIZE_FOCUS_RING,
                alvo.height(),
            ),
            cor,
        )
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_library_table.py -v`
Expected: PASS nos quatro.

- [ ] **Step 5: Ligar na aba**

Em `src/trackclassifier/ui/library_tab.py`, no topo, acrescentar o import:

```python
from .widgets.library_table import LibraryTable
```

Em `_monta_tabela`, trocar a primeira linha:

```python
        tabela = LibraryTable()
```

O resto do método fica idêntico — os delegates, o cabeçalho e a ligação do scroll continuam iguais.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: tudo verde, incluindo `tests/test_library_tab.py`. Se algum teste montar a tabela por tipo (`isinstance(..., QTableView)`), continua valendo — `LibraryTable` é um `QTableView`.

- [ ] **Step 7: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/library_table.py src/trackclassifier/ui/library_tab.py tests/test_library_table.py
git commit -m "feat(trackclassifier): anel de foco de teclado na Biblioteca"
```

---

### Task 4: Ctrl+Z deixa de ser exclusivo da Revisão

**Files:**
- Modify: `src/trackclassifier/ui/window.py:261-263` (`_desfazer`)
- Test: `tests/test_window.py` (acrescentar um teste)

**Interfaces:**
- Consumes: `self._worker.undo` (já existe, ligado à `review_tab.undo_requested` em `window.py:92`), `service.undo_last()` (já distingue inbox de reclassificação pela `origem_label`)
- Produces: nada novo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_window.py`:

```python
def test_ctrl_z_desfaz_uma_reclassificacao_na_biblioteca(qapp, tmp_path):
    """O desfazer e estado do SERVICO (_ultima_decisao), nao da tela.

    undo_last ja sabe devolver uma reclassificacao para a biblioteca com o
    rotulo antigo em vez de joga-la na fila de revisao -- so a janela e que
    checava a aba atual antes de chamar o worker.
    """
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)

        tabela = janela.library_tab._table
        tabela.setCurrentIndex(tabela.model().index(0, Column.TITULO))
        linha = tabela.model().row_at(0)
        origem = next(
            rotulo
            for rotulo, pasta in config.folders.items()
            if list(pasta.glob(Path(linha.path).name))
        )
        destino = Label.UP if origem is not Label.UP else Label.DOWN

        _tecla(janela, {Label.DOWN: Qt.Key.Key_1, Label.NEUTRAL: Qt.Key.Key_2, Label.UP: Qt.Key.Key_3}[destino])
        _espera_sinal(janela._worker.states_changed)
        assert list(config.folders[destino].glob(Path(linha.path).name))

        QTest.keyClick(janela, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[origem].glob(Path(linha.path).name))
        assert not list(config.folders[destino].glob(Path(linha.path).name))
    finally:
        janela.close()
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `uv run pytest tests/test_window.py::test_ctrl_z_desfaz_uma_reclassificacao_na_biblioteca -v`
Expected: FAIL no último par de asserts — a track continua na pasta de destino, porque `_desfazer` não faz nada fora da Revisão.

- [ ] **Step 3: Tirar a checagem de aba**

Em `src/trackclassifier/ui/window.py`, substituir `_desfazer` inteiro:

```python
    def _desfazer(self) -> None:
        """Vale nas duas abas, diferente de Space/Left/Right.

        O que da para desfazer e estado do servico (_ultima_decisao), nao da
        tela: undo_last devolve uma decisao da inbox para a fila de revisao e
        uma reclassificacao para a biblioteca com o rotulo antigo, olhando a
        origem_label que ele mesmo guardou.

        A Biblioteca nao anuncia a tecla em lugar nenhum -- ela nao tem
        rodape de atalhos. E divida conhecida, nao esquecimento: a legenda
        da Revisao (DecisionBar) continua sendo a unica que a documenta.
        """
        self._worker.undo()
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `uv run pytest tests/test_window.py::test_ctrl_z_desfaz_uma_reclassificacao_na_biblioteca -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: tudo verde. Os testes de undo na Revisão que já existem continuam valendo — o caminho `review_tab.undo_requested -> worker.undo` continua ligado em `window.py:92`.

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/window.py tests/test_window.py
git commit -m "fix(trackclassifier): ctrl+Z tambem desfaz na Biblioteca"
```

---

### Task 5: Nomes acessíveis nos widgets pintados à mão

Um widget desenhado em `paintEvent` não tem texto nenhum para um leitor de tela: o valor existe só como pixel. `meter.py`, `ordinal_scale.py` e `confusion_matrix.py` já resolveram isso e servem de modelo — nome fixo em `setAccessibleName`, valor corrente em `setAccessibleDescription`, atualizado onde o valor muda.

**Files:**
- Modify: `src/trackclassifier/ui/widgets/waveform_view.py` (nome + descrição por track)
- Modify: `src/trackclassifier/ui/widgets/upcoming_list.py` (nome + total da fila)
- Modify: `src/trackclassifier/ui/widgets/key_chip.py` (nome: "11A" sozinho não diz que é tonalidade)
- Modify: `src/trackclassifier/ui/widgets/metric_block.py` (nome vem do rótulo do bloco)
- Modify: `src/trackclassifier/ui/widgets/class_balance.py` (nomear cada `Meter` por classe)
- Modify: `src/trackclassifier/ui/widgets/guess_bar.py` (nomear o `Meter` da confiança)
- Test: `tests/test_acessibilidade.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: nada consumido por tasks posteriores.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_acessibilidade.py`:

```python
"""Widget pintado a mao nao tem texto: o valor existe so como pixel.

Sem nome e descricao acessiveis, um leitor de tela anuncia a classe do
widget e nada mais. Um teste por widget, e nao uma varredura do pacote: a
heuristica "e QWidget, tem paintEvent, logo precisa de nome" da falso
positivo em todo container.
"""

from tests.test_viewmodel import _config, _servico
from trackclassifier.keys import Key, KeyNotation, Mode
from trackclassifier.ui.viewmodel import library_state
from trackclassifier.ui.widgets.class_balance import ClassBalance
from trackclassifier.ui.widgets.guess_bar import GuessBar
from trackclassifier.ui.widgets.key_chip import KeyChip
from trackclassifier.ui.widgets.metric_block import MetricBlock
from trackclassifier.ui.widgets.upcoming_list import UpcomingList
from trackclassifier.ui.widgets.waveform_view import WaveformView


def test_a_onda_grande_diz_de_que_track_ela_e(qapp, tmp_path):
    servico = _servico(_config(tmp_path))
    linha = library_state(servico).rows[0]
    onda = WaveformView()

    onda.set_row(linha)

    assert onda.accessibleName() == "Onda"
    assert linha.display_title in onda.accessibleDescription()


def test_a_onda_sem_track_nao_promete_track(qapp):
    onda = WaveformView()

    onda.set_row(None)

    assert onda.accessibleDescription() == "sem track"


def test_a_fila_diz_quantas_vem_a_seguir(qapp, tmp_path):
    servico = _servico(_config(tmp_path))
    lista = UpcomingList()

    lista.set_rows(library_state(servico).rows[:3])

    assert lista.accessibleName() == "Proximas da fila"
    assert "3" in lista.accessibleDescription()


def test_o_chip_diz_que_e_tonalidade(qapp):
    chip = KeyChip()

    chip.set_key(Key(11, Mode.MINOR))
    chip.set_notation(KeyNotation.CAMELOT)

    assert chip.accessibleName() == "Tonalidade"


def test_o_bloco_de_metrica_leva_o_proprio_rotulo(qapp):
    bloco = MetricBlock("BPM")

    bloco.set_value("138")

    assert bloco.accessibleName() == "BPM"
    assert bloco.accessibleDescription() == "138"


def test_cada_barra_do_balanco_diz_de_que_classe_e(qapp):
    balanco = ClassBalance()

    balanco.set_counts((5, 9, 2))

    nomes = [barra.accessibleName() for barra in balanco._barras]
    assert nomes == ["Balanco -1", "Balanco neutra", "Balanco +1"]


def test_o_medidor_do_palpite_diz_que_e_confianca(qapp):
    faixa = GuessBar()

    faixa.set_guess("+1", 0.82, low_confidence=False)

    assert faixa.medidor.accessibleName() == "Confianca do palpite"
```

Antes de rodar: conferir a assinatura real de `ClassBalance.set_counts` e o nome do atributo das barras (`self._barras` em `class_balance.py`), e a ordem de `LABELS_EM_ORDEM` (`["-1", "neutra", "+1"]`) — o teste acima assume as duas coisas.

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_acessibilidade.py -v`
Expected: FAIL nos sete, com `assert '' == 'Onda'` e equivalentes.

- [ ] **Step 3: Nomear os widgets**

`waveform_view.py`, dentro de `set_row`, depois de `self._row = row`:

```python
        # A onda inteira e pixel: sem isto um leitor de tela anuncia
        # "WaveformView" e nada mais.
        self.setAccessibleName("Onda")
        self.setAccessibleDescription(row.display_title if row else "sem track")
```

`upcoming_list.py`, dentro de `set_rows`, depois de `self._model.set_rows(list(rows))`:

```python
        self.setAccessibleName("Proximas da fila")
        self.setAccessibleDescription(f"{len(rows)} tracks")
```

`key_chip.py`, no fim do `__init__`, antes de `self._repinta()`:

```python
        # "11A" sozinho nao diz de que grandeza e -- o chip comunica isso
        # pela cor, que um leitor de tela nao le.
        self.setAccessibleName("Tonalidade")
```

`metric_block.py`, no `__init__` (o rótulo já chega como parâmetro):

```python
        self.setAccessibleName(rotulo)
```

e em `set_value`:

```python
        self.setAccessibleDescription(valor or "")
```

`class_balance.py`, onde cada `Meter` é criado no `__init__` (dentro do laço sobre `LABELS_EM_ORDEM`), depois de instanciar a barra:

```python
            # Meter se anuncia como "Medidor"; tres deles em sequencia
            # anunciariam a mesma coisa tres vezes.
            barra.setAccessibleName(f"Balanco {rotulo}")
```

`guess_bar.py`, depois de `self.medidor = Meter(...)`:

```python
        self.medidor.setAccessibleName("Confianca do palpite")
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_acessibilidade.py -v`
Expected: PASS nos sete.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: tudo verde — em especial `tests/test_meter.py`, que afirma o nome "Medidor" do `Meter` genérico (os nomes novos são sobrescritas de quem o usa, não mudança no `Meter`).

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/ tests/test_acessibilidade.py
git commit -m "feat(trackclassifier): nome e valor acessiveis nos widgets pintados"
```

---

### Task 6: A coluna Classificação ganha texto

**Files:**
- Modify: `src/trackclassifier/ui/widgets/track_model.py:135-153` (ramo do `DisplayRole` em `data()`)
- Test: `tests/test_window.py` (acrescentar; é onde os testes do `TrackTableModel` moram)

**Interfaces:**
- Consumes: `TrackRow.label` (rótulo do domínio: `"-1"`, `"neutra"`, `"+1"` ou `None`)
- Produces: `TrackTableModel.data(index_da_classificacao, DisplayRole)` passa a devolver o rótulo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_window.py`:

```python
def test_a_coluna_de_classificacao_tem_texto_para_leitor_de_tela(qapp, tmp_path):
    """DisplayRole, e nao AccessibleTextRole: data() e chamado ~88 mil vezes
    por rolagem da biblioteca real e o proprio codigo documenta que trabalho
    descartado ali custou 9% do tempo de paint. O Qt cai no DisplayRole
    sozinho para o texto acessivel da celula, e este ramo ja existia.

    Visualmente nada muda: _pinta_fundo zera opcao.text e o
    ClassificationDelegate desenha os segmentos por conta propria.
    """
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    textos = {
        modelo.data(modelo.index(i, Column.CLASSIFICACAO), Qt.ItemDataRole.DisplayRole)
        for i in range(modelo.rowCount())
    }

    assert textos <= {"-1", "neutra", "+1", None}
    assert textos & {"-1", "neutra", "+1"}


def test_a_coluna_de_capa_continua_sem_texto(qapp, tmp_path):
    """Uma capa nao carrega informacao que valha anunciar."""
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert (
        modelo.data(modelo.index(0, Column.CAPA), Qt.ItemDataRole.DisplayRole) is None
    )
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `uv run pytest tests/test_window.py -k classificacao_tem_texto -v`
Expected: FAIL — `assert set() & {'-1', 'neutra', '+1'}`, porque hoje a coluna devolve `None`.

- [ ] **Step 3: Devolver o rótulo no ramo que já existe**

Em `src/trackclassifier/ui/widgets/track_model.py`, dentro do bloco do `DisplayRole`, antes do `return None` final:

```python
        if coluna is Column.CLASSIFICACAO:
            # Texto so para quem le por acessibilidade e para a busca: o
            # ClassificationDelegate pinta os segmentos por conta propria e
            # _pinta_fundo zera opcao.text antes de desenhar o fundo, entao
            # nada aparece duas vezes. Aqui dentro do ramo do DisplayRole,
            # e nao num AccessibleTextRole novo -- data() e caminho quente.
            return linha.label
```

Manter o comentário `# Capa e onda sao pintadas pelos delegates.` no `return None` final, ajustado para não mencionar mais a classe.

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_window.py -k "classificacao_tem_texto or capa_continua" -v`
Expected: PASS nos dois.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: tudo verde. Ponto de atenção: `tests/test_library_tab.py` tem testes de busca incremental — a coluna agora casa com o texto digitado, e um teste que conte resultados pode mudar de número. Se mudar, o valor novo é o correto; ajuste o teste e explique no commit.

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/track_model.py tests/test_window.py
git commit -m "feat(trackclassifier): a coluna de classificacao passa a ter texto"
```

---

### Task 7: Medida final e fechamento da pendência (manual)

**Files:**
- Modify: `docs/superpowers/plans/2026-08-07-telas-v02-pendencias.md` (as três pendências saem)

- [ ] **Step 1: Medir de novo, do mesmo jeito**

Run: `uv run dj review`
Repetir exatamente o procedimento da Task 0: aquecer os thumbs numa passada, depois medir o primeiro paint da Biblioteca e a mediana das paradas de rolagem, densidade `comfortable`.

- [ ] **Step 2: Comparar**

Critério: **regressão é acima de 1,5× a medida da Task 0**. Abaixo disso é ruído de máquina, não sinal.

Se regrediu, suspeitos em ordem de custo esperado: o retângulo de fundo da onda (`WaveformDelegate`), a coluna CAPA, o anel de foco (o único acrescentado por este plano — para isolá-lo, comente o corpo de `LibraryTable.paintEvent` depois do `super()` e meça de novo).

- [ ] **Step 3: Apagar o arquivo de pendências**

As três foram fechadas: barra do player (Tasks 1 e 2), anel de foco e teclado (Tasks 3, 4, 5), medição (Tasks 0 e 7).

```bash
git rm docs/superpowers/plans/2026-08-07-telas-v02-pendencias.md
```

Se alguma pendência sobrar de fato — por exemplo, a regressão apareceu e o conserto não cabe aqui —, **não apague o arquivo**: reescreva-o com o que sobrou e os números medidos.

- [ ] **Step 4: Commit com os números crus**

Os números vão na mensagem, não num "medimos e está ok" — é o que permite a próxima pessoa comparar.

```bash
git commit -m "docs(trackclassifier): fecha as pendencias das telas v0.2

Primeiro paint da Biblioteca: <baseline> ms -> <final> ms.
Parada de rolagem: <baseline> ms -> <final> ms.
Referencia de ba53271: 29,5 ms e 5,6 ms com 354 tracks."
```

---

## Ordem e dependências

- Task 0 **antes** da Task 3 — é o que torna o anel isolável na Task 7.
- Task 2 depende da Task 1 (`VolumeRail`).
- Tasks 4, 5 e 6 são independentes entre si e das demais.
- Task 7 depende de tudo.
