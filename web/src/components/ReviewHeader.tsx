import type { TrackRow } from "../api/types";
import { useKeyNotation } from "../hooks/useKeyNotation";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { Meter } from "./ui/Meter";
import { OrdinalScale } from "./ui/OrdinalScale";

interface ReviewHeaderProps {
  track: TrackRow;
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
  remaining,
  position,
  lowConfidence,
}: ReviewHeaderProps) {
  useKeyNotation(); // re-render quando notação muda
  const subtitle = [track.artist, track.genre].filter(Boolean).join(" · ");
  const progress = remaining > 0 ? position / remaining : 0;

  return (
    <div className="review-header">
      <CoverArt sha1={track.sha1} size={136} radius={10} />
      <div className="review-identity">
        <div className="review-title">{track.display_title}</div>
        {subtitle && <div className="review-artist">{subtitle}</div>}
        <div className="review-chips">
          {track.genre && <span className="chip">{track.genre}</span>}
          {track.bpm > 0 && (
            <span className="chip">{Math.round(track.bpm)} BPM</span>
          )}
          <KeyChip keyData={track.key} />
          <span className="chip">{formatDuration(track.duration_s)}</span>
          {formatExtension(track.filename) && (
            <span className="chip">{formatExtension(track.filename)}</span>
          )}
        </div>
      </div>

      <div className="review-stats">
        {/* GuessBar */}
        {track.predicted && (
          <div className="stat-card guess-bar">
            <span className="micro-label">Palpite</span>
            <OrdinalScale label={track.predicted} size="guess" />
            <span
              className="guess-value"
              style={{
                color: `var(--color-class-${CLASS_NAMES[track.predicted] || "neutro"})`,
              }}
            >
              {CLASS_LABELS[track.predicted] || track.predicted}
            </span>
            <Meter
              value={track.confidence ?? 0}
              color={
                (track.confidence ?? 0) < 0.4
                  ? "var(--color-state-warning)"
                  : "var(--color-text-secondary)"
              }
              height={2}
              label="Confiança do palpite"
            />
            <span className="guess-confidence">
              confiança {(track.confidence ?? 0).toFixed(2)}
            </span>
            {lowConfidence && (
              <span className="micro-label warning-text">
                Modelo com poucos exemplos · confiança reduzida pela metade
              </span>
            )}
          </div>
        )}

        {/* Progresso */}
        <div className="stat-card progress-card">
          <span className="micro-label">Progresso da revisão</span>
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
          <Meter value={progress} color="var(--color-accent-base)" height={8} />
        </div>
      </div>
    </div>
  );
}
