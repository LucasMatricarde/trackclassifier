import type { TrackRow } from "../api/types";
import type { DetectedKey } from "../hooks/useReviewState";
import { useKeyNotation } from "../hooks/useKeyNotation";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { Meter } from "./ui/Meter";

interface ReviewHeaderProps {
  track: TrackRow;
  /** Key estimada pelo audio que chegou por WS depois do snapshot da fila. */
  detectedKey?: DetectedKey;
  remaining: number;
  position: number;
  lowConfidence: boolean;
}

const CLASS_NAMES: Record<string, string> = {
  "+1": "animada",
  neutra: "neutro",
  "-1": "lento",
};

const CLASS_LABELS: Record<string, string> = {
  "+1": "+1",
  neutra: "neutra",
  "-1": "-1",
};

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function formatExtension(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "";
}

/**
 * Header da aba Revisão: capa, título, chips, GuessBar, Progresso.
 * Port de review_header.py.
 */
export function ReviewHeader({
  track,
  detectedKey,
  remaining,
  position,
  lowConfidence,
}: ReviewHeaderProps) {
  const { notation, setNotation } = useKeyNotation();
  // So o artista: o genero ja aparece como chip logo abaixo (mockup)
  const subtitle = track.artist;
  const progress = remaining > 0 ? position / remaining : 0;
  // A tag manda: so cai para a estimativa quando a linha da fila nao traz key.
  const key = track.key ?? detectedKey?.key ?? null;
  const keySource = track.key ? track.key_source : (detectedKey?.source ?? null);

  return (
    <div className="review-header">
      <CoverArt sha1={track.sha1} size={132} radius={8} />
      <div className="review-identity">
        <div className="review-title">{track.display_title}</div>
        {subtitle && <div className="review-artist">{subtitle}</div>}
        <div className="review-chips">
          {track.genre && <span className="chip">{track.genre}</span>}
          {track.bpm > 0 && (
            <span className="chip">{Math.round(track.bpm)} BPM</span>
          )}
          {/* Sem tonalidade: so o "—". Com ela, o proprio badge alterna a
              notacao (o mockup nao tem um chip "CAMELOT" ao lado). */}
          {key ? (
            <button
              type="button"
              className="key-chip-trigger"
              title={
                keySource === "audio"
                  ? "Tonalidade estimada pelo áudio"
                  : "Alternar notação da tonalidade"
              }
              onClick={() =>
                setNotation(notation === "camelot" ? "classic" : "camelot")
              }
            >
              <KeyChip keyData={key} />
            </button>
          ) : (
            <KeyChip keyData={null} />
          )}
          <span className="chip">{formatDuration(track.duration_s)}</span>
          {formatExtension(track.filename) && (
            <span className="chip">{formatExtension(track.filename)}</span>
          )}
        </div>
      </div>

      <div className="review-stats">
        {/* GuessBar (mockup: duas colunas -- previsao com chip solido e
            confianca com valor + barra) */}
        {track.predicted && (
          <div className="stat-card guess-bar">
            <div className="guess-col">
              <span className="label-sentence">Previsão do modelo</span>
              <span
                className="guess-chip"
                style={{
                  background: `var(--color-class-${CLASS_NAMES[track.predicted] || "neutro"})`,
                }}
              >
                {CLASS_LABELS[track.predicted] || track.predicted}
              </span>
            </div>
            <div className="guess-col">
              <span className="label-sentence">Confiança</span>
              <span className="guess-confidence-value">
                {(track.confidence ?? 0).toFixed(2)}
              </span>
              <Meter
                value={track.confidence ?? 0}
                color={
                  (track.confidence ?? 0) < 0.4
                    ? "var(--color-state-warning)"
                    : "var(--color-text-secondary)"
                }
                height={6}
                label="Confiança do palpite"
              />
            </div>
            {lowConfidence && (
              <span className="micro-label warning-text">
                Modelo com poucos exemplos · confiança reduzida pela metade
              </span>
            )}
          </div>
        )}

        {/* Progresso */}
        <div className="stat-card progress-card">
          <span className="label-sentence">Progresso da revisão</span>
          <div className="progress-numbers">
            <span className="progress-count">
              {position} / {remaining}
            </span>
            {remaining > 0 && (
              <span className="progress-pct muted">
                {Math.round(progress * 100)}%
              </span>
            )}
          </div>
          <Meter value={progress} color="var(--color-accent-base)" height={6} />
        </div>
      </div>
    </div>
  );
}
