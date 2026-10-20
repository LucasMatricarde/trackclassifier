import { VolumeRail } from "./ui/VolumeRail";
import { VDivider } from "./ui/VDivider";
import { Kbd } from "./ui/Kbd";

interface PlayerBarProps {
  isPlaying: boolean;
  positionMs: number;
  durationMs: number;
  onToggle: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onSkip: () => void;
  onRemove: () => void;
  onBulk: () => void;
  onVolumeChange: (v: number) => void;
  enabled: boolean;
}

function formatDuration(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/**
 * Barra de transporte + ações da aba Revisão.
 * Port de player_bar.py.
 */
export function PlayerBar({
  isPlaying,
  positionMs,
  durationMs,
  onToggle,
  onPrevious,
  onNext,
  onSkip,
  onRemove,
  onBulk,
  onVolumeChange,
  enabled,
}: PlayerBarProps) {
  return (
    <div className="player-bar" data-testid="player-bar">
      <button
        className="transport-play"
        onClick={onToggle}
        aria-label={isPlaying ? "Pausar" : "Tocar"}
        disabled={!enabled}
      >
        {isPlaying ? "⏸" : "▶"}
      </button>
      <button
        className="transport-nav"
        onClick={onPrevious}
        aria-label="Música anterior"
        disabled={!enabled}
      >
        ⏮
      </button>
      <button
        className="transport-nav"
        onClick={onNext}
        aria-label="Próxima música"
        disabled={!enabled}
      >
        ⏭
      </button>
      <VDivider />
      <span className="micro-label">Volume</span>
      <VolumeRail value={80} onChange={onVolumeChange} />
      <span className="mono time-display">
        {formatDuration(positionMs)} / {formatDuration(durationMs)}
      </span>
      <div className="player-spacer" />
      <span className="micro-label">Ações</span>
      <div className="action-group">
        <button className="action-btn" onClick={onSkip} disabled={!enabled}>
          Pular
        </button>
        <Kbd>S</Kbd>
      </div>
      <div className="action-group">
        <button className="action-btn" onClick={onRemove} disabled={!enabled}>
          Remover
        </button>
        <Kbd>D</Kbd>
      </div>
      <button
        className="action-btn bulk-btn"
        onClick={onBulk}
        disabled={!enabled}
        title="Aprovar em bloco (confiança ≥ 0.75)"
      >
        ✓ Aprovar em bloco
      </button>
    </div>
  );
}
