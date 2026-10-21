import { Meter } from "./ui/Meter";
import {
  CLASS_BY_LABEL,
  LABELS_IN_ORDER,
  balanceRecommendation,
} from "../model";

/**
 * Balanço do treino: 3 barras horizontais com contagem por classe.
 *
 * Port de class_balance.py: normalizado pela maior contagem,
 * recomendação derivada aparece quando menor < 70% da maior.
 */

function corBaseDoRotulo(rotulo: string): string {
  const classe = CLASS_BY_LABEL[rotulo];
  switch (classe) {
    case "animada":
      return "var(--color-classification-animada-base)";
    case "neutro":
      return "var(--color-classification-neutro-base)";
    case "lento":
      return "var(--color-classification-lento-base)";
  }
}

function nomeClasseCss(rotulo: string): string {
  return CLASS_BY_LABEL[rotulo];
}

interface ClassBalanceProps {
  classCounts: number[];
}

export function ClassBalance({ classCounts }: ClassBalanceProps) {
  const rec = balanceRecommendation(classCounts);
  const maior = Math.max(...classCounts);

  return (
    <div className="class-balance">
      <div className="class-balance-title">Balanco do treino</div>

      <div className="class-balance-bars">
        {LABELS_IN_ORDER.map((rotulo, i) => (
          <div key={rotulo} className="class-balance-bar">
            <div className="class-balance-bar-top">
              <span className={`class-balance-name ${nomeClasseCss(rotulo)}`}>{rotulo}</span>
              <span className="class-balance-count">{classCounts[i]}</span>
            </div>
            <Meter
              value={maior > 0 ? classCounts[i] / maior : 0}
              color={corBaseDoRotulo(rotulo)}
              height={6}
              label={`Balanço ${rotulo}`}
            />
          </div>
        ))}
      </div>

      {rec && (
        <div className="class-balance-recommendation">{rec}</div>
      )}
    </div>
  );
}
