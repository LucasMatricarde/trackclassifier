import { useEffect, useState } from "react";
import { apiFetch, onWSMessage, scan } from "../api/client";
import type { LibraryState, ModelState } from "../api/types";
import { dataCurta } from "../model-logic";
import type { TrainControl } from "../hooks/useModelState";
import { IconeRefresh } from "./ui/ModelIcons";

/**
 * Header persistente do app (mockup): logo, abas, status de scan e botao
 * ESCANEAR. Revisao, Biblioteca, Modelo e Configuracao.
 *
 * Na aba Modelo, o header ganha a ilha do mockup: ultimo treinamento,
 * versao ativa e o botao RETREINAR -- que compartilha o useModelState do
 * App (mesmo guard do botao do painel: dois gatilhos, um treino em voo).
 */
export type Aba = "revisao" | "biblioteca" | "modelo" | "configuracao";

interface AppHeaderProps {
  aba: Aba;
  onAba: (aba: Aba) => void;
  treino?: TrainControl;
}

export function AppHeader({ aba, onAba, treino }: AppHeaderProps) {
  const [library, setLibrary] = useState<LibraryState | null>(null);
  const [model, setModel] = useState<ModelState | null>(null);
  const [pending, setPending] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [progresso, setProgresso] = useState<{ done: number; total: number } | null>(
    null
  );

  useEffect(() => {
    apiFetch<LibraryState>("/api/library/state").then(setLibrary).catch(() => {});
    apiFetch<ModelState>("/api/model/state").then(setModel).catch(() => {});

    return onWSMessage((msg) => {
      if (msg.type === "states_changed") {
        setLibrary(msg.library);
        setModel(msg.model);
        setPending(msg.review.remaining);
      }
      if (msg.type === "scan_progress") {
        setScanning(true);
        setProgresso({ done: msg.done, total: msg.total });
      }
      if (msg.type === "scan_finished") {
        setScanning(false);
        setProgresso(null);
      }
    });
  }, []);

  const analisadas = library?.total ?? model?.n_examples ?? 0;
  const total = analisadas + pending;

  const disparaScan = async () => {
    setScanning(true);
    try {
      await scan();
    } finally {
      setScanning(false);
      setProgresso(null);
    }
  };

  return (
    <header className="app-header">
      <div className="app-logo">
        <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
          <g fill="var(--color-accent-base)">
            <rect x="2" y="8" width="2.5" height="6" rx="1" />
            <rect x="7" y="4" width="2.5" height="14" rx="1" />
            <rect x="12" y="6.5" width="2.5" height="9" rx="1" />
            <rect x="17" y="2.5" width="2.5" height="17" rx="1" />
          </g>
        </svg>
        <span className="app-logo-text">TrackClassifier</span>
      </div>

      <nav className="app-tabs" aria-label="Abas">
        <button
          type="button"
          className={`app-tab${aba === "revisao" ? " app-tab-active" : ""}`}
          aria-current={aba === "revisao" ? "page" : undefined}
          onClick={() => onAba("revisao")}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M3 2.5v11l10-5.5-10-5.5Z"
              fill="currentColor"
              opacity="0.9"
            />
          </svg>
          Revisão
        </button>
        <button
          type="button"
          className={`app-tab${aba === "biblioteca" ? " app-tab-active" : ""}`}
          aria-current={aba === "biblioteca" ? "page" : undefined}
          onClick={() => onAba("biblioteca")}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M5 2v12M1.5 4.5v7M8.5 3.5v9M12 5v6M15.5 6.5v3"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          Biblioteca
        </button>
        <button
          type="button"
          className={`app-tab${aba === "modelo" ? " app-tab-active" : ""}`}
          aria-current={aba === "modelo" ? "page" : undefined}
          onClick={() => onAba("modelo")}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M2 13.5V9M6 13.5V6M10 13.5V8M14 13.5V3.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </svg>
          Modelo
        </button>
        <button
          type="button"
          className={`app-tab${aba === "configuracao" ? " app-tab-active" : ""}`}
          aria-current={aba === "configuracao" ? "page" : undefined}
          onClick={() => onAba("configuracao")}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.4" fill="none" />
            <path
              d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </svg>
          Configuração
        </button>
      </nav>

      <div className="app-scan">
        {aba === "modelo" && treino && (
          <div className="app-model-island" data-testid="header-model-island">
            <div className="model-island-item">
              <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
                <rect x="4" y="8.5" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.4" fill="none" />
                <path d="M7 8.5V6.2a3 3 0 0 1 6 0v2.3" stroke="currentColor" strokeWidth="1.4" fill="none" />
              </svg>
              <div className="model-island-text">
                <span className="model-island-label">Último treinamento</span>
                <span className="model-island-value">
                  {treino.state?.last_trained_at
                    ? dataCurta(treino.state.last_trained_at)
                    : "—"}
                </span>
              </div>
            </div>
            <div className="model-island-item">
              <span className="model-island-dot" aria-hidden="true" />
              <div className="model-island-text">
                <span className="model-island-label">Modelo ativo</span>
                <span className="model-island-value">
                  {treino.state?.version ?? "Sem treinamento"}
                </span>
              </div>
            </div>
            <button
              type="button"
              className="btn-model-retrain"
              data-testid="header-model-retrain"
              onClick={treino.requestTrain}
              disabled={treino.treinando || !!treino.state?.train_blocked_reason}
              aria-disabled={treino.treinando || !!treino.state?.train_blocked_reason}
            >
              <IconeRefresh />
              {treino.treinando ? "Treinando…" : "Retreinar"}
            </button>
          </div>
        )}
        {/* O mockup do Modelo nao desenha scan no header: a ilha ocupa o
            lugar. Nas outras abas o bloco segue igual (Revisao congelada). */}
        {aba !== "modelo" && (
          <>
            <div className="scan-status">
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
                <path d="M8 4.5V8l2.5 1.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              <div className="scan-status-text">
                <span>{scanning ? "Escaneando" : "Scan concluído"}</span>
                <span className="muted">
                  {scanning && progresso
                    ? `${progresso.done} / ${progresso.total} · ${analisadas} analisadas`
                    : `${total} tracks · ${analisadas} analisadas`}
                </span>
              </div>
            </div>
            <button
              type="button"
              className="btn-scan"
              onClick={disparaScan}
              disabled={scanning}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M2 5.5V3a1 1 0 0 1 1-1h2.5M10.5 2H13a1 1 0 0 1 1 1v2.5M14 10.5V13a1 1 0 0 1-1 1h-2.5M5.5 14H3a1 1 0 0 1-1-1v-2.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path d="M4.5 8h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {scanning ? "Escaneando…" : "Escanear"}
            </button>
          </>
        )}
      </div>
    </header>
  );
}

