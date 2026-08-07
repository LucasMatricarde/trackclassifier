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

Uma janela simples toca a faixa, mostra a sugestao, e voce confirma ou
corrige com um toque de tecla. Cada correcao ja realimenta o aprendizado, e o
app fica melhor com o tempo.

## Baixar

[**Baixar TrackClassifier (macOS)**](https://github.com/LucasMatricarde/trackclassifier/releases/latest/download/TrackClassifier-latest.zip)

[**Baixar TrackClassifier (Windows)**](https://github.com/LucasMatricarde/trackclassifier/releases/latest/download/TrackClassifier-latest-windows.zip)

O link baixa direto a versao mais recente, em `.zip`. Depois de baixar:
descompacte e abra `TrackClassifier.app` (macOS) ou `TrackClassifier.exe`
dentro da pasta `TrackClassifier` (Windows).

No macOS, da segunda vez em diante o proprio app avisa quando tem atualizacao
nova. No Windows ainda nao tem esse aviso -- pra atualizar, baixe o `.zip`
novo por este mesmo link e substitua a pasta.

### Na primeira vez que for abrir (macOS)

O macOS vai bloquear com uma mensagem tipo "'TrackClassifier' Not
Opened -- Apple could not verify...". Isso acontece porque o app e feito por
um desenvolvedor independente, sem o selo pago da Apple -- nao e sinal de
nada errado.

O jeito confiavel de abrir pelo Terminal (funciona em qualquer versao do
macOS):

```bash
cd ~/Downloads/TrackClassifier-latest   # ajuste pro caminho onde descompactou
xattr -cr TrackClassifier.app abrir.command
open TrackClassifier.app
```

Isso resolve de vez -- da segunda vez em diante, abrir normal pelo Finder (o
app, dois cliques) funciona.

Se preferir sem Terminal: clique com o botao direito (ou Control+clique) em
`abrir.command` ou no `.app` e escolha **Open** no menu. Isso mostra um botao
**Open** que dois cliques nao mostram. **Nao funciona no macOS Sequoia (15)
em diante** -- a Apple removeu esse atalho pra binario sem assinatura
nenhuma, e o aviso volta a so ter "Move to Trash"/"Done" mesmo pelo clique
direito. Nesse caso so resta o Terminal acima, ou System Settings > Privacy
& Security > rolar ate o aviso do TrackClassifier > **Open Anyway** (so
aparece depois de tentar abrir pelo menos uma vez).

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

Na janela principal:

| Tecla | O que faz |
| --- | --- |
| `1` | marca como "desce a pista" |
| `2` | marca como "neutra" |
| `3` | marca como "sobe a pista" |
| `espaco` | toca / pausa a faixa |

Cada decisao ja move o arquivo pra pasta certa. De tempos em tempos o app
retreina sozinho com base nas suas ultimas escolhas, entao as sugestoes vao
ficando mais precisas conforme voce usa.

A janela tambem tem duas abas extras:

- **Biblioteca** -- visao geral de tudo que ja foi classificado, com capa,
  BPM e tonalidade de cada faixa.
- **Modelo** -- um resumo simples de quao bem o app esta acertando as
  sugestoes ultimamente.

## Duvidas comuns

**Preciso saber programar pra usar?**
Nao. Baixe, abra, e siga o assistente da primeira vez.

**O app apaga alguma musica?**
Nao. Ele so move os arquivos entre as suas proprias pastas, nunca apaga
nada.

**Funciona offline?**
Sim, tudo roda no seu computador. A unica coisa pela internet e checar se
tem atualizacao nova do app.

**Quero conferir a integridade do download ou pegar uma versao antiga.**
Use a [pagina de releases](https://github.com/LucasMatricarde/trackclassifier/releases):
cada versao tem um `.zip` fixo com um `.sha256` do lado pra conferencia. Os
links de "Source code" que o GitHub adiciona sozinho sao so o codigo-fonte,
nao o app -- pode ignorar.

## Quer mexer no codigo?

Esse README e pra quem so usa o app. Guia tecnico completo (rodar do
codigo-fonte, testar, empacotar, publicar release) esta em
[`docs/DESENVOLVIMENTO.md`](docs/DESENVOLVIMENTO.md).
