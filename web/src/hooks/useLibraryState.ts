import { useCallback, useEffect, useState } from "react";
import { getLibraryState, onWSMessage } from "../api/client";
import type { LibraryState } from "../api/types";

/**
 * Estado da aba Biblioteca.
 *
 * Espelha o padrao do useReviewState: fetch inicial e a fonte de verdade,
 * o WebSocket e otimizacao. Um states_changed novo substitui o estado
 * inteiro -- a biblioteca nao tem janela local como a fila de revisao.
 */
export function useLibraryState() {
  const [state, setState] = useState<LibraryState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const novo = await getLibraryState();
      setState(novo);
      setError(null);
    } catch (erro) {
      // O apiFetch ja extrai o `detail` do backend; TypeError e falha de
      // rede, cujo texto cru ("Failed to fetch") nao diz nada ao usuario.
      setError(
        erro instanceof TypeError
          ? "Falha de conexao com o servidor."
          : erro instanceof Error
            ? erro.message
            : String(erro)
      );
    }
  }, []);

  // Fetch inicial + WS
  useEffect(() => {
    void reload();

    const unsub = onWSMessage((msg) => {
      if (msg.type === "states_changed") {
        setState(msg.library);
      }
      if (msg.type === "error") {
        setError(msg.message);
      }
    });
    return unsub;
  }, [reload]);

  return { state, error, reload };
}