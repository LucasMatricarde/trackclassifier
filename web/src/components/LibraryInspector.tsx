import { formatDuration } from "../library";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { ClassChip } from "./ui/ClassChip";
import { WaveformCanvas } from "./WaveformCanvas";
import { InspectorWaveform } from "./ui/InspectorWaveform";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { Tooltip } from "./ui/Tooltip";
import { useState } from "react";
import type { TrackRow } from "../api/types";

type InspectorTab = "info" | "analysis" | "file";

interface LibraryInspectorProps {
  track: TrackRow | null;
  /** 0..1 posicao do playhead. */
  progress?: number;
  /** Se os buckets RGB ja estao prontos. */
  peaksReady?: boolean;
  /** Callback ao clicar/arrastar na onda. */
  onSeek?: (fraction: number) => void;
  /** Play/pause do player. */
  onToggle?: () => void;
  /** Se esta tocando. */
  isPlaying?: boolean;
  /** Callback para classificar a track. */
  onClassify?: (label: number) => void;
  /** Callback para remover a track. */
  onRemove?: () => void;
  /** Callback para revelar no Finder. */
  onReveal?: () => void;
  /** Se pode revelar (so no Electron). */
  canReveal?: boolean;
  /** Mensagem de erro para exibir. */
  error?: string | null;
}

/**
 * Inspetor da Biblioteca — ficha tecnica da track selecionada.
 * Abas: Informações (campos + confiança + onda), Análise (onda maior + detalhes BPM/Key), Arquivo (caminho, nome, formato).
 * "Adicionar à fila de revisão" desabilitado + tooltip "Indisponível" (sem endpoint backend).
 */
export function LibraryInspector({
  track,
  progress = 0,
  peaksReady = false,
  onSeek,
  onToggle,
  isPlaying = false,
  onClassify,
  onRemove,
  onReveal,
  canReveal = false,
  error = null,
}: LibraryInspectorProps) {
  if (!track) {
    return (
      <div className="library-inspector" data-testid="library-inspector-empty">
        <p className="muted">Nenhuma track selecionada</p>
      </div>
    );
  }

  const bpm = Math.round(track.bpm);
  const [confirmRemoving, setConfirmRemoving] = useState(false);
  const [activeTab, setActiveTab] = useState<InspectorTab>("info");

  const renderTabContent = () => {
    switch (activeTab) {
      case "info":
        return (
          <>
            <dl className="library-inspector-fields">
              <div className="field-row">
                <dt className="muted">Gênero</dt>
                <dd data-testid="library-inspector-genre">
                  {track.genre ?? "—"}
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">BPM</dt>
                <dd className="mono" data-testid="library-inspector-bpm">
                  {bpm}
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">Key (Camelot)</dt>
                <dd data-testid="library-inspector-key">
                  <KeyChip keyData={track.key} />
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">Duração</dt>
                <dd className="mono" data-testid="library-inspector-duration">
                  {formatDuration(track.duration_s)}
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">Classe atual</dt>
                <dd data-testid="library-inspector-class">
                  <ClassChip label={track.label} />
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">Confiança</dt>
                <dd className="mono" data-testid="library-inspector-confidence">
                  {track.confidence !== undefined && track.confidence !== null
                    ? track.confidence.toFixed(2)
                    : "—"}
                </dd>
              </div>
            </dl>

            <InspectorWaveform
              trackSha1={track.sha1}
              peakOffset={track.peak_offset_s}
              duration={track.duration_s}
              progress={progress}
            />
          </>
        );

      case "analysis":
        return (
          <div className="library-analysis-tab">
            <WaveformCanvas
              track={track}
              progress={progress}
              onSeek={onSeek}
              height={180}
              peaksReady={peaksReady}
            />
            <div className="library-analysis-detail">
              <div className="field-row">
                <dt className="muted">BPM estimado</dt>
                <dd className="mono">{bpm}</dd>
              </div>
              <div className="field-row">
                <dt className="muted">Key detalhada</dt>
                <dd>
                  {track.key ? (
                    <>
                      <KeyChip keyData={track.key} />
                      <span className="library-key-classic muted">
                        {track.key.classic}
                      </span>
                    </>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div className="field-row">
                <dt className="muted">Energia (média)</dt>
                <dd className="mono">
                  {track.energy_curve && track.energy_curve.length > 0
                    ? (track.energy_curve.reduce((a, b) => a + b, 0) / track.energy_curve.length).toFixed(2)
                    : "—"}
                </dd>
              </div>
            </div>
          </div>
        );

      case "file":
        return (
          <dl className="library-inspector-fields library-file-fields">
            <div className="field-row">
              <dt className="muted">Caminho</dt>
              <dd data-testid="library-inspector-path" title={track.path_hint ?? ""}>
                {track.path_hint ?? "—"}
              </dd>
            </div>
            <div className="field-row">
              <dt className="muted">Arquivo</dt>
              <dd data-testid="library-inspector-filename">
                {track.filename ?? "—"}
              </dd>
            </div>
            <div className="field-row">
              <dt className="muted">Formato</dt>
              <dd data-testid="library-inspector-format">
                {track.filename?.split(".").pop()?.toUpperCase() ?? "—"}
              </dd>
            </div>
          </dl>
        );
    }
  };

  return (
    <div className="library-inspector">
      {error && (
        <div className="library-error-banner" data-testid="library-error">
          {error}
        </div>
      )}

      {/* Cabeçalho: capa (102px) com play 48px centrado e ⋮ no canto sup. dir.,
          título/artista empilhados abaixo */}
      <div className="library-inspector-header">
        <div className="library-inspector-cover-wrapper">
          <CoverArt
            sha1={track.sha1}
            size={102}
            radius={10}
            testId="library-inspector-cover"
          />
          <button
            type="button"
            className="library-cover-play"
            data-testid="library-play-inspector-header"
            onClick={onToggle}
            disabled={!onToggle}
            aria-label={isPlaying ? "Pausar" : "Reproduzir"}
          >
            {isPlaying ? (
              <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">
                <rect x="3" y="2" width="3" height="12" fill="currentColor" />
                <rect x="10" y="2" width="3" height="12" fill="currentColor" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M4 3v10l8-5-8-5Z" fill="currentColor" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className="library-cover-more"
            data-testid="library-inspector-more"
            aria-label="Mais opções"
            title="Mais opções"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="3" r="1.5" fill="currentColor" />
              <circle cx="8" cy="8" r="1.5" fill="currentColor" />
              <circle cx="8" cy="13" r="1.5" fill="currentColor" />
            </svg>
          </button>
        </div>
        <div className="library-inspector-title-block">
          <h2
            className="library-inspector-title"
            data-testid="library-inspector-title"
          >
            {track.display_title}
          </h2>
          <p className="library-inspector-artist muted">
            {track.artist ?? "—"}
          </p>
        </div>
      </div>

      {/* Abas */}
      <div className="library-inspector-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "info"}
          className={`library-inspector-tab ${activeTab === "info" ? "active" : ""}`}
          onClick={() => setActiveTab("info")}
          data-testid="library-tab-info"
        >
          Informações
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "analysis"}
          className={`library-inspector-tab ${activeTab === "analysis" ? "active" : ""}`}
          onClick={() => setActiveTab("analysis")}
          data-testid="library-tab-analysis"
        >
          Análise
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "file"}
          className={`library-inspector-tab ${activeTab === "file" ? "active" : ""}`}
          onClick={() => setActiveTab("file")}
          data-testid="library-tab-file"
        >
          Arquivo
        </button>
      </div>

      <div className="library-inspector-tab-content">
        {renderTabContent()}
      </div>

      {/* Ações rápidas — apenas na aba Informações */}
      {activeTab === "info" && (
        <div className="library-inspector-actions">
          <h3 className="muted">Ações rápidas</h3>

          {/* Classificação: 3 botões em caixas com bolinha colorida + kbd */}
          <div className="class-actions-boxed">
            <button
              type="button"
              className="class-action-boxed class-action-boxed-down"
              data-testid="library-class-down"
              aria-label="Classificar como -1 (1)"
              onClick={() => onClassify?.(-1)}
              disabled={!onClassify}
            >
              <span className="class-action-dot class-action-dot-down" />
              <span className="class-action-label">Classificar como -1</span>
              <kbd className="kbd kbd-inspector">1</kbd>
            </button>
            <button
              type="button"
              className="class-action-boxed class-action-boxed-neutral"
              data-testid="library-class-neutral"
              aria-label="Classificar como neutra (2)"
              onClick={() => onClassify?.(0)}
              disabled={!onClassify}
            >
              <span className="class-action-dot class-action-dot-neutral" />
              <span className="class-action-label">Classificar como neutra</span>
              <kbd className="kbd kbd-inspector">2</kbd>
            </button>
            <button
              type="button"
              className="class-action-boxed class-action-boxed-up"
              data-testid="library-class-up"
              aria-label="Classificar como +1 (3)"
              onClick={() => onClassify?.(1)}
              disabled={!onClassify}
            >
              <span className="class-action-dot class-action-dot-up" />
              <span className="class-action-label">Classificar como +1</span>
              <kbd className="kbd kbd-inspector">3</kbd>
            </button>
          </div>

          {/* Ações de arquivo: ícone + label + kbd. O mockup lista as três
              linhas sempre; as indisponíveis ficam com aria-disabled (texto
              continua legível) em vez de `disabled`, que as apagaria. */}
          <div className="file-actions-list">
            <Tooltip text={onToggle ? undefined : "Indisponível"}>
              <button
                type="button"
                className={`file-action-row ${onToggle ? "" : "file-action-row-unavailable"}`}
                data-testid="library-play-row"
                aria-label="Reproduzir (Espaço)"
                onClick={onToggle}
                aria-disabled={!onToggle || undefined}
              >
                <span className="file-action-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M4 3v10l8-5-8-5Z" fill="currentColor" />
                  </svg>
                </span>
                <span className="file-action-label">Reproduzir</span>
                <kbd className="kbd kbd-inspector">Space</kbd>
              </button>
            </Tooltip>
            <Tooltip text="Indisponível">
              <button
                type="button"
                className="file-action-row file-action-row-unavailable"
                data-testid="library-queue-row"
                aria-label="Adicionar à fila de revisão (R) — indisponível"
                aria-disabled="true"
              >
                <span className="file-action-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    <path
                      d="M3 4h8 M3 8h10 M3 12h10"
                      stroke="currentColor"
                      strokeWidth="1.3"
                      strokeLinecap="round"
                      fill="none"
                    />
                  </svg>
                </span>
                <span className="file-action-label">Adicionar à fila de revisão</span>
                <kbd className="kbd kbd-inspector">R</kbd>
              </button>
            </Tooltip>
            <Tooltip text={canReveal ? undefined : "Indisponível"}>
              <button
                type="button"
                className={`file-action-row ${canReveal ? "" : "file-action-row-unavailable"}`}
                data-testid="library-reveal-row"
                aria-label="Abrir no Finder (⌘ F)"
                onClick={onReveal}
                aria-disabled={!canReveal || undefined}
              >
                <span className="file-action-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    <path
                      fill="currentColor"
                      d="M15 7H8.5L7.5 5H3.5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"
                    />
                  </svg>
                </span>
                <span className="file-action-label">Abrir no Finder</span>
                <kbd className="kbd kbd-inspector">⌘ F</kbd>
              </button>
            </Tooltip>
          </div>

          {/* Remover da biblioteca — botão vermelho outline full width */}
          <button
            type="button"
            className="file-action-btn file-action-danger file-action-full"
            data-testid="library-remove"
            aria-label="Remover da biblioteca"
            onClick={() => setConfirmRemoving(true)}
            disabled={!onRemove}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M4 5v9a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V5M9 5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v2M5 5v9M10 5v9"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
            Remover da biblioteca
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirmRemoving}
        onConfirm={() => {
          onRemove?.();
          setConfirmRemoving(false);
        }}
        onCancel={() => setConfirmRemoving(false)}
        title="Remover da biblioteca"
        message="Tem certeza? O arquivo vai para a lixeira do sistema."
        confirmLabel="Confirmar"
        cancelLabel="Cancelar"
      />
    </div>
  );
}