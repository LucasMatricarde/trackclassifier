import { useEffect, useRef, useState } from "react";
import { TechDetail } from "./TechDetail";
import type { ModelState } from "../api/types";

/**
 * Configuracoes do modelo (mockup): dois steppers que mapeiam 1:1 no
 * config.toml ([model] retrain_every/min_examples) via POST
 * /api/model/settings, botao RETREINAR AGORA (mesmo gatilho do header --
 * um guard so no hook) e o disclosure "Opcoes avancadas", que e o
 * TechDetail (alpha/cortes/extractor) em vez de modal ficticio.
 *
 * O stepper edita local e o commit vai em debounce: cada clique de passo
 * e um POST (tosco e que maltrata o disco), mas solto o envio no fim da
 * rajada de cliques. O valor exibido nunca "salta" para o config vivo --
 * o que aparece e o estado local ate o reload do WS chegar.
 */

interface ModelSettingsPanelProps {
  state: ModelState;
  treinando: boolean;
  onTrain: () => void;
  onSettings: (retrainEvery: number, minExamples: number) => void;
}

interface StepperProps {
  testId: string;
  etiqueta: string;
  hint: string;
  valor: number;
  minimo?: number;
  onChange: (novo: number) => void;
}

function Stepper({ testId, etiqueta, hint, valor, minimo = 1, onChange }: StepperProps) {
  return (
    <div className="settings-stepper">
      <div className="settings-stepper-labels">
        <span className="settings-stepper-label">{etiqueta}</span>
        <span className="settings-stepper-hint">{hint}</span>
      </div>
      <div className="settings-stepper-control" data-testid={testId}>
        <button
          className="settings-stepper-btn"
          onClick={() => onChange(Math.max(minimo, valor - 1))}
          disabled={valor <= minimo}
          aria-label={`Diminuir ${etiqueta}`}
        >
          −
        </button>
        <input
          className="settings-stepper-value"
          data-testid={`${testId}-value`}
          type="number"
          min={minimo}
          value={valor}
          onChange={(e) => {
            const novo = Number(e.target.value);
            if (Number.isFinite(novo) && novo >= minimo) onChange(novo);
          }}
          aria-label={etiqueta}
        />
        <button
          className="settings-stepper-btn"
          onClick={() => onChange(valor + 1)}
          aria-label={`Aumentar ${etiqueta}`}
        >
          +
        </button>
      </div>
    </div>
  );
}

export function ModelSettingsPanel({
  state,
  treinando,
  onTrain,
  onSettings,
}: ModelSettingsPanelProps) {
  // Estado local de edicao: o painel segue o servidor no states_changed,
  // mas enquanto o usuario clica, ele ve o que digitou (o reload tb
  // poderia reseta-lo no meio da rajada).
  const [retrain, setRetrain] = useState(state.retrain_every);
  const [minExemplos, setMinExemplos] = useState(state.min_examples);

  // Config vindo do servidor e verdade nova (WS/reload): resincroniza o
  // local quando a fonte externa muda e nao ha edicao pendente.
  const pendente = useRef(false);
  useEffect(() => {
    if (pendente.current) return;
    setRetrain(state.retrain_every);
    setMinExemplos(state.min_examples);
  }, [state.retrain_every, state.min_examples]);

  // Debounce do commit: uma rajada de cliques vira um POST com o valor
  // final (500ms e o tempo de rajada humana; mesmo do slider da revisao).
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const commit = (retrainEvery: number, minExamples: number) => {
    pendente.current = true;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      pendente.current = false;
      onSettings(retrainEvery, minExamples);
    }, 500);
  };
  useEffect(() => () => clearTimeout(timer.current), []);

  const bloqueado = !!state.train_blocked_reason;

  return (
    <section className="model-panel settings" data-testid="model-settings">
      <header className="model-panel-head">
        <h2>Configurações do modelo</h2>
        <p>Ajuste parâmetros e inicie o retreino.</p>
      </header>

      <Stepper
        testId="settings-retrain"
        etiqueta="Retreinar a cada"
        hint="Decisões entre retreinos automáticos"
        valor={retrain}
        onChange={(novo) => {
          setRetrain(novo);
          commit(novo, minExemplos);
        }}
      />

      <Stepper
        testId="settings-min"
        etiqueta="Mínimo de exemplos por classe"
        hint="Abaixo disso o modelo entra em modo de baixa confiança"
        valor={minExemplos}
        onChange={(novo) => {
          setMinExemplos(novo);
          commit(retrain, novo);
        }}
      />

      <button
        className="btn-solid"
        data-testid="model-train-panel"
        onClick={onTrain}
        disabled={bloqueado || treinando}
        aria-disabled={bloqueado || treinando}
      >
        {treinando ? "TREINANDO…" : "RETREINAR AGORA"}
      </button>

      {bloqueado && (
        <p className="settings-blocked-reason" role="alert" data-testid="settings-blocked-reason">
          {state.train_blocked_reason}
        </p>
      )}

      <div className="settings-advanced">
        <TechDetail state={state} />
      </div>
    </section>
  );
}
