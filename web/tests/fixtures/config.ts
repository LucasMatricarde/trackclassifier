import type { Page, Route } from "@playwright/test";
import { libraryFixa, modeloFixo, reviewFixa } from "./modelo";

/**
 * Estado sintetico da aba Configuracao, servido pelos caminhos reais do
 * app (fetch + WebSocket) sem tocar no config.toml do usuario.
 *
 * Por que stubar tudo: com o auto-save do dashboard, qualquer edicao VALIDA
 * daria apply no config real -- os testes precisam de um backend de
 * mentira. O shim de WebSocket e o mesmo da fixture do Modelo: serve.py
 * retransmite states_changed no connect e o App segue o WS.
 */

export interface ConfigRaw {
  folders?: Record<string, string>;
  paths?: Record<string, string>;
  model?: Record<string, unknown>;
  [chave: string]: unknown;
}

export const configRawFixo: ConfigRaw = {
  folders: {
    inbox: "/musicas/entrada",
    up: "/musicas/Trik Trik +1",
    neutral: "/musicas/Trik Trik",
    down: "/musicas/Trik Trik -1",
  },
  paths: { data_dir: "/dados/trackclassifier" },
  model: { retrain_every: 10, min_examples: 50 },
};

export interface StubConfigHandle {
  /** Raws recebidos em POST /api/config/apply, em ordem. */
  aplicacoes: ConfigRaw[];
}

export interface StubConfigOpts {
  /** Handler custom para o apply (default: grava e devolve ok). */
  apply?: (route: Route, handle: StubConfigHandle) => Promise<void>;
}

export async function stubConfig(
  page: Page,
  opts: StubConfigOpts = {}
): Promise<StubConfigHandle> {
  const handle: StubConfigHandle = { aplicacoes: [] };
  let atual: ConfigRaw = JSON.parse(JSON.stringify(configRawFixo));

  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { ok: true, token: "stub", configured: true } })
  );
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { raw: atual, active_profile: "default", profiles: ["default"] },
    })
  );
  await page.route("**/api/config/validate", async (route) => {
    const body = route.request().postDataJSON() as { raw: ConfigRaw };
    const errors: Record<string, string> = {};
    // Mesma mensagem do validate_settings do servidor para inbox vazio.
    if (!body.raw.folders?.inbox?.trim()) {
      errors.inbox = "Escolha a pasta de entrada.";
    }
    await route.fulfill({ json: { valid: Object.keys(errors).length === 0, errors } });
  });
  if (opts.apply) {
    await page.route("**/api/config/apply", (route) => opts.apply!(route, handle));
  } else {
    await page.route("**/api/config/apply", async (route) => {
      const body = route.request().postDataJSON() as { raw: ConfigRaw };
      handle.aplicacoes.push(body.raw);
      atual = body.raw;
      await route.fulfill({ json: { ok: true } });
    });
  }

  const statesChanged = {
    type: "states_changed",
    review: reviewFixa,
    library: libraryFixa,
    model: modeloFixo,
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

  return handle;
}
