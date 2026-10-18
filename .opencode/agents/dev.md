---
description: Trabalho no trackclassifier com contexto enxuto (k3-256k, effort high)
mode: primary
model: kimi-code-plan-global/k3-256k#high
steps: 12
# Negar a tool remove a DEFINICAO dela da request, nao so bloqueia a chamada:
# medido com provider falso, 12 tools/3.488 tok -> 8 tools/2.090 tok (~1.400 tok
# por request). `task` e o tool `subagent`. Reverter = apagar a linha.
permission:
  webfetch: deny
  websearch: deny
  question: deny
  task: deny
---

Trabalhe no trackclassifier. Antes de mexer numa area, invoque a skill dela:
`arquitetura`, `audio-features`, `apresentacao`, `concorrencia`, `empacotamento`
ou `ui`.

Codigo, testes e commits seguem o `AGENTS.md` do repo -- portugues sem acentos,
API publica em ingles, comentarios que explicam o porque.
