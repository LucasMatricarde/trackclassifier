import { useCallback, useEffect, useState } from "react";
import { getModelState, trainModel, onWSMessage } from "../api/client";
import type { ModelState } from "../api/types";

/**
 * Estado da aba Modelo.
 *
 * Fetch inicial + WebSocket states_changed.model.
 * Inclui funcao para solicitar treino do modelo.
 */
export function useModelState() {
  const [state, setState] = useState<ModelState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const novo = await getModelState();
      setState(novo);
      setError(null);
    } catch (erro) {
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
        setState(msg.model);
      }
      if (msg.type === "error") {
        setError(msg.message);
      }
    });
    return unsub;
  }, [reload]);

  const requestTrain = useCallback(async () => {
    try {
      await trainModel();
      await reload();
    } catch (erro) {
      setError(
        erro instanceof TypeError
          ? "Falha de conexao com o servidor."
          : erro instanceof Error
            ? erro.message
            : String(erro)
      );
    }
  }, [reload]);

  return { state, error, reload, requestTrain };
}
