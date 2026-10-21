import type { ReactNode } from "react";
import { Sparkline } from "./Sparkline";
import type { ChipDelta } from "../model-logic";

/**
 * Card metrico do dashboard (mockup): micro-label, numero grande, chip de
 * delta, hint e sparkline no pe. A cor da accentca do card entra via classe
 * (metric-spark-*) porque o dash card pinta os tres itens (chip, sparkline)
 * com o mesmo token de cor.
 */
interface MetricCardProps {
  testId: string;
  rotulo: string;
  hint: string;
  /** Valor formatado pelo chamador (percentual/decimal/contagem). */
  valor: string;
  delta?: ChipDelta | null;
  classeCor: "acc" | "mae" | "f1" | "exemplos";
  /** Serie cronologica do historico para a sparkline. */
  serie: number[];
  icone: ReactNode;
}

export function MetricCard({
  testId,
  rotulo,
  hint,
  valor,
  delta,
  classeCor,
  serie,
  icone,
}: MetricCardProps) {
  return (
    <article className="metric-card" data-testid={testId}>
      <header className="metric-card-head">
        <span className="metric-card-icon" aria-hidden="true">
          {icone}
        </span>
        <span className="metric-card-label">{rotulo}</span>
        {delta && (
          <span
            className={`metric-delta ${delta.bom ? "metric-delta-bom" : "metric-delta-ruim"}`}
            data-testid={`${testId}-delta`}
          >
            <span aria-hidden="true">{delta.direcao === "up" ? "▲" : "▼"}</span> {delta.texto}
          </span>
        )}
      </header>
      <div className="metric-card-value" data-testid={`${testId}-valor`}>
        {valor}
      </div>
      <p className="metric-card-hint">{hint}</p>
      <div className={`metric-card-spark metric-card-spark-${classeCor}`}>
        <Sparkline valores={serie} testId={`${testId}-spark`} />
      </div>
    </article>
  );
}
