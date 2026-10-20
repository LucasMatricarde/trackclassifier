import { VolumeRail } from "./ui/VolumeRail";

interface LibraryTransportProps {
  isPlaying: boolean;
  positionMs: number;
  durationMs: number;
  onToggle: () => void;
  onSeek: (ms: number) => void;
  onVolumeChange: (v: number) => void;
  enabled: boolean;
}

/**
 * Barra de transporte fixa no fim da aba Biblioteca.
 * Contem play/pause, tempo, seek range e volume.
 */
export function LibraryTransport({
  isPlaying,
  positionMs,
  durationMs,
  onToggle,
  onSeek,
  onVolumeChange,
  enabled,
}: LibraryTransportProps) {
  const formatMs = (ms: number) => {
    const total = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fraction = Number(e.target.value);
    if (durationMs > 0) {
      onSeek(fraction * durationMs);
    }
  };

  const progress = durationMs > 0 ? positionMs / durationMs : 0;

  return (
    <div
      className="library-player"
      data-testid="library-player"
      aria-label="Transporte da Biblioteca"
    >
      <button
        type="button"
        className="library-play"
        data-testid="library-play"
        onClick={onToggle}
        disabled={!enabled}
        aria-label={isPlaying ? "Pausar" : "Reproduzir"}
        aria-pressed={isPlaying}
      >
        {isPlaying ? (
          <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">
            <rect x="3" y="2" width="3" height="12" fill="currentColor" />
            <rect x="10" y="2" width="3" height="12" fill="currentColor" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M4 3v10l8-5-8-5Z"
              fill="currentColor"
            />
          </svg>
        )}
      </button>

      <div className="library-time" data-testid="library-time">
        <span className="mono">{formatMs(positionMs)}</span>
        <span className="muted"> / </span>
        <span className="mono">{formatMs(durationMs)}</span>
      </div>

      <input
        type="range"
        className="library-seek"
        min="0"
        max="1"
        step="0.001"
        value={progress}
        onChange={handleSeekChange}
        disabled={!enabled || durationMs <= 0}
        aria-label="Posicao da reproducao"
      />

      <VolumeRail
        value={Math.round(100)}
        onChange={(v) => onVolumeChange(v / 100)}
        width={100}
      />
    </div>
  );
}