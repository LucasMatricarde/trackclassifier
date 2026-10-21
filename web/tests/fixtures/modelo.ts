import type { Page, Route } from "@playwright/test";
import type {
  LibraryState,
  ModelState,
  ReviewState,
} from "../../src/api/types";

/**
 * Estado sintetico da aba Modelo, espelhando ModelState de
 * ../src/api/types.ts, e o instalador que entrega esse estado pelo caminho
 * real do app (fetch + WebSocket) sem depender da biblioteca local.
 *
 * Por que o shim de WebSocket: serve.py retransmite states_changed no
 * connect, e tanto o AppHeader quanto o useModelState seguem o WS. Stub
 * atrapalhando so o fetch atende metade do caminho e o estado real da
 * biblioteca sobrescreve a fixture. O WS falso conecta e entrega o
 * states_changed sintetico com os mesmos valores das rotas de fetch.
 */

export const reviewFixa: ReviewState = {
  current: null,
  upcoming: [],
  low_confidence: false,
  remaining: 0,
  profiles: ["default"],
  active_profile: "default",
};

export const libraryFixa: LibraryState = {
  rows: [],
  class_counts: [3, 14, 13],
  total: 30,
  genres: [],
  keys: [],
};

export const modeloFixo: ModelState = {
  accuracy: 0.923,
  ordinal_mae: 0.25,
  // Linhas batem com class_counts (3/14/13); tem severidade 0, 1 e 2 nao
  // zeradas (o teste de fidelidade de cor usa :not(.zero)) e celulas
  // zeradas nas tres severidades.
  confusion: [
    [2, 0, 1],
    [0, 13, 1],
    [0, 1, 12],
  ],
  n_examples: 30,
  failures: [
    ["a1.mp3", "Falha ao decodificar", "AudioDecodeError"],
    ["a2.mp3", "Falha ao decodificar", "AudioDecodeError"],
    ["a3.mp3", "Falha ao decodificar", "AudioDecodeError"],
    ["a4.mp3", "Falha ao decodificar", "AudioDecodeError"],
    ["a5.mp3", "Falha ao decodificar", "AudioDecodeError"],
    ["a6.mp3", "arquivo faltando", "PathNotFound"],
  ],
  // lento (3) tem 21% da maior (14): abaixo do limiar de 70%, a linha de
  // recomendacao aparece.
  class_counts: [3, 14, 13],
  decisions_since_train: 5,
  retrain_every: 10,
  train_blocked_reason: null,
  low_confidence: true,
  alpha: 0.8,
  thresholds: [0.351, 0.649],
  extractor_name: "handcrafted-v1",
};

export interface StubModeloOpts {
  /** Sobrescreve campos do ModelState (ex.: train_blocked_reason). */
  model?: Partial<ModelState>;
  /**
   * Estado servido nos GETs de /api/model/state posteriores ao POST de
   * treino: requestTrain refaz o fetch e o teste ve a metrica nova sem
   * depender do WS.
   */
  stateAposTreino?: ModelState;
  /** Handler custom para POST /api/model/train (default: ok). */
  train?: (route: Route) => Promise<void>;
}

export async function stubAbaModelo(page: Page, opts: StubModeloOpts = {}) {
  const model: ModelState = { ...modeloFixo, ...opts.model };
  let treinado = false;

  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: { ok: true, token: "stub", configured: true },
    })
  );
  await page.route("**/api/model/state", (route) =>
    route.fulfill({ json: treinado && opts.stateAposTreino ? opts.stateAposTreino : model })
  );
  await page.route("**/api/review/state", (route) => route.fulfill({ json: reviewFixa }));
  if (opts.train) {
    await page.route("**/api/model/train", (route) => opts.train!(route));
  } else {
    await page.route("**/api/model/train", async (route) => {
      treinado = true;
      await route.fulfill({ json: { ok: true } });
    });
  }

  const statesChanged = {
    type: "states_changed",
    review: reviewFixa,
    library: libraryFixa,
    model,
  };

  await page.addInitScript((msg) => {
    const payload = JSON.stringify(msg);
    class FakeWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      readyState = 0;
      url: string;
      onopen: unknown = null;
      onmessage: unknown = null;
      onerror: unknown = null;
      onclose: unknown = null;
      // Client.ts atribui os handlers logo apos o construtor, entao o
      // connect tem que esperar o proximo macrotask.
      constructor(url: string) {
        this.url = url;
        setTimeout(() => {
          this.readyState = 1;
          // deno-lint-ignore no-explicit-any
          const self = this as any;
          if (self.onopen) self.onopen({ type: "open" });
          if (self.onmessage) self.onmessage({ type: "message", data: payload });
        }, 0);
      }
      send() {}
      close() {
        // deno-lint-ignore no-explicit-any
        const self = this as any;
        self.readyState = 3;
        if (self.onclose) self.onclose({ type: "close" });
      }
    }
    (window as any).WebSocket = FakeWebSocket;
  }, statesChanged);
}
