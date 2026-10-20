import { useEffect, useState } from "react";
import { connectWS, getWSStatus, onWSStatus } from "../api/client";

/**
 * Conecta o WebSocket e expoe o status da conexao.
 *
 * O status vem do cliente, e nao da promessa de connectWS: a promessa so
 * resolve na primeira conexao, entao uma queda posterior deixaria a aba
 * presa no loading para sempre.
 */
export function useWebSocket() {
  const [connected, setConnected] = useState(getWSStatus() === "open");

  useEffect(() => {
    const unsub = onWSStatus((status) => setConnected(status === "open"));
    connectWS().catch(() => {});
    return unsub;
  }, []);

  return { connected };
}
