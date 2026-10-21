import type { TrackRow } from "../api/types";
import { CoverArt } from "./ui/CoverArt";

interface QueueStripProps {
  /** Janela completa [current, ...upcoming] -- o primeiro card é a track atual. */
  tracks: TrackRow[];
  /** Total restante na fila (backend), para o rótulo "N músicas restantes". */
  remaining: number;
  /** Índice do card selecionado na janela (0 = current). */
  selectedIndex: number;
  /** Clique num card pula para aquela posição na janela local. */
  onSelect: (index: number) => void;
}

/**
 * Fila de revisão como strip horizontal de cards (mockup + QueueItem do Qt:
 * bg surface-panel, radius sm; a atual ganha borda de acento de 2px).
 */
export function QueueStrip({ tracks, remaining, selectedIndex, onSelect }: QueueStripProps) {
  if (tracks.length === 0) return null;

  return (
    <section className="queue-strip" data-testid="queue-strip">
      <div className="queue-strip-label">
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path
            d="M2.5 4h13M2.5 9h13M2.5 14h8"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        <div className="queue-strip-label-text">
          <span className="queue-strip-title">Fila de revisão</span>
          <span className="queue-strip-count muted">
            {remaining} {remaining === 1 ? "música restante" : "músicas restantes"}
          </span>
        </div>
      </div>

      <div className="queue-cards" role="listbox" aria-label="Fila de revisão">
        {tracks.map((track, i) => (
          <button
            key={track.sha1}
            type="button"
            role="option"
            aria-selected={i === selectedIndex}
            className={`queue-card${i === selectedIndex ? " queue-card-current" : ""}`}
            onClick={() => onSelect(i)}
          >
            <CoverArt sha1={track.sha1} size={52} radius={3} />
            <span className="queue-card-text">
              <span className="queue-card-title">{track.display_title}</span>
              {track.artist && (
                <span className="queue-card-artist muted">{track.artist}</span>
              )}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
