import { useCallback, useEffect, useRef, useState } from "react";
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
  const [treinando, setTreinando] = useState(false);
  // Guard por ref e nao por estado: dois cliques no mesmo frame chamam a
  // MESMA closure (o state ainda esta false neles) e o batching do React
  // empurra o setTreinando para depois. O ref escreve sincrono e fecha a
  // janela; o estado vive so para desabilitar o botao na tela.
  const treinoEmVoo = useRef(false);

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
    // No maximo um treino no ar: o desktop enfileira os treinos na thread
    // unica do worker (moveToThread); dois POSTs concorrentes no backend
    // rodariam fit() e model.save() ao mesmo tempo, e service.train() nao
    // tem lock. No maximo um, sempre.
    if (treinoEmVoo.current) {
      return;
    }
    treinoEmVoo.current = true;
    setTreinando(true);
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
    } finally {
      treinoEmVoo.current = false;
      setTreinando(false);
    }
  }, [reload]);

  return { state, error, treinando, reload, requestTrain };
}
