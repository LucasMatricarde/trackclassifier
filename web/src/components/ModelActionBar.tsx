import type { ModelState } from "../api/types";

interface ModelActionBarProps {
  state: ModelState;
  onTrain: () => void;
  disabled?: boolean;
}

export function ModelActionBar({ state, onTrain, disabled = false }: ModelActionBarProps) {
  const bloqueado = !!state.train_blocked_reason;
  const fracao = state.retrain_every > 0 ? state.decisions_since_train / state.retrain_every : 0;

  return (
    <div className="model-action-bar">
      <button
        className="model-action-btn"
        onClick={onTrain}
        disabled={bloqueado || disabled}
        aria-disabled={bloqueado || disabled}
      >
        RETREINAR
      </button>

      {bloqueado && (
        <span className="model-action-reason" role="alert">
          {state.train_blocked_reason}
        </span>
      )}

      {!bloqueado && (
        <div className="model-action-progress" role="progressbar" aria-valuenow={Math.round(fracao * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso até o retreino automático">
          <div className="model-progress-track">
            <div className="model-progress-fill" style={{ width: `${fracao * 100}%` }} />
          </div>
          <span className="model-progress-label">
            {state.decisions_since_train} / {state.retrain_every} até o retreino automático
          </span>
        </div>
      )}

      {state.low_confidence && (
        <span className="model-action-warning">
          poucos exemplos · acurácia LOO ainda ruidosa
        </span>
      )}
    </div>
  );
}
