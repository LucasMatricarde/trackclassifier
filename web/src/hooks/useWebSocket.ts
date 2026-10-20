import { useEffect, useState } from "react";
import { connectWS, onWSMessage } from "../api/client";
import type { WSMessage } from "../api/types";

/**
 * Conecta o WebSocket e expõe o último evento recebido + status.
 */
export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  useEffect(() => {
    let cancelled = false;

    connectWS()
      .then(() => {
        if (!cancelled) setConnected(true);
      })
      .catch(() => {
        if (!cancelled) setConnected(false);
      });

    const unsub = onWSMessage((msg) => {
      setLastMessage(msg);
    });

    return () => {
      cancelled = true;
      unsub();
    };
  }, []);

  return { connected, lastMessage };
}
