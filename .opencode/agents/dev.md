---
description: Trabalho no trackclassifier com contexto enxuto (k3-256k, effort high)
mode: primary
# Via o daemon do rtk-proxy (127.0.0.1:8787/v1, definido no config global): ganha
# compression + CCR no trafego. Validado em 2026-10-18: respondeu de verdade e o
# Kimi aceitou `output_config.effort=high` (o campo ia como no-op antes). Se o
# daemon cair, o fallback e `kimi-code-plan-global/k3-256k#high` (vai direto).
model: kimi-rtk/k3-256k#high
steps: 12
# Negar a tool remove a DEFINICAO dela da request, nao so bloqueia a chamada:
# medido no fio (provider falso, agente dev, 1 mensagem) o conjunto com estes
# quatro denies fica em 9 tools = 8.435 B (~2.108 tok).
#
# `task` (nome da tool no fio: `subagent`) e o mais caro dos quatro -- so a
# definicao dele sao 2.697 B (~674 tok) em TODA requisicao. Quem precisa dele e
# o /graphify, entao ele mora no agente `graphify.md`, que tem `task` liberado:
# o custo aparece so enquanto se roda /graphify, e nao no `dev` o tempo todo.
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
