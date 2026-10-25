import { decimal } from "../model-logic";
import type { ModelState } from "../api/types";
import { ModelPanelHead } from "./ModelPanelHead";
import { IconePainelBarras } from "./ui/ModelIcons";

/**
 * Desempenho por classe (mockup): cada classe e um bloco arredondado com
 * o fill tingido da classe. A esquerda, dot com halo + valor da classe na
 * cor dela + rotulo de energia; a direita, tres colunas
 * Precisao/Recall/F1 com valor de duas casas e barra na cor da classe.
 * As cores vem dos tokens de classificacao (lento/neutro/animada) e dos
 * fills color.model.class-row-*.
 */

const CLASSES = [
  { key: "lento", valor: "-1", nome: "Energia baixa" },
  { key: "neutro", valor: "neutra", nome: "Energia equilibrada" },
  { key: "animada", valor: "+1", nome: "Energia alta" },
] as const;

const METRICAS = [
  { rotulo: "Precisão", testId: "precision" },
  { rotulo: "Recall", testId: "recall" },
  { rotulo: "F1", testId: "f1" },
] as const;

interface PerClassPanelProps {
  state: ModelState;
}

export function PerClassPanel({ state }: PerClassPanelProps) {
  const porClasse = state.per_class;
  return (
    <section className="model-panel per-class" data-testid="per-class">
      <ModelPanelHead
        icone={<IconePainelBarras />}
        titulo="Desempenho por classe"
        subtitulo="Precisão, recall e F1 para cada classe de classificação."
      />
      {porClasse ? (
        <ul className="per-class-list">
          {CLASSES.map((classe, i) => (
            <li className={`per-class-row per-class-${classe.key}`} key={classe.key}>
              <div className="per-class-id">
                <span className="per-class-dot" aria-hidden="true" />
                <span className="per-class-id-text">
                  <span className="per-class-valor">{classe.valor}</span>
                  <span className="per-class-nome">{classe.nome}</span>
                </span>
              </div>
              <dl className="per-class-cols">
                {METRICAS.map((metrica, m) => {
                  const v = porClasse[i][m];
                  return (
                    <div className="per-class-col" key={metrica.testId}>
                      <dt>{metrica.rotulo}</dt>
                      <dd data-testid={`per-class-${metrica.testId}-${i}`}>
                        <span className="per-class-num">{decimal(v, 2)}</span>
                        <span className="per-class-bar">
                          <span
                            className="per-class-bar-fill"
                            style={{ width: `${Math.max(0, Math.min(1, v ?? 0)) * 100}%` }}
                          />
                        </span>
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </li>
          ))}
        </ul>
      ) : (
        <p className="history-empty" data-testid="per-class-empty">
          Sem treino: as métricas por classe aparecem depois do primeiro treinamento.
        </p>
      )}
    </section>
  );
}
