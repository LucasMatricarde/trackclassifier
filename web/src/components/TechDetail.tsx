import { useState } from "react";
import type { ModelState } from "../api/types";

/**
 * Rodapé técnico recolhível: alpha, cortes e extrator.
 *
 * Port de tech_detail.py: resumo de uma linha quando fechado,
 * valores nomeados quando aberto.
 */

function resumoTecnico(alpha: number | null, thresholds: [number, number] | null, extractorName: string): string {
  if (alpha === null || thresholds === null) {
    return extractorName;
  }
  const [t1, t2] = thresholds;
  return `alpha ${alpha.toFixed(2)} · cortes ${t1.toFixed(3)} / ${t2.toFixed(3)} · ${extractorName}`;
}

interface TechDetailProps {
  state: ModelState;
}

export function TechDetail({ state }: TechDetailProps) {
  const [aberto, setAberto] = useState(false);

  const temTreino = state.accuracy !== null;
  const resumo = resumoTecnico(state.alpha, state.thresholds, state.extractor_name);

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
        {/* Resumo e corpo dizem a mesma coisa em densidades diferentes:
            mostrar os dois juntos e repeticao (port de tech_detail.py). */}
        {!aberto && <span className="tech-detail-summary">{resumo}</span>}
      </button>

      <div id="tech-detail-body" className="tech-detail-body" hidden={!aberto}>
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
    </div>
  );
}
