import { Meter } from "./ui/Meter";

/**
 * Balanço do treino: 3 barras horizontais com contagem por classe.
 *
 * Port de class_balance.py: normalizado pela maior contagem,
 * recomendação derivada aparece quando menor < 70% da maior.
 */

const LABELS_EM_ORDEM = ["-1", "neutra", "+1"] as const;
const CLASSE_POR_ROTULO: Record<string, "animada" | "neutro" | "lento"> = {
  "+1": "animada",
  "neutra": "neutro",
  "-1": "lento",
};

const LIMIAR_DESBALANCO = 0.70;

function corBaseDoRotulo(rotulo: string): string {
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

function nomeClasseCss(rotulo: string): string {
  return CLASSE_POR_ROTULO[rotulo];
}

function recomendacao(classCounts: number[]): string | null {
  const maior = Math.max(...classCounts);
  if (maior === 0) return null;
  const indice = classCounts.indexOf(Math.min(...classCounts));
  const proporcao = classCounts[indice] / maior;
  if (proporcao >= LIMIAR_DESBALANCO) return null;
  const rotulo = LABELS_EM_ORDEM[indice];
  const maiorRotulo = LABELS_EM_ORDEM[classCounts.indexOf(maior)];
  return `${rotulo} tem ${Math.round(proporcao * 100)}% dos exemplos de ${maiorRotulo}. Rotular mais ${rotulo} é o que mais reduz o erro agora.`;
}

interface ClassBalanceProps {
  classCounts: number[];
}

export function ClassBalance({ classCounts }: ClassBalanceProps) {
  const rec = recomendacao(classCounts);
  const maior = Math.max(...classCounts);

  return (
    <div className="class-balance">
      <div className="class-balance-title">Balanco do treino</div>

      <div className="class-balance-bars">
        {LABELS_EM_ORDEM.map((rotulo, i) => (
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
