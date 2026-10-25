import type { ReactNode } from "react";
import { Sparkline } from "./Sparkline";
import type { ChipDelta } from "../model-logic";

/**
 * Card metrico do dashboard (mockup): tile de icone tingido a esquerda;
 * na coluna, label pequeno, valor grande com o badge de delta ao lado,
 * descricao e a sparkline no pe. A cor do card entra pela classe
 * metric-card-<cor>, que define `color`: tile, icone e sparkline herdam o
 * mesmo token via currentColor/color-mix.
 */
const CLASSE_DO_DELTA = {
  bom: "metric-delta-bom",
  ruim: "metric-delta-ruim",
  neutro: "metric-delta-neutro",
} as const;

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
    <article className={`metric-card metric-card-${classeCor}`} data-testid={testId}>
      <span className="metric-card-tile" aria-hidden="true">
        {icone}
      </span>
      <div className="metric-card-body">
        <span className="metric-card-label">{rotulo}</span>
        <div className="metric-card-value-row">
          <span className="metric-card-value" data-testid={`${testId}-valor`}>
            {valor}
          </span>
          {delta && (
            <span
              className={`metric-delta ${CLASSE_DO_DELTA[delta.bom === null ? "neutro" : delta.bom ? "bom" : "ruim"]}`}
              data-testid={`${testId}-delta`}
            >
              {/* Sem variacao visivel nao ha seta: o badge cinza so diz "igual". */}
              {delta.direcao !== "flat" && (
                <span aria-hidden="true">{delta.direcao === "up" ? "▲ " : "▼ "}</span>
              )}
              {delta.texto}
            </span>
          )}
        </div>
        <p className="metric-card-hint">{hint}</p>
      </div>
      <div className={`metric-card-spark metric-card-spark-${classeCor}`}>
        <Sparkline valores={serie} testId={`${testId}-spark`} />
      </div>
    </article>
  );
}
