import { decimal } from "../model-logic";
import type { ModelState } from "../api/types";

/**
 * Desempenho por classe (mockup): uma linha por classe com circulo de cor
 * e tres colunas precisao/recall/F1 com barra. Os rotulos seguem o vocab
 * das action cards da revisao ("-1 Energy baixa" etc.), e as cores vem
 * dos tokens de classificacao (lento/neutro/animada).
 */

const CLASSES = [
  { key: "lento", valor: "-1", nome: "Energia baixa" },
  { key: "neutro", valor: "neutra", nome: "Energia equilibrada" },
  { key: "animada", valor: "+1", nome: "Energia alta" },
] as const;

interface PerClassPanelProps {
  state: ModelState;
}

export function PerClassPanel({ state }: PerClassPanelProps) {
  const porClasse = state.per_class;
  return (
    <section className="model-panel per-class" data-testid="per-class">
      <header className="model-panel-head">
        <h2>Desempenho por classe</h2>
        <p>Precisão, recall e F1 para cada classe de classificação.</p>
      </header>
      {porClasse ? (
      <ul className="per-class-list">
        {CLASSES.map((classe, i) => {
          const [precisao, recall, f1] = porClasse ? porClasse[i] : [null, null, null];
          return (
            <li className={`per-class-row per-class-${classe.key}`} key={classe.key}>
              <header className="per-class-row-head">
                <span className={`per-class-dot dot-${classe.key}`} aria-hidden="true" />
                <span className="per-class-valor">{classe.valor}</span>
                <span className="per-class-nome">{classe.nome}</span>
              </header>
              <dl className="per-class-cols">
                <div>
                  <dt>Precisão</dt>
                  <dd data-testid={`per-class-precision-${i}`}>
                    <span className="per-class-num">{decimal(precisao)}</span>
                    <span className="per-class-bar">
                      <span
                        className="per-class-bar-fill"
                        style={{ width: `${Math.max(0, Math.min(1, precisao ?? 0)) * 100}%` }}
                      />
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Recall</dt>
                  <dd data-testid={`per-class-recall-${i}`}>
                    <span className="per-class-num">{decimal(recall)}</span>
                    <span className="per-class-bar">
                      <span
                        className="per-class-bar-fill"
                        style={{ width: `${Math.max(0, Math.min(1, recall ?? 0)) * 100}%` }}
                      />
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>F1</dt>
                  <dd data-testid={`per-class-f1-${i}`}>
                    <span className="per-class-num">{decimal(f1)}</span>
                    <span className="per-class-bar">
                      <span
                        className="per-class-bar-fill"
                        style={{ width: `${Math.max(0, Math.min(1, f1 ?? 0)) * 100}%` }}
                      />
                    </span>
                  </dd>
                </div>
              </dl>
            </li>
          );
        })}
      </ul>
      ) : (
        <p className="history-empty" data-testid="per-class-empty">
          Sem treino: as métricas por classe aparecem depois do primeiro treinamento.
        </p>
      )}
    </section>
  );
}
