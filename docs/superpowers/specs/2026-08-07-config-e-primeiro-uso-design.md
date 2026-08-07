# Configuração e Primeiro uso — design

Data: 2026-08-07

## Objetivo

Redesenhar a aba Configuração e o diálogo de primeiro uso sobre os tokens v0.2,
tornando visível o que o formulário atual esconde: **as três pastas de destino
não são caminhos de configuração, são para onde os arquivos são fisicamente
movidos.**

`TrackService.decide()` chama `move_to_folder`. É a operação mais consequente do
app — irreversível fora do `undo_last` de um nível — e hoje é configurada num
`QFormLayout` que alinha `inbox`, `up`, `neutral`, `down` e `data_dir` como se
fossem cinco caminhos equivalentes. Quatro são pastas de música, um é cache, e
três recebem arquivos movidos.

As duas telas vão numa spec só porque compartilham o `SettingsForm` inteiro.
Separá-las duplicaria metade do texto e criaria risco de divergência.

Referência visual: `design/mockups/config-primeiro-uso.html`.

Depende de: `docs/superpowers/specs/2026-08-07-linha-instrumento-e-tokens-v02-design.md`
(fases 1 e 2) e da decisão de vocabulário de botão em
`docs/superpowers/specs/2026-08-07-aba-modelo-design.md`.

## O que já existe e este trabalho não pode quebrar

- `ui/settings_tab.py` — `SettingsTab` com o sinal `config_saved(object)`, os
  métodos `set_scanning(bool)`, `salvar()`, `botao_habilitado()`, e a constante
  `_MOTIVO_SCAN`. **Os sinais e a API pública não mudam.**
- `ui/settings_form.py` — `SettingsForm` com `validity_changed(bool)`,
  `set_draft`, `draft()`, `is_valid()`, `show_errors()`, `erro_do_campo()`,
  `campo_visivel()`, `escolher_para_o_teste()`. `_CampoDePasta` recebe o
  callable `escolher_pasta` **injetado** — `QFileDialog.getExistingDirectory`
  abre modal nativa e travaria a suíte. Preservar a injeção.
- O modo raiz: `QCheckBox` que troca entre apontar três pastas existentes e
  criar a estrutura sob uma raiz, escondendo/mostrando linhas via
  `setRowVisible`. Ver o comentário no código para por que `setVisible()` no
  campo sozinho não basta.
- `ui/first_run.py` — `FirstRunDialog`, `_BOAS_VINDAS`, `config()`,
  `confirmar()`.
- `config.py` — `Config(folders, inbox, data_dir, retrain_every, min_examples)`,
  `ConfigError`, `_resolve_dir` que levanta quando a pasta não existe,
  `NOMES_DE_PASTA`.
- Salvar desabilita durante o scan, com o motivo ao lado. Comportamento
  correto, mantido — a thread do serviço está bloqueada dentro de
  `analyze_all` e `reload_config` só rodaria no fim.

## Decisões de design

### A tela conta o fluxo, não lista campos

Quatro seções com cabeçalho mono/caixa alta, na ordem em que o dado percorre o
app:

| Seção | Campos | Papel |
|---|---|---|
| Entrada | `inbox` | De onde vêm tracks novas |
| Destinos | `-1`, `neutra`, `+1` | Para onde o arquivo é **movido** ao classificar |
| Dados do app | `data_dir` | Cache, modelo, capas. Não é pasta de música |
| Modelo | `retrain_every`, `min_examples` | Numéricos, secundários |

Sob o cabeçalho Entrada, uma linha explicando que classificar move o arquivo.
É a informação que o usuário mais precisa antes de apontar as pastas e a que
o formulário atual nunca dá.

### Destinos carregam a cor da classe

Ponto de 7px e rótulo em `classification.<x>.base`, na ordem de `LABEL_ORDER`.
O mapeamento pasta↔classe passa a se explicar sozinho, com a mesma cor que o
usuário já vê no chip da lista e nos alvos da Revisão.

Rótulos usam o vocabulário do domínio (`-1`, `neutra`, `+1`), não os nomes de
chave da config (`down`, `neutral`, `up`) — o usuário nunca vê essas chaves em
nenhum outro lugar do app.

### Contagem de arquivos por pasta

Chip à direita de cada campo válido: `N TRACKS` nos destinos, `N NOVAS` na
inbox, `N ANÁLISES · N MB` no cache. Ancora o campo — "esse caminho é mesmo o
que eu acho?" se responde com um número, não relendo o path.

**Não reutilizar `scan_labeled` para isso.** Ele calcula SHA1 de cada arquivo e
é caro; a contagem só precisa de `Path.iterdir()` filtrando por
`SUPPORTED_SUFFIXES`. Função nova, barata.

Ainda assim é I/O, e o campo revalida a cada tecla digitada. Portanto:
**debounce de ~300ms e execução na thread do serviço**, nunca na thread da GUI.
Enquanto não chegou, o chip fica ausente — não um spinner, não "carregando".

### Validação nova: pastas colididas

Duas ou mais pastas apontando para o mesmo diretório devem invalidar o
formulário.

O caso concreto: se `inbox` e `neutral` coincidem, `decide()` chama
`move_to_folder` para a pasta onde o arquivo já está e `_destino_livre` o
renomeia com sufixo `" (1)"` — corrompe o nome do arquivo em silêncio, sem
erro visível.

Comparar por caminho resolvido (`Path.resolve()`), não pela string digitada:
`~/Music/Tracks` e `/Users/x/Music/Tracks/` são a mesma pasta. O erro aparece
nos dois campos envolvidos, nomeando o outro.

### Primeiro uso é o mesmo formulário, outro enquadramento

Nada de componente duplicado. O que muda:

- Pergunta em destaque (`font.size.large`) mais a frase de `_BOAS_VINDAS`
  reescrita para mencionar que os arquivos são movidos.
- O checkbox de criar estrutura ganha destaque real — card com borda em
  `accent.base`, não uma linha solta no meio do form. É o caminho feliz de
  quem nunca usou o app.
- Com ele marcado, só `inbox` e a raiz ficam visíveis. O comportamento já
  existe; muda só a hierarquia visual.
- Duas ações: `COMEÇAR` (contorno, acento) e `CANCELAR` (contorno neutro).
  Cancelar sai com código 0 — desistir da configuração não é falha, como o
  código já faz.

### Botões seguem o vocabulário fechado na spec da aba Modelo

`SALVAR`, `COMEÇAR`, `CANCELAR`, `ESCOLHER` em `font.family.mono`,
`font.case.label`, `font.tracking.widest`. Tratamento contorno; `ESCOLHER` usa
a variante neutra, não a de acento — há um por campo, e seis botões laranja na
mesma tela anulariam o acento.

## Estados

| Estado | Tratamento |
|---|---|
| Pasta não existe | Campo com borda `state.danger`, chip `NÃO ENCONTRADA`, Salvar desabilitado com o motivo ao lado |
| Pastas colididas | Erro nos dois campos, nomeando o outro |
| Scan em andamento | Salvar desabilitado com `_MOTIVO_SCAN`. Já existe |
| Modo raiz marcado | Destinos ocultos, ajuda listando os nomes que serão criados |
| Config ausente ou ilegível | `FirstRunDialog`, preenchido com o que der para aproveitar. Já existe em `_tenta_carregar` |
| Contagem ainda não computada | Chip ausente. Sem spinner, sem placeholder |
| Pasta vazia | Chip `0 TRACKS` — é válido, não é erro |

## Fora de escopo

- Editar `config.toml` durante o scan. A limitação é arquitetural (o loop de
  eventos da thread do serviço está parado dentro de `analyze_all`) e já está
  tratada com o botão desabilitado e o motivo visível.
- Migrar pastas existentes ao trocar um destino. Trocar o caminho não move
  nada; o próximo scan simplesmente lê de outro lugar. Comportamento atual,
  mantido, mas vale uma linha de ajuda dizendo isso.
- Perfis locais / múltiplas bibliotecas na mesma máquina.

## Testes

- `escolher_pasta` continua injetável; nenhum teste abre `QFileDialog`.
- Colisão: `inbox == neutral` invalida o formulário e `validity_changed(False)`
  é emitido; caminhos equivalentes mas escritos diferente (`~/x` vs `/Users/…/x`,
  com e sem barra final) também colidem.
- A contagem não usa `scan_labeled` — teste que garanta que nenhum SHA1 é
  calculado ao digitar um caminho.
- Debounce: digitar rápido não dispara uma contagem por tecla.
- Modo raiz: alternar esconde e reexibe as linhas certas via `campo_visivel`.
- `set_scanning(True)` desabilita Salvar e mostra `_MOTIVO_SCAN`; `False`
  restaura o estado de validade anterior, não habilita cegamente.
- Rótulos de botão em mono/caixa alta nas duas telas.
