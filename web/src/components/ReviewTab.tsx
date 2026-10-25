import { useEffect, useRef, useState } from "react";
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
import { ErrorBanner } from "./ui/ErrorBanner";
import { ConfirmDialog } from "./ui/ConfirmDialog";

export function ReviewTab() {
  const review = useReviewState();
  const player = useAudioPlayer();
  const { connected } = useWebSocket();

  const { displayed, position, remaining, state } = review;

  const [confirmandoBloco, setConfirmandoBloco] = useState(false);
  const [executandoBloco, setExecutandoBloco] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  // Ref e nao estado: o botao desabilitado so protege depois do re-render,
  // e dois cliques no mesmo frame ainda chamariam o onConfirm duas vezes.
  const blocoEmAndamento = useRef(false);

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

  // O status some sozinho: e informacao de uma acao pontual, nao um estado.
  useEffect(() => {
    if (!status) return;
    const id = setTimeout(() => setStatus(null), 4000);
    return () => clearTimeout(id);
  }, [status]);

  /**
   * Aprova em bloco. O Qt pergunta antes (review_tab.py:_pedir_bloco):
   * o bloco mexe em varias tracks de uma vez, entao a confirmacao existe
   * porque o alcance e grande -- nao porque o destino seja irreversivel.
   */
  const aprovarEmBloco = async () => {
    if (blocoEmAndamento.current) return;
    blocoEmAndamento.current = true;
    setExecutandoBloco(true);
    const count = await review.bulkApprove();
    blocoEmAndamento.current = false;
    setExecutandoBloco(false);
    setConfirmandoBloco(false);
    if (count === null) return;
    setStatus(
      count > 0 ? `${count} tracks aprovadas.` : "Nenhuma track elegível."
    );
  };

  if (!state) {
    return (
      <div className="review-loading" data-testid="review-tab">
        {review.error ? (
          <div className="review-retry">
            {/* Sem botao de fechar aqui: dispensar o aviso tiraria da tela
                o unico caminho de volta -- o "Tentar novamente". */}
            <ErrorBanner message={review.error} />
            <button
              type="button"
              className="btn-primary"
              onClick={() => void review.reload()}
              data-testid="review-retry"
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <p>{connected ? "Carregando…" : "Conectando ao servidor…"}</p>
        )}
      </div>
    );
  }

  const profileIndex = state.profiles.indexOf(state.active_profile);

  // A barra de perfil fica fora do early return da fila vazia: sem ela,
  // um perfil sem pendencias prenderia o usuario no EmptyState, sem
  // caminho de volta para o outro perfil (o backend sempre manda todos).
  // Sem o rotulo "Perfil:": o mockup nao tem esse texto. Com um perfil so
  // (o "default" de quem nunca criou outro) nao ha o que trocar e o seletor
  // virava a pill "DEFAULT", que o mockup tambem nao tem: so aparece com
  // dois ou mais.
  const profileBar = state.profiles.length > 1 && (
    <div className="profile-bar">
      <Segmented
        options={state.profiles}
        selected={profileIndex}
        onChange={(i) => review.switchProfile(state.profiles[Number(i)])}
      />
    </div>
  );

  if (!displayed) {
    return (
      <div className="review-tab" data-testid="review-tab">
        {review.error && (
          <ErrorBanner message={review.error} onDismiss={review.clearError} />
        )}
        {!connected && (
          <div className="review-offline" role="status" data-testid="review-offline">
            Sem conexão em tempo real; reconectando…
          </div>
        )}
        {profileBar}
        <EmptyState
          title="Fila vazia"
          subtitle="Nenhuma track nova na inbox."
          actionLabel="Escanear"
          onAction={review.scan}
        />
      </div>
    );
  }

  return (
    <div className="review-tab" data-testid="review-tab">
      {review.error && (
        <ErrorBanner message={review.error} onDismiss={review.clearError} />
      )}
      {status && (
        <div className="review-status" role="status" data-testid="review-status">
          {status}
        </div>
      )}
      {!connected && (
        <div className="review-offline" role="status" data-testid="review-offline">
          Sem conexão em tempo real; reconectando…
        </div>
      )}

      {profileBar}

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
          height={240}
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
            height={64}
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
        onBulk={() => setConfirmandoBloco(true)}
        onVolumeChange={player.setVolume}
        loop={player.loop}
        onToggleLoop={() => player.setLoop(!player.loop)}
        rate={player.rate}
        onCycleRate={player.cycleRate}
        enabled={!!displayed}
      />

      <DecisionBar track={displayed} onDecide={review.decide} />

      <QueueStrip
        tracks={state.current ? [state.current, ...state.upcoming] : state.upcoming}
        remaining={remaining}
        selectedIndex={position}
        onSelect={(i) => review.goTo(i)}
      />

      <ConfirmDialog
        open={confirmandoBloco}
        title="Aprovar em bloco"
        message="Mover todas as tracks com confiança >= 0.75?"
        confirmLabel="Aprovar"
        busy={executandoBloco}
        onConfirm={() => void aprovarEmBloco()}
        onCancel={() => setConfirmandoBloco(false)}
      />
    </div>
  );
}
