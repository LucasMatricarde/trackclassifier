import { dataCurta, percentual, decimal } from "../model-logic";
import type { ModelState } from "../api/types";
import { ModelPanelHead } from "./ModelPanelHead";
import { IconeRelogio } from "./ui/ModelIcons";

/**
 * Historico de treinamentos (mockup): tabela com os treinos recentes
 * primeiro. A primeira linha e o modelo ativo hoje (o joblib carregado);
 * as demais nao tem conceito real de "arquivado" no produto, entao o
 * status delas em dash.
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
        subtitulo="Últimos treinamentos realizados."
      />

      {linhas.length === 0 ? (
        <p className="history-empty" data-testid="history-empty">
          Ainda sem treinamentos. Rotule exemplos e rode o primeiro treino.
        </p>
      ) : (
        <table className="history-table">
          <thead>
            <tr>
              {COLUNAS.map((coluna) => (
                <th key={coluna} scope="col">
                  {coluna}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((entrada, i) => (
              <tr key={i} data-testid="history-row">
                <td data-testid="history-ts">{dataCurta(entrada.ts)}</td>
                <td data-testid="history-version">{entrada.version}</td>
                <td>{entrada.n_examples}</td>
                <td>{percentual(entrada.accuracy, 1)}</td>
                <td>{decimal(entrada.ordinal_mae)}</td>
                <td data-testid="history-status">
                  {i === 0 ? <span className="history-status-active">Ativo</span> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
