# Fidelidade visual

O mockup e a unica fonte de verdade. Nao interprete, nao "melhore", replique.
Cores: amostrar do mockup em pixel antes de especificar (pick color /
`getImageData`) -- nunca estimar a olho.

Os mockups ficam em `design/mockup/`, os tokens em `design/design-tokens.json`.
Estas regras valem para toda mudanca de UI; as regras de teste e isolamento
(fila mockada, backend descartavel, hash do acervo) moram no `AGENTS.md`, secao
"Gate de qualidade".

## 1. Definition of done -- evidencia de render, nunca de CSS

Uma correcao visual SO esta pronta quando houver UMA das duas provas:

- valor COMPUTADO via devtools (`getComputedStyle` / painel Styles) capturado
  no print, OU
- medicao em pixels do proprio screenshot (recorte + contagem de px, ou
  `getImageData`).

NUNCA declare "aplicado/corrigido" com base apenas no CSS escrito ou em teste
de token. Se o CSS diz X e o render mostra Y, o render esta certo -- o seletor
nao casa com o DOM real. Corrija a estrutura (wrappers, especificidade), nao
repita a mesma regra.

## 2. Higiene de build (Electron + Vite)

Depois de alterar CSS, tokens ou temas:

1. Parar o app
2. `rm -rf web/dist web/.vite`
3. Rebuild e so entao screenshot para validacao

Cache do Vite ja invalidou 2 verificacoes completas -- nunca confie no build
quente.

## 3. Tokens, nao valores locais

Cores, fontes, raios e espacamentos vivem em `design/design-tokens.json` e sao
aplicados via variaveis (`--accent`, `--radius-md`, `--font-ui`...). O
`web/src/styles/tokens.css` e gerado (`uv run python design/build_tokens.py`):
nao edite a mao.

PROIBIDO: `font-family`, cor ou radius inline em componente; sobrescrever token
em scoped CSS sem comentario justificativo no PR.

## 4. Escopo por iteracao

Uma regiao por vez, com screenshot de aceite antes de avancar. Telas aprovadas
(Revisao; Biblioteca; Modelo; Configuracao) sao congeladas: mexer nelas exige
pedido explicito. Crie variantes (ex.: `badge--fixed`, `.class-chip`) em vez de
alterar componente base reutilizado.

## 5. Sem elementos inventados

Se nao esta no mockup, nao entra na tela (ex.: "PERFIL: DEFAULT", "PICO 3:00",
badges de contagem fora da spec). Se remover algo, remover completamente.

## 6. Overlays

Todo overlay (hover, selecao, highlight) precisa de pai com
`position: relative` e `inset: 0`, ou background aplicado direto no elemento
alvo (`<tr>`, botao). Overlay absoluto solto = bug. Verifique z-index e
cobertura antes de entregar.

## 7. Validacao numerica

Ao comparar com mockup, meca (pixels/hex) em vez de olhar: larguras, alturas,
gaps, saturacao, border-radius. "Parece certo" nao e aceite.

## Fichas tecnicas por tela

A ficha e a referencia numerica da tela (hex, geometrias e tokens medidos no
mockup e validados no render). Indice e infraestrutura de teste em
[`README.md`](README.md).

- [`ficha-tecnica-revisao.md`](ficha-tecnica-revisao.md)
- [`ficha-tecnica-biblioteca.md`](ficha-tecnica-biblioteca.md)
- [`ficha-tecnica-modelo.md`](ficha-tecnica-modelo.md)
- [`ficha-tecnica-configuracao.md`](ficha-tecnica-configuracao.md)
