import { useConfig } from "../hooks/useConfig";
import type { ConfigDraftValues } from "../configDraft";

interface CampoProps {
  campo: keyof ConfigDraftValues;
  rotulo: string;
  valor: string;
  erro?: string;
  mono?: boolean;
  onChange: (campo: keyof ConfigDraftValues, valor: string) => void;
}

function Campo({ campo, rotulo, valor, erro, mono, onChange }: CampoProps) {
  return (
    <label className="config-field">
      <span className="config-label">{rotulo}</span>
      <input
        type="text"
        className={`config-input${mono ? " config-input-mono" : ""}${
          erro ? " config-input-error" : ""
        }`}
        data-testid={`config-${campo}`}
        value={valor}
        spellCheck={false}
        autoComplete="off"
        onChange={(e) => onChange(campo, e.target.value)}
      />
      {erro && <span className="config-error">{erro}</span>}
    </label>
  );
}

const DESTINOS = [
  { campo: "up", rotulo: "+1", classe: "animada" },
  { campo: "neutral", rotulo: "neutra", classe: "neutro" },
  { campo: "down", rotulo: "-1", classe: "lento" },
] as const;

/**
 * Aba Configuracao: port do settings_form.py.
 *
 * A ordem das secoes conta o fluxo do dado (entrada -> destinos -> dados do
 * app -> modelo), nao uma lista de campos equivalentes: tres pastas recebem
 * arquivo movido, e a tela precisa dizer isso.
 *
 * Sem seletor nativo de pasta por enquanto: o campo e texto. No Electron
 * isso vira dialog via IPC; no browser, `webkitdirectory` nao devolve um
 * caminho absoluto, entao nao serve.
 */
export function ConfigTab() {
  const c = useConfig();

  if (c.carregando) {
    return <div className="config-loading">Carregando configuração…</div>;
  }

  if (!c.state || !c.draft) {
    return (
      <div className="config-loading">
        <p>{c.falha ?? "Não foi possível carregar a configuração."}</p>
        <button type="button" className="config-save" onClick={c.recarrega}>
          Tentar de novo
        </button>
      </div>
    );
  }

  // O guard acima estreita c.draft, mas nao dentro dos callbacks .map;
  // a copia local mantem o tipo estreito no JSX inteiro.
  const draft = c.draft;

  return (
    <div className="config-tab" data-testid="config-tab">
      <header className="config-header">
        <div>
          <h1 className="config-title">Configuração</h1>
          <p className="config-subtitle">
            Para onde a música entra, para onde vai e o que o modelo aprende.
          </p>
        </div>
        {c.state.profiles.length > 1 && (
          <span className="config-profile">Perfil: {c.state.active_profile}</span>
        )}
      </header>

      {c.falha && (
        <div className="config-banner config-banner-error" role="alert">
          {c.falha}
        </div>
      )}
      {c.saved && !c.falha && (
        <div className="config-banner config-banner-ok" role="status">
          Configuração salva.
        </div>
      )}

      <section className="config-panel">
        <h2 className="config-section-title">Entrada</h2>
        <Campo
          campo="inbox"
          rotulo="Pasta de entrada"
          valor={draft.inbox}
          erro={c.errors.inbox}
          mono
          onChange={c.atualiza}
        />
      </section>

      <section className="config-panel">
        <h2 className="config-section-title">Destinos</h2>
        <p className="config-hint">
          Ao classificar, o arquivo é movido para a pasta do destino.
        </p>
        <div className="config-destinos">
          {DESTINOS.map((destino) => (
            <div key={destino.campo} className="config-destino">
              <span
                className={`config-dot config-dot-${destino.classe}`}
                aria-hidden="true"
              />
              <Campo
                campo={destino.campo}
                rotulo={destino.rotulo}
                valor={draft[destino.campo]}
                erro={c.errors[destino.campo]}
                mono
                onChange={c.atualiza}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="config-panel">
        <h2 className="config-section-title">Dados do app</h2>
        <Campo
          campo="data_dir"
          rotulo="Pasta de dados do app"
          valor={draft.data_dir}
          erro={c.errors.data_dir}
          mono
          onChange={c.atualiza}
        />
      </section>

      <section className="config-panel">
        <h2 className="config-section-title">Modelo</h2>
        <p className="config-hint">
          O modelo retreina sozinho depois de um número de decisões.
        </p>
        <div className="config-numericos">
          <label className="config-field">
            <span className="config-label">Retreinar a cada</span>
            <input
              type="number"
              min={1}
              max={1000}
              className="config-input config-input-numero"
              data-testid="config-retrain_every"
              value={draft.retrain_every}
              onChange={(e) =>
                c.atualiza("retrain_every", Number(e.target.value))
              }
            />
          </label>
          <label className="config-field">
            <span className="config-label">Mínimo de exemplos</span>
            <input
              type="number"
              min={1}
              max={1000}
              className="config-input config-input-numero"
              data-testid="config-min_examples"
              value={draft.min_examples}
              onChange={(e) =>
                c.atualiza("min_examples", Number(e.target.value))
              }
            />
          </label>
        </div>
      </section>

      <footer className="config-actions">
        <button
          type="button"
          className="config-save"
          data-testid="config-save"
          disabled={!c.podeSalvar}
          onClick={c.salvar}
        >
          {c.saving ? "Salvando…" : "Salvar"}
        </button>
      </footer>
    </div>
  );
}
