import type { ReactNode } from "react";
import type { TrainControl } from "../hooks/useModelState";
import {
  percentual,
  decimal,
  chipDelta,
  serieDaHistoria,
} from "../model-logic";
import { MetricCard } from "./MetricCard";
import { PerClassPanel } from "./PerClassPanel";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { ClassDistribution } from "./ClassDistribution";
import { HistoryPanel } from "./HistoryPanel";
import { ModelSettingsPanel } from "./ModelSettingsPanel";
import { FailureList } from "./FailureList";
import { ErrorBanner } from "./ui/ErrorBanner";
import { IconeBarrasTitulo, IconeExterno, IconeInfo } from "./ui/ModelIcons";

/**
 * Aba Modelo — dashboard do mockup
 * (design/mockup/TrackClassifier Model Dashboard.png; design em
 * docs/superpowers/specs/2026-10-21-aba-modelo-dashboard-web.md).
 *
 * Paridade com o painel PySide6 fica para o desktop; aqui a estrutura e
 * a do PNG e as cores seguem os tokens do produto. As invariants do
 * desktop que o mockup nao desenha continuam na tela: falhas de analise
 * visiveis mesmo sem treino.
 *
 * useModelState mora no App (o header empresta o mesmo controle), entao
 * a aba recebe o TrainControl por props.
 */

const BANNER =
  "O modelo analisa características das músicas e sugere a classificação baseada na energia e no seu critério.";

// "Saiba mais" aponta para a spec da aba: e o unico texto que explica o
// que cada metrica mede e de onde vem.
const SAIBA_MAIS_URL =
  "https://github.com/LucasMatricarde/trackclassifier/blob/main/docs/superpowers/specs/2026-10-21-aba-modelo-dashboard-web.md";

interface ModelTabProps {
  /** useModelState vive no App: header e aba dividem um guard de treino so. */
  control: TrainControl;
}

export function ModelTab({ control }: ModelTabProps) {
  const { state, error, treinando, requestTrain, requestSettings } = control;

  if (!state) {
    return (
      <div className="model-tab" data-testid="model-tab">
        {error && <ErrorBanner message={error} testId="model-error" />}
        <div className="review-loading">Carregando…</div>
      </div>
    );
  }

  return (
    <div className="model-tab" data-testid="model-tab">
      {error && <ErrorBanner message={error} testId="model-error" />}

      <header className="model-dash-head">
        <div className="model-dash-title">
          <span className="model-title-icon">
            <IconeBarrasTitulo />
          </span>
          <div>
            <h1 className="model-title">Modelo de Classificação</h1>
            <p className="model-subtitle">
              Analise o desempenho do modelo, visualize métricas e gerencie o treinamento.
            </p>
          </div>
        </div>
        <aside className="model-banner" data-testid="model-banner">
          <span className="model-banner-icon">
            <IconeInfo />
          </span>
          <p>{BANNER}</p>
          {/* target=_blank: no Electron o setWindowOpenHandler do shell
              manda o link para o navegador do sistema em vez de abrir uma
              janela do app. */}
          <a
            className="model-banner-link"
            href={SAIBA_MAIS_URL}
            target="_blank"
            rel="noreferrer noopener"
            data-testid="model-banner-link"
          >
            Saiba mais
            <IconeExterno />
          </a>
        </aside>
      </header>

      <BlocoCards state={state} />

      <div className="model-row model-row-triple">
        <PerClassPanel state={state} />
        <ConfusionMatrix confusion={state.confusion} />
        <ClassDistribution classCounts={state.class_counts} />
      </div>

      <div className="model-row model-row-pair">
        <HistoryPanel state={state} />
        <ModelSettingsPanel
          state={state}
          treinando={treinando}
          onTrain={requestTrain}
          onSettings={requestSettings}
        />
      </div>

      <BlocoFalhas state={state} />
    </div>
  );
}

function BlocoCards({ state }: { state: NonNullable<TrainControl["state"]> }) {
  const treinado = state.accuracy !== null;

  const iconeExemplos = <ICone d="M4 5h16v3H4zM4 10h16v3H4zM4 15h16v3H4z" />;
  const iconeAcc = <ICone d="M12 3l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.4 7.2 17.9l.9-5.4L4.2 8.7l5.4-.8z" />;
  const iconeErro = <ICone d="M4 16h16v3H4zM4 10h11v3H4zM4 4h6v3H4z" />;
  const iconeF1 = <ICone d="M7 17L17 7M8 7a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm8 7a1.5 1.5 0 110 3 1.5 1.5 0 010-3z" />;

  return (
    <div className="model-cards" data-testid="model-cards">
      <MetricCard
        testId="metric-exemplos"
        rotulo="Exemplos rotulados"
        hint="Músicas usadas no treinamento"
        valor={String(state.n_examples)}
        classeCor="exemplos"
        serie={serieDaHistoria(state, "n_examples")}
        icone={iconeExemplos}
      />
      <MetricCard
        testId="metric-acc"
        rotulo="Acurácia (leave-one-out)"
        hint="Capacidade de acertar a classificação"
        valor={percentual(state.accuracy, 1)}
        delta={chipDelta(state.deltas?.accuracy, "percentual")}
        classeCor="acc"
        serie={serieDaHistoria(state, "accuracy")}
        icone={iconeAcc}
      />
      <MetricCard
        testId="metric-mae"
        rotulo="Erro ordinal médio"
        hint="Quanto menor, melhor"
        valor={decimal(state.ordinal_mae)}
        delta={chipDelta(state.deltas?.ordinal_mae, "decimal")}
        classeCor="mae"
        serie={serieDaHistoria(state, "ordinal_mae")}
        icone={iconeErro}
      />
      <MetricCard
        testId="metric-f1"
        rotulo="Score F1 (ponderado)"
        hint="Equilíbrio entre precisão e recall"
        valor={percentual(state.weighted_f1, 1)}
        delta={chipDelta(state.deltas?.weighted_f1, "percentual")}
        classeCor="f1"
        serie={serieDaHistoria(state, "weighted_f1")}
        icone={iconeF1}
      />
      {!treinado && (
        <p className="model-sem-treino" data-testid="model-sem-treino" hidden>
          Sem treino: metricas em --.
        </p>
      )}
    </div>
  );
}

function BlocoFalhas({ state }: { state: NonNullable<TrainControl["state"]> }) {
  if (state.failures.length === 0) {
    return null;
  }
  return (
    <div className="model-row model-row-falhas">
      <FailureList failures={state.failures} />
    </div>
  );
}

function ICone({ d }: { d: string }): ReactNode {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}
