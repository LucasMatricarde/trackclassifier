import type { TrackRow } from "../api/types";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { OrdinalScale } from "./ui/OrdinalScale";
import { WaveformCanvas } from "./WaveformCanvas";

interface UpcomingListProps {
  tracks: TrackRow[];
  currentIndex: number;
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/**
 * As próximas da fila, em densidade compacta.
 * Port de upcoming_list.py — tabela simples, sem virtualização pesada (máx 3).
 */
export function UpcomingList({ tracks, currentIndex }: UpcomingListProps) {
  if (tracks.length === 0) return null;

  return (
    <div className="upcoming-list" data-testid="upcoming-list">
      <table>
        <tbody>
          {tracks.map((track, i) => (
            <tr
              key={track.sha1}
              className={i === currentIndex ? "upcoming-current" : ""}
            >
              <td className="col-cover">
                <CoverArt sha1={track.sha1} size={34} radius={3} />
              </td>
              <td className="col-title">
                <span className="title">{track.display_title}</span>
                {track.artist && (
                  <span className="artist muted">{track.artist}</span>
                )}
              </td>
              <td className="col-waveform">
                <WaveformCanvas
                  track={track}
                  progress={0}
                  height={22}
                  className="waveform-row"
                  energyOnly
                />
              </td>
              <td className="col-genre">{track.genre || "—"}</td>
              <td className="col-bpm mono">
                {track.bpm > 0 ? Math.round(track.bpm) : "—"}
              </td>
              <td className="col-key">
                <KeyChip keyData={track.key} />
              </td>
              <td className="col-class">
                <OrdinalScale label={track.predicted} size="line" />
              </td>
              <td className="col-duration mono">
                {formatDuration(track.duration_s)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
