import type {
  ModelState,
  ConfigState,
  ConfigStats,
  HealthState,
  LibraryState,
  Profile,
  ProfilesState,
  ReviewState,
  ScanStatus,
  ValidationResult,
  WSMessage,
} from "./types";

const API_BASE = "";
let token: string | null = null;

function wsUrl(t: string): string {
  // Em dev o Vite (5173) nao tem o WS no proxy para este cliente: conecta
  // direto no backend. No build servido pelo proprio FastAPI, same-origin.
  const base = import.meta.env.DEV
    ? "ws://127.0.0.1:8765"
    : `ws://${window.location.host}`;
  return `${base}/ws?token=${t}`;
}

async function fetchToken(): Promise<string> {
  if (token) return token;
  const res = await fetch(`${API_BASE}/api/health`);
  const data: { token: string } = await res.json();
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

export async function getLibraryState(): Promise<LibraryState> {
  return apiFetch<LibraryState>("/api/library/state");
}

export async function getModelState(): Promise<ModelState> {
  return apiFetch<ModelState>("/api/model/state");
}

export async function trainModel(): Promise<{ ok: boolean }> {
  return apiFetch("/api/model/train", { method: "POST" });
}

export async function updateModelSettings(body: {
  retrain_every: number;
  min_examples: number;
}): Promise<{ ok: boolean }> {
  return apiFetch("/api/model/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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

const JSON_HEADERS = { "Content-Type": "application/json" };

/** Servidor antigo (`{active, all}` so com nomes) vira o formato completo, sem
 * pastas: a tela segue funcionando ate o backend novo subir. */
function normalizaPerfis(bruto: unknown): ProfilesState {
  const dado = bruto as { active: string; profiles?: Profile[]; all?: string[] };
  if (Array.isArray(dado.profiles)) {
    return { active: dado.active, profiles: dado.profiles };
  }
  const vazio = { "-1": "", neutra: "", "+1": "" };
  return {
    active: dado.active,
    profiles: (dado.all ?? []).map((nome) => ({
      id: nome,
      name: nome === "default" ? "Padrão" : nome,
      inputDir: "",
      destDirs: vazio,
      orgToggles: { create: false, move: false, copy: false },
      model: { retrainEvery: 10, minPerClass: 15 },
      complete: true,
    })),
  };
}

export async function getProfiles(): Promise<ProfilesState> {
  return normalizaPerfis(await apiFetch("/api/profiles"));
}

export async function createProfile(
  name: string,
  copyFolders: boolean
): Promise<ProfilesState> {
  return apiFetch<ProfilesState>("/api/profiles", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name, copyFolders }),
  });
}

export async function renameProfile(
  id: string,
  name: string
): Promise<ProfilesState> {
  return apiFetch<ProfilesState>(`/api/profiles/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name }),
  });
}

export async function duplicateProfile(id: string): Promise<ProfilesState> {
  return apiFetch<ProfilesState>(
    `/api/profiles/${encodeURIComponent(id)}/duplicate`,
    { method: "POST" }
  );
}

export async function deleteProfile(id: string): Promise<ProfilesState> {
  return apiFetch<ProfilesState>(`/api/profiles/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function activateProfile(id: string): Promise<ProfilesState> {
  return apiFetch<ProfilesState>("/api/profiles/switch", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ id }),
  });
}

export async function getHealth(): Promise<HealthState> {
  return apiFetch<HealthState>("/api/health");
}

export async function getConfig(): Promise<ConfigState> {
  return apiFetch<ConfigState>("/api/config");
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

export async function getConfigStats(): Promise<ConfigStats> {
  return apiFetch<ConfigStats>("/api/config/stats");
}

export async function resetConfig(): Promise<{ ok: boolean }> {
  return apiFetch("/api/config/reset", { method: "POST" });
}

export async function scan(): Promise<void> {
  await apiFetch("/api/scan", { method: "POST" });
}

export async function getScanStatus(): Promise<ScanStatus> {
  return apiFetch<ScanStatus>("/api/scan/status");
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

export type WSStatus = "connecting" | "open" | "closed";

let wsStatus: WSStatus = "closed";
let wsPromise: Promise<void> | null = null;
let wsRetryTimer: ReturnType<typeof setTimeout> | null = null;
const wsStatusListeners = new Set<(status: WSStatus) => void>();

function setWSStatus(status: WSStatus) {
  wsStatus = status;
  wsStatusListeners.forEach((fn) => fn(status));
}

export function getWSStatus(): WSStatus {
  return wsStatus;
}

/**
 * Assina o status da conexao. O listener e chamado na hora com o estado
 * atual, para o consumidor nao comecar em "desconectado" quando o socket
 * ja esta aberto.
 */
export function onWSStatus(fn: (status: WSStatus) => void): () => void {
  wsStatusListeners.add(fn);
  fn(wsStatus);
  return () => {
    wsStatusListeners.delete(fn);
  };
}

/**
 * Agenda uma reconexao. Um timer so: com dois hooks chamando connectWS,
 * cada queda geraria duas tentativas e o segundo socket ficaria orfao.
 */
function agendarReconexao() {
  if (wsRetryTimer) return;
  wsRetryTimer = setTimeout(() => {
    wsRetryTimer = null;
    void connectWS().catch(() => {});
  }, 2000);
}

export async function connectWS(): Promise<void> {
  if (ws?.readyState === WebSocket.OPEN) return;
  // Uma promessa so por tentativa: dois hooks chamando connectWS no mesmo
  // tick criariam dois sockets, e o segundo sobrescreveria o primeiro no
  // singleton -- o socket orfao continuaria aberto pelo resto da sessao.
  if (wsPromise) return wsPromise;

  setWSStatus("connecting");

  wsPromise = (async () => {
    let t: string;
    try {
      t = await fetchToken();
    } catch (e) {
      // Sem token nao ha nem handshake: e o mesmo caso de backend fora.
      setWSStatus("closed");
      agendarReconexao();
      throw e;
    }

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(wsUrl(t));
      ws = socket;

      socket.onopen = () => {
        setWSStatus("open");
        if (wsRetryTimer) {
          clearTimeout(wsRetryTimer);
          wsRetryTimer = null;
        }
        resolve();
      };

      socket.onerror = (e) => {
        setWSStatus("closed");
        // Agenda aqui tambem: o onclose normalmente vem em seguida, mas se
        // ele nao vier (socket morto sem close), ficariamos sem retry.
        agendarReconexao();
        reject(e);
      };

      socket.onclose = () => {
        setWSStatus("closed");
        if (ws === socket) ws = null;
        agendarReconexao();
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage;
          wsListeners.forEach((fn) => fn(msg));
        } catch (e) {
          console.error("WS parse error:", e);
        }
      };
    });
  })();

  try {
    await wsPromise;
  } finally {
    wsPromise = null;
  }
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
