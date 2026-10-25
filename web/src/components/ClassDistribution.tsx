import { balanceRecommendation } from "../model";
import { ModelPanelHead } from "./ModelPanelHead";
import { IconeInfo, IconePizza } from "./ui/ModelIcons";

/**
 * Distribuição das classes (mockup): por classe, rotulo na cor da classe
 * com a contagem "71 (15,4%)" a direita e a barra embaixo; mais o card de
 * recomendacao quando o balanco desanda. Regra identica ao desktop
 * (class_balance.py -- port em model.ts): minoria abaixo de 70% do pico
 * gera o texto.
 *
 * O percentual do texto e sobre o TOTAL (soma 100%, como no mockup); o
 * comprimento da barra segue relativo a maior classe, para a maior encher
 * a trilha. O botao "Ver recomendacoes" e so visual por ora: nao ha tela
 * de recomendacoes no produto (aria-disabled, sem handler).
 */

const CLASSES = [
  { key: "lento", valor: "-1" },
  { key: "neutro", valor: "neutra" },
  { key: "animada", valor: "+1" },
] as const;

const umaCasa = (n: number) => n.toFixed(1).replace(".", ",");

interface ClassDistributionProps {
  classCounts: number[];
}

export function ClassDistribution({ classCounts }: ClassDistributionProps) {
  const maior = Math.max(...classCounts);
  const total = classCounts.reduce((soma, n) => soma + n, 0);
  const rec = balanceRecommendation(classCounts);

  return (
    <section className="model-panel class-distribution" data-testid="class-distribution">
      <ModelPanelHead
        icone={<IconePizza />}
        titulo="Distribuição das classes"
        subtitulo="Quantidade de exemplos no conjunto de treinamento."
      />

      <ul className="distribution-bars">
        {CLASSES.map((classe, i) => {
          const count = classCounts[i] ?? 0;
          const largura = maior > 0 ? (count / maior) * 100 : 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <li className={`distribution-row distribution-${classe.key}`} key={classe.key}>
              <span className="distribution-valor">{classe.valor}</span>
              <span className="distribution-count" data-testid={`distribution-count-${i}`}>
                {count} ({umaCasa(pct)}%)
              </span>
              <span
                className="distribution-track"
                role="meter"
                aria-label={`Exemplos ${classe.valor}`}
                aria-valuenow={count}
                aria-valuemin={0}
                aria-valuemax={maior}
              >
                <span className="distribution-fill" style={{ width: `${largura}%` }} />
              </span>
            </li>
          );
        })}
      </ul>

      {rec && (
        <div className="distribution-recommendation" data-testid="distribution-recommendation">
          <span className="distribution-recommendation-icon">
            <IconeInfo />
          </span>
          <div className="distribution-recommendation-body">
            <p className="distribution-recommendation-text">
              {rec} Isso pode aumentar o erro para a classe minoritária.
            </p>
            <button
              type="button"
              className="btn-outline-accent"
              aria-disabled="true"
              data-testid="distribution-recommendation-btn"
            >
              Ver recomendações
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
