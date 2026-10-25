import type { ReactNode } from "react";
import { useConfig } from "../hooks/useConfig";
import type { ConfigDraftValues } from "../configDraft";
import { IconeEngrenagem, IconeInfo } from "./ui/ModelIcons";

interface CampoProps {
  campo: keyof ConfigDraftValues;
  rotulo: string;
  valor: string;
  erro?: string;
  onChange: (campo: keyof ConfigDraftValues, valor: string) => void;
}

function Campo({ campo, rotulo, valor, erro, onChange }: CampoProps) {
  const seletor = window.trackclassifier?.selectFolder;
  const id = `config-${campo}`;

  return (
    <div className="config-field">
      <label className="config-label" htmlFor={id}>
        {rotulo}
      </label>
      <div className="config-input-row">
        <input
          id={id}
          type="text"
          className={`config-input config-input-mono${
            erro ? " config-input-error" : ""
          }`}
          data-testid={`config-${campo}`}
          value={valor}
          spellCheck={false}
          autoComplete="off"
          onChange={(e) => onChange(campo, e.target.value)}
        />
        {seletor && (
          <button
            type="button"
            className="config-pick"
            onClick={() => {
              void seletor(valor)
                .then((escolhido) => {
                  if (escolhido) onChange(campo, escolhido);
                })
                .catch(() => {});
            }}
          >
            Escolher…
          </button>
        )}
      </div>
      {erro && <span className="config-error">{erro}</span>}
    </div>
  );
}

const DESTINOS = [
  { campo: "up", rotulo: "+1", classe: "animada" },
  { campo: "neutral", rotulo: "neutra", classe: "neutro" },
  { campo: "down", rotulo: "-1", classe: "lento" },
] as const;

const SUBTITULOS = [
  "Defina a pasta de entrada e os destinos para cada classificação.",
  "Comportamento ao criar pastas e mover arquivos.",
  "Cache de análises, modelo, capas e banco de dados da aplicação.",
  "Parâmetros de treinamento e quantidade mínima de exemplos.",
] as const;

function SectionCard({
  numero,
  titulo,
  children,
}: {
  numero: number;
  titulo: string;
  children?: ReactNode;
}) {
  return (
    <section className="config-section" data-testid={`config-section-${numero}`}>
      <header className="config-section-head">
        <span className="config-section-badge" aria-hidden="true">
          {numero}
        </span>
        <div>
          <h2 className="config-section-titulo">{titulo}</h2>
          <p className="config-section-sub">{SUBTITULOS[numero - 1]}</p>
        </div>
      </header>
      {children}
    </section>
  );
}

/**
 * Aba Configuracao do dashboard (mockup Settings): titulo com tile de
 * engrenagem, card de auto-save, 4 cards de secao numerados e sidebar de
 * resumo. Auto-save: o mockup nao desenha botao Salvar -- useConfig aplica
 * sozinho (ver o hook). O conteudo das secoes 1/3/4 e o do formulario
 * original; a fase B o reescreve no layout do mockup.
 */
export function ConfigDashboard() {
  const c = useConfig({ autoSave: true });

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

  const draft = c.draft;

  return (
    <div className="config-dash" data-testid="config-tab">
      <header className="config-dash-head">
        <div className="config-dash-title">
          <span className="config-title-tile" aria-hidden="true">
            <IconeEngrenagem tamanho={26} />
          </span>
          <div>
            <h1 className="config-title">Configurações</h1>
            <p className="config-subtitle">
              Configure pastas, organização, modelo e preferências do
              TrackClassifier.
            </p>
          </div>
        </div>
        <aside className="config-info-card" data-testid="config-info-card">
          <span className="config-info-icon" aria-hidden="true">
            <IconeInfo />
          </span>
          <p>
            Todas as configurações são salvas automaticamente. As alterações
            são aplicadas na próxima operação.
          </p>
        </aside>
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

      <div className="config-columns">
        <div className="config-main">
          <SectionCard numero={1} titulo="Pastas e organização">
            <Campo
              campo="inbox"
              rotulo="Pasta de entrada"
              valor={draft.inbox}
              erro={c.errors.inbox}
              onChange={c.atualiza}
            />
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
                    onChange={c.atualiza}
                  />
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard numero={2} titulo="Organização automática" />

          <SectionCard numero={3} titulo="Dados do aplicativo">
            <Campo
              campo="data_dir"
              rotulo="Pasta de dados do app"
              valor={draft.data_dir}
              erro={c.errors.data_dir}
              onChange={c.atualiza}
            />
          </SectionCard>

          <SectionCard numero={4} titulo="Modelo de classificação">
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
          </SectionCard>
        </div>

        <aside className="config-sidebar" data-testid="config-sidebar">
          <h2 className="config-sidebar-title">Resumo da configuração</h2>
        </aside>
      </div>
    </div>
  );
}
