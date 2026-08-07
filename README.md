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

O link baixa direto a versao mais recente, em `.zip`. Depois de baixar:
descompacte e abra `TrackClassifier.app`. Da segunda vez em diante o proprio
app avisa quando tem atualizacao nova.

### Na primeira vez que for abrir

O macOS vai bloquear com uma mensagem tipo "'TrackClassifier' Not
Opened -- Apple could not verify...". Isso acontece porque o app e feito por
um desenvolvedor independente, sem o selo pago da Apple -- nao e sinal de
nada errado.

Pra abrir mesmo assim: dentro do `.zip` tem um arquivo chamado
`abrir.command` do lado do app. De dois cliques nele (em vez do app) so essa
primeira vez -- ele libera o app e ja abre sozinho. Da segunda vez em diante,
abrir normal pelo Finder funciona.

Se preferir, tambem da pra liberar pelo Terminal:

```bash
xattr -cr TrackClassifier.app
```

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
