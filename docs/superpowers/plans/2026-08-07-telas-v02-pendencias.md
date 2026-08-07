# Telas v0.2 — pendências conhecidas

Três itens deixados de fora das Fases 0–4, registrados aqui para não se
perderem entre os planos individuais.

## 1. Barra do player continua v0.1

`ui/widgets/player_bar.py` não foi tocado. O volume é um `QSlider` azul
padrão; o mockup pede um trilho de 2px com marcador, no mesmo vocabulário
visual do resto da Revisão. É o único elemento das três telas que ainda não
fala v0.2.

Escopo: reescrever `PlayerBar` sobre `Meter` (o widget que a Fase 1 já criou
para o balanço de classes e o contador de retreino) ou uma variante
interativa dele. Cabe como task avulsa ou spec própria — não depende de mais
nada das Fases 0–4.

## 2. Anel de foco de teclado não entrou

A spec original (`2026-08-07-linha-instrumento-e-tokens-v02-design.md`) pede
Focus = Selected + anel interno de `accent.base`. A barra de seleção de 2px
entrou na Fase 2 (`CoverDelegate`); o anel, não — ele só faz sentido junto do
resto do teclado (1/2/3, Z, setas na Biblioteca), que ficou para a Fase 4 e
não coube.

Escopo: `SIZE_FOCUS_RING` já existe no token e já é consumido pela barra de
2px (reaproveitado, não pelo anel). Falta: os atalhos 1/2/3/Z na Biblioteca
roteando por `worker.decide` vs `reclassify` (a spec já resolveu esse
roteamento — ver `path_for`), e o anel pintado no delegate quando a linha
tem foco de teclado (`option.state & QStyle.State_HasFocus`).

## 3. Perf da linha nova não medida contra o número de referência

`ba53271` mediu 29,5 ms no primeiro paint e 5,6 ms por parada de rolagem,
numa biblioteca real de 354 tracks com capas em disco. A verificação da Fase
2 rodou com 9 `TrackRow` sintéticas e sem capa gravada — o `CoverDelegate`
nunca bateu no cache de disco, então o número medido (~2,5 ms) não é
comparável e não prova nem desmente regressão.

A coluna nova (CAPA) e o retângulo de fundo da onda são custo adicional por
linha; nada no código sugere problema, mas a única forma de saber é rodar
`uv run dj review` contra uma biblioteca real e medir como `ba53271` fez.

Escopo: sem código novo — é uma sessão de medição com a biblioteca do
usuário. Se regredir, o comentário do `ba53271` original documenta a técnica
de perfilamento usada.
