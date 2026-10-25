import { useEffect, useRef, useState } from "react";
import { TechDetail } from "./TechDetail";
import type { ModelState } from "../api/types";
import { ModelPanelHead } from "./ModelPanelHead";
import { Tooltip } from "./ui/Tooltip";
import { IconeEngrenagem, IconeInfo, IconeRefresh } from "./ui/ModelIcons";

/**
 * Configuracoes do modelo (mockup): dois inputs lado a lado que mapeiam
 * 1:1 no config.toml ([model] retrain_every/min_examples) via POST
 * /api/model/settings; RETREINAR AGORA (mesmo gatilho do header -- um
 * guard so no hook) e OPCOES AVANCADAS, que abre o TechDetail
 * (alpha/cortes/extractor) embaixo em vez de um modal ficticio.
 *
 * O input edita local e o commit vai em debounce: cada passo do spinner
 * seria um POST (maltrata o disco), entao o envio sai no fim da rajada.
 * O valor exibido nunca "salta" para o config vivo -- o que aparece e o
 * estado local ate o reload do WS chegar.
 */

interface ModelSettingsPanelProps {
  state: ModelState;
  treinando: boolean;
  onTrain: () => void;
  onSettings: (retrainEvery: number, minExamples: number) => void;
}

interface CampoProps {
  testId: string;
  etiqueta: string;
  /** Explicacao do campo: vai no tooltip do icone de info (mockup). */
  hint: string;
  valor: number;
  minimo?: number;
  onChange: (novo: number) => void;
}

function CampoNumerico({ testId, etiqueta, hint, valor, minimo = 1, onChange }: CampoProps) {
  return (
    <div className="settings-field" data-testid={testId}>
      <span className="settings-field-label">
        <label htmlFor={`${testId}-value`}>{etiqueta}</label>
        <Tooltip text={hint}>
          <span className="settings-field-info" tabIndex={0} aria-label={hint}>
            <IconeInfo tamanho={13} />
          </span>
        </Tooltip>
      </span>
      <span className="settings-field-row">
        <input
          id={`${testId}-value`}
          className="settings-field-input"
          data-testid={`${testId}-value`}
          type="number"
          min={minimo}
          value={valor}
          onChange={(e) => {
            const novo = Number(e.target.value);
            if (Number.isFinite(novo) && novo >= minimo) onChange(novo);
          }}
        />
        <span className="settings-field-suffix">músicas</span>
      </span>
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
  const [avancado, setAvancado] = useState(false);

  return (
    <section className="model-panel settings" data-testid="model-settings">
      <ModelPanelHead
        icone={<IconeEngrenagem />}
        titulo="Configurações do modelo"
        subtitulo="Ajuste parâmetros e inicie um novo treinamento."
      />

      <div className="settings-fields">
        <CampoNumerico
          testId="settings-retrain"
          etiqueta="Retreinar a cada"
          hint="Decisões entre retreinos automáticos"
          valor={retrain}
          onChange={(novo) => {
            setRetrain(novo);
            commit(novo, minExemplos);
          }}
        />
        <CampoNumerico
          testId="settings-min"
          etiqueta="Mínimo de exemplos por classe"
          hint="Abaixo disso o modelo entra em modo de baixa confiança"
          valor={minExemplos}
          onChange={(novo) => {
            setMinExemplos(novo);
            commit(retrain, novo);
          }}
        />
      </div>

      <div className="settings-actions">
        <button
          className="btn-solid"
          data-testid="model-train-panel"
          onClick={onTrain}
          disabled={bloqueado || treinando}
          aria-disabled={bloqueado || treinando}
        >
          <IconeRefresh />
          {treinando ? "TREINANDO…" : "RETREINAR AGORA"}
        </button>
        <button
          type="button"
          className="btn-settings-advanced"
          data-testid="settings-advanced-toggle"
          onClick={() => setAvancado((a) => !a)}
          aria-expanded={avancado}
          aria-controls="tech-detail-body"
        >
          <IconeEngrenagem tamanho={16} />
          Opções avançadas
        </button>
      </div>

      {bloqueado && (
        <p className="settings-blocked-reason" role="alert" data-testid="settings-blocked-reason">
          {state.train_blocked_reason}
        </p>
      )}

      <p className="settings-footnote">O treinamento usa os exemplos rotulados da biblioteca.</p>

      {avancado && <TechDetail state={state} id="tech-detail-body" />}
    </section>
  );
}
