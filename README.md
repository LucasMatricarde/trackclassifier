# TrackClassifier

Um assistente pessoal pra DJ organizar musica nova. Ele aprende do seu jeito
de classificar as faixas e, quando chega musica nova na pasta de downloads,
ja sugere se ela sobe a pista, e neutra, ou desce a pista -- pra voce so
confirmar ou corrigir.

## Como funciona, em resumo

Voce ja mantem (ou vai criar) tres pastas de musica: uma pra faixas que
"sobem a pista" (`+1`), uma pra faixas neutras, e uma pra faixas que "descem
a pista" (`-1`). O TrackClassifier escuta essas pastas, aprende o padrao por
tras das suas escolhas e passa a sugerir, sozinho, onde cada faixa nova
deveria entrar.

O app toca a faixa, mostra a onda, o BPM e a tonalidade, e traz a sugestao;
voce confirma ou corrige com um toque de tecla. Cada correcao ja realimenta o
aprendizado, e o app fica melhor com o tempo.

## Baixar

[**Baixar TrackClassifier (macOS)**](https://github.com/LucasMatricarde/trackclassifier/releases/latest/download/TrackClassifier-latest-macos.zip)

[**Baixar TrackClassifier (Windows)**](https://github.com/LucasMatricarde/trackclassifier/releases/latest/download/TrackClassifier-latest-windows.zip)

O link baixa direto a versao mais recente, em `.zip`. Depois de baixar:
descompacte e abra `TrackClassifier.app` (macOS) ou `TrackClassifier.exe`
dentro da pasta `TrackClassifier` (Windows).

O download tem cerca de 330 MB no macOS e 460 MB no Windows: o app traz o seu
proprio navegador embutido, entao nao depende de nada instalado na maquina.

No macOS, da segunda vez em diante o proprio app avisa quando tem atualizacao
nova (e voce pode pedir em **TrackClassifier > Buscar atualizacoes...**). No Windows ainda nao tem esse aviso -- pra atualizar, baixe o `.zip`
novo por este mesmo link e substitua a pasta.

### Na primeira vez que for abrir (macOS)

O macOS vai bloquear com uma mensagem tipo "'TrackClassifier' Not
Opened -- Apple could not verify...". Isso acontece porque o app e feito por
um desenvolvedor independente, sem o selo pago da Apple -- nao e sinal de
nada errado.

O jeito confiavel de abrir pelo Terminal (funciona em qualquer versao do
macOS):

```bash
cd ~/Downloads/TrackClassifier-latest-macos   # ajuste pro caminho onde descompactou
xattr -cr TrackClassifier.app abrir.command
open TrackClassifier.app
```

Isso resolve de vez -- da segunda vez em diante, abrir normal pelo Finder (o
app, dois cliques) funciona.

Esse mesmo `xattr -cr` e o que deixa o app se atualizar sozinho: sem ele o
macOS roda o app de uma copia temporaria somente leitura, e o "Buscar
atualizacoes" avisa que nao da para atualizar. Mover o `TrackClassifier.app`
para `~/Applications` pelo Finder tambem resolve.

Se preferir sem Terminal: clique com o botao direito (ou Control+clique) em
`abrir.command` ou no `.app` e escolha **Open** no menu. Isso mostra um botao
**Open** que dois cliques nao mostram. **Nao funciona no macOS Sequoia (15)
em diante** -- a Apple removeu esse atalho pra binario sem assinatura
nenhuma, e o aviso volta a so ter "Move to Trash"/"Done" mesmo pelo clique
direito. Nesse caso so resta o Terminal acima, ou System Settings > Privacy
& Security > rolar ate o aviso do TrackClassifier > **Open Anyway** (so
aparece depois de tentar abrir pelo menos uma vez).

Nesses caminhos sem Terminal o app continua em quarentena. Se depois o
"Buscar atualizacoes" disser que o app esta numa copia temporaria, mova o
`.app` para `~/Applications` pelo Finder e abra de novo.

Se aparecer um aviso pedindo confirmacao e voce clicar em **Move to Trash**
por engano, o arquivo vai pro lixo -- baixe o `.zip` de novo.

### Na primeira vez que for abrir (Windows)

O Windows vai mostrar uma tela azul do SmartScreen: "O Windows protegeu o
computador". E o mesmo motivo do aviso do macOS -- o app nao tem assinatura
paga -- e nao e sinal de problema.

Clique em **Mais informacoes** e depois em **Executar assim mesmo**. So na
primeira vez.

## Usando o app

Na primeira vez que voce abrir, um assistente pede pra voce indicar suas
pastas de musica (a de energia alta, neutra, baixa, e a de downloads onde
chegam as faixas novas). Depois disso e so usar.

O app tem quatro abas: **Revisao**, **Biblioteca**, **Modelo** e
**Configuracao**.

### Revisao

E a tela principal: mostra a proxima faixa da fila com a sugestao do app.
Voce ouve, confere a onda e decide pelo teclado:

| Tecla | O que faz |
| --- | --- |
| `1` | marca como "desce a pista" |
| `2` | marca como "neutra" |
| `3` | marca como "sobe a pista" |
| `espaco` | toca / pausa a faixa |
| `Backspace` ou `Ctrl+Z` (`Cmd+Z` no Mac) | desfaz a ultima decisao |
| `S` ou seta direita | pula a faixa, sem decidir |
| seta esquerda | volta pra faixa anterior |
| `D` | manda a faixa pra lixeira do sistema |

Cada decisao ja move o arquivo pra pasta certa. De tempos em tempos o app
retreina sozinho com base nas suas ultimas escolhas, entao as sugestoes vao
ficando mais precisas conforme voce usa. Tambem da pra **aprovar em bloco** as
sugestoes elegiveis de uma vez (o app pergunta antes de confirmar).

Se voce usa mais de um perfil de pastas (por exemplo, um por estilo), a
Revisao mostra uma barra pra trocar de perfil.

Cuidado com o `D`: ele nao conta como decisao, nao ensina nada ao modelo e
**nao da pra desfazer pelo app**. O arquivo vai pra lixeira do sistema, de
onde voce pode restaura-lo pelo Finder (ou Explorer) e depois reescanear.

### Biblioteca

Visao geral de tudo que ja foi classificado, com capa, BPM e tonalidade de
cada faixa, e um player pra ouvir.

### Modelo

Um resumo de quao bem o app esta acertando as sugestoes ultimamente:
metricas, acertos por classe e historico de treinos.

### Configuracao

Salva sozinha, sem botao de salvar. Tem quatro secoes:

1. **Pastas e organizacao** -- a pasta de entrada e as de destino.
2. **Organizacao automatica** -- criar as pastas se nao existirem e mover os
   arquivos depois de classificar.
3. **Dados do aplicativo** -- quanto espaco o app usa, e a opcao de
   restaurar os padroes.
4. **Modelo de classificacao** -- de quantas em quantas decisoes retreinar e o
   minimo de exemplos pra comecar a treinar.

## Onde ficam seus dados

A configuracao fica em `~/.trackclassifier/config.toml`, e o cache das faixas
ja analisadas, o modelo treinado e o historico de treinos ficam dentro dessa
mesma pasta. Suas musicas continuam so nas suas pastas: o app move arquivos
entre elas e nunca altera o conteudo de uma faixa.

## Duvidas comuns

**Preciso saber programar pra usar?**
Nao. Baixe, abra, e siga o assistente da primeira vez.

**O app apaga alguma musica?**
So se voce pedir. As decisoes `1`/`2`/`3` apenas movem o arquivo entre as suas
proprias pastas. A unica coisa que tira uma faixa do lugar e a tecla `D`, que
manda o arquivo pra lixeira do sistema (nao pra um apagamento definitivo) --
da pra restaurar de la.

**Errei uma decisao. Da pra voltar?**
Da: `Backspace` ou `Ctrl+Z` (`Cmd+Z` no Mac) desfaz a ultima decisao e devolve
o arquivo pra pasta de onde ele saiu. A excecao e o `D`, que nao entra no
desfazer.

**Posso ter pastas diferentes por estilo?**
Pode: o app aceita varios perfis de pastas, e a Revisao mostra uma barra pra
trocar de um pro outro. Os perfis ficam no `config.toml`.

**Funciona offline?**
Sim, tudo roda no seu computador. A unica coisa pela internet e checar se
tem atualizacao nova do app.

**Quero conferir a integridade do download ou pegar uma versao antiga.**
Use a [pagina de releases](https://github.com/LucasMatricarde/trackclassifier/releases):
cada versao tem um `.zip` fixo com um `.sha256` do lado pra conferencia. Os
links de "Source code" que o GitHub adiciona sozinho sao so o codigo-fonte,
nao o app -- pode ignorar.

**"Buscar atualizacoes" diz que o macOS abriu o app de uma copia temporaria.**
O app foi baixado e aberto sem sair da pasta de download, entao o macOS o
roda de uma copia somente leitura (App Translocation) e ele nao consegue se
trocar. Feche o app e faca um destes: arraste o `TrackClassifier.app` para
`~/Applications` pelo Finder, ou rode `xattr -cr TrackClassifier.app` no
Terminal, na pasta onde ele esta. Depois abra de novo e tente atualizar.

## Quer mexer no codigo?

Esse README e pra quem so usa o app. Guia tecnico completo (rodar do
codigo-fonte, testar, empacotar, publicar release) esta em
[`docs/DESENVOLVIMENTO.md`](docs/DESENVOLVIMENTO.md). Quem trabalha com
agentes de codigo deve comecar pelo [`AGENTS.md`](AGENTS.md), e as medidas de
cada tela (hex, geometrias, tokens) estao em [`docs/ui/`](docs/ui/README.md).
