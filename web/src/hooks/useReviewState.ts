import { useCallback, useEffect, useRef, useState } from "react";
import {
  decide as apiDecide,
  undo as apiUndo,
  remove as apiRemove,
  bulkApprove as apiBulkApprove,
  switchProfile as apiSwitchProfile,
  scan as apiScan,
  computePeaks as apiComputePeaks,
  getReviewState,
  onWSMessage,
} from "../api/client";
import type { ReviewState, TrackRow } from "../api/types";

/**
 * Estado da aba Revisão com janela local de navegação.
 *
 * Espelha a lógica de review_tab.py: skip/back navegam DENTRO do snapshot
 * [current] + upcoming (máx. 4 tracks), sem round-trip ao backend.
 * Um states_changed novo sempre reseta a posição para 0.
 */
export function useReviewState() {
  const [state, setState] = useState<ReviewState | null>(null);
  const [position, setPosition] = useState(0);
  const [peaksRequested, setPeaksRequested] = useState<Set<string>>(new Set());
  const [peaksReady, setPeaksReady] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Snapshot local: [current, ...upcoming]
  const window_ = state?.current
    ? [state.current, ...state.upcoming]
    : [];
  const displayed: TrackRow | null =
    position >= 0 && position < window_.length ? window_[position] : null;

  // Fetch inicial + WS
  useEffect(() => {
    getReviewState()
      .then(setState)
      .catch((e) => setError(String(e)));

    const unsub = onWSMessage((msg) => {
      if (msg.type === "states_changed") {
        setState(msg.review);
        setPosition(0); // reset janela local
      }
      if (msg.type === "error") {
        setError(msg.message);
      }
      if (msg.type === "peaks_ready") {
        setPeaksRequested((prev) => {
          const next = new Set(prev);
          next.delete(msg.sha1);
          return next;
        });
        // Guarda o sha1 pronto: a linha da fila veio do states_changed
        // anterior e ainda tem peaks_path null. Sem isto a onda ficaria no
        // fallback mono ate o proximo broadcast, que so vem na proxima acao.
        setPeaksReady((prev) => new Set(prev).add(msg.sha1));
      }
      if (msg.type === "peaks_failed") {
        setPeaksRequested((prev) => {
          const next = new Set(prev);
          next.delete(msg.sha1);
          return next;
        });
      }
    });
    return unsub;
  }, []);

  // Ações (sempre sobre a track EXIBIDA, que pode não ser state.current)
  const decide = useCallback(
    async (label: number) => {
      if (!displayed) return;
      await apiDecide(displayed.sha1, label);
      // states_changed via WS vai chegar e resetar position
    },
    [displayed]
  );

  const undo = useCallback(async () => {
    await apiUndo();
  }, []);

  const remove = useCallback(async () => {
    if (!displayed) return;
    await apiRemove(displayed.sha1);
  }, [displayed]);

  const bulkApprove = useCallback(async () => {
    await apiBulkApprove();
  }, []);

  const skip = useCallback(() => {
    setPosition((p) => Math.min(p + 1, window_.length - 1));
  }, [window_.length]);

  const back = useCallback(() => {
    setPosition((p) => Math.max(p - 1, 0));
  }, []);

  const switchProfile = useCallback(async (name: string) => {
    await apiSwitchProfile(name);
  }, []);

  const scan = useCallback(async () => {
    await apiScan();
  }, []);

  // Peaks: pede uma vez por sha1 quando a track exibida não tem
  const requestPeaks = useCallback(
    (sha1: string) => {
      if (
        !displayed ||
        displayed.peaks_path ||
        peaksReady.has(sha1) ||
        peaksRequested.has(sha1)
      ) {
        return;
      }
      setPeaksRequested((prev) => new Set(prev).add(sha1));
      apiComputePeaks(sha1).catch(() => {
        setPeaksRequested((prev) => {
          const next = new Set(prev);
          next.delete(sha1);
          return next;
        });
      });
    },
    [displayed, peaksRequested, peaksReady]
  );

  return {
    state,
    displayed,
    position,
    remaining: state?.remaining ?? 0,
    peaksReady,
    error,
    decide,
    undo,
    remove,
    bulkApprove,
    skip,
    back,
    switchProfile,
    scan,
    requestPeaks,
  };
}
