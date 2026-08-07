# Estados de tela (mockup 06) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar os quatro estados do mockup `06-estados` que hoje não existem ou divergem — o empty state do Modelo, a busca sem resultado, a linha tocando e o cabeçalho ordenável — junto com a escala de altura de controles que a revisão expôs.

**Architecture:** Três frentes independentes. O `EmptyState` ganha múltiplas ações com variante, o que destrava o botão neutro do Modelo e os dois botões da busca sem resultado. O cabeçalho da Biblioteca vira uma subclasse de `QHeaderView` que pinta a seção à mão — mesmo padrão de `LibraryTable`, porque o QSS não alcança "coluna ativa" nem a posição da seta. A linha tocando liga `row_states.py` (hoje código morto) aos delegates e, na Task 7, ao player compartilhado.

**Tech Stack:** Python 3.11+, PySide6, pytest com `QT_QPA_PLATFORM=offscreen` (`tests/conftest.py`), uv, ruff.

**Mockup de referência:** `06-estados.html` do pack (bundle React; o template legível sai de `<script type="__bundler/template">`).

## Global Constraints

- **Português sem acentos** em código: variáveis locais, funções internas, comentários, docstrings, mensagens de erro e nomes de teste. API pública (dataclasses, métodos de classe, campos JSON) em inglês.
- Comentários explicam **por que**, não o quê — e são longos quando a decisão não é óbvia.
- **Nenhum literal `#RRGGBB` fora de `design/design-tokens.json`.** `tests/test_tokens.py::test_nenhum_hex_fora_do_json` varre `ui/` linha a linha, docstrings inclusive. Cor sempre via token; cor com alfa via `ui/colors.tinta`.
- `ui/viewmodel.py` não importa Qt (teste gramatical falha se importar).
- `design/build_tokens.py` é a única fonte de `ui/tokens.py` e `ui/app.qss`. Editar os gerados à mão quebra `tests/test_tokens.py::test_arquivos_gerados_estao_em_dia_com_o_json`. Depois de mexer no JSON ou no template: `uv run python design/build_tokens.py`.
- Só a thread do `ServiceWorker` fala com `TrackService`. Widget não chama serviço direto.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` é gate do CI.
- Commits: conventional commits com escopo, ex.: `feat(trackclassifier): ...`.
- Rodar `uv run pytest` inteiro antes de cada commit que toque `ui/` — a suíte leva ~70s e usa ffmpeg de verdade.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `design/design-tokens.json` | **Modificar.** Um token novo: `size.control.accent` = 32 (altura do botão de acento nos mockups 01/05/06). `size.control.primary` (36) continua sendo a altura da **barra** do player, que é quem a lê. |
| `design/build_tokens.py` | **Modificar.** Alturas de controle passam a bater com o total renderizado (Task 1) e o QSS ganha `QHeaderView::section:hover` como fallback. |
| `ui/widgets/empty_state.py` | **Modificar.** Lista de ações com variante em vez de uma ação primária fixa. |
| `ui/widgets/library_header.py` | **Criar.** `LibraryHeader(QHeaderView)` — pinta seção, cor por estado (ativa/hover/inerte) e seta ao lado do rótulo. |
| `ui/library_tab.py` | **Modificar.** Instala o `LibraryHeader`, mantém o cabeçalho na busca sem resultado, monta a copy interpolada e as duas ações. |
| `ui/model_tab.py` | **Modificar.** Empty state de "nenhum exemplo rotulado", com sinal para trocar de aba. |
| `ui/window.py` | **Modificar.** Liga o sinal do Modelo à troca de aba; Task 7 passa o player para a Biblioteca. |
| `ui/widgets/delegates.py` | **Modificar.** `CoverDelegate` desenha ▶; `WaveformDelegate` desenha o playhead. Ambos consultam `row_states`. |
| `ui/widgets/track_model.py` | **Modificar.** Coluna `DURACAO` vira tempo restante em `text.primary` enquanto a track toca. |

---

### Task 1: A escala de altura dos controles bate com os mockups

O `min-height` do Qt Style Sheets vale para o **contents rect**, então soma com padding e borda. Medido sob o `app.qss` de hoje: `QPushButton` primário **50px**, genérico **42px**, `QSpinBox` **43px**, `QLineEdit` **32px**, `QComboBox` **24px**. Os mockups 01, 05 e 06 usam **32** para o botão de acento e **28** para todo o resto.

**Files:**
- Modify: `design/design-tokens.json` (acrescentar `size.control.accent`)
- Modify: `design/build_tokens.py` (helper de subtração da borda + os quatro blocos)
- Modify: `src/trackclassifier/ui/tokens.py` e `src/trackclassifier/ui/app.qss` (**gerados** — nunca à mão)
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: token `SIZE_CONTROL_ACCENT = 32` em `ui/tokens.py`. A Task 2 não o consome (o botão sai do QSS), mas a Task 8 o cita na conferência visual.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/test_tokens.py`:

```python
def test_a_altura_renderizada_dos_controles_bate_com_os_tokens(qapp):
    """min-height no QSS vale para o CONTENTS rect, nao para o widget.

    Sem descontar padding e borda, um botao com min-height 28 renderiza 42.
    Os mockups (01, 05 e 06) usam 32 no botao de acento e 28 no resto, e
    esse numero e o do WIDGET -- e o que o olho mede na tela.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QSpinBox

    from trackclassifier.ui import fonts
    from trackclassifier.ui.tokens import SIZE_CONTROL_ACCENT, SIZE_CONTROL_BASE

    fonts.registra_fontes()
    anterior = QApplication.instance().styleSheet()
    QApplication.instance().setStyleSheet(
        (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")
    )
    try:
        acento = QPushButton("Escanear")
        acento.setProperty("variant", "primary")
        assert acento.sizeHint().height() == SIZE_CONTROL_ACCENT

        for widget in (QPushButton("Limpar"), QLineEdit(), QComboBox(), QSpinBox()):
            assert widget.sizeHint().height() == SIZE_CONTROL_BASE, type(widget).__name__
    finally:
        QApplication.instance().setStyleSheet(anterior)
```

`Path` já não é necessário se `RAIZ` estiver no escopo do módulo — está (`tests/test_tokens.py:8`). Deixe o import local só se o ruff reclamar de nome não usado.

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `uv run pytest tests/test_tokens.py -k altura_renderizada -v`
Expected: FAIL — `ImportError: cannot import name 'SIZE_CONTROL_ACCENT'`.

- [ ] **Step 3: Acrescentar o token**

Em `design/design-tokens.json`, dentro de `size.control`, ao lado de `base` e `primary`:

```json
      "accent": {
        "value": "32px",
        "desc": "Altura do botao de acento (CTA). Distinta de control.primary (36px), que e a altura da BARRA do player -- o unico consumidor dela."
      }
```

Conferir a forma exata das chaves vizinhas antes de colar: o arquivo usa `{"value": ..., "desc": ...}` por folha.

- [ ] **Step 4: Descontar a borda no template do QSS**

Em `design/build_tokens.py`, acrescentar o helper acima de `build_qss`:

```python
def sem_borda(valor: str, borda: int = 2) -> str:
    """'28px' -> '26px'.

    O `min-height` do Qt Style Sheets vale para o CONTENTS rect: o widget
    final soma padding e borda por cima. Para o total bater com o token, o
    valor escrito no QSS tem que ser o token menos as duas bordas de 1px --
    o padding vertical destes blocos e zero de proposito, pelo mesmo motivo.
    """
    return f"{int(valor.removesuffix('px')) - borda}px"
```

E, na chamada de `.format(...)` de `build_qss`, acrescentar:

```python
        controlAccent=t["--size-control-accent"],
        controlSemBorda=sem_borda(t["--size-control-base"]),
        controlAccentSemBorda=sem_borda(t["--size-control-accent"]),
```

`control` e `controlPrimary` continuam existindo — `controlPrimary` segue sendo lido do Python por `player_bar.py`, e `control` continua servindo qualquer bloco que não esteja nesta task.

- [ ] **Step 5: Corrigir os quatro blocos do template**

Em `build_qss`, no bloco `QPushButton`:

```
    padding: 0 {space5};
    min-height: {controlSemBorda};
```

Em `QPushButton[variant="primary"]`, trocar `min-height: {controlPrimary};` por:

```
    padding: 0 20px;
    min-height: {controlAccentSemBorda};
```

O `20px` é literal porque não está na escala de espaço (`space6` é 16, `space7` é 24) e é padding **horizontal** de um controle, não espaçamento de layout. Deixe o comentário dizendo isso, no mesmo tom do resto do template.

Em `QLineEdit`:

```
    padding: 0 {space4};
    min-height: {controlSemBorda};
```

Em `QSpinBox`, trocar `padding: {space2} {space3};` e `min-height: {control};` por:

```
    padding: 0 {space3};
    min-height: {controlSemBorda};
```

E acrescentar um bloco novo para o `QComboBox` (hoje não existe no template — os dois combos da Biblioteca herdam o estilo nativo, que mede 24px):

```
QComboBox {{
    background: {surface2};
    border: 1px solid {borderDefault};
    border-radius: {radiusSm};
    color: {textPrimary};
    padding: 0 {space4};
    min-height: {controlSemBorda};
}}
QComboBox:focus {{ border-color: {accentBase}; }}
```

- [ ] **Step 6: Regerar e revisar o diff**

Run: `uv run python design/build_tokens.py`
Depois: `git diff src/trackclassifier/ui/app.qss src/trackclassifier/ui/tokens.py`
Expected: só as linhas dos cinco blocos e a constante `SIZE_CONTROL_ACCENT` nova.

- [ ] **Step 7: Rodar o teste e ver passar**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS em todos, inclusive `test_arquivos_gerados_estao_em_dia_com_o_json`.

- [ ] **Step 8: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: verde. Ponto de atenção: `tests/test_player_bar.py::test_a_barra_tem_a_altura_de_controle_primario` afirma `barra.height() == SIZE_CONTROL_PRIMARY` — continua valendo, porque `PlayerBar` chama `setFixedHeight` direto do Python e não passa pelo QSS. Se algum teste de janela afirmar altura de botão em pixel, o valor novo é o correto: ajuste e explique no commit.

- [ ] **Step 9: Lint e commit**

```bash
uv run ruff check .
git add design/ src/trackclassifier/ui/tokens.py src/trackclassifier/ui/app.qss tests/test_tokens.py
git commit -m "fix(trackclassifier): altura renderizada dos controles bate com os mockups"
```

---

### Task 2: `EmptyState` aceita mais de uma ação, com variante

Hoje o widget cria no máximo um botão e o força a `variant="primary"`. O mockup pede botão **neutro** no Modelo e **dois** botões neutros na busca sem resultado.

**Files:**
- Modify: `src/trackclassifier/ui/widgets/empty_state.py`
- Modify: `src/trackclassifier/ui/review_tab.py:141-144` e `src/trackclassifier/ui/library_tab.py:129-142` (call sites)
- Test: `tests/test_empty_state.py`

**Interfaces:**
- Produces: `Acao(rotulo: str, variante: str = "primary")` — `NamedTuple` no mesmo módulo.
- Produces: `EmptyState(titulo: str, subtitulo: str = "", acoes: Sequence[Acao] = (), parent=None)`, sinal `acao_clicada(str)` (carrega o rótulo original, **sem** caixa alta), método `acionar(rotulo: str) -> None`, `rotulos_das_acoes() -> tuple[str, ...]`.
- Consumidos pelas Tasks 3 e 4.

O sinal antigo `action_clicked` e o parâmetro `acao` **saem**. Duas APIs para a mesma coisa é pior que um call site a mais para arrumar; são três no total.

- [ ] **Step 1: Reescrever os testes**

Substituir `tests/test_empty_state.py` inteiro:

```python
"""O empty state e o rosto do app: as tres abas abrem vazias."""

import pytest

from trackclassifier.ui.widgets.empty_state import Acao, EmptyState


def test_sem_acao_nao_cria_botao(qapp):
    vazio = EmptyState("Fila vazia")

    assert vazio.rotulos_das_acoes() == ()


def test_com_acao_emite_o_rotulo_ao_clicar(qapp):
    vazio = EmptyState("Fila vazia", "Escaneie a inbox", (Acao("Escanear"),))
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Escanear")

    assert recebidos == ["Escanear"]


def test_duas_acoes_sao_distinguiveis_pelo_rotulo(qapp):
    """A busca sem resultado tem dois botoes; um sinal sem argumento
    obrigaria a aba a adivinhar qual deles foi clicado."""
    vazio = EmptyState(
        "Nada encontrado",
        "",
        (Acao("Limpar busca", "base"), Acao("Filtro: todos", "base")),
    )
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Filtro: todos")

    assert vazio.rotulos_das_acoes() == ("Limpar busca", "Filtro: todos")
    assert recebidos == ["Filtro: todos"]


def test_o_rotulo_do_sinal_nao_leva_a_caixa_alta_da_tela(qapp):
    """O botao mostra ESCANEAR (font.case.label), mas quem escuta compara
    com a string que passou -- caixa alta e apresentacao, nao identidade."""
    vazio = EmptyState("Fila vazia", "", (Acao("Escanear"),))
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Escanear")

    assert recebidos == ["Escanear"]


def test_acionar_rotulo_inexistente_levanta(qapp):
    """Erro de programacao, nao estado possivel de tela: silenciar deixaria
    um botao renomeado parar de funcionar sem ninguem notar."""
    vazio = EmptyState("Fila vazia", "", (Acao("Escanear"),))

    with pytest.raises(KeyError):
        vazio.acionar("Cancelar")


def test_subtitulo_vazio_nao_ocupa_altura(qapp):
    """Um QLabel vazio ainda reserva a altura da linha e desloca o bloco
    centralizado para cima."""
    vazio = EmptyState("Fila vazia")

    assert vazio.subtitulo_visivel() is False


def test_o_subtitulo_aceita_rich_text(qapp):
    """A busca sem resultado destaca o termo e o filtro dentro da frase --
    ver LibraryTab._texto_sem_resultado."""
    vazio = EmptyState("x", "Nada em <b>kernel</b>")

    assert "kernel" in vazio.texto_do_subtitulo()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_empty_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'Acao'`.

- [ ] **Step 3: Reescrever o widget**

`src/trackclassifier/ui/widgets/empty_state.py`:

```python
"""Bloco centralizado para tela sem conteudo.

Existe porque as tres abas abrem vazias -- e uma frase no canto superior
esquerdo dentro de um vazio de altura inteira e o que o app mostrava antes.
A acao opcional e o ponto: "Fila vazia. Use Escanear" manda o usuario
procurar um botao; um botao Escanear aqui dispara o scan.

Sao ACOES no plural, com variante, e nao um botao primario fixo: o mockup
06 pede neutro no Modelo ("Ir para a revisao" nao e a acao principal
daquela tela, e classificar) e DOIS neutros na busca sem resultado. O sinal
carrega o rotulo porque, com dois botoes, um sinal sem argumento obrigaria
a aba a adivinhar qual deles foi clicado.
"""

from typing import NamedTuple, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_4, SPACE_5
from ..typography import estiliza_label


class Acao(NamedTuple):
    rotulo: str
    #: Valor da propriedade dinamica `variant` do QSS. "primary" e o
    #: contorno de acento; "base" e o botao neutro (a ausencia da
    #: propriedade tambem daria neutro, mas nomear e o que deixa a
    #: escolha visivel no call site).
    variante: str = "primary"


class EmptyState(QWidget):
    acao_clicada = Signal(str)

    def __init__(
        self,
        titulo: str,
        subtitulo: str = "",
        acoes: Sequence[Acao] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._titulo = QLabel(titulo)
        self._titulo.setObjectName("TrackTitle")
        self._titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitulo = QLabel(subtitulo)
        self._subtitulo.setObjectName("Hint")
        self._subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # RichText e nao PlainText: a busca sem resultado destaca o termo e
        # o filtro DENTRO da frase, e tres QLabel emendados nao alinham na
        # mesma baseline nem quebram linha juntos.
        self._subtitulo.setTextFormat(Qt.TextFormat.RichText)
        self._subtitulo.setVisible(bool(subtitulo))

        self._botoes: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_5)
        layout.addStretch(1)
        layout.addWidget(self._titulo)
        layout.addWidget(self._subtitulo)

        if acoes:
            faixa = QHBoxLayout()
            faixa.setSpacing(SPACE_4)
            faixa.addStretch(1)
            for acao in acoes:
                botao = QPushButton()
                # Rotulo de botao fala mono/caixa alta no app inteiro -- ver
                # ui/typography.py.
                estiliza_label(botao, acao.rotulo)
                botao.setProperty("variant", acao.variante)
                # O rotulo ORIGINAL viaja no sinal: quem escuta comparou com
                # a string que passou, nao com a versao em caixa alta.
                botao.clicked.connect(
                    lambda _=False, rotulo=acao.rotulo: self.acao_clicada.emit(rotulo)
                )
                self._botoes[acao.rotulo] = botao
                faixa.addWidget(botao)
            faixa.addStretch(1)
            # Os stretches dos dois lados, e nao AlignHCenter: num
            # QVBoxLayout o botao esticaria a largura inteira e leria como
            # faixa de fundo, nao como botao.
            layout.addLayout(faixa)

        layout.addStretch(1)

    def set_texto(self, titulo: str, subtitulo: str = "") -> None:
        self._titulo.setText(titulo)
        self._subtitulo.setText(subtitulo)
        self._subtitulo.setVisible(bool(subtitulo))

    def rotulos_das_acoes(self) -> tuple[str, ...]:
        return tuple(self._botoes)

    def subtitulo_visivel(self) -> bool:
        return not self._subtitulo.isHidden()

    def texto_do_subtitulo(self) -> str:
        return self._subtitulo.text()

    def acionar(self, rotulo: str) -> None:
        """Aciona um botao pelo rotulo. Existe para o teste percorrer o
        mesmo caminho do clique real."""
        self._botoes[rotulo].click()
```

- [ ] **Step 4: Arrumar os dois call sites**

Em `src/trackclassifier/ui/review_tab.py`, trocar o import e o bloco de `self._vazio`:

```python
from .widgets.empty_state import Acao, EmptyState
```

```python
        self._vazio = EmptyState(VAZIO_TITULO, VAZIO_SUBTITULO, (Acao("Escanear"),))
        self._vazio.acao_clicada.connect(lambda _rotulo: self.scan_requested.emit())
```

E `acionar_empty_state`, na superfície de teste:

```python
    def acionar_empty_state(self) -> None:
        self._vazio.acionar("Escanear")
```

Em `src/trackclassifier/ui/library_tab.py`, o mesmo para `self._vazio` (o `self._sem_resultado` é reescrito inteiro na Task 3 — aqui basta trocar a assinatura para `EmptyState("Nenhuma track encontrada", "Nenhuma track casa com a busca ou o filtro.")`, sem ações, para o módulo continuar importando):

```python
from .widgets.empty_state import Acao, EmptyState
```

```python
        self._vazio = EmptyState(
            "Nenhuma track analisada",
            "Escaneie a inbox para popular a biblioteca.",
            (Acao("Escanear"),),
        )
        self._vazio.acao_clicada.connect(lambda _rotulo: self.scan_requested.emit())
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_empty_state.py -v`
Expected: PASS nos sete.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: verde. Falhas esperadas aqui: qualquer teste que use `action_clicked` ou `EmptyState(..., acao=...)` — `grep -rn "action_clicked\|acionar_empty_state" tests/ src/` antes de rodar e ajustar tudo o que aparecer.

- [ ] **Step 7: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/empty_state.py src/trackclassifier/ui/review_tab.py src/trackclassifier/ui/library_tab.py tests/
git commit -m "feat(trackclassifier): empty state aceita varias acoes com variante"
```

---

### Task 3: Busca sem resultado — cabeçalho fica, copy diz o que foi buscado

Três desvios de uma vez: hoje `self._table.setVisible(False)` derruba o cabeçalho junto; a copy é genérica; e não há ação nenhuma. O mockup mantém a barra de busca **e** o cabeçalho de coluna, diz o termo e o filtro dentro da frase, informa o tamanho da biblioteca e o escopo da busca, e oferece dois botões neutros.

**Files:**
- Modify: `src/trackclassifier/ui/library_tab.py` (`_reaplica_filtros`, montagem do `_sem_resultado`, dois slots novos)
- Test: `tests/test_library_tab.py`

**Interfaces:**
- Consumes: `Acao` e `EmptyState.acao_clicada` da Task 2.
- Produces: `LibraryTab._texto_sem_resultado() -> tuple[str, str]` (título, subtítulo em rich text) — usado só internamente e pelos testes.

- [ ] **Step 1: Escrever os testes que falham**

O arquivo já tem `_aba_com(n_linhas: int, altura_viewport: int = 140)` e `_linha(indice)` (linhas 22 e 39). Todas as linhas de `_linha` têm `label="+1"` e `title=None`, então o filtro "+1" sozinho nunca zera o resultado — os testes abaixo combinam sempre um termo impossível com o filtro.

Acrescentar a `tests/test_library_tab.py`:

```python
#: Termo que nao casa com nenhum `_linha`, cujo filename e "track0000.wav".
_IMPOSSIVEL = "nao-existe-nenhuma-track-com-isso"


def test_a_busca_sem_resultado_mantem_o_cabecalho(qapp):
    """Biblioteca vazia e busca sem resultado sao estados diferentes: na
    segunda o usuario ainda esta DENTRO da tabela, e esconder o cabecalho
    junto com as linhas apaga a referencia de onde ele esta."""
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)

    assert aba._sem_resultado.isVisibleTo(aba)
    assert aba._table.isVisibleTo(aba)
    assert aba._table.maximumHeight() == aba._table.horizontalHeader().height()


def test_a_biblioteca_vazia_esconde_a_tabela_inteira(qapp):
    """Sem nenhuma track nao ha coluna que valha mostrar."""
    aba = LibraryTab()
    aba.set_state(LibraryState(rows=()))

    assert aba._vazio.isVisibleTo(aba)
    assert not aba._table.isVisibleTo(aba)


def test_a_copy_sem_resultado_cita_o_termo_e_o_filtro(qapp):
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)
    aba._filtro.setCurrentText("+1")
    titulo, subtitulo = aba._texto_sem_resultado()

    assert _IMPOSSIVEL in titulo
    assert "+1" in titulo
    assert "5" in subtitulo
    assert "nome do arquivo" in subtitulo


def test_sem_filtro_a_copy_nao_inventa_filtro(qapp):
    """'Todos' e a ausencia de filtro; cita-lo faria o usuario procurar um
    filtro que ele nao ligou."""
    aba = _aba_com(5)

    aba._busca.setText(_IMPOSSIVEL)
    titulo, _ = aba._texto_sem_resultado()

    assert "Todos" not in titulo


def test_sem_termo_a_copy_fala_so_do_filtro(qapp):
    aba = _aba_com(5)

    aba._filtro.setCurrentText("-1")
    titulo, _ = aba._texto_sem_resultado()

    assert "-1" in titulo
    assert "Nada em" not in titulo


def test_limpar_busca_devolve_as_linhas(qapp):
    aba = _aba_com(5)
    aba._busca.setText(_IMPOSSIVEL)

    aba._sem_resultado.acionar("Limpar busca")

    assert aba._busca.text() == ""
    assert aba._table.isVisibleTo(aba)
    assert not aba._sem_resultado.isVisibleTo(aba)


def test_a_acao_de_filtro_volta_para_todos(qapp):
    aba = _aba_com(5)
    aba._busca.setText(_IMPOSSIVEL)
    aba._filtro.setCurrentText("-1")

    aba._sem_resultado.acionar("Filtro: todos")

    assert aba._filtro.currentText() == "Todos"
```

**Um teste existente muda de resposta.** `test_busca_sem_resultado_tem_estado_proprio` (linha 224) termina com `assert not aba._table.isVisibleTo(aba)` — é exatamente o comportamento que esta task corrige. Trocar a última linha por:

```python
    # A tabela CONTINUA na tela, encolhida ate o cabecalho: o usuario ainda
    # esta dentro dela. Ver test_a_busca_sem_resultado_mantem_o_cabecalho.
    assert aba._table.isVisibleTo(aba)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_library_tab.py -k sem_resultado -v`
Expected: FAIL — `AttributeError: 'LibraryTab' object has no attribute '_texto_sem_resultado'`.

- [ ] **Step 3: Montar o empty state novo**

Em `src/trackclassifier/ui/library_tab.py`, acrescentar aos imports de tokens:

```python
from .tokens import (
    COLOR_ACCENT_TEXT,
    COLOR_TEXT_PRIMARY,
    FONT_FAMILY_MONO,
    SIZE_ART_ROW_COMFORTABLE,
    ...
)
```

Duas constantes de módulo, junto de `_ROTULO_DENSIDADE`:

```python
#: Rotulos das duas acoes da busca sem resultado. Constante porque o
#: EmptyState devolve o rotulo no sinal e a aba compara por igualdade --
#: duas strings soltas divergiriam na primeira renomeacao.
_LIMPAR_BUSCA = "Limpar busca"
_FILTRO_TODOS = "Filtro: todos"

#: Valor do combo que significa "sem filtro". Ja aparecia solto em
#: _reaplica_filtros; virou constante para as duas leituras nao divergirem.
_TODOS = "Todos"
```

Substituir o bloco de `self._sem_resultado`:

```python
        # Diferente da biblioteca vazia: aqui a busca continua na tela e o
        # usuario esta DENTRO da tabela. As duas acoes existem porque o
        # mockup 06 as pede -- e porque, com filtro ligado, apagar o termo
        # sozinho nao traz nada de volta.
        self._sem_resultado = EmptyState(
            "",
            "",
            (Acao(_LIMPAR_BUSCA, "base"), Acao(_FILTRO_TODOS, "base")),
        )
        self._sem_resultado.acao_clicada.connect(self._acao_sem_resultado)
        self._sem_resultado.setVisible(False)
```

Os dois slots, junto de `_muda_notacao`:

```python
    def _acao_sem_resultado(self, rotulo: str) -> None:
        if rotulo == _LIMPAR_BUSCA:
            # setText dispara textChanged, que ja chama _reaplica_filtros.
            self._busca.setText("")
        elif rotulo == _FILTRO_TODOS:
            self._filtro.setCurrentText(_TODOS)

    def _texto_sem_resultado(self) -> tuple[str, str]:
        """(titulo, subtitulo em rich text) da busca sem resultado.

        Separado de _reaplica_filtros para o teste ler a copy sem depender
        de o widget estar visivel. O destaque do termo e do filtro e rich
        text porque tres QLabel emendados nao alinham na mesma baseline nem
        quebram linha juntos.
        """
        termo = self._busca.text().strip()
        rotulo = self._filtro.currentText()
        mono = f"font-family:{FONT_FAMILY_MONO}"
        partes = []
        if termo:
            partes.append(f'Nada em <span style="{mono};color:{COLOR_TEXT_PRIMARY}">{termo}</span>')
        if rotulo != _TODOS:
            ligacao = "com o filtro" if partes else "Nada com o filtro"
            partes.append(
                f'{ligacao} <span style="{mono};color:{COLOR_ACCENT_TEXT}">{rotulo}</span>'
            )
        titulo = " ".join(partes) if partes else "Nada encontrado"
        subtitulo = (
            f"{len(self._todas)} tracks na biblioteca. "
            "A busca cobre titulo, artista e nome do arquivo."
        )
        return titulo, subtitulo
```

O título carrega o rich text, porque é ele que vai em cima — o mockup põe a frase destacada na primeira linha (12px) e o contexto na segunda (11px, `text.muted`). Então o `EmptyState` da Task 2 precisa de `self._titulo.setTextFormat(Qt.TextFormat.RichText)` ao lado do que já foi feito no subtítulo, mais um teste gêmeo do `test_o_subtitulo_aceita_rich_text`:

```python
def test_o_titulo_aceita_rich_text(qapp):
    """A busca sem resultado destaca o termo dentro da PRIMEIRA linha."""
    vazio = EmptyState("Nada em <b>kernel</b>")

    assert "kernel" in vazio.texto_do_titulo()
```

com o acessor correspondente no widget:

```python
    def texto_do_titulo(self) -> str:
        return self._titulo.text()
```

- [ ] **Step 4: Manter o cabeçalho em `_reaplica_filtros`**

Substituir o bloco final de `_reaplica_filtros` (a partir do comentário "Tres estados distintos"):

```python
        # Tres estados distintos, nao dois. Biblioteca vazia oferece
        # escanear; busca sem resultado NAO -- escanear nao traria de volta
        # o que o filtro escondeu. A diferenca visivel vai alem da copy: na
        # busca sem resultado a tabela CONTINUA na tela, encolhida ate o
        # cabecalho, porque o usuario ainda esta dentro dela e as colunas
        # sao a referencia de onde ele esta.
        vazia = not self._todas
        sem_resultado = bool(self._todas) and not linhas

        self._vazio.setVisible(vazia)
        self._sem_resultado.setVisible(sem_resultado)
        if sem_resultado:
            titulo, subtitulo = self._texto_sem_resultado()
            self._sem_resultado.set_texto(titulo, subtitulo)
        self._table.setVisible(not vazia)
        # QWIDGETSIZE_MAX e o "sem teto" do Qt; None nao existe nesta API.
        self._table.setMaximumHeight(
            self._table.horizontalHeader().height() if sem_resultado else QWIDGETSIZE_MAX
        )
```

`QWIDGETSIZE_MAX` vem de `from PySide6.QtWidgets import QWIDGETSIZE_MAX`. Se a constante não estiver exposta nessa versão do PySide6, use `16777215` com um comentário dizendo que é o valor do Qt — confirme com `python -c "from PySide6.QtWidgets import QWIDGETSIZE_MAX; print(QWIDGETSIZE_MAX)"` antes de escolher.

E no `__init__`, o `_sem_resultado` deixa de ter stretch próprio disputando com a tabela:

```python
        layout.addLayout(barra)
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._table)
        layout.addWidget(self._sem_resultado, 1)
```

A ordem importa: com a tabela encolhida ao cabeçalho, a mensagem tem que vir **abaixo** dele, como no mockup.

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_library_tab.py -v`
Expected: PASS. Os testes de busca incremental que já existem continuam valendo — nenhum deles afirma visibilidade da tabela; se algum afirmar, o valor novo é o correto.

- [ ] **Step 6: Rodar a suíte inteira e conferir com os olhos**

Run: `uv run pytest`

Depois, screenshot offscreen: monte a `LibraryTab` com linhas, digite um termo impossível, `widget.grab().save(...)` e compare com o painel "Busca sem resultado" do mockup. Confira em especial que o cabeçalho aparece inteiro e que a mensagem não colou nele.

- [ ] **Step 7: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/library_tab.py src/trackclassifier/ui/widgets/empty_state.py tests/
git commit -m "feat(trackclassifier): busca sem resultado mantem o cabecalho e diz o que foi buscado"
```

---

### Task 4: Empty state do Modelo — nenhum exemplo rotulado

Dois estados, não um. **Zero exemplos** é o empty state do mockup, com ação para a Revisão. **Tem exemplos mas nunca treinou** continua sendo o `sem_treino` de hoje, dentro do card de métricas — trocar um pelo outro faria a tela dizer "nenhum exemplo rotulado" com cinco exemplos na mão, o que é falso.

**Files:**
- Modify: `src/trackclassifier/ui/model_tab.py`
- Modify: `src/trackclassifier/ui/window.py` (liga o sinal à troca de aba)
- Test: `tests/test_model_tab.py`, `tests/test_window.py`

**Interfaces:**
- Consumes: `Acao` e `EmptyState.acao_clicada` da Task 2; `ModelState.n_examples`.
- Produces: `ModelTab.review_requested` (`Signal()`), `ModelTab.vazio_visivel() -> bool`.

- [ ] **Step 1: Escrever os testes que falham**

O arquivo já tem `estado(**mudancas)` (sem underscore, linha 21), que parte de um `BASE` treinado. Acrescentar a `tests/test_model_tab.py`:

```python
def test_sem_exemplo_nenhum_a_aba_e_so_o_empty_state(qapp):
    """Cards de metrica, matriz e balanco com zero em tudo nao informam
    nada -- so ocupam a tela com estrutura vazia."""
    aba = ModelTab()

    aba.set_state(estado(n_examples=0, class_counts=(0, 0, 0), accuracy=None, confusion=None))

    assert aba.vazio_visivel() is True
    assert aba.conteudo_visivel() is False


def test_com_exemplos_e_sem_treino_o_empty_state_nao_aparece(qapp):
    """Estado diferente: ha o que aprender, so nao treinou ainda. Quem
    responde por ele e o `sem_treino` dentro do card de metricas."""
    aba = ModelTab()

    aba.set_state(estado(n_examples=5, class_counts=(2, 2, 1), accuracy=None, confusion=None))

    assert aba.vazio_visivel() is False
    assert aba.conteudo_visivel() is True
    assert aba.sem_treino.isVisibleTo(aba)


def test_o_botao_do_empty_state_pede_a_revisao(qapp):
    aba = ModelTab()
    aba.set_state(estado(n_examples=0, class_counts=(0, 0, 0), accuracy=None, confusion=None))
    recebidos = []
    aba.review_requested.connect(lambda: recebidos.append(True))

    aba.acionar_empty_state()

    assert recebidos == [True]
```

`isVisibleTo(aba)` e não `isVisible()`: sem `show()` na janela, `isVisible()` é `False` para tudo em `QT_QPA_PLATFORM=offscreen` — é o padrão que `tests/test_library_tab.py` já usa.

E a `tests/test_window.py`:

```python
def test_o_empty_state_do_modelo_leva_para_a_revisao(qapp, tmp_path):
    """O botao promete uma tela; sem a troca de aba ele so emite um sinal
    que ninguem escuta."""
    janela = MainWindow(_servico(_config(tmp_path)))
    try:
        janela.tabs.setCurrentWidget(janela.model_tab)

        janela.model_tab.review_requested.emit()

        assert janela.tabs.currentWidget() is janela.review_tab
    finally:
        janela.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_model_tab.py -v`
Expected: FAIL — `AttributeError: 'ModelTab' object has no attribute 'vazio_visivel'`.

- [ ] **Step 3: Montar o empty state na aba**

Em `src/trackclassifier/ui/model_tab.py`, acrescentar aos imports:

```python
from .widgets.empty_state import Acao, EmptyState
```

No `__init__`, envolver tudo o que existe hoje num container e pôr o empty state ao lado:

```python
    train_requested = Signal()
    #: Pedido de ir para a aba Revisao. A aba nao troca de aba sozinha: quem
    #: e dona do QTabWidget e a MainWindow, e um widget que mexe no pai
    #: acopla os dois na direcao errada.
    review_requested = Signal()
```

```python
        # Tudo que so faz sentido com exemplo rotulado vira um widget so --
        # mesmo movimento de ReviewTab._bloco. Com zero exemplos, tres cards
        # zerados nao informam nada: so ocupam a tela com estrutura vazia.
        self._conteudo = QWidget()
        interno = QVBoxLayout(self._conteudo)
        interno.setContentsMargins(0, 0, 0, 0)
        interno.setSpacing(SPACE_5)
        interno.addLayout(faixa_cards)
        interno.addWidget(self._faixa_acao())
        interno.addWidget(self.falhas, 1)
        interno.addWidget(self._faixa_detalhe())

        self._vazio = EmptyState(
            "Nenhum exemplo rotulado",
            "Classifique tracks na Revisao para o modelo ter o que aprender.",
            # Neutro, e nao acento: a acao principal desta tela e retreinar,
            # e o botao de acento ja e dela. Aqui o botao so aponta o
            # caminho -- o trabalho acontece na outra aba.
            (Acao("Ir para a revisao", "base"),),
        )
        self._vazio.acao_clicada.connect(lambda _rotulo: self.review_requested.emit())
        self._vazio.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._conteudo, 1)
```

No topo de `set_state`:

```python
        # n_examples, e nao class_counts: sao a mesma informacao aqui, mas
        # n_examples e o campo que nomeia a condicao ("nenhum exemplo
        # rotulado") e nao depende da ordem das classes.
        vazio = state.n_examples == 0
        self._vazio.setVisible(vazio)
        self._conteudo.setVisible(not vazio)
        if vazio:
            # Nada abaixo daqui tem o que mostrar, e set_confusion/
            # set_counts com tudo zerado so repintariam widgets escondidos.
            return
```

E a superfície de teste, no fim da classe:

```python
    # ---- superficie de teste --------------------------------------------

    def vazio_visivel(self) -> bool:
        return not self._vazio.isHidden()

    def conteudo_visivel(self) -> bool:
        return not self._conteudo.isHidden()

    def acionar_empty_state(self) -> None:
        self._vazio.acionar("Ir para a revisao")
```

- [ ] **Step 4: Ligar o sinal na janela**

Em `src/trackclassifier/ui/window.py`, dentro de `_conecta()`, junto das outras ligações das abas:

```python
        self.model_tab.review_requested.connect(
            lambda: self.tabs.setCurrentWidget(self.review_tab)
        )
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_model_tab.py tests/test_window.py -k "modelo or empty or exemplo" -v`
Expected: PASS.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: verde. Ponto de atenção: testes de `test_model_tab.py` que leem `aba.exemplos.text()` ou `aba.matriz` com estado zerado agora encontram widgets escondidos — `isVisible()` vira `False`, mas o texto continua lá. Se algum afirmar visibilidade, o valor novo é o correto.

- [ ] **Step 7: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/model_tab.py src/trackclassifier/ui/window.py tests/
git commit -m "feat(trackclassifier): empty state de nenhum exemplo rotulado na aba Modelo"
```

---

### Task 5: Cabeçalho ordenável fala v0.2

Três coisas que o QSS não alcança: a coluna ativa acende (`text.primary`), as outras acendem só no hover (`text.secondary`), e a seta fica **ao lado do rótulo** — o Qt nativo a desenha na borda direita da seção, o que na coluna Título (que é `Stretch`) a joga a ~80px do texto. Verificado com protótipo: `paintSection` sobrescrito resolve os três de uma vez.

**Files:**
- Create: `src/trackclassifier/ui/widgets/library_header.py`
- Modify: `src/trackclassifier/ui/library_tab.py:192-206` (`_monta_tabela`)
- Modify: `design/build_tokens.py` + gerados (fallback `:hover` para qualquer outro header)
- Test: `tests/test_library_header.py`

**Interfaces:**
- Consumes: tokens `COLOR_SURFACE_0`, `COLOR_TEXT_PRIMARY`, `COLOR_TEXT_SECONDARY`, `COLOR_TEXT_MUTED`, `COLOR_BORDER_DEFAULT`, `SPACE_3`, `SPACE_4`; `ui.colors.para_qcolor`.
- Produces: `LibraryHeader(parent: QWidget | None = None)`, subclasse de `QHeaderView` horizontal, com `secao_sob_o_mouse() -> int` e `ALINHAMENTO: dict[int, Qt.AlignmentFlag]`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_library_header.py`:

```python
"""O cabecalho ordenavel: a coluna ativa acende, as outras so no hover.

Testes de imagem comparam DOIS estados entre si, nunca contra cor absoluta:
a cor exata sai do token e o teste nao pode virar uma segunda copia dele.
"""

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QImage

from trackclassifier.ui.widgets.library_header import LibraryHeader
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel


def _cabecalho(qapp) -> LibraryHeader:
    from PySide6.QtWidgets import QTableView

    tabela = QTableView()
    cabecalho = LibraryHeader(tabela)
    tabela.setHorizontalHeader(cabecalho)
    tabela.setModel(TrackTableModel([]))
    tabela.resize(1180, 60)
    for coluna in Column:
        tabela.setColumnWidth(coluna, coluna.width)
    cabecalho._tabela_para_teste = tabela  # mantem viva
    return cabecalho


def _imagem(cabecalho: LibraryHeader) -> QImage:
    imagem = QImage(cabecalho.size(), QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#000000"))
    cabecalho.render(imagem)
    return imagem


def test_a_coluna_ordenada_e_pintada_diferente_das_outras(qapp):
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)
    por_titulo = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.AscendingOrder)
    por_bpm = _imagem(cabecalho)

    assert por_titulo != por_bpm


def test_ascendente_e_descendente_desenham_setas_diferentes(qapp):
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.AscendingOrder)
    subindo = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.DescendingOrder)
    descendo = _imagem(cabecalho)

    assert subindo != descendo


def test_o_hover_acende_a_coluna_sob_o_mouse(qapp):
    cabecalho = _cabecalho(qapp)
    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)

    sem_hover = _imagem(cabecalho)
    cabecalho.marca_hover(int(Column.BPM))
    com_hover = _imagem(cabecalho)

    assert cabecalho.secao_sob_o_mouse() == int(Column.BPM)
    assert sem_hover != com_hover


def test_sair_do_cabecalho_apaga_o_hover(qapp):
    cabecalho = _cabecalho(qapp)
    cabecalho.marca_hover(int(Column.BPM))

    cabecalho.leaveEvent(QEvent(QEvent.Type.Leave))

    assert cabecalho.secao_sob_o_mouse() == -1


def test_a_onda_nao_recebe_seta_nem_acende(qapp):
    """TrackTableModel.sort retorna cedo para Onda e Capa -- um indicador
    ali prometeria uma ordenacao que nao acontece."""
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)
    antes = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.WAVEFORM, Qt.SortOrder.AscendingOrder)
    depois = _imagem(cabecalho)

    assert antes == depois
```

O último teste é o mais forte do arquivo: ele fixa que clicar em Onda não muda nada na tela, que é o que `TrackTableModel.sort` já promete no dado.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_library_header.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets.library_header'`.

- [ ] **Step 3: Escrever o cabeçalho**

Criar `src/trackclassifier/ui/widgets/library_header.py`:

```python
"""Cabecalho da tabela da Biblioteca, pintado a mao.

Tres coisas do mockup 06 que o Qt Style Sheets nao alcanca:

- **A coluna ativa acende.** Nao ha seletor de "secao ordenada" no QSS.
  `setHighlightSections(True)` acende a secao CLICADA, que nao e a mesma
  coisa: depois de um reset de modelo a ordenacao continua e o destaque
  some.
- **O hover.** `QHeaderView::section:hover` existe, mas so alcanca a secao
  inteira -- e aqui o hover muda a cor do TEXTO, que ja e pintado aqui.
  Deixar metade no QSS e metade no paint deixaria as duas cores mudando em
  arquivos diferentes.
- **A posicao da seta.** O estilo nativo desenha o indicador na borda
  direita da secao. Na coluna Titulo, que e `Stretch`, isso a joga a ~80px
  do rotulo -- o mockup a quer a 6px dele.

Mesmo movimento de `library_table.py`: o que o QSS nao alcanca vira
`paintEvent`/`paintSection` num lugar so, com token, e nao cinco delegates
emendando retangulos.
"""

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPolygon
from PySide6.QtWidgets import QHeaderView, QWidget

from ..colors import para_qcolor
from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_SURFACE_0,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    SPACE_3,
    SPACE_4,
)

#: Colunas sem ordem natural. Espelha o early-return de
#: `TrackTableModel.sort` -- se as duas listas divergirem, o cabecalho
#: promete uma ordenacao que o modelo nao faz. Por indice, e nao por
#: `Column`, para este modulo nao importar track_model (que importa
#: delegates, que ja e um ciclo apertado).
SEM_ORDEM = (0, 2)  # Column.CAPA, Column.WAVEFORM

#: Lado do triangulo da seta, em px. Nao vem da escala de espaco: e a
#: dimensao de um glifo desenhado, do mesmo tipo que SIZE_WAVE_BAR.
_LADO_SETA = 7


class LibraryHeader(QHeaderView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._hover = -1
        # Sem isto o Qt so entrega mouseMoveEvent com botao apertado, e o
        # hover do cabecalho so apareceria durante um arrasto.
        self.setMouseTracking(True)
        self.setSectionsClickable(True)
        # O destaque nativo da secao clicada seria uma SEGUNDA nocao de
        # "coluna ativa", concorrendo com a do indicador de ordenacao.
        self.setHighlightSections(False)

    # ---- hover ----------------------------------------------------------

    def secao_sob_o_mouse(self) -> int:
        return self._hover

    def marca_hover(self, secao: int) -> None:
        """Publico para o teste nao precisar sintetizar QMouseEvent com
        coordenada, que depende da largura real das colunas."""
        if secao == self._hover:
            return
        anterior, self._hover = self._hover, secao
        for alvo in (anterior, secao):
            if alvo >= 0:
                self.updateSection(alvo)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().mouseMoveEvent(event)
        self.marca_hover(self.logicalIndexAt(event.position().toPoint()))

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().leaveEvent(event)
        self.marca_hover(-1)

    # ---- pintura --------------------------------------------------------

    def _cor_do_texto(self, logical: int):
        if logical == self.sortIndicatorSection() and logical not in SEM_ORDEM:
            return para_qcolor(COLOR_TEXT_PRIMARY)
        if logical == self._hover and logical not in SEM_ORDEM:
            return para_qcolor(COLOR_TEXT_SECONDARY)
        return para_qcolor(COLOR_TEXT_MUTED)

    def paintSection(  # noqa: N802 (assinatura do Qt)
        self, painter: QPainter, rect: QRect, logical: int
    ) -> None:
        # Nao chama super(): o desenho nativo traria o texto na cor da
        # paleta e a seta na borda direita, e os dois teriam que ser
        # cobertos depois. Pintar do zero e menos codigo e nao depende da
        # ordem em que o estilo desenha.
        painter.save()
        painter.fillRect(rect, para_qcolor(COLOR_SURFACE_0))
        painter.fillRect(
            QRect(rect.left(), rect.bottom(), rect.width(), 1),
            para_qcolor(COLOR_BORDER_DEFAULT),
        )

        texto = str(
            self.model().headerData(logical, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            or ""
        )
        cor = self._cor_do_texto(logical)
        # A fonte vem do widget: familia, tamanho e tracking ja foram
        # aplicados por ui/typography.aplica_tracking na aba.
        painter.setFont(self.font())
        painter.setPen(cor)

        alinhamento = ALINHAMENTO.get(logical, Qt.AlignmentFlag.AlignLeft)
        interno = rect.adjusted(SPACE_4, 0, -SPACE_4, 0)
        metricas = painter.fontMetrics()
        largura = metricas.horizontalAdvance(texto)

        if alinhamento & Qt.AlignmentFlag.AlignRight:
            x_texto = interno.right() - largura
        elif alinhamento & Qt.AlignmentFlag.AlignHCenter:
            x_texto = interno.center().x() - largura // 2
        else:
            x_texto = interno.left()

        painter.drawText(
            QRect(x_texto, interno.top(), largura, interno.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            texto,
        )

        if logical == self.sortIndicatorSection() and logical not in SEM_ORDEM:
            self._desenha_seta(painter, x_texto + largura + SPACE_3, interno, cor)
        painter.restore()

    def _desenha_seta(self, painter: QPainter, x: int, interno: QRect, cor) -> None:
        """Triangulo cheio a SPACE_3 do fim do rotulo.

        Apontando para BAIXO em ordem crescente: a leitura e "a lista corre
        deste valor para baixo a partir do topo", que e a mesma convencao do
        mockup (a seta descendente e a mesma girada 180 graus).
        """
        meio = interno.center().y()
        topo = meio - _LADO_SETA // 3
        base = meio + _LADO_SETA // 3
        if self.sortIndicatorOrder() is Qt.SortOrder.AscendingOrder:
            pontos = [QPoint(x, base), QPoint(x + _LADO_SETA, base), QPoint(x + _LADO_SETA // 2, topo)]
        else:
            pontos = [QPoint(x, topo), QPoint(x + _LADO_SETA, topo), QPoint(x + _LADO_SETA // 2, base)]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cor)
        painter.drawPolygon(QPolygon(pontos))
        painter.restore()


#: Alinhamento do rotulo por coluna, espelhando o TextAlignmentRole do
#: TrackTableModel: cabecalho desalinhado do dado obriga o olho a procurar
#: a qual numero cada rotulo pertence. Por indice pelo mesmo motivo de
#: SEM_ORDEM.
ALINHAMENTO = {
    4: Qt.AlignmentFlag.AlignRight,   # Column.BPM
    5: Qt.AlignmentFlag.AlignHCenter,  # Column.KEY
    6: Qt.AlignmentFlag.AlignHCenter,  # Column.CLASSIFICACAO
    7: Qt.AlignmentFlag.AlignRight,   # Column.DURACAO
}
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_library_header.py -v`
Expected: PASS nos cinco.

- [ ] **Step 5: Instalar na aba**

Em `src/trackclassifier/ui/library_tab.py`, `_monta_tabela`, **antes** de aplicar as larguras (trocar o header reseta as seções):

```python
        cabecalho = LibraryHeader(tabela)
        tabela.setHorizontalHeader(cabecalho)
        # O tracking do micro-label nao vem do QSS (que nao tem
        # letter-spacing) -- ver o docstring de ui/typography.py.
        aplica_tracking(cabecalho)
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setSectionResizeMode(Column.TITULO, QHeaderView.ResizeMode.Stretch)
        for coluna in Column:
            if coluna is not Column.TITULO:
                tabela.setColumnWidth(coluna, coluna.width)
```

`setHighlightSections(False)` sai daqui — passou a ser responsabilidade do `LibraryHeader.__init__`. Import: `from .widgets.library_header import LibraryHeader`.

- [ ] **Step 6: Fallback no QSS**

Em `design/build_tokens.py`, acrescentar depois do bloco `QHeaderView::section`:

```
QHeaderView::section:hover {{ color: {textSecondary}; }}
```

Vale para qualquer header que não seja o da Biblioteca (hoje nenhum — `UpcomingList` esconde o dele). Existe para o próximo não nascer sem hover.

Run: `uv run python design/build_tokens.py`

- [ ] **Step 7: Rodar a suíte e conferir com os olhos**

Run: `uv run pytest`

Depois, screenshot offscreen da `LibraryTab` com linhas, em três estados: ordenada por Título ascendente, por BPM descendente, e com hover em Gênero (`aba._table.horizontalHeader().marca_hover(int(Column.GENERO))`). Comparar com o painel "Cabecalho ordenavel" do mockup: a coluna ativa em `text.primary`, as outras em `text.muted`, a com hover em `text.secondary`, a seta colada no rótulo.

- [ ] **Step 8: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/library_header.py src/trackclassifier/ui/library_tab.py design/ src/trackclassifier/ui/app.qss tests/test_library_header.py
git commit -m "feat(trackclassifier): cabecalho ordenavel com coluna ativa, hover e seta ao lado do rotulo"
```

---

### Task 6: A linha tocando — os três sinais

> **Dependência dura:** esta task só faz sentido junto com a Task 7. `row_states.py` foi criado na fase 2 e nunca consumido — hoje só `tests/test_row_states.py` o importa. Parar aqui repetiria exatamente esse erro, com mais código morto. Se a Task 7 for cortada, **corte esta também** e registre a lacuna.

O mockup é explícito sobre o escopo: *"A linha tocando muda tres coisas: ▶ sobre a capa, playhead branco na onda e a duracao vira tempo restante em text.primary. Nada de cor nova — tocar nao e classe."* O fundo `surface.2` com barra de acento que aparece no mockup é o tratamento de **seleção** que já existe — não é um terceiro fundo.

**Files:**
- Modify: `src/trackclassifier/ui/widgets/delegates.py` (`CoverDelegate`, `WaveformDelegate`)
- Modify: `src/trackclassifier/ui/widgets/track_model.py` (coluna `DURACAO` + `ForegroundRole`)
- Test: `tests/test_delegates.py`, `tests/test_window.py`

**Interfaces:**
- Consumes: `estado_da_linha(row, *, sha1_tocando, motivo_da_falha) -> EstadoDaLinha` de `ui/widgets/row_states.py` (já existe, não muda).
- Produces: `CoverDelegate.set_tocando(sha1: str | None) -> None`.
- Produces: `WaveformDelegate.set_tocando(sha1: str | None, fracao: float) -> None`.
- Produces: `TrackTableModel.set_tocando(sha1: str | None, restante_s: float) -> None`.
- Os três são chamados por `LibraryTab.set_tocando` na Task 7.

- [ ] **Step 1: Escrever os testes que falham**

O arquivo já tem `_pinta(delegate, index, selecionado: bool) -> QImage` (linha 29) e `_modelo(tmp_path) -> TrackTableModel` (linha 45). Todos os testes de pintura comparam duas imagens entre si, nunca contra cor absoluta — a cor sai do token e o teste não pode virar uma segunda cópia dele. Acrescentar a `tests/test_delegates.py`:

```python
def test_a_capa_da_linha_tocando_muda_de_pintura(qapp, tmp_path):
    """Um triangulo de play sobre a capa."""
    from trackclassifier.ui.widgets.delegates import CoverDelegate

    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.CAPA)
    delegate = CoverDelegate()

    parada = _pinta(delegate, index, False)
    delegate.set_tocando(modelo.row_at(0).sha1)
    tocando = _pinta(delegate, index, False)

    assert parada != tocando


def test_so_a_linha_que_toca_ganha_o_play(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import CoverDelegate

    modelo = _modelo(tmp_path)
    outro = modelo.index(1, Column.CAPA)
    delegate = CoverDelegate()

    delegate.set_tocando(modelo.row_at(0).sha1)
    com_outra_tocando = _pinta(delegate, outro, False)
    delegate.set_tocando(None)
    parada = _pinta(delegate, outro, False)

    assert com_outra_tocando == parada


def test_a_onda_da_linha_tocando_ganha_playhead(qapp, tmp_path):
    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.WAVEFORM)
    delegate = WaveformDelegate()

    parada = _pinta(delegate, index, False)
    delegate.set_tocando(modelo.row_at(0).sha1, 0.46)
    tocando = _pinta(delegate, index, False)

    assert parada != tocando


def test_o_playhead_anda_com_a_fracao(qapp, tmp_path):
    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.WAVEFORM)
    sha1 = modelo.row_at(0).sha1
    delegate = WaveformDelegate()

    delegate.set_tocando(sha1, 0.10)
    cedo = _pinta(delegate, index, False)
    delegate.set_tocando(sha1, 0.90)
    tarde = _pinta(delegate, index, False)

    assert cedo != tarde


def test_a_linha_que_falhou_nao_vira_tocando(qapp, tmp_path):
    """Precedencia de row_states: FALHOU > TOCANDO. Nao da para tocar o que
    nao decodifica, e esconder a falha atrasaria a descoberta."""
    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.WAVEFORM)
    sha1 = modelo.row_at(0).sha1
    delegate = WaveformDelegate()
    delegate.registrar_falha(sha1, "ffmpeg nao encontrado")

    delegate.set_tocando(sha1, 0.5)
    com_falha = _pinta(delegate, index, False)
    delegate.set_tocando(None, 0.0)
    sem_tocar = _pinta(delegate, index, False)

    assert com_falha == sem_tocar
```

E a `tests/test_window.py`, junto dos testes de `TrackTableModel`:

```python
def test_a_duracao_da_linha_tocando_vira_tempo_restante(qapp, tmp_path):
    """Contagem regressiva, e nao duracao total: com a track tocando, o que
    o DJ precisa saber e quanto falta para o proximo mix."""
    servico = _servico(_config(tmp_path))
    linhas = list(library_state(servico).rows)
    modelo = TrackTableModel(linhas)

    modelo.set_tocando(linhas[0].sha1, 201.0)

    tocando = modelo.data(modelo.index(0, Column.DURACAO), Qt.ItemDataRole.DisplayRole)
    parada = modelo.data(modelo.index(1, Column.DURACAO), Qt.ItemDataRole.DisplayRole)
    assert tocando == "-3:21"
    assert not parada.startswith("-")


def test_so_a_linha_tocando_tem_duracao_em_text_primary(qapp, tmp_path):
    servico = _servico(_config(tmp_path))
    linhas = list(library_state(servico).rows)
    modelo = TrackTableModel(linhas)

    modelo.set_tocando(linhas[0].sha1, 201.0)

    assert modelo.data(modelo.index(0, Column.DURACAO), Qt.ItemDataRole.ForegroundRole) is not None
    assert modelo.data(modelo.index(1, Column.DURACAO), Qt.ItemDataRole.ForegroundRole) is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_delegates.py -k tocando -v`
Expected: FAIL — `AttributeError: 'CoverDelegate' object has no attribute 'set_tocando'`.

- [ ] **Step 3: O ▶ sobre a capa**

Em `src/trackclassifier/ui/widgets/delegates.py`, acrescentar aos imports:

```python
from ..colors import tinta
from ..tokens import COLOR_WAVEBAND_PLAYHEAD
from .row_states import EstadoDaLinha, estado_da_linha
```

E, no `CoverDelegate.__init__`:

```python
        #: sha1 da track que o player esta tocando, ou None. Vem de fora
        #: (LibraryTab.set_tocando) porque o delegate nao tem -- e nao deve
        #: ter -- acesso ao player.
        self._tocando: str | None = None
```

```python
    def set_tocando(self, sha1: str | None) -> None:
        """Quem chama repinta o viewport. Sem clear_cache: o play e um
        overlay desenhado por cima da miniatura, e a miniatura em si nao
        muda -- invalidar o LRU aqui redecodificaria a capa a cada segundo
        de reproducao."""
        self._tocando = sha1
```

No fim de `CoverDelegate.paint`, depois do `painter.restore()` que fecha o desenho da miniatura:

```python
        if estado_da_linha(
            linha, sha1_tocando=self._tocando, motivo_da_falha=None
        ) is not EstadoDaLinha.TOCANDO:
            return

        # Veu escuro sob o triangulo: sobre uma capa clara, um play branco
        # sem contraste some. tinta() e a unica forma de cor com alfa aqui
        # -- ver a constraint de hex do repositorio.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tinta(COLOR_TEXT_INVERSE, 0.55))
        painter.drawRoundedRect(arte, float(RADIUS_SM), float(RADIUS_SM))

        lado = max(1, arte.width() // 3)
        meio = arte.center()
        painter.setBrush(QColor(COLOR_WAVEBAND_PLAYHEAD))
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(meio.x() - lado // 2, meio.y() - lado // 2),
                    QPoint(meio.x() - lado // 2, meio.y() + lado // 2),
                    QPoint(meio.x() + lado // 2, meio.y()),
                ]
            )
        )
        painter.restore()
```

Imports adicionais no topo: `QPoint` de `PySide6.QtCore` e `QPolygon` de `PySide6.QtGui`.

Confirmar a assinatura de `tinta` em `ui/colors.py` antes de usar (`tinta(hex: str, alfa: float) -> QColor`); se divergir, ajuste a chamada, **não** escreva um hex com alfa à mão.

- [ ] **Step 4: O playhead na onda da linha**

No `WaveformDelegate.__init__`:

```python
        #: (sha1, fracao 0..1) da track tocando. A fracao nao entra na chave
        #: do cache de pixmap de proposito: o playhead e desenhado POR CIMA
        #: do pixmap, e incluir a posicao na chave geraria um pixmap novo a
        #: cada quadro -- 60 renders de onda por segundo.
        self._tocando: str | None = None
        self._fracao = 0.0
```

```python
    def set_tocando(self, sha1: str | None, fracao: float) -> None:
        """Quem chama repinta o viewport."""
        self._tocando = sha1
        self._fracao = min(1.0, max(0.0, fracao))
```

No fim de `WaveformDelegate.paint`, depois do `drawPixmap`:

```python
        if estado_da_linha(
            linha, sha1_tocando=self._tocando, motivo_da_falha=motivo
        ) is not EstadoDaLinha.TOCANDO:
            return

        # 1px branco cheio, a mesma marca da onda grande da Revisao
        # (waveform_view.py). Sem arredondar para dentro da caixa: o
        # playhead em 1.0 tem que encostar na borda direita, nao sumir.
        x = rect.left() + min(rect.width() - 1, round(rect.width() * self._fracao))
        painter.save()
        painter.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()
```

O `motivo` já está calculado acima no método — o `return` do ramo de falha acontece antes, então este trecho só roda para linhas sem falha; passar `motivo` mesmo assim mantém a precedência explícita e sobrevive a uma reordenação futura do método.

- [ ] **Step 5: A duração vira tempo restante**

Em `src/trackclassifier/ui/widgets/track_model.py`, no `__init__`:

```python
        #: (sha1, segundos restantes) da track tocando. A coluna DURACAO nao
        #: tem delegate -- e pintada pelo Qt a partir do DisplayRole -- entao
        #: o "-3:21" e a cor saem daqui, e nao de codigo de pintura.
        self._tocando: str | None = None
        self._restante_s = 0.0
```

```python
    def set_tocando(self, sha1: str | None, restante_s: float) -> None:
        """Emite dataChanged so na coluna DURACAO.

        Reset de modelo aqui perderia a selecao a cada segundo de
        reproducao -- o mesmo motivo de set_notation nao resetar.
        """
        anterior = self._tocando
        self._tocando = sha1
        self._restante_s = max(0.0, restante_s)
        if not self._rows:
            return
        if anterior == sha1 and sha1 is None:
            return
        self.dataChanged.emit(
            self.index(0, Column.DURACAO),
            self.index(len(self._rows) - 1, Column.DURACAO),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole],
        )
```

No `data()`, antes do `if role != Qt.ItemDataRole.DisplayRole:`:

```python
        if role == Qt.ItemDataRole.ForegroundRole:
            # Unico uso do role no modelo: a duracao da linha tocando sobe
            # de text.primary (o default herdado da paleta) para o branco
            # cheio do playhead -- "este numero esta andando".
            if (
                Column(index.column()) is Column.DURACAO
                and self._rows[index.row()].sha1 == self._tocando
            ):
                return QColor(COLOR_WAVEBAND_PLAYHEAD)
            return None
```

E, no ramo do `DisplayRole`, substituir o de `DURACAO`:

```python
        if coluna is Column.DURACAO:
            # Contagem regressiva com o sinal explicito: "3:21" e "-3:21"
            # na mesma coluna precisam se distinguir sem cor, para quem le
            # por leitor de tela.
            if linha.sha1 == self._tocando:
                return f"-{format_duration(self._restante_s)}"
            return format_duration(linha.duration_s)
```

Imports novos no topo: `from PySide6.QtGui import QColor` e `from ..tokens import COLOR_WAVEBAND_PLAYHEAD`.

- [ ] **Step 6: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_delegates.py tests/test_window.py -k "tocando or restante" -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: verde. Ponto de atenção: `tests/test_window.py` tem testes que leem a coluna `DURACAO` — nenhum deles põe track tocando, então o formato antigo continua saindo.

- [ ] **Step 8: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/widgets/delegates.py src/trackclassifier/ui/widgets/track_model.py tests/
git commit -m "feat(trackclassifier): os tres sinais da linha tocando na tabela"
```

---

### Task 7: Tocar a partir da Biblioteca

Sem isto a Task 6 é código inalcançável. Hoje o player é privado da Revisão (`window.py:51` cria, `ReviewTab` recebe) e a Biblioteca não toca nada.

**Decisão de produto, explícita:** o player é **um só**. Dar play numa linha da Biblioteca troca o que estava carregado da Revisão. É o comportamento de um app de uma janela e uma saída de áudio; a alternativa (dois players) daria dois áudios simultâneos.

**Files:**
- Modify: `src/trackclassifier/ui/library_tab.py` (recebe o player, duplo-clique, `set_tocando`)
- Modify: `src/trackclassifier/ui/window.py:52` (passa o player para a `LibraryTab`)
- Test: `tests/test_library_tab.py`

**Interfaces:**
- Consumes: `CoverDelegate.set_tocando`, `WaveformDelegate.set_tocando`, `TrackTableModel.set_tocando` da Task 6.
- Consumes: `BasePlayer.load(path: Path, duracao_ms: int)`, `.play()`, `.position_changed`, `.duration_ms` de `ui/widgets/player.py` (confirmar os nomes exatos antes de escrever — `review_tab.py:269-270` e `:295-299` são a referência viva).
- Produces: `LibraryTab(player, parent=None)` — a assinatura muda; `window.py` é o único call site fora dos testes.

- [ ] **Step 1: Escrever os testes que falham**

Primeiro, `_aba_com` passa a receber o player (é o helper de todo o arquivo):

```python
def _aba_com(
    n_linhas: int, altura_viewport: int = 140, player=None
) -> LibraryTab:
    ...
    aba = LibraryTab(player or SimulatedPlayer())
```

com `from trackclassifier.ui.widgets.player import SimulatedPlayer` no topo. O resto do helper fica igual.

Os testes novos:

```python
def test_duplo_clique_toca_a_linha(qapp):
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)

    aba.toca_linha(0)

    # is_playing e property em BasePlayer, nao metodo.
    assert player.is_playing is True
    assert aba._model._tocando == aba._model.row_at(0).sha1


def test_a_posicao_do_player_move_o_playhead_da_linha(qapp):
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)
    aba.toca_linha(0)

    # _linha tem duration_s=180.0, entao 30s e ~1/6 da track.
    aba._atualiza_tocando(30_000)

    assert 0.0 < aba._waveform_delegate._fracao <= 1.0


def test_trocar_de_track_solta_a_anterior(qapp):
    """Duas linhas com play ao mesmo tempo seria mentira: o player e um so."""
    player = SimulatedPlayer()
    aba = _aba_com(5, player=player)

    aba.toca_linha(0)
    aba.toca_linha(1)

    assert aba._model._tocando == aba._model.row_at(1).sha1
```

`SimulatedPlayer.load` ignora o conteúdo do caminho (só guarda a duração em ms), então o `path_hint` inexistente de `_linha` não é problema — mas `play()` retorna cedo se a duração for zero, e por isso `toca_linha` tem que passar `int(linha.duration_s * 1000)` no `load`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_library_tab.py -k "toca or playhead" -v`
Expected: FAIL — `TypeError: LibraryTab.__init__() got an unexpected keyword argument 'player'`.

- [ ] **Step 3: A aba recebe o player**

Em `src/trackclassifier/ui/library_tab.py`:

```python
    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._player.position_changed.connect(self._atualiza_tocando)
        self._tocando: str | None = None
```

Na montagem da tabela:

```python
        tabela.doubleClicked.connect(lambda index: self.toca_linha(index.row()))
```

Duplo-clique, e não clique simples: clique simples já seleciona, e tocar a cada seleção transformaria navegar pela lista com as setas numa sequência de tracks começando e parando.

Os dois métodos:

```python
    def toca_linha(self, indice: int) -> None:
        linha = self._model.row_at(indice)
        if linha is None:
            return
        self._tocando = linha.sha1
        # Path aqui e nao no viewmodel: ui/viewmodel.py e a fronteira de
        # dados puros -- mesmo motivo de review_tab.py:269.
        self._player.load(Path(linha.path_hint), int(linha.duration_s * 1000))
        self._player.play()
        self._propaga_tocando(0.0, linha.duration_s)

    def _atualiza_tocando(self, posicao_ms: int) -> None:
        linha = next(
            (l for l in self._todas if l.sha1 == self._tocando), None  # noqa: E741
        )
        if linha is None:
            return
        duracao_ms = self._player.duration_ms
        fracao = posicao_ms / duracao_ms if duracao_ms > 0 else 0.0
        self._propaga_tocando(fracao, max(0.0, linha.duration_s - posicao_ms / 1000))

    def _propaga_tocando(self, fracao: float, restante_s: float) -> None:
        """Um lugar so avisa os tres. Cada delegate guardando o proprio
        sha1 por caminhos diferentes e como as quatro definicoes de
        'pendente' que row_states.py existe para evitar."""
        self._cover_delegate.set_tocando(self._tocando)
        self._waveform_delegate.set_tocando(self._tocando, fracao)
        self._model.set_tocando(self._tocando, restante_s)
        self._table.viewport().update()
```

`from pathlib import Path` no topo.

- [ ] **Step 4: A janela passa o player**

Em `src/trackclassifier/ui/window.py`:

```python
        self.library_tab = LibraryTab(self._player)
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `uv run pytest tests/test_library_tab.py -v`
Expected: PASS. Todo teste que hoje faz `LibraryTab()` precisa passar um `SimulatedPlayer()` — ajuste todos de uma vez.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: verde. `grep -rn "LibraryTab(" tests/ src/` antes, para não sobrar call site.

- [ ] **Step 7: Lint e commit**

```bash
uv run ruff check .
git add src/trackclassifier/ui/library_tab.py src/trackclassifier/ui/window.py tests/
git commit -m "feat(trackclassifier): duplo clique toca a linha na Biblioteca"
```

---

### Task 8: Ver com os próprios olhos

Nenhum teste deste plano compara contra o mockup — todos comparam estados entre si. Esta task é a única que olha.

**Files:**
- Modify: `docs/superpowers/plans/2026-08-07-estados-de-tela.md` (registrar o que destoou)

- [ ] **Step 1: Screenshot dos quatro estados**

Script offscreen (`QT_QPA_PLATFORM=offscreen`, `app.setStyleSheet(app.qss)`, `fonts.registra_fontes()` antes de tudo), largura **1180** — a mesma do mockup:

1. `LibraryTab` com zero linhas → empty state da Biblioteca.
2. `ReviewTab` sem track → empty state da Revisão.
3. `ModelTab` com `n_examples=0` → empty state do Modelo.
4. `LibraryTab` com linhas + termo de busca impossível → busca sem resultado.
5. `LibraryTab` ordenada por Título asc, por BPM desc, e com hover em Gênero.
6. `LibraryTab` com `toca_linha(0)` e `_atualiza_tocando` em ~46% → linha tocando.

- [ ] **Step 2: Comparar item a item com `06-estados.html`**

Checklist do mockup, na ordem em que ele apresenta:

- [ ] Empty state: título 12px medium `text.primary`, subtítulo 11px `text.muted`, gap 12px, bloco centrado nos dois eixos.
- [ ] Botão de acento com **32px** de altura (Task 1) e o neutro com 28px.
- [ ] Busca sem resultado: barra de busca **e** cabeçalho na tela; termo em mono `text.primary`; filtro em mono `accent.text`; contagem da biblioteca no subtítulo; dois botões neutros.
- [ ] Linha tocando: ▶ sobre a capa, playhead branco de 1px na onda, duração como `-M:SS` em branco cheio. **Nenhuma cor nova** — se apareceu, é bug.
- [ ] Cabeçalho: ativa `text.primary`, hover `text.secondary`, inertes `text.muted`, seta a 6px do rótulo, Onda sem seta.

- [ ] **Step 3: Medir o paint da Biblioteca**

A linha tocando acrescenta dois desenhos por linha e um `dataChanged` por quadro do player. Referência de `ba53271`: **29,5 ms** no primeiro paint e **5,6 ms** por parada de rolagem, com 354 tracks. Critério de regressão: acima de **1,5×**. Medir com uma track tocando e a Biblioteca aberta — é o pior caso que este plano cria.

- [ ] **Step 4: Registrar aqui o que destoou**

Escrever a seção "Como foi verificado" no fim deste arquivo, no mesmo formato do plano da fase 2 — incluindo os bugs achados só olhando, que é o que aquela seção pegou da última vez.

**Como foi verificado:** script offscreen descartavel (nao commitado — `QT_QPA_PLATFORM=offscreen`,
`fonts.registra_fontes()` e `app.setStyleSheet(app.qss)` antes de qualquer widget), largura
**1180**, a mesma do mockup. Seis estados renderizados a partir do codigo real: `LibraryTab`
vazia, `ReviewTab` vazia, `ModelTab` vazia (`n_examples=0`), `LibraryTab` com 5 linhas + termo de
busca impossivel + filtro `-1`, `LibraryTab` com 12 linhas ordenada por Titulo asc / BPM desc /
hover em Genero, e `LibraryTab` com `toca_linha(0)` + `_atualiza_tocando(82_800)` (46% de uma
track de 180s via `SimulatedPlayer`). Cada PNG foi olhado, e os pontos mais finos — cor do
cabecalho, cor da duracao, posicao do playhead — tambem foram amostrados pixel a pixel com
`QImage.pixel()`, para nao depender so do olho numa imagem de 1180px de largura.

**Nenhum bug achado so olhando.** As sete tasks anteriores fecharam a lacuna com o mockup sem
deixar residuo visual:

- **Empty states** (Biblioteca, Revisao, Modelo): titulo 12px peso 500 em `#E4EAF0`
  (`QLabel#TrackTitle` nao sobrescreve tamanho — herda os 12px do `QWidget` base do QSS;
  `font-weight:500` esta explicito na regra), subtitulo 11px em `#5C6672` (`QLabel#Hint`), gap de
  12px (`SPACE_5` no `QVBoxLayout`), bloco centrado nos dois eixos dentro da area livre abaixo da
  barra de busca/atalhos. Botao de acento (Biblioteca e Revisao) mede **32px** de altura
  (`QPushButton.sizeHint()` confirmado programaticamente, igual a `SIZE_CONTROL_ACCENT`); botao
  neutro do Modelo mede **28px** (igual a `SIZE_CONTROL_BASE`).
- **Busca sem resultado:** barra de busca e cabecalho de coluna continuam na tela, tabela
  encolhida ate a altura do cabecalho; titulo em rich text com o termo em mono `#E4EAF0` e o
  filtro em mono `#FFA582` ("Nada em nao-existe-nenhuma-track-com-isso com o filtro -1");
  subtitulo com a contagem da biblioteca ("5 tracks na biblioteca. A busca cobre titulo, artista e
  nome do arquivo."); dois botoes neutros LIMPAR BUSCA / FILTRO: TODOS.
- **Linha tocando:** os tres sinais e so eles. A amostragem de pixel confirmou: duracao da linha
  tocando em `#fdfdfd` (branco cheio — antialiasing de `COLOR_WAVEBAND_PLAYHEAD`), duracao das
  linhas paradas em `#e4eaf0` (`text.primary`, a cor normal — nenhuma mudanca ali); playhead na
  onda numa coluna correspondente a fracao 0,464 para uma chamada com fracao 0,46; triangulo de
  play visivel sobre a capa da linha 0 e ausente nas demais. Nenhum fundo ou borda novos: o
  retangulo de fundo da linha tocando saiu pixel-identico ao das linhas vizinhas.
- **Cabecalho ordenavel:** amostragem de pixel com BPM ativo (desc) e Genero em hover deu
  exatamente `CAPA`/`TITULO`/`ONDA`/`KEY`/`CLASSE`/`DUR` = `#5c6672` (muted), `GENERO` (hover) =
  `#9ba7b4` (secondary), `BPM` (ativo) = `#e4eaf0` (primary) — as tres cores batem literalmente
  com os tokens, nao so "parecem parecidas". A seta muda de direcao entre asc/desc e fica colada
  ao rotulo (nasce em `x_texto + largura + SPACE_3`, ou seja, 6px, direto no codigo). Onda: forcar
  `sortIndicator` para `Column.WAVEFORM` produziu uma imagem pixel a pixel identica a de Titulo
  ordenado — nenhuma seta, nenhum realce.

**O que bateu:** tudo o que o checklist do Step 2 pedia, sem excecao — os cinco itens acima.

**Perf: aproximada, nao comparavel 1:1 com `ba53271`, e o motivo importa.** `ba53271` mediu
29,5 ms no primeiro paint e 5,6 ms por parada de rolagem com 354 tracks **reais** (capas em disco,
tags lidas). Aqui, 354 `TrackRow` **sinteticas** (sem capa em disco, sem peaks) com uma tocando
(`toca_linha(0)` + `_atualiza_tocando(80_000)`) deram 3,3 ms no primeiro repaint do viewport e
3,3 ms de media em 5 paradas de rolagem simuladas (10/30/50/70/90% da scrollbar) — 0,11× e 0,59×
da referencia, bem abaixo do teto de 1,5×, mas os numeros absolutos nao sao comparaveis: faltam os
dois custos que dominam o original, decodificar/cachear a capa do disco e ler os buckets de onda
reais. O que da para afirmar do **codigo**, e nao da medicao: os dois desenhos novos por linha
tocando (triangulo sobre a capa em `CoverDelegate.paint`, linha de 1px em
`WaveformDelegate.paint`) sao `QPainter.drawPolygon`/`drawLine`, baratos comparados ao
`drawPixmap` que ja acontecia antes; e o `dataChanged` por quadro emitido por
`set_tocando(sha1, restante_s)` atinge so a coluna `DURACAO`
(`dataChanged.emit(index(0, DURACAO), index(N-1, DURACAO), ...)`), nao a linha inteira. A medicao
real com a biblioteca do usuario continua pendente, como ja registrado na fase 2 — risco aberto,
nao item fechado.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-07-estados-de-tela.md
git commit -m "docs(trackclassifier): registro da conferencia visual dos estados de tela"
```

---

## Ordem e dependências

- **Task 1** antes de tudo: as outras tasks conferem altura de botão com o olho na Task 8.
- **Task 2** antes das Tasks 3 e 4 (as duas consomem `Acao`/`acao_clicada`).
- **Task 3** e **Task 4** são independentes entre si.
- **Task 5** é independente de todas as outras.
- **Task 6 e Task 7 andam juntas.** Task 6 sozinha é código inalcançável — o defeito exato que `row_states.py` já tem hoje. Se a Task 7 não for feita, corte a Task 6 e apague `row_states.py` + `tests/test_row_states.py` num commit próprio, documentando a lacuna.
- **Task 8** depende de tudo.

## Divergências conhecidas do mockup, aceitas

- **`Titulo · Artista` vs `Titulo · artista`.** O mockup escreve o "A" maiúsculo; o app usa `texto_de_label()`, que sobe tudo para caixa alta. Renderizado, os dois são idênticos. Nada a fazer.
- **Coluna Capa não ordena.** O mockup só menciona Onda, mas Capa também não tem ordem natural e `TrackTableModel.sort` já retorna cedo para ela desde a fase 2. `SEM_ORDEM` no `LibraryHeader` mantém as duas alinhadas.
- **`size.control.primary` (36px) continua existindo** e não é a altura de botão nenhum — é a altura da barra do player, lida direto do Python por `player_bar.py`. Renomeá-la para `size.control.player` seria mais honesto e é uma limpeza para outro dia.
