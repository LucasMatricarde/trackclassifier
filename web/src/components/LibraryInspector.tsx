import { formatDuration } from "../library";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { ClassChip } from "./ui/ClassChip";
import { WaveformCanvas } from "./WaveformCanvas";
import type { TrackRow } from "../api/types";

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
}

/**
 * Inspetor da Biblioteca — ficha tecnica da track selecionada.
 * Nao renderiza Confianca: na Biblioteca a track ja esta classificada e
 * a confianca do modelo sobre decisao humana tomada nao muda acao.
 * Mostrar condicional (so quando existir) evita travessao permanente.
 */
export function LibraryInspector({
  track,
  progress = 0,
  peaksReady = false,
  onSeek,
  onToggle,
  isPlaying = false,
}: LibraryInspectorProps) {
  if (!track) {
    return (
      <div className="library-inspector" data-testid="library-inspector-empty">
        <p className="muted">Nenhuma track selecionada</p>
      </div>
    );
  }

  const bpm = Math.round(track.bpm);

  return (
    <div className="library-inspector">
      <div className="library-inspector-header">
        <CoverArt
          sha1={track.sha1}
          size={120}
          radius={6}
          testId="library-inspector-cover"
        />
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

      <dl className="library-inspector-fields">
        <div className="field-row">
          <dt className="muted">Genero</dt>
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
          <dt className="muted">Key</dt>
          <dd data-testid="library-inspector-key">
            <KeyChip keyData={track.key} />
          </dd>
        </div>
        <div className="field-row">
          <dt className="muted">Duracao</dt>
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
      </dl>

      <div className="library-inspector-wave">
        <WaveformCanvas
          track={track}
          progress={progress}
          onSeek={onSeek}
          height={120}
          peaksReady={peaksReady}
        />
        <button
          type="button"
          className="library-inspector-play"
          data-testid="library-play-inspector"
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
      </div>

      <div className="library-inspector-actions">
        <h3 className="muted">Acoes rapidas</h3>
        <div className="class-actions">
          <button
            type="button"
            className="class-action-btn class-action-down"
            data-testid="library-class-down"
            aria-label="Classificar como lento (1)"
          >
            <span className="class-action-label">Lento</span>
            <kbd className="kbd">1</kbd>
          </button>
          <button
            type="button"
            className="class-action-btn class-action-neutral"
            data-testid="library-class-neutral"
            aria-label="Classificar como neutro (2)"
          >
            <span className="class-action-label">Neutro</span>
            <kbd className="kbd">2</kbd>
          </button>
          <button
            type="button"
            className="class-action-btn class-action-up"
            data-testid="library-class-up"
            aria-label="Classificar como animado (3)"
          >
            <span className="class-action-label">Animado</span>
            <kbd className="kbd">3</kbd>
          </button>
        </div>

        <h3 className="muted">Acoes de arquivo</h3>
        <div className="file-actions">
          <button
            type="button"
            className="file-action-btn"
            data-testid="library-reveal"
            aria-label="Revelar no Finder"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M3 13v-8a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1ZM8 4v8M11 4v8"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
            Revelar no Finder
          </button>
          <button
            type="button"
            className="file-action-btn file-action-danger"
            data-testid="library-remove"
            aria-label="Remover da biblioteca"
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
            Remover
          </button>
        </div>
      </div>
    </div>
  );
}