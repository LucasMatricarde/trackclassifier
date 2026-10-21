import { useModelState } from "../hooks/useModelState";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { ClassBalance } from "./ClassBalance";
import { ModelMetrics } from "./ModelMetrics";
import { FailureList } from "./FailureList";
import { ModelActionBar } from "./ModelActionBar";
import { TechDetail } from "./TechDetail";
import { EmptyState } from "./EmptyState";
import { ErrorBanner } from "./ui/ErrorBanner";

/**
 * Aba Modelo: métricas, matriz, balanço, retreino, falhas e detalhe técnico.
 *
 * Port de model_tab.py — mesmo layout e dados, usando o hook useModelState.
 */

export function ModelTab() {
  const { state, error, treinando, requestTrain } = useModelState();

  if (!state) {
    return (
      <div className="model-tab" data-testid="model-tab">
        <div className="review-loading">Carregando…</div>
      </div>
    );
  }

  const vazio = state.n_examples === 0;
  const treinado = state.accuracy !== null;

  return (
    <div className="model-tab" data-testid="model-tab">
      {error && <ErrorBanner message={error} testId="model-error" />}

      <header className="model-header">
        <h1 className="model-title">Modelo de Classificacao</h1>
      </header>

      {vazio ? (
        <EmptyState
          title="Nenhum exemplo rotulado"
          subtitle="Classifique tracks na Revisao para o modelo ter o que aprender."
          actionLabel="Ir para a revisao"
          onAction={() => {
            // Navegar para aba Revisão - será tratado pelo App
            const event = new CustomEvent("navegar-para-revisao");
            window.dispatchEvent(event);
          }}
          testId="model-empty"
        />
      ) : (
        <>
          {/* Port de model_tab._card_metricas: sem treino, o bloco mostra
              o painel "ainda nao treinado" no lugar dos cards — mesma
              slot de layout, e o desktop esconde metricas os dois juntos. */}
          {treinado ? (
            <ModelMetrics state={state} />
          ) : (
            <div className="model-sem-treino">
              <span className="model-sem-treino-title">
                Modelo ainda nao treinado.
              </span>
              <span className="model-sem-treino-note">
                Metricas aparecem depois do primeiro retreino.
              </span>
            </div>
          )}

          <div className="model-cards-row">
            <ConfusionMatrix confusion={state.confusion} />
            <ClassBalance classCounts={state.class_counts} />
          </div>

          <ModelActionBar state={state} onTrain={requestTrain} disabled={treinando} />
        </>
      )}

      {/* Fora do ternario de proposito (port do comentario de model_tab
          sobre self.falhas): FailureList e TechDetail sao as UNICAS
          superficies que mostram service.failures() — uma biblioteca
          fresca com zero exemplos rotulados mas com falha de scan nao
          tem outro lugar para descobrir o que falhou. A lista e o
          detalhe se escondem sozinhos quando nao tem o que mostrar. */}
      <FailureList failures={state.failures} />
      <TechDetail state={state} />
    </div>
  );
}
