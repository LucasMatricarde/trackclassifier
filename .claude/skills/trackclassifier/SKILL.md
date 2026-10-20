---
name: trackclassifier
description: Ponto de entrada para o contexto do TrackClassifier. Selecione a sub-skill de arquitetura, áudio e features, apresentação, concorrência, empacotamento ou UI conforme a parte do projeto alterada.
has-sub-skill: true
---

# TrackClassifier

Agrupa o conhecimento operacional do projeto. Os nomes existentes das skills continuam válidos.

- `trackclassifier-arquitetura` — pipeline, cache, modelo, estado e testes.
- `trackclassifier-audio-features` — decodificação, espectros e vetores de features.
- `trackclassifier-apresentacao` — metadados, capas, tonalidade e ondas.
- `trackclassifier-concorrencia` — pool do scan, threads e cancelamento.
- `trackclassifier-empacotamento` — builds, bundles e releases.
- `trackclassifier-ui` — camadas e componentes da interface PySide6.
- `graphify-consulta` — orientacao no grafo de conhecimento: onde mora um simbolo, quem chama o que, o que um PR toca, por que uma decisao foi tomada.
