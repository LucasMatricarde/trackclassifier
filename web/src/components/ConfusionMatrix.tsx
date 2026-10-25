import { Fragment } from "react";
import type { ModelState } from "../api/types";
import { LABELS_IN_ORDER, severityClass } from "../model";
import { ModelPanelHead } from "./ModelPanelHead";
import { IconeGrade } from "./ui/ModelIcons";

/**
 * Matriz de confusão do dashboard (mockup): cor por severidade ordinal
 * (distância |i-j|, a mesma logica de confusion_matrix.py) e INTENSIDADE
 * pela quantidade de exemplos.
 *
 * As tres bases foram amostradas do PNG: diagonal azul (acerto), ambar a
 * uma classe de distancia e vinho entre -1 e +1. A cor segue a distancia,
 * nao a classe prevista: no mockup a coluna -1 tem o 9 em ambar e o 1 em
 * vinho. A intensidade entra por color-mix com a superficie do painel --
 * a maior contagem da matriz pinta o token cru, a menor ~75% dele. A
 * celula vazia (0) fica na superficie crua.
 *
 * Classes na ordem LABEL_ORDER: "-1" (lento), "neutra" (neutro), "+1" (animada).
 */

const BG_POR_SEVERIDADE: Record<number, string> = {
  0: "var(--color-model-cm-diag)",
  1: "var(--color-model-cm-adjacente)",
  2: "var(--color-model-cm-extremo)",
};

/** Classe CSS da cor do rotulo/cabecalho de cada classe (lento/neutro/animada). */
const CLASSE_DO_ROTULO = ["confusion-cls-lento", "confusion-cls-neutro", "confusion-cls-animada"];

/** Intensidade: 0 exemplos na superficie; maximo, o token cru. */
export function corDaCelula(valor: number, maximo: number, severidade: number): string {
  if (valor === 0 || maximo === 0) {
    return "var(--color-surface-2)";
  }
  const fracao = 0.75 + 0.25 * Math.min(1, valor / maximo);
  return `color-mix(in srgb, ${BG_POR_SEVERIDADE[severidade]} ${(fracao * 100).toFixed(0)}%, var(--color-surface-panel))`;
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
      <ModelPanelHead
        icone={<IconeGrade />}
        titulo="Matriz de confusão"
        subtitulo="Classificação real (linhas) x prevista (colunas)."
      />

      {/* Grade explicita: coluna 1 = "Real" (vertical), 2 = rotulos das
          linhas, 3-5 = celulas; linha 1 = "Previsto", 2 = cabecalhos. As
          posicoes vao inline porque o auto-placement poria o primeiro
          rotulo de linha no buraco ao lado de "Previsto". */}
      <div className="confusion-grid" role="grid" aria-label="Matriz de confusão">
        <div className="confusion-axis confusion-axis-previsto" aria-hidden="true">
          Previsto
        </div>
        <div className="confusion-axis confusion-axis-real" aria-hidden="true">
          Real
        </div>

        {LABELS_IN_ORDER.map((rotulo, j) => (
          <div
            key={`col-${j}`}
            className={`confusion-label col ${CLASSE_DO_ROTULO[j]}`}
            role="columnheader"
            style={{ gridColumn: j + 3 }}
          >
            {rotulo}
          </div>
        ))}

        {LABELS_IN_ORDER.map((rotulo, i) => (
          <Fragment key={`row-${rotulo}`}>
            <div
              className={`confusion-label row ${CLASSE_DO_ROTULO[i]}`}
              role="rowheader"
              style={{ gridRow: i + 3 }}
            >
              {rotulo}
            </div>
            {LABELS_IN_ORDER.map((_rotuloCol, j) => {
              const valor = confusion[i][j];
              const dist = Math.abs(i - j);
              return (
                <div
                  key={`cell-${i}-${j}`}
                  className={`confusion-cell ${severityClass(i, j)}${valor === 0 ? " zero" : ""}`}
                  style={{
                    background: corDaCelula(valor, maximo, dist),
                    gridRow: i + 3,
                    gridColumn: j + 3,
                  }}
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

      {/* So a nota do mockup: a cor ja diz a severidade na propria celula. */}
      <footer className="confusion-legend">
        <span className="confusion-legend-swatch" aria-hidden="true" />
        <p className="confusion-legend-note">
          Quanto mais escuro, maior a quantidade de exemplos.
        </p>
      </footer>
    </section>
  );
}
