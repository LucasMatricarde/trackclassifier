# TrackClassifier — classificação automática de tracks por energia

**Data:** 2026-08-05
**Status:** design aprovado, pronto para plano de implementação

## Problema

Hoje a organização das tracks é manual: cada arquivo novo é ouvido do começo ao fim e movido à mão para uma de três pastas, conforme o efeito que a track tem na pista.

| Rótulo | Significado |
|---|---|
| `+1` | Track animada — joga o público para cima, agita a pista |
| `neutra` | Nem animada nem lenta — sustenta a pista |
| `-1` | Track lenta — quebra o ritmo e prepara a pista para uma `+1` |

O processo não escala com o volume de downloads. O objetivo é aprender o critério pessoal a partir das tracks já separadas e pré-classificar as novas, deixando para o humano apenas a confirmação.

## Contexto do acervo

Levantado na fase de brainstorming, condiciona todas as decisões abaixo:

- **Fonte da verdade dos rótulos:** pastas no disco. Track dentro de `/Tracks +1` tem rótulo `+1`.
- **Volume rotulado atual:** menos de 100 tracks no total das três pastas.
- **Homogeneidade:** um único gênero. BPM e sonoridade próximos entre si; a diferença entre rótulos é sutil e mora dentro do mesmo estilo.
- **Modo de uso desejado:** o sistema sugere, o humano confirma ou corrige, e só então o arquivo é movido.
- **Interface:** aplicação web local com player, para ouvir um trecho antes de decidir.

## Decisões de arquitetura

### As pastas são o banco de dados

Não existe base de rótulos paralela ao sistema de arquivos. O rótulo de uma track **é** a pasta em que ela está. Consequências:

- Sem risco de dessincronia entre banco e disco.
- O usuário continua livre para reorganizar as pastas manualmente; o sistema simplesmente lê o novo estado na próxima execução.
- Nenhuma migração de dados existentes é necessária.

### Escore ordinal contínuo, não classificação em três classes

Os rótulos têm ordem natural (`-1` < `neutra` < `+1`). O modelo é treinado como **regressão** sobre um alvo contínuo (`-1 → 0.0`, `neutra → 0.5`, `+1 → 1.0`) e a saída é um escore em `[0, 1]` cortado em três faixas.

Motivos:

1. Com menos de 100 exemplos, regressão ordinal extrai mais sinal do que classificação em três classes independentes — o modelo aproveita a informação de que `neutra` está *entre* os extremos.
2. O escore contínuo permite ranquear tracks dentro de uma mesma faixa (qual `+1` é a mais energética), útil na montagem de set.
3. A distância do escore ao corte mais próximo dá uma medida natural de confiança.

### Extração de features atrás de uma interface

`FeatureExtractor` é um contrato com um método `extract(caminho) -> vetor`. A implementação inicial é baseada em descritores de áudio calculados à mão. Nenhuma outra peça do sistema conhece o conteúdo do vetor.

Isso torna a substituição por embeddings de modelo pré-treinado (CLAP, OpenL3) uma troca de peça isolada, caso a acurácia estabilize em nível insatisfatório conforme o dataset cresce.

## Componentes

| Peça | Responsabilidade | Depende de |
|---|---|---|
| `config` | Lê `config.toml`: caminho das três pastas rotuladas e da pasta de download. | — |
| `library` | Varre as pastas rotuladas e a de download. Devolve `(caminho, rótulo \| None)`. Cache indexado por SHA1 do arquivo. | `config` |
| `features` | `extract(caminho) -> vetor`. Decodifica via ffmpeg e calcula descritores. | ffmpeg, librosa |
| `model` | Treina sobre `(vetor, rótulo)`. Prediz escore e confiança. Persiste modelo e cortes. | `features` |
| `audio` | Serve o arquivo original por HTTP range requests e informa o offset do pico de energia. Transcodifica apenas formatos não suportados por navegador. | ffmpeg |
| `web` | Servidor FastAPI e página de revisão. Fila ordenada por confiança crescente. | `model`, `audio` |
| `apply` | Move o arquivo confirmado para a pasta correspondente. | `library` |

## Fluxo de dados

```
pastas rotuladas ──> features ──> treina modelo
                                       │
pasta download ──> features ───────────┴──> escore + confiança
                                                    │
                                              fila web (menos confiante primeiro)
                                                    │
                                        humano ouve, confirma ou corrige
                                                    │
                                        move para pasta rotulada
                                                    │
                                        dataset cresce ──> retreina
```

O ciclo se fecha: cada correção do humano vira exemplo de treino na execução seguinte.

## Extração de features

### Janelamento

A análise é feita em **janelas de 10 segundos com salto de 5 segundos**, não sobre a track inteira. Uma única medida agregada sobre a track toda distorce o resultado: introduções e finalizações puxam a média para baixo, e uma track `-1` com um pico curto fica indistinguível de uma `+1` de energia constante.

### Descritores por janela

Dez medidas por janela:

- Energia RMS
- Densidade de onsets (ataques por segundo)
- Fluxo espectral
- Centroide espectral (brilho)
- Razão percussivo/harmônico
- Energia da banda grave (20–250 Hz)
- Razão de energia da banda aguda
- Rolloff espectral
- Largura de banda espectral
- Taxa de cruzamento por zero

### Agregação por track

Quatro estatísticas de cada descritor: mediana, percentil 90, percentil 10 e **razão percentil 90 / mediana**.

A razão p90/mediana mede quanto a track sobe em relação ao próprio corpo — distingue energia constante de energia que explode em um trecho. É a estatística mais informativa do conjunto para o critério em questão.

Mais quatro descritores globais: BPM, LUFS integrado, faixa dinâmica e duração.

Total: 44 features por track.

## Modelo

### Regularização como resposta ao regime de poucos dados

44 features para menos de 100 exemplos é um regime em que o número de variáveis se aproxima do número de amostras. Modelos flexíveis (gradient boosting, random forest) sobreajustam gravemente nessas condições.

O modelo é **regressão Ridge** com padronização das features (`StandardScaler`). O hiperparâmetro `alpha` é escolhido por validação leave-one-out. Regularização L2 forte é a ferramenta adequada para esse regime.

### Calibração dos cortes

Os dois limiares que separam as três faixas **não são fixos** em 0,33 e 0,66. São escolhidos por busca que maximiza a acurácia em validação leave-one-out sobre os dados reais. A largura da faixa `neutra` é uma característica pessoal do critério do usuário e é aprendida, não assumida.

### Confiança

Confiança de uma predição é a distância normalizada entre o escore e o corte mais próximo. Um escore de 0,34 com corte em 0,35 é um empate técnico e vai para o topo da fila de revisão; um escore de 0,95 é uma decisão firme.

### Métricas reportadas a cada treino

- Acurácia em validação leave-one-out
- Matriz de confusão
- **Erro ordinal médio** — confundir `+1` com `neutra` é um erro leve; confundir `+1` com `-1` é grave. A acurácia isolada não distingue os dois casos.

### Expectativa de desempenho

Com aproximadamente 90 exemplos e três classes, a acurácia inicial esperada fica entre 60% e 75% (chute aleatório: 33%). O valor do sistema não está em acertar tudo, e sim em ordenar a fila por incerteza: as predições confiantes são aprovadas em bloco e a atenção do usuário se concentra nas duvidosas.

### Cache

A extração de features custa entre 5 e 15 segundos por track. O vetor resultante é persistido em parquet, indexado pelo SHA1 do arquivo. Arquivo inalterado nunca é reprocessado.

## Interface de revisão

### Reprodução de áudio

O servidor entrega o **arquivo original** via HTTP range requests, e o player HTML5 posiciona a reprodução no segundo do pico de energia. O usuário navega a track inteira livremente. ffmpeg é acionado apenas para transcodificar formatos que o navegador não reproduz (AIFF, FLAC); MP3 e WAV são servidos diretamente.

Essa escolha elimina a necessidade de gerar e armazenar clipes de prévia.

### Tela

`dj review` sobe o servidor FastAPI em localhost e abre o navegador. A fila é ordenada por confiança crescente.

Cada card exibe:

- Nome do arquivo, BPM e duração
- Rótulo sugerido em destaque, com barra de confiança
- **Sparkline da curva de energia** da track inteira, desenhada a partir do RMS por janela já calculado na extração — custo computacional zero. Permite reconhecer a forma da track (sobe e sustenta, plana, cai no meio) sem reproduzir o áudio.
- Player posicionado no pico de energia

### Ações

Botões `+1`, `neutra`, `-1` e `pular`, com atalhos de teclado `1`, `2`, `3` e barra de espaço para reproduzir.

Um botão de **aprovação em bloco** aceita de uma vez todas as predições acima de um limiar de confiança.

### Retreino

Automático a cada 10 decisões novas. O treino de uma Ridge sobre uma matriz 100×44 é instantâneo e não justifica etapa manual.

## Manipulação de arquivos

Regras invioláveis:

- O arquivo é **movido**, nunca copiado — copiar duplicaria o acervo.
- Se já existir arquivo de mesmo nome no destino, um sufixo é acrescentado. **Nunca sobrescreve.**
- O conteúdo do arquivo nunca é modificado: sem reescrita de tag ID3, sem recodificação. O arquivo que sai da pasta de download é byte a byte idêntico ao que chega à pasta rotulada.

## Tratamento de erros

| Situação | Comportamento |
|---|---|
| Arquivo corrompido ou falha do ffmpeg | Marca como erro sem interromper a fila. Exibido em seção "Falharam" na interface. |
| Pasta configurada não existe | Falha no startup com mensagem explícita. Não cria pastas automaticamente. |
| Alguma das três classes sem exemplos | Recusa treinar e informa qual classe falta. |
| Menos de 15 exemplos no total | Treina, mas marca todas as predições como baixa confiança e exibe aviso na interface. |
| Track mais curta que uma janela | Analisa com janela reduzida. Abaixo de 10 segundos, pula com aviso. |
| Arquivo removido entre o scan e a decisão | Detectado no momento de mover; removido da fila sem interromper o fluxo. |

## Estratégia de testes

Todos os testes são determinísticos e independentes do acervo real do usuário.

- **`features`**: áudio sintético gerado em memória (silêncio, ruído branco, trem de pulsos em BPM conhecido) com asserções sobre valores esperados. Um trem de pulsos a 128 BPM deve produzir detecção de 128 BPM.
- **`model`**: dataset sintético com separação conhecida deve produzir acurácia leave-one-out alta. Cobre também a calibração dos cortes.
- **`library`**: pastas temporárias verificam o mapeamento caminho → rótulo.
- **`apply`**: movimentação correta, geração de sufixo em colisão de nome, tolerância a arquivo ausente, e igualdade de hash antes e depois da movimentação.
- **`web`**: `TestClient` do FastAPI verifica a ordenação da fila por confiança e que `POST /decide` move o arquivo e retorna o próximo item.

A qualidade subjetiva da classificação não é objeto de teste automatizado — é precisamente o que o ciclo de correção humana resolve.

## Interface de linha de comando

- `dj scan` — extrai features das tracks ainda não processadas
- `dj review` — sobe o servidor web de revisão
- `dj train` — retreina explicitamente e imprime as métricas

## Stack

Python, com `librosa` para análise de áudio, `scikit-learn` para o modelo, `ffmpeg` para decodificação e `FastAPI` para o servidor. Interface em HTML e JavaScript sem framework.

A escolha de Python decorre do ecossistema de análise de áudio, sem alternativa comparável em outras linguagens.

## Fora de escopo

Cada item abaixo é um projeto próprio, a ser considerado apenas depois que este provar valor:

- Integração com Rekordbox, Serato ou Traktor
- Escrita de metadados ID3 nos arquivos
- Detecção de tonalidade e compatibilidade harmônica (Camelot)
- Sugestão de ordem de set
- Processo residente vigiando a pasta de download
- Autenticação ou suporte a múltiplos usuários
- Empacotamento em contêiner

## Localização

`ProjetosPessoais/TrackClassifier/` neste repositório.
