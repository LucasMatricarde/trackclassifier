import type { ModelState } from "../api/types";

/**
 * Detalhe tecnico do modelo: alpha, cortes e extrator (port de
 * tech_detail.py). Quem abre e fecha e o botao OPCOES AVANCADAS do painel
 * de configuracoes; o resumo de uma linha do desktop nao existe aqui
 * porque o mockup nao o desenha.
 */

interface TechDetailProps {
  state: ModelState;
  /** id que o aria-controls do botao aponta. */
  id: string;
}

export function TechDetail({ state, id }: TechDetailProps) {
  const temTreino = state.accuracy !== null;

  return (
    <div id={id} className="tech-detail-body" data-testid="tech-detail">
      {temTreino && (
        <div className="tech-detail-item">
          <span className="tech-detail-label">alpha</span>
          <span className="tech-detail-value">{state.alpha?.toFixed(2)}</span>
        </div>
      )}
      {temTreino && (
        <div className="tech-detail-item">
          <span className="tech-detail-label">cortes</span>
          <span className="tech-detail-value">
            {state.thresholds
              ? `${state.thresholds[0].toFixed(3)} / ${state.thresholds[1].toFixed(3)}`
              : "—"}
          </span>
        </div>
      )}
      <div className="tech-detail-item">
        <span className="tech-detail-label">extrator</span>
        <span className="tech-detail-value">{state.extractor_name}</span>
      </div>
    </div>
  );
}
