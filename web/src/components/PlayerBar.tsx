import { VolumeRail } from "./ui/VolumeRail";
import { VDivider } from "./ui/VDivider";
import { Kbd } from "./ui/Kbd";
import { RepeatIcon, VolumeIcon } from "./ui/PlayerIcons";

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
  /** 0..1, como no <audio>; a conversao para o 0-100 do trilho fica aqui. */
  volume: number;
  onVolumeChange: (v: number) => void;
  loop: boolean;
  onToggleLoop: () => void;
  rate: number;
  onCycleRate: () => void;
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
  volume,
  onVolumeChange,
  loop,
  onToggleLoop,
  rate,
  onCycleRate,
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
      <span className="player-volume-icon" data-testid="player-volume-icon" role="img" aria-label="Volume">
        <VolumeIcon />
      </span>
      <VolumeRail value={volume * 100} onChange={(v) => onVolumeChange(v / 100)} />
      <span className="mono time-display">
        {formatDuration(positionMs)} / {formatDuration(durationMs)}
      </span>
      <button
        type="button"
        className={`player-icon-btn${loop ? " active" : ""}`}
        data-testid="player-loop"
        aria-label="Repetir"
        aria-pressed={loop}
        title="Repetir"
        onClick={onToggleLoop}
        disabled={!enabled}
      >
        <RepeatIcon />
      </button>
      <button
        type="button"
        className="player-speed-chip"
        data-testid="player-speed"
        aria-label={`Velocidade ${rate}x`}
        title="Velocidade de reprodução"
        onClick={onCycleRate}
        disabled={!enabled}
      >
        {rate}x
      </button>
      <div className="player-spacer" />
      <span className="label-sentence">Ações</span>
      <div className="action-group">
        <button className="action-btn" onClick={onSkip} disabled={!enabled}>
          {/* icones portados de src/trackclassifier/ui/icons (viewBox 24) */}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 5.5v13l9-6.5z" fill="currentColor" stroke="none" />
            <path d="M17 5v14" />
          </svg>
          <span>Pular</span>
          <Kbd>S</Kbd>
        </button>
      </div>
      <div className="action-group">
        <button className="action-btn" onClick={onRemove} disabled={!enabled}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 7h16" />
            <path d="M10 7V5h4v2" />
            <path d="M6.5 7l1 13h9l1-13" />
            <path d="M10 11v5" />
            <path d="M14 11v5" />
          </svg>
          <span>Remover</span>
          <Kbd>D</Kbd>
        </button>
      </div>
      <button
        className="action-btn bulk-btn"
        onClick={onBulk}
        disabled={!enabled}
        title="Aprovar em bloco (confiança ≥ 0.75)"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M5 12.5l5 5 9-9" />
        </svg>
        <span>Aprovar em bloco</span>
      </button>
    </div>
  );
}
