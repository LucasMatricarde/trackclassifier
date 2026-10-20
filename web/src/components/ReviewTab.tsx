import { useEffect } from "react";
import { useReviewState } from "../hooks/useReviewState";
import { useAudioPlayer } from "../hooks/useAudioPlayer";
import { useKeyboard } from "../hooks/useKeyboard";
import { useWebSocket } from "../hooks/useWebSocket";
import { ReviewHeader } from "./ReviewHeader";
import { WaveformCanvas } from "./WaveformCanvas";
import { DecisionBar } from "./DecisionBar";
import { PlayerBar } from "./PlayerBar";
import { QueueStrip } from "./QueueStrip";
import { EmptyState } from "./EmptyState";
import { Segmented } from "./ui/Segmented";

export function ReviewTab() {
  const review = useReviewState();
  const player = useAudioPlayer();
  const { connected } = useWebSocket();

  const { displayed, position, remaining, state } = review;

  // Carrega áudio quando a track muda
  useEffect(() => {
    if (displayed && displayed.sha1 !== player.loadedSha1) {
      player.load(displayed.sha1, displayed.duration_s * 1000);
      player.seek(displayed.peak_offset_s * 1000);
    }
  }, [displayed, player]);

  // Pede os buckets da track exibida (o scan so traz energy_curve)
  useEffect(() => {
    if (displayed) review.requestPeaks(displayed.sha1);
  }, [displayed, review.requestPeaks]);

  // Teclado
  useKeyboard(
    {
      onDecide: review.decide,
      onUndo: review.undo,
      onTogglePlay: player.toggle,
      onSkip: review.skip,
      onBack: review.back,
      onRemove: review.remove,
    },
    true
  );

  const fraction =
    player.durationMs > 0 ? player.positionMs / player.durationMs : 0;

  if (!connected) {
    return (
      <div className="review-loading" data-testid="review-tab">
        <p>Conectando ao servidor…</p>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="review-loading" data-testid="review-tab">
        <p>Carregando…</p>
      </div>
    );
  }

  if (!displayed) {
    return (
      <EmptyState
        title="Fila vazia"
        subtitle="Nenhuma track nova na inbox."
        actionLabel="Escanear"
        onAction={review.scan}
        testId="review-tab"
      />
    );
  }

  const upcomingTracks = state.upcoming.slice(position);
  const profileIndex = state.profiles.indexOf(state.active_profile);

  return (
    <div className="review-tab" data-testid="review-tab">
      {state.profiles.length > 1 && (
        <div className="profile-bar">
          <span className="micro-label">Perfil:</span>
          <Segmented
            options={state.profiles}
            selected={profileIndex}
            onChange={(i) => review.switchProfile(state.profiles[i])}
          />
        </div>
      )}

      <ReviewHeader
        track={displayed}
        remaining={remaining}
        position={position + 1}
        lowConfidence={state.low_confidence}
      />

      <div className="wave-panel">
        <WaveformCanvas
          track={displayed}
          progress={fraction}
          onSeek={player.seekFraction}
          height={120}
          className="waveform-main"
          ruler
          peaksReady={review.peaksReady.has(displayed.sha1)}
        />
        <div className="wave-overview-row">
          <button
            type="button"
            className="overview-step"
            aria-label="Voltar uma janela"
            onClick={() => player.seekFraction(Math.max(0, fraction - 1 / 6))}
          >
            ‹
          </button>
          <WaveformCanvas
            track={displayed}
            progress={fraction}
            onSeek={player.seekFraction}
            height={32}
            className="waveform-overview"
            peaksReady={review.peaksReady.has(displayed.sha1)}
            windowBox
          />
          <button
            type="button"
            className="overview-step"
            aria-label="Avançar uma janela"
            onClick={() => player.seekFraction(Math.min(1, fraction + 1 / 6))}
          >
            ›
          </button>
        </div>
      </div>

      <PlayerBar
        isPlaying={player.isPlaying}
        positionMs={player.positionMs}
        durationMs={player.durationMs}
        onToggle={player.toggle}
        onPrevious={review.back}
        onNext={review.skip}
        onSkip={review.skip}
        onRemove={review.remove}
        onBulk={review.bulkApprove}
        onVolumeChange={player.setVolume}
        enabled={!!displayed}
      />

      <DecisionBar track={displayed} onDecide={review.decide} />

      <QueueStrip
        tracks={displayed ? [displayed, ...upcomingTracks] : upcomingTracks}
        remaining={remaining}
        onSelect={(i) => review.goTo(position + i)}
      />
    </div>
  );
}
