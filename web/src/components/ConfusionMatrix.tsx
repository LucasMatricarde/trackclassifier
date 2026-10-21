import type { ModelState } from "../api/types";

/**
 * Matriz de confusão colorida por severidade ordinal.
 *
 * Port de confusion_matrix.py: mesma lógica de severidade (distância |i-j|)
 * e mesma paleta de cores vinda dos tokens.
 *
 * Classes (em ordem LABEL_ORDER): "-1" (lento), "neutra", "+1" (animada)
 */

const LABELS_EM_ORDEM = ["-1", "neutra", "+1"] as const;

const CLASSE_POR_ROTULO: Record<string, "animada" | "neutro" | "lento"> = {
  "+1": "animada",
  "neutra": "neutro",
  "-1": "lento",
};

function severidade(i: number, j: number): number {
  return Math.abs(i - j);
}

function classeDaSeveridade(_valor: number, i: number, j: number): string {
  const dist = severidade(i, j);
  if (dist === 0) return "severity-0";
  if (dist === 1) return "severity-1";
  return "severity-2";
}

function corDoRotulo(rotulo: string): string {
  const classe = CLASSE_POR_ROTULO[rotulo];
  switch (classe) {
    case "animada":
      return "var(--color-classification-animada-base)";
    case "neutro":
      return "var(--color-classification-neutro-base)";
    case "lento":
      return "var(--color-classification-lento-base)";
  }
}

interface ConfusionMatrixProps {
  confusion: ModelState["confusion"];
}

export function ConfusionMatrix({ confusion }: ConfusionMatrixProps) {
  if (!confusion) {
    return null;
  }

  return (
    <div className="confusion-matrix">
      <div className="confusion-header">
        <span className="confusion-title">Matriz de confusao</span>
        <span className="confusion-convention">real x previsto</span>
      </div>

      <div className="confusion-grid" role="grid" aria-label="Matriz de confusão">
        {/* Cabeçalho vazio canto superior esquerdo */}
        <div className="confusion-label" aria-hidden="true" />

        {/* Cabeçalhos de coluna (PREVISTO) */}
        {LABELS_EM_ORDEM.map((rotulo, j) => (
          <div
            key={`col-${j}`}
            className="confusion-label col"
            style={{ color: corDoRotulo(rotulo) }}
            role="columnheader"
          >
            {rotulo}
          </div>
        ))}

        {/* Linhas (REAL) */}
        {LABELS_EM_ORDEM.map((rotulo, i) => (
          <>
            {/* Rótulo da linha */}
            <div
              key={`row-label-${i}`}
              className="confusion-label row"
              style={{ color: corDoRotulo(rotulo) }}
              role="rowheader"
            >
              {rotulo}
            </div>

            {/* Células da linha */}
            {LABELS_EM_ORDEM.map((_rotuloCol, j) => {
              const valor = confusion[i][j];
              const isZero = valor === 0;
              return (
                <div
                  key={`cell-${i}-${j}`}
                  className={`confusion-cell ${classeDaSeveridade(valor, i, j)} ${isZero ? "zero" : ""}`}
                  role="gridcell"
                  aria-label={`Real ${rotulo}, previsto ${LABELS_EM_ORDEM[j]}: ${valor}`}
                >
                  {valor}
                </div>
              );
            })}
          </>
        ))}

        {/* Legenda */}
        <div className="confusion-legend" style={{ gridColumn: "1 / -1" }}>
          <div className="confusion-legend-item">
            <div
              className="confusion-legend-swatch severity-0"
              style={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border-default)" }}
              aria-hidden="true"
            />
            <span className="confusion-legend-text">acerto</span>
          </div>
          <div className="confusion-legend-item">
            <div
              className="confusion-legend-swatch severity-1"
              style={{ background: "var(--color-classification-neutro-bg)" }}
              aria-hidden="true"
            />
            <span className="confusion-legend-text">erro leve · 1 classe</span>
          </div>
          <div className="confusion-legend-item">
            <div
              className="confusion-legend-swatch severity-2"
              style={{ background: "color-mix(in srgb, var(--color-state-danger) 12%, transparent)" }}
              aria-hidden="true"
            />
            <span className="confusion-legend-text">erro grave · 2 classes</span>
          </div>
        </div>
      </div>
    </div>
  );
}
