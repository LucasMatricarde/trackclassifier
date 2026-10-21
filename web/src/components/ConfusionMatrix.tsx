import { Fragment } from "react";
import type { ModelState } from "../api/types";
import { LABELS_IN_ORDER, severityClass } from "../model";

/**
 * Matriz de confusão do dashboard (mockup): cor por severidade ordinal
 * (distância |i-j|, a mesma logica de confusion_matrix.py) e INTENSIDADE
 * pela quantidade de exemplos.
 *
 * O escurecimento usa color-mix sobre os tokens de severidade: quanto
 * maior a contagem da celula, mais o token entra na mistura com a
 * superficie. A celula vazia (0) fica na superficie crua, entao a nota
 * da legenda ("Quanto mais escuro, maior a quantidade") vale dentro de
 * cada severidade.
 *
 * Classes na ordem LABEL_ORDER: "-1" (lento), "neutra" (neutro), "+1" (animada).
 */

const BG_POR_SEVERIDADE: Record<number, string> = {
  0: "var(--color-classification-lento-base)",
  1: "var(--color-classification-neutro-base)",
  2: "var(--color-state-danger)",
};

/** Intensidade: 0 exemplos na superficie; maximo, ~85% do token. */
export function corDaCelula(valor: number, maximo: number, severidade: number): string {
  if (valor === 0 || maximo === 0) {
    return "var(--color-surface-2)";
  }
  const fracao = Math.max(0.12, Math.min(0.85, valor / maximo * 0.85));
  return `color-mix(in srgb, ${BG_POR_SEVERIDADE[severidade]} ${(fracao * 100).toFixed(0)}%, var(--color-surface-2))`;
}

interface ConfusionMatrixProps {
  confusion: ModelState["confusion"];
}

export function ConfusionMatrix({ confusion }: ConfusionMatrixProps) {
  if (!confusion) {
    return null;
  }
  const maximo = Math.max(1, ...confusion.flat());

  return (
    <section className="model-panel confusion" data-testid="confusion-panel">
      <header className="model-panel-head">
        <h2>Matriz de confusão</h2>
        <p>Classificação real (linhas) x prevista (colunas).</p>
      </header>

      <div className="confusion-grid" role="grid" aria-label="Matriz de confusão">
        {/* Cabeçalho vazio canto superior esquerdo */}
        <div className="confusion-label" aria-hidden="true" />

        {/* Cabeçalhos de coluna (PREVISTO) */}
        {LABELS_IN_ORDER.map((rotulo, j) => (
          <div key={`col-${j}`} className="confusion-label col" role="columnheader">
            {rotulo}
          </div>
        ))}

        {/* Linhas (REAL) */}
        {LABELS_IN_ORDER.map((rotulo, i) => (
          <Fragment key={`row-${rotulo}`}>
            <div className="confusion-label row" role="rowheader">
              {rotulo}
            </div>
            {LABELS_IN_ORDER.map((_rotuloCol, j) => {
              const valor = confusion[i][j];
              const dist = Math.abs(i - j);
              return (
                <div
                  key={`cell-${i}-${j}`}
                  className={`confusion-cell ${severityClass(i, j)}${valor === 0 ? " zero" : ""}`}
                  style={{ background: corDaCelula(valor, maximo, dist) }}
                  role="gridcell"
                  aria-label={`Real ${rotulo}, previsto ${LABELS_IN_ORDER[j]}: ${valor}`}
                >
                  {valor}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>

      {/* A nota do mockup explica a intensidade; a cor explica a severidade. */}
      <footer className="confusion-legend">
        <p className="confusion-legend-note">
          Quanto mais escuro, maior a quantidade de exemplos.
        </p>
        <div className="confusion-legend-items">
          <span className="confusion-legend-item">
            <span className="confusion-legend-swatch" style={{ background: BG_POR_SEVERIDADE[0] }} aria-hidden="true" />
            acerto
          </span>
          <span className="confusion-legend-item">
            <span className="confusion-legend-swatch" style={{ background: BG_POR_SEVERIDADE[1] }} aria-hidden="true" />
            erro leve
          </span>
          <span className="confusion-legend-item">
            <span className="confusion-legend-swatch" style={{ background: BG_POR_SEVERIDADE[2] }} aria-hidden="true" />
            erro grave
          </span>
        </div>
      </footer>
    </section>
  );
}
