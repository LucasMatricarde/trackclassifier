import { useEffect, useState, type ReactNode } from "react";
import { getConfigStats } from "../api/client";
import type { ConfigStats } from "../api/types";
import { useConfig } from "../hooks/useConfig";
import type { ConfigDraftValues } from "../configDraft";
import { IconeBanco, IconeEngrenagem, IconeInfo, IconePasta } from "./ui/ModelIcons";
import { Toggle } from "./ui/Toggle";

type CampoToggle = "create_under_root" | "auto_move_enabled" | "copia_entrada";

interface LinhaToggle {
  campo: CampoToggle;
  titulo: string;
  desc: string;
  /** So visual: o mockup desenha, o backend ainda nao tem o campo. */
  somenteVisual?: boolean;
}

const ORGANIZACAO: readonly LinhaToggle[] = [
  {
    campo: "create_under_root",
    titulo: "Criar pastas automaticamente",
    desc: "Cria a estrutura de pastas se não existir.",
  },
  {
    campo: "auto_move_enabled",
    titulo: "Mover arquivos após classificação",
    desc: "Move os arquivos da pasta de entrada para o destino.",
  },
  {
    campo: "copia_entrada",
    titulo: "Manter uma cópia na entrada",
    desc: "Mantém uma cópia do arquivo original.",
    somenteVisual: true,
  },
];

interface LinhaCaminhoProps {
  campo: keyof ConfigDraftValues;
  valor: string;
  erro?: string;
  onChange: (campo: keyof ConfigDraftValues, valor: string) => void;
}

/** Input de caminho com botao-icone de pasta e ESCOLHER, como o mockup. */
function LinhaCaminho({ campo, valor, erro, onChange }: LinhaCaminhoProps) {
  const seletor = window.trackclassifier?.selectFolder;
  const id = `config-${campo}`;

  const escolher = () => {
    void seletor?.(valor)
      .then((escolhido) => {
        if (escolhido) onChange(campo, escolhido);
      })
      .catch(() => {});
  };

  return (
    <div className="config-path-row">
      <input
        id={id}
        type="text"
        className={`config-input config-input-mono${erro ? " config-input-error" : ""}`}
        data-testid={id}
        value={valor}
        spellCheck={false}
        autoComplete="off"
        onChange={(e) => onChange(campo, e.target.value)}
      />
      <button
        type="button"
        className="config-icon-btn"
        data-testid={`config-icone-${campo}`}
        aria-label={`Escolher pasta ${campo}`}
        disabled={!seletor}
        onClick={escolher}
      >
        <IconePasta />
      </button>
      <button
        type="button"
        className="config-escolher"
        data-testid={`config-escolher-${campo}`}
        disabled={!seletor}
        onClick={escolher}
      >
        Escolher
      </button>
      {erro && <span className="config-error">{erro}</span>}
    </div>
  );
}

const DESTINOS = [
  { campo: "down", nome: "-1", energia: "Energia baixa", classe: "lento" },
  { campo: "neutral", nome: "neutra", energia: "Energia equilibrada", classe: "neutro" },
  { campo: "up", nome: "+1", energia: "Energia alta", classe: "animada" },
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
  const [stats, setStats] = useState<ConfigStats | null>(null);

  useEffect(() => {
    let vivo = true;
    // Degradacao: stats falhou, a tela segue sem as pills (invariante do
    // projeto para borda: nao derruba a tela inteira por um numero).
    getConfigStats()
      .then((s) => {
        if (vivo) setStats(s);
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

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
  const totalTracks = stats
    ? stats.destinations.up + stats.destinations.neutral + stats.destinations.down
    : 0;

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
            <div className="config-block">
              <div className="config-block-head">
                <span className="config-block-label">Pasta de entrada</span>
                {stats && (
                  <span className="config-pill" data-testid="config-pill-novas">
                    {stats.inbox_new}{" "}
                    {stats.inbox_new === 1 ? "NOVA" : "NOVAS"}
                  </span>
                )}
              </div>
              <LinhaCaminho
                campo="inbox"
                valor={draft.inbox}
                erro={c.errors.inbox}
                onChange={c.atualiza}
              />
            </div>

            <hr className="config-hairline" data-testid="config-hairline" />

            <div className="config-block">
              <div className="config-block-head">
                <div>
                  <span className="config-block-label">Pastas de destino</span>
                  <p className="config-block-sub">
                    Classificar MOVE o arquivo da pasta de entrada para o
                    destino correspondente.
                  </p>
                </div>
                {stats && (
                  <span className="config-pill" data-testid="config-pill-tracks">
                    {totalTracks} TRACKS
                  </span>
                )}
              </div>
              {DESTINOS.map((destino) => (
                <div
                  key={destino.campo}
                  className="config-destino-row"
                  data-testid="config-destino-row"
                >
                  <span
                    className={`config-destino-dot config-destino-dot-${destino.classe}`}
                    aria-hidden="true"
                  />
                  <span className="config-destino-nome">{destino.nome}</span>
                  <span className="config-destino-energia">
                    {destino.energia}
                  </span>
                  <LinhaCaminho
                    campo={destino.campo}
                    valor={draft[destino.campo]}
                    erro={c.errors[destino.campo]}
                    onChange={c.atualiza}
                  />
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard numero={2} titulo="Organização automática">
            <div className="config-toggle-row">
              {ORGANIZACAO.map((t) => (
                <Toggle
                  key={t.campo}
                  testid={`config-toggle-${t.campo}`}
                  ligado={
                    t.somenteVisual
                      ? true
                      : Boolean(
                          draft[
                            t.campo as "create_under_root" | "auto_move_enabled"
                          ]
                        )
                  }
                  somenteVisual={t.somenteVisual}
                  onChange={
                    t.somenteVisual
                      ? undefined
                      : (v) =>
                          c.atualiza(
                            t.campo as "create_under_root" | "auto_move_enabled",
                            v
                          )
                  }
                  rotulo={t.titulo}
                  descricao={t.desc}
                />
              ))}
            </div>
          </SectionCard>

          <SectionCard numero={3} titulo="Dados do aplicativo">
            <div className="config-dados-body">
              <div className="config-dados-esquerda">
                <div className="config-block-head">
                  <span className="config-block-label">
                    Pasta de dados do app
                  </span>
                  {stats && (
                    <span className="config-pill" data-testid="config-pill-dados">
                      {stats.analyses}{" "}
                      {stats.analyses === 1 ? "ANÁLISE" : "ANÁLISES"} ·{" "}
                      {Math.floor(stats.data_dir_mb)} MB
                    </span>
                  )}
                </div>
                <LinhaCaminho
                  campo="data_dir"
                  valor={draft.data_dir}
                  erro={c.errors.data_dir}
                  onChange={c.atualiza}
                />
              </div>

              <div className="config-storage" data-testid="config-storage">
                <div className="config-storage-head">
                  <span className="config-storage-icon" aria-hidden="true">
                    <IconeBanco tamanho={26} />
                  </span>
                  <div className="config-storage-texto">
                    <span
                      className="config-storage-titulo"
                      data-testid="config-storage-titulo"
                    >
                      Uso de armazenamento
                    </span>
                    <div className="config-storage-valores">
                      <strong data-testid="config-storage-usado">
                        {stats ? Math.floor(stats.data_dir_mb) : 0} MB
                        utilizados
                      </strong>
                      <span data-testid="config-storage-total">de 2 GB</span>
                    </div>
                  </div>
                </div>
                <div
                  className="config-storage-barra"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={2048}
                  aria-valuenow={Math.round(stats?.data_dir_mb ?? 0)}
                >
                  <span
                    className="config-storage-fill"
                    data-testid="config-storage-fill"
                    style={{
                      width: `${Math.min(100, ((stats?.data_dir_mb ?? 0) / 2048) * 100).toFixed(1)}%`,
                    }}
                  />
                </div>
                <button
                  type="button"
                  className="config-abrir-pasta"
                  data-testid="config-abrir-pasta"
                  aria-disabled={!window.trackclassifier?.revealItem}
                  onClick={() => {
                    void window.trackclassifier?.revealItem(draft.data_dir);
                  }}
                >
                  <IconePasta tamanho={14} />
                  Abrir pasta
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard numero={4} titulo="Modelo de classificação">
            <div className="config-modelo-body">
              <div className="config-modelo-campos">
                <div className="config-num-field">
                  <span className="config-block-label">Retreinar a cada</span>
                  <div className="config-num-row">
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      className="config-input"
                      data-testid="config-retrain_every"
                      value={draft.retrain_every}
                      onChange={(e) =>
                        c.atualiza("retrain_every", Number(e.target.value))
                      }
                    />
                    <span className="config-num-sufixo">
                      músicas classificadas
                    </span>
                  </div>
                </div>
                <div className="config-num-field">
                  <span className="config-block-label">
                    Mínimo de exemplos por classe
                  </span>
                  <div className="config-num-row">
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      className="config-input"
                      data-testid="config-min_examples"
                      value={draft.min_examples}
                      onChange={(e) =>
                        c.atualiza("min_examples", Number(e.target.value))
                      }
                    />
                    <span className="config-num-sufixo">músicas</span>
                  </div>
                </div>
              </div>

              <aside
                className="config-recomendacao"
                data-testid="config-recomendacao"
              >
                <span
                  className="config-recomendacao-icone"
                  aria-hidden="true"
                >
                  <IconeInfo tamanho={22} />
                </span>
                <div>
                  <span className="config-recomendacao-titulo">
                    Recomendação
                  </span>
                  <p className="config-recomendacao-texto">
                    Use pelo menos 20 exemplos por classe para obter um modelo
                    mais estável e preciso.
                  </p>
                </div>
              </aside>
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
