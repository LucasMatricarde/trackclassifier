---
description: Roda /graphify (grafo de conhecimento do repo); libera `task`, que o dev nega
mode: primary
model: kimi-rtk/k3-256k#high
# Passos maiores que os 12 do `dev`: aqui o trabalho e orquestrar subagentes.
steps: 24
permission:
  webfetch: deny
  websearch: deny
  question: deny
---

Este agente existe por um motivo so: o `/graphify` precisa da tool `task`
(subagente), e o `dev` a nega porque so a definicao dela custa 2.697 B
(~674 tok) em toda requisicao -- medido no fio com provider falso. Aqui ela esta
liberada; o resto segue igual ao `dev` (mesmo modelo, instrucoes do `AGENTS.md`,
mesmo allowlist de skills).

Use este agente quando for rodar `/graphify` e volte para o `dev` depois: o
`graphify` paga os 674 tok por requisicao, o `dev` nao.
