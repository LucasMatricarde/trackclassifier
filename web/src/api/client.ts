import type {
  ConfigDraft,
  ReviewState,
  ValidationResult,
  WSMessage,
} from "./types";

const API_BASE = "";
let token: string | null = null;

function wsUrl(): string {
  // Conecta direto no backend (CORS já permite localhost:5173)
  return `ws://127.0.0.1:8765/ws?token=${token}`;
}

async function fetchToken(): Promise<string> {
  if (token) return token;
  const res = await fetch(`${API_BASE}/api/health`);
  const data = await res.json();
  token = data.token;
  return token;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const t = await fetchToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      "X-Auth-Token": t,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getReviewState(): Promise<ReviewState> {
  return apiFetch<ReviewState>("/api/review/state");
}

export async function decide(sha1: string, label: number): Promise<void> {
  await apiFetch("/api/review/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sha1, label }),
  });
}

export async function undo(): Promise<void> {
  await apiFetch("/api/review/undo", { method: "POST" });
}

export async function remove(sha1: string): Promise<void> {
  await apiFetch("/api/review/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sha1, label: 0 }),
  });
}

export async function bulkApprove(): Promise<{ count: number }> {
  return apiFetch("/api/review/bulk", { method: "POST" });
}

export async function switchProfile(name: string): Promise<void> {
  await apiFetch("/api/profiles/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function getConfig(): Promise<ConfigDraft> {
  return apiFetch<ConfigDraft>("/api/config");
}

export async function validateConfig(
  raw: Record<string, unknown>
): Promise<ValidationResult> {
  return apiFetch<ValidationResult>("/api/config/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw }),
  });
}

export async function applyConfig(
  raw: Record<string, unknown>
): Promise<{ ok: boolean }> {
  return apiFetch("/api/config/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw }),
  });
}

export async function scan(): Promise<void> {
  await apiFetch("/api/scan", { method: "POST" });
}

export async function cancelScan(): Promise<void> {
  await apiFetch("/api/scan/cancel", { method: "POST" });
}

export async function computePeaks(sha1: string): Promise<void> {
  await apiFetch(`/api/peaks/${sha1}/compute`, { method: "POST" });
}

// WebSocket singleton
let ws: WebSocket | null = null;
let wsListeners: ((msg: WSMessage) => void)[] = [];

export async function connectWS(): Promise<void> {
  if (ws?.readyState === WebSocket.OPEN) return;
  const t = await fetchToken();

  return new Promise((resolve, reject) => {
    ws = new WebSocket(wsUrl());

    ws.onopen = () => {
      console.log("WS conectado");
      resolve();
    };

    ws.onerror = (e) => {
      console.error("WS erro:", e);
      reject(e);
    };

    ws.onclose = () => {
      console.log("WS desconectado, tentando reconectar em 2s...");
      ws = null;
      setTimeout(connectWS, 2000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        wsListeners.forEach((fn) => fn(msg));
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };
  });
}

export function onWSMessage(fn: (msg: WSMessage) => void): () => void {
  wsListeners.push(fn);
  return () => {
    wsListeners = wsListeners.filter((l) => l !== fn);
  };
}

export function getAudioUrl(sha1: string): string {
  return `${API_BASE}/api/audio/${sha1}?token=${token}`;
}

export function getCoverUrl(sha1: string): string {
  return `${API_BASE}/api/cover/${sha1}?token=${token}`;
}

export function getThumbUrl(sha1: string): string {
  return `${API_BASE}/api/thumb/${sha1}?token=${token}`;
}

export function getPeaksUrl(sha1: string): string {
  return `${API_BASE}/api/peaks/${sha1}?token=${token}`;
}
