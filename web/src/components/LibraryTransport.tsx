import { useEffect } from "react";
import type { AudioPlayer } from "../hooks/useAudioPlayer";
import { CoverArt } from "./ui/CoverArt";
import { VolumeRail } from "./ui/VolumeRail";
import { VolumeIcon } from "./ui/PlayerIcons";
import { VDivider } from "./ui/VDivider";

interface LibraryTransportProps {
  track: {
    sha1: string;
    display_title: string;
    artist: string | null;
    duration_s: number;
  } | null;
  /**
   * Player compartilhado. Vive no LibraryTab para que o play do inspetor e o
   * da barra sejam o mesmo botao (o mockup mostra os dois acesos).
   */
  player: AudioPlayer;
}

/**
 * Barra de player da Biblioteca — fiel ao mockup.
 * Contem: capa mini + titulo/artista + coracao + transporte completo
 * (favorito, shuffle, prev, play, next, repeat) + tempo + progresso +
 * volume + icones de fila no fim.
 * O player vem pronto do LibraryTab (HTMLAudioElement + /api/audio/:sha1).
 */
export function LibraryTransport({ track, player }: LibraryTransportProps) {
  const {
    positionMs,
    durationMs,
    isPlaying,
    loadedSha1,
    load,
    toggle,
    seekFraction,
    volume,
    setVolume,
  } = player;

  const formatMs = (ms: number) => {
    const total = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fraction = Number(e.target.value);
    if (durationMs > 0) {
      seekFraction(fraction);
    }
  };

  const progress = durationMs > 0 ? positionMs / durationMs : 0;

  // Carrega a track quando selecao muda
  const trackSha1 = track?.sha1 ?? null;
  const trackDurationMs = track ? track.duration_s * 1000 : 0;

  useEffect(() => {
    if (trackSha1 && trackSha1 !== loadedSha1) {
      load(trackSha1, trackDurationMs);
    }
  }, [trackSha1, loadedSha1, trackDurationMs, load]);

  const enabled = track !== null;

  return (
    <div
      className="library-player"
      data-testid="library-player"
      aria-label="Transporte da Biblioteca"
    >
      {/* Capa mini + titulo/artista */}
      <div className="library-player-track">
        {track ? (
          <>
            <CoverArt
              sha1={track.sha1}
              size={40}
              radius={4}
              testId="library-player-cover"
            />
            <div className="library-player-meta">
              <span className="library-player-title" data-testid="library-player-title">
                {track.display_title}
              </span>
              <span className="library-player-artist muted">
                {track.artist ?? "—"}
              </span>
            </div>
            <button
              type="button"
              className="library-player-fav"
              data-testid="library-player-fav"
              title="Favoritar"
              disabled={!enabled}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path
                  d="M9 16.5l-6.5-4.5c-1.5-1-1.5-2.8 0-3.8l6.5-6.5c1.5-1 3.8-1 5.3 0l6.5 6.5c1.5 1 1.5 2.8 0 3.8L9 16.5Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </>
        ) : (
          <span className="muted">Nenhuma track selecionada</span>
        )}
      </div>

      <VDivider />

      {/* Transporte: favorito, shuffle, prev, play, next, repeat.
          O coracao e so visual (disabled) -- nao existe campo de favorito
          no modelo; mesmo contrato dos icones de fila/playlist no fim. */}
      <div className="library-player-transport">
        <button
          type="button"
          className="library-transport-btn"
          data-testid="library-transport-fav"
          title="Favorito"
          disabled
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"
              stroke="currentColor"
              strokeWidth="1.8"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          className="library-transport-btn"
          data-testid="library-shuffle"
          title="Aleatório"
          disabled={!enabled}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
        </button>
        <button
          type="button"
          className="library-transport-btn"
          data-testid="library-prev"
          title="Anterior"
          disabled={!enabled}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path
              d="M13 15V3l-9 6 9 6Z"
              fill="currentColor"
              stroke="none"
            />
            <path
              d="M5 3v12"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <button
          type="button"
          className="library-transport-play"
          data-testid="library-play"
          onClick={toggle}
          disabled={!enabled}
          aria-label={isPlaying ? "Pausar" : "Reproduzir"}
          aria-pressed={isPlaying}
        >
          {isPlaying ? (
            <svg width="24" height="24" viewBox="0 0 16 16" aria-hidden="true">
              <rect x="3" y="2" width="3" height="12" fill="currentColor" />
              <rect x="10" y="2" width="3" height="12" fill="currentColor" />
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M4 3v10l8-5-8-5Z" fill="currentColor" />
            </svg>
          )}
        </button>
        <button
          type="button"
          className="library-transport-btn"
          data-testid="library-next"
          title="Próxima"
          disabled={!enabled}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path
              d="M5 3v12l9-6-9-6Z"
              fill="currentColor"
              stroke="none"
            />
            <path
              d="M13 3v12"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <button
          type="button"
          className="library-transport-btn"
          data-testid="library-repeat"
          title="Repetir"
          disabled={!enabled}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path
              d="M3 6v6h6M15 12v6h-6M3 6h6M15 12h-6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
        </button>
      </div>

      <VDivider />

      {/* Tempo + progresso */}
      <div className="library-player-progress">
        <span className="library-time mono" data-testid="library-time">
          {formatMs(positionMs)} / {formatMs(durationMs)}
        </span>
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
      </div>

      <VDivider />

      {/* Volume */}
      <div className="library-player-volume">
        <button
          type="button"
          className="library-volume-btn"
          data-testid="library-volume-icon"
          aria-label="Volume"
        >
          <VolumeIcon />
        </button>
        <VolumeRail value={volume * 100} onChange={(v) => setVolume(v / 100)} width={100} />
      </div>

      <VDivider />

      {/* Icones de fila/playlist no fim */}
      <div className="library-player-queue">
        <button
          type="button"
          className="library-queue-btn"
          data-testid="library-queue"
          title="Fila de reproducao"
          disabled
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <rect x="2" y="2" width="3" height="14" rx="0.5" fill="currentColor" />
            <rect x="7.5" y="2" width="3" height="14" rx="0.5" fill="currentColor" />
            <rect x="13" y="2" width="3" height="14" rx="0.5" fill="currentColor" />
          </svg>
        </button>
        <button
          type="button"
          className="library-queue-btn"
          data-testid="library-playlist"
          title="Playlists"
          disabled
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path
              d="M3 3h12v12H3ZM7 7h8M7 11h8M7 15h8"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}