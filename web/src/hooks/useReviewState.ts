import { useCallback, useEffect, useState } from "react";
import {
  decide as apiDecide,
  undo as apiUndo,
  remove as apiRemove,
  bulkApprove as apiBulkApprove,
  scan as apiScan,
  computePeaks as apiComputePeaks,
  getReviewState,
  onWSMessage,
} from "../api/client";
import type { ReviewState, TrackRow } from "../api/types";

/**
 * Mensagem de erro para a tela. O apiFetch ja extrai o `detail` do
 * backend; aqui so se evita o prefixo "Error:" e o texto cru de falha de
 * rede, que nao diz nada ao usuario.
 */
function mensagemDeErro(erro: unknown): string {
  if (erro instanceof TypeError) return "Falha de conexão com o servidor.";
  return erro instanceof Error ? erro.message : String(erro);
}

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

  /**
   * Recarrega a fila do backend.
   *
   * Usado na partida, no retry e depois de cada ação: o WebSocket é
   * otimização, não pré-requisito. Sem isto, uma queda de conexão deixaria
   * a fila parada mesmo com a ação tendo sido gravada.
   */
  const reload = useCallback(async () => {
    try {
      const novo = await getReviewState();
      setState(novo);
      setPosition(0);
      setError(null);
    } catch (erro) {
      setError(mensagemDeErro(erro));
    }
  }, []);

  // Fetch inicial + WS
  useEffect(() => {
    void reload();

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
  }, [reload]);

  // Ações (sempre sobre a track EXIBIDA, que pode não ser state.current)
  const decide = useCallback(
    async (label: number) => {
      if (!displayed) return;
      try {
        await apiDecide(displayed.sha1, label);
        await reload();
      } catch (erro) {
        setError(mensagemDeErro(erro));
      }
    },
    [displayed, reload]
  );

  const undo = useCallback(async () => {
    try {
      await apiUndo();
      await reload();
    } catch (erro) {
      setError(mensagemDeErro(erro));
    }
  }, [reload]);

  const remove = useCallback(async () => {
    if (!displayed) return;
    try {
      await apiRemove(displayed.sha1);
      await reload();
    } catch (erro) {
      setError(mensagemDeErro(erro));
    }
  }, [displayed, reload]);

  /**
   * Aprova em bloco. Devolve quantas tracks foram aprovadas, ou null quando
   * falhou -- o erro ja foi publicado no banner.
   */
  const bulkApprove = useCallback(async (): Promise<number | null> => {
    try {
      const { count } = await apiBulkApprove();
      await reload();
      return count;
    } catch (erro) {
      setError(mensagemDeErro(erro));
      return null;
    }
  }, [reload]);

  const skip = useCallback(() => {
    setPosition((p) => Math.min(p + 1, window_.length - 1));
  }, [window_.length]);

  const back = useCallback(() => {
    setPosition((p) => Math.max(p - 1, 0));
  }, []);

  // Clique num card da fila: salto direto para a posicao na janela local
  const goTo = useCallback(
    (i: number) => {
      setPosition(Math.min(Math.max(i, 0), window_.length - 1));
    },
    [window_.length]
  );

  const scan = useCallback(async () => {
    try {
      await apiScan();
    } catch (erro) {
      setError(mensagemDeErro(erro));
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

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
    reload,
    clearError,
    decide,
    undo,
    remove,
    bulkApprove,
    skip,
    back,
    goTo,
    scan,
    requestPeaks,
  };
}
