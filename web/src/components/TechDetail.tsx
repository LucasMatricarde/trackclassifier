import { useState } from "react";
import type { ModelState } from "../api/types";
import { techSummary } from "../model";

/**
 * Rodapé técnico recolhível: alpha, cortes e extrator.
 *
 * Port de tech_detail.py: resumo de uma linha quando fechado,
 * valores nomeados quando aberto.
 */

interface TechDetailProps {
  state: ModelState;
}

export function TechDetail({ state }: TechDetailProps) {
  const [aberto, setAberto] = useState(false);

  const temTreino = state.accuracy !== null;
  const resumo = techSummary(state.alpha, state.thresholds, state.extractor_name);

  return (
    <div className="tech-detail">
      <button
        className="tech-detail-trigger"
        onClick={() => setAberto((a) => !a)}
        aria-expanded={aberto}
        aria-controls="tech-detail-body"
      >
        <span className="tech-detail-arrow">{aberto ? "▾" : "▸"}</span>
        <span>Detalhe tecnico</span>
        <span className="tech-detail-summary">{resumo}</span>
      </button>

      <div id="tech-detail-body" className="tech-detail-body" hidden={!aberto}>
        {temTreino && (
          <>
            <div className="tech-detail-item">
              <span className="tech-detail-label">alpha</span>
              <span className="tech-detail-value">{state.alpha?.toFixed(2)}</span>
            </div>
            <div className="tech-detail-item">
              <span className="tech-detail-label">cortes</span>
              <span className="tech-detail-value">
                {state.thresholds ? `${state.thresholds[0].toFixed(3)} / ${state.thresholds[1].toFixed(3)}` : "—"}
              </span>
            </div>
          </>
        )}
        <div className="tech-detail-item">
          <span className="tech-detail-label">extrator</span>
          <span className="tech-detail-value">{state.extractor_name}</span>
        </div>
      </div>
    </div>
  );
}
