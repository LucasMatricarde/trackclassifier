import { balanceRecommendation } from "../model";

/**
 * Distribuição das classes (mockup): barras horizontais com contagem e
 * percentual por classe, mais o painel de recomendacao quando o balanco
 * desanda. Regra identica ao desktop (class_balance.py -- port em
 * model.ts): minoria abaixo de 70% do pico gera o texto; a cor das
 * barras vem dos tokens de classificacao, na mesma ordem de rodas.
 */

const CLASSES = [
  { key: "lento", valor: "-1", cor: "var(--color-classification-lento-base)" },
  { key: "neutro", valor: "neutra", cor: "var(--color-classification-neutro-base)" },
  { key: "animada", valor: "+1", cor: "var(--color-classification-animada-base)" },
] as const;

interface ClassDistributionProps {
  classCounts: number[];
}

export function ClassDistribution({ classCounts }: ClassDistributionProps) {
  const maior = Math.max(...classCounts);
  const rec = balanceRecommendation(classCounts);

  return (
    <section className="model-panel class-distribution" data-testid="class-distribution">
      <header className="model-panel-head">
        <h2>Distribuição das classes</h2>
        <p>Quantidade de exemplos no conjunto de treinamento.</p>
      </header>

      <ul className="distribution-bars">
        {CLASSES.map((classe, i) => {
          const count = classCounts[i] ?? 0;
          const pct = maior > 0 ? Math.round((count / maior) * 100) : 0;
          return (
            <li className="distribution-row" key={classe.key}>
              <span className={`distribution-valor valor-${classe.key}`}>{classe.valor}</span>
              <span
                className="distribution-track"
                role="meter"
                aria-label={`Exemplos ${classe.valor}`}
                aria-valuenow={count}
                aria-valuemin={0}
                aria-valuemax={maior}
              >
                <span
                  className="distribution-fill"
                  style={{ width: `${pct}%`, background: classe.cor }}
                />
              </span>
              <span className="distribution-count" data-testid={`distribution-count-${i}`}>
                <strong>{count}</strong>
                <span className="distribution-pct">{pct}%</span>
              </span>
            </li>
          );
        })}
      </ul>

      {rec && (
        <div className="distribution-recommendation" data-testid="distribution-recommendation">
          <p className="distribution-recommendation-text">{rec}</p>
          <p className="distribution-recommendation-hint">
            Isso pode aumentar o erro para a classe minoritária.
          </p>
        </div>
      )}
    </section>
  );
}
