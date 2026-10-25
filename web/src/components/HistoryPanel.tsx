import { dataCurta, percentual, decimal, statusDeHistorico } from "../model-logic";
import type { ModelState } from "../api/types";
import { ModelPanelHead } from "./ModelPanelHead";
import { IconeRelogio, IconeReticencias } from "./ui/ModelIcons";

/**
 * Historico de treinamentos (mockup): tabela com os treinos recentes
 * primeiro. A primeira linha e o modelo ativo hoje (o joblib carregado,
 * dot verde); as demais aparecem como Arquivado (dot cinza). A coluna
 * final tem o botao de reticencias do mockup em todas as linhas -- so
 * visual por ora (aria-disabled): nao ha acao sobre treino antigo.
 *
 * Paginacao nao existe: o viewmodel entrega ate 12 (o cap de 50 mora no
 * JSON). A key da linha e o momento na LISTA, nao o ts -- dois treinos
 * dentro do mesmo segundo colidem no ts.
 */

const COLUNAS = ["Data", "Versão", "Exemplos", "Acurácia", "Erro ordinal", "Status"] as const;

interface HistoryPanelProps {
  state: ModelState;
}

export function HistoryPanel({ state }: HistoryPanelProps) {
  const linhas = state.history;

  return (
    <section className="model-panel history" data-testid="history-panel">
      <ModelPanelHead
        icone={<IconeRelogio />}
        titulo="Histórico de treinamentos"
        subtitulo="Últimos treinamentos realizados e comparação de métricas."
      />

      {linhas.length === 0 ? (
        <p className="history-empty" data-testid="history-empty">
          Ainda sem treinamentos. Rotule exemplos e rode o primeiro treino.
        </p>
      ) : (
        <div className="history-frame">
          <table className="history-table">
            <thead>
              <tr>
                {COLUNAS.map((coluna) => (
                  <th key={coluna} scope="col">
                    {coluna}
                  </th>
                ))}
                <th scope="col" aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {linhas.map((entrada, i) => {
                const status = statusDeHistorico(i);
                return (
                  <tr key={i} data-testid="history-row">
                    <td data-testid="history-ts">{dataCurta(entrada.ts)}</td>
                    <td data-testid="history-version">{entrada.version}</td>
                    <td>{entrada.n_examples}</td>
                    <td>{percentual(entrada.accuracy, 1)}</td>
                    <td>{decimal(entrada.ordinal_mae)}</td>
                    <td data-testid="history-status">
                      <span
                        className={`history-status history-status-${status === "Ativo" ? "ativo" : "arquivado"}`}
                      >
                        {status}
                      </span>
                    </td>
                    <td className="history-acoes">
                      <button
                        type="button"
                        className="history-menu"
                        aria-label={`Ações do treino ${entrada.version}`}
                        aria-disabled="true"
                        data-testid="history-menu"
                      >
                        <IconeReticencias />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
