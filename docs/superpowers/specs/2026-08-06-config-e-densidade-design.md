# Configuração, primeiro uso e densidade da janela — design

Data: 2026-08-06

## Origem

Três capturas do app rodando mostraram as abas Revisão, Biblioteca e Modelo
todas vazias, com campos e botões desalinhados entre si e um botão `Escanear`
solto fora da faixa da barra de abas.

Uma entrevista curta com o único usuário do app produziu o achado que reordena
a prioridade: **o app nunca rodou com dados reais.** Não é preferência de
layout — é que não existe caminho na interface para apontar as pastas. O
`config.toml` precisa ser escrito à mão, e `load_config` exige que as quatro
pastas já existam. Quem abre o app pela primeira vez não passa daí.

Consequência para este design: a densidade só é tratada onde é defeito
objetivo (alinhamento, margem ausente, botão esticado, componente faltando).
Nenhuma decisão do tipo "esta aba merece mais tela que aquela" entra aqui —
essa escolha depende de uso real que ainda não aconteceu.

### Achados da revisão do build

1. **Portão fechado.** Sem configuração pela interface, o fluxo primário não
   começa.
2. **Nenhuma aba tem empty state.** O que existe é uma frase no canto superior
   esquerdo dentro de um vazio de altura inteira. Como o app abre vazio, esse é
   o rosto dele hoje.
3. **A densidade é defeito medível, não gosto.** Nenhum layout chama
   `setContentsMargins`/`setSpacing`, então tudo herda o default do Qt; o
   seletor `QLabel#SectionLabel` carrega `padding: 12px 8px 6px 8px` e é
   aplicado a cinco widgets dos quais só um é cabeçalho de seção. Daí três
   alinhamentos diferentes na mesma coluna da Revisão. Botões primários entram
   direto num `QVBoxLayout` e esticam à largura da janela.
4. **Um componente specado nunca foi construído.** A spec de 2026-08-05 lista
   `widgets/transport_bar.py` e `widgets/now_playing.py`; nenhum existe. Os
   tokens `size.control`, `size.control_primary`, `size.wave_player` e a regra
   `QWidget#PlayerBar` no QSS estão órfãos. Na prática não há botão de play,
   tempo decorrido nem volume em lugar nenhum — o playback é 100% teclado.
   Metade do vazio da aba Revisão é esse buraco.

Os tokens `size.sidebar` e `QWidget#Sidebar` também estão órfãos, mas são
vestígio do design system de referência: a spec de 2026-08-05 decidiu abas, não
sidebar. **Não** são reintroduzidos.

## Escopo

Dentro:

- Configuração pela interface: 4ª aba `Configuracao` e diálogo de primeiro uso,
  compartilhando um formulário só.
- Escrita do `config.toml` e criação da estrutura de pastas.
- `PlayerBar` na aba Revisão.
- Passe de densidade e empty states nas três abas existentes.

Fora (avaliado e adiado conscientemente):

- Barra única de status unificando `Escanear`, progresso e estado do modelo, com
  a legenda de teclas saindo da tela. Mexe na `MainWindow` inteira e a decisão
  fica melhor depois do app rodar com dados reais.
- Playback na aba Biblioteca.
- Sidebar.

## Configuração

### Escrita do TOML

`config.py` ganha duas funções:

```python
def save_config(path: Path, config: Config) -> None
def read_raw(path: Path) -> dict          # parse sem validar; {} se ausente ou ilegivel
```

`save_config` cria o diretório-pai quando falta — empacotado, o caminho padrão
é `~/.trackclassifier/config.toml` e a pasta pode não existir na primeira
gravação.

`read_raw` existe por causa do caso "config existe mas uma pasta sumiu":
`load_config` levanta `ConfigError` e não devolve nada aproveitável, então o
diálogo não teria com que se preencher. `read_raw` entrega o dicionário cru
para o formulário mostrar os caminhos que o usuário já tinha digitado, com o
erro apontado no campo que falhou. Não substitui `load_config` em lugar
nenhum — não valida nada.

A serialização usa **`tomli-w`** (puro Python, sem dependências transitivas),
não um serializador caseiro. O motivo é concreto: um caminho como
`~/Music/DJ's Tracks` ou qualquer pasta com aspas exige escape correto de
string básica TOML, e um serializador de seis linhas escrito à mão erra isso
uma vez e corrompe o config em silêncio. A dependência entra também no bundle
do PyInstaller, que já carrega pandas e librosa — o custo relativo é nulo.

### Validação, fora do Qt

A validação mora em `config.py` como função pura, não dentro do widget:

```python
@dataclass(frozen=True)
class SettingsDraft:
    """O que o formulario tem digitado, ainda sem garantia de ser valido."""
    inbox: str
    up: str
    neutral: str
    down: str
    data_dir: str
    retrain_every: int
    min_examples: int
    #: True no modo "criar a estrutura": up/neutral/down sao derivados de
    #: `root` e ainda nao existem no disco.
    create_under_root: bool
    root: str

@dataclass(frozen=True)
class SettingsError:
    field: str      # "inbox" | "up" | "neutral" | "down" | "root" | "data_dir"
    message: str

def validate_settings(draft: SettingsDraft) -> list[SettingsError]
def apply_draft(draft: SettingsDraft) -> Config    # cria as pastas do modo raiz
```

`validate_settings` nunca toca no disco além de perguntar se um caminho existe;
quem cria pasta é `apply_draft`, chamada só depois da validação passar. Separar
os dois é o que permite validar a cada tecla digitada no formulário sem criar
pasta a cada tecla digitada.

Isso é o que a torna testável em `test_config.py` sem `QApplication`, e mantém
o formulário responsável só por desenhar. Regras:

- As quatro pastas precisam ser **distintas**. Com `inbox` igual a `neutral`,
  decidir "neutra" mandaria `apply` mover o arquivo para dentro da própria
  pasta; o `os.open(O_CREAT|O_EXCL)` de `_destino_livre` responderia criando um
  duplicado com nome novo, sem erro nenhum. É falha silenciosa, e por isso
  vira validação e não comentário.
- Precisam existir — ou serem criadas, no modo raiz descrito abaixo.
- `data_dir` continua sendo criado quando falta, como já acontece hoje.

### O formulário

`ui/settings_form.py` — `SettingsForm(QWidget)`, sem chrome de diálogo:

- **Inbox**: picker de pasta.
- **Destino**, em dois modos exclusivos:
  - *Usar as minhas pastas*: três pickers (`+1`, `neutra`, `-1`), que podem
    estar em lugares diferentes do disco.
  - *Criar a estrutura*: um picker de raiz; o app cria `+1/`, `neutra/` e
    `-1/` dentro dela. Os nomes vêm do vocabulário que o app já usa na tela e
    nos atalhos `1/2/3`, não de um jargão novo.
- **Avançado**, recolhido: `retrain_every`, `min_examples`, `data_dir`.

Erro de validação aparece ao lado do campo culpado, não numa caixa modal.

### Primeiro uso

O gatilho é a **ausência do arquivo de config**, não uma flag "já abriu antes"
guardada em algum lugar. O mesmo diálogo cobre um segundo caso que hoje é beco
sem saída: config existe mas uma pasta foi apagada ou renomeada — o diálogo
abre preenchido com o que deu para ler e o erro apontado no campo.

`ui/first_run.py` — `FirstRunDialog(QDialog)` = `SettingsForm` + texto de
boas-vindas + `Comecar`. Cancelar fecha o app sem escrever nada.

Ordem em `ui/__main__.py` inverte: hoje `load_config` roda antes do
`QApplication`; um diálogo exige o contrário.

```python
def main(config_path: str = "config.toml") -> int:
    caminho = Path(config_path)
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))

    config = _tenta_carregar(caminho)          # None se ausente ou invalido
    if config is None:
        dialogo = FirstRunDialog(caminho)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return 0
        config = dialogo.config

    janela = MainWindow(TrackService(config))
    janela.show()
    return app.exec()
```

### O que sai de `cli.py`

`_prepara_config_padrao` e `_mostra_erro_grafico` são **removidas**. A primeira
copia o `config.example.toml` com `/Users/SEU_USUARIO/...` dentro, o que
transforma "não tem config" em "config inválido apontando para pastas
fictícias" — diagnóstico pior, não melhor, e agora ativamente atrapalha, porque
esconde do app a única condição que dispara o primeiro uso. A segunda existe só
para exibir o `ConfigError` que o diálogo passa a tratar.

`dj scan` e `dj train` seguem headless, com `ConfigError` no stderr e sem
importar Qt.

### A 4ª aba

`ui/settings_tab.py` — `SettingsTab` = o mesmo `SettingsForm` + `Salvar`. Uma
validação, um formulário, dois pontos de entrada.

Salvar precisa recriar o `TrackService`: mudou pasta ou `data_dir`, mudaram o
cache e o modelo. Isso vira um slot novo:

```python
@Slot(object)
def reload_config(self, config: Config) -> None:
```

Ele constrói o serviço novo **dentro da thread do worker** e re-emite
`states_changed`, mantendo a regra de uma só thread dona do serviço — sem lock,
sem parquet escrito de dois lugares.

Com uma restrição que precisa ser explícita na tela: durante um scan o loop de
eventos da thread do worker está parado dentro de `analyze_all`, então um slot
enfileirado só rodaria quando o scan terminasse. `Salvar` fica **desabilitado
enquanto escaneia**, com o motivo dito ao lado do botão.

## PlayerBar

`ui/widgets/player_bar.py`, com `objectName="PlayerBar"` — a regra do QSS que
já existe passa a ter dono.

Fica **dentro da aba Revisão**, não como rodapé global da janela. A tentação é
o rodapé estilo Spotify, mas só a Revisão tem track corrente: o `Space` é
desabilitado fora dela de propósito, e a Biblioteca não toca nada. Um rodapé
global prometeria playback na Biblioteca — feature que ninguém pediu. Se a
Biblioteca ganhar playback um dia, o componente sobe de lugar sem reescrita.

Conteúdo: play/pause (`SIZE_CONTROL_PRIMARY`), decorrido/total em fonte mono, e
volume. Tudo é ligação de sinal ao `BasePlayer` que a aba já recebe — não há
lógica de reprodução nova. O botão reflete `playing_changed`, então o estado
não dessincroniza quando o playback é acionado pelo `Space`.

## Densidade

Quatro correções nomeadas, não um "dar uma respirada geral":

1. **`#SectionLabel` deixa de ser genérico.** Hoje ele veste cinco widgets e só
   um ("Falhas de analise") é cabeçalho de seção. O padding que faz sentido lá
   é o que joga o aviso e a legenda para fora do alinhamento na Revisão. Nasce
   um `#Hint` sem padding para texto auxiliar; `#SectionLabel` fica só para
   cabeçalho. A edição é em `design/build_tokens.py` com regeneração — o
   `app.qss` é gerado e não se toca à mão.
2. **Toda aba declara `setContentsMargins`/`setSpacing`** a partir dos tokens de
   espaço, em vez de herdar o default do Qt.
3. **`Retreinar` e `Aprovar em bloco` param de esticar.** Botão primário com a
   largura da janela não lê como botão, lê como faixa de fundo.
4. **`Escanear` encaixa na barra de abas.** A causa é específica: como
   `cornerWidget` do `QTabWidget`, o `min-height: 28px` do QSS mais padding e
   borda dão a ele cerca de 42px contra os ~24px da tab bar, e é isso que
   estica a faixa e o faz sobrar para fora. Ganha altura casada com a tab bar e
   `variant="ghost"`. **Continua sendo `cornerWidget`** — promovê-lo a toolbar
   de verdade é a opção adiada no Escopo.

Detalhe pequeno com efeito visível: a capa da Revisão é um `QLabel` de 44×44
fixos que só faz `clear()` quando a track não tem arte — o buraco segue
reservado. Passa a ser escondida.

## Empty states

`ui/widgets/empty_state.py` — título, subtítulo e ação opcional, centralizado
nos dois eixos.

- **Revisão vazia** e **Biblioteca vazia**: botão `Escanear` que dispara o scan
  de verdade, em vez de uma frase mandando o usuário procurar o botão.
- **Modelo não treinado**: o texto e o `Retreinar` deixam de morar no canto
  superior esquerdo.

Na Revisão, o bloco inteiro da track (capa, onda, player, palpite) é escondido
quando não há track. É o `stretch=1` da onda sobre um bloco vazio que hoje
produz o vazio de altura inteira.

## Testes

- `test_config.py`: round-trip `save_config`/`load_config`, incluindo caminho
  com apóstrofo e com acento — o caso que motivou o `tomli-w`; `validate_settings`
  para pastas repetidas, ausentes e para a criação da estrutura na raiz.
- `test_window.py`: config ausente abre o `FirstRunDialog`; config inválido
  abre o diálogo preenchido; `Salvar` desabilitado durante scan.
- `test_worker.py`: `reload_config` troca o serviço e re-emite `states_changed`.
- `test_viewmodel.py`: segue barrando import de Qt — `settings_form.py` não é
  viewmodel, mas a validação que ele consome vive em `config.py`, sem Qt.
- `test_tokens.py`: segue barrando hex literal fora do JSON; o `#Hint` novo
  nasce do JSON como todo o resto.

## Arquivos

```
src/trackclassifier/
  config.py            + save_config, validate_settings, SettingsError
  cli.py               - _prepara_config_padrao, - _mostra_erro_grafico
  ui/
    __main__.py        ordem invertida: QApplication antes de carregar config
    window.py          4a aba, Escanear encaixado, botao de empty state
    review_tab.py      PlayerBar, empty state, capa escondida, margens
    library_tab.py     empty state, margens
    model_tab.py       empty state, botao sem esticar, margens
    settings_form.py   NOVO
    settings_tab.py    NOVO
    first_run.py       NOVO
    worker.py          + reload_config
    widgets/
      player_bar.py    NOVO
      empty_state.py   NOVO
design/
  build_tokens.py      + #Hint, #SectionLabel deixa de ser generico
pyproject.toml         + tomli-w
CLAUDE.md              atualiza a secao do executavel do macOS
```

## Documentação

O `CLAUDE.md` descreve hoje, na seção do executável do macOS, o comportamento
de copiar o `config.example.toml` para `~/.trackclassifier/config.toml` na
primeira execução empacotada, e o `QMessageBox` de erro de config. Este design
remove os dois. A seção é atualizada no mesmo commit — instrução que descreve
código que não existe mais é pior que instrução nenhuma.
