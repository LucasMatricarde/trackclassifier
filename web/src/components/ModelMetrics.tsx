import type { ModelState } from "../api/types";

interface ModelMetricsProps {
  state: ModelState;
}

export function ModelMetrics({ state }: ModelMetricsProps) {
  const treinado = state.accuracy !== null;

  return (
    <div className="model-metrics-row">
      <div className="metric-card">
        <span className="metric-label">Exemplos rotulados</span>
        <span className="metric-value">{state.n_examples}</span>
      </div>

      <div className="metric-card">
        <span className="metric-label">Acuracia (leave-one-out)</span>
        <span className="metric-value">
          {treinado ? `${(state.accuracy! * 100).toFixed(1)}%` : "—"}
        </span>
      </div>

      <div className="metric-card">
        <span className="metric-label">Erro ordinal medio</span>
        <span className="metric-value">
          {treinado ? state.ordinal_mae!.toFixed(3) : "—"}
        </span>
      </div>
    </div>
  );
}
