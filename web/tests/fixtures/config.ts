import type { Page, Route } from "@playwright/test";
import type { Profile, ScanPhase } from "../../src/api/types";
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

export interface ConfigStatsFixo {
  data_dir_mb: number;
  analyses: number;
  inbox_new: number;
  destinations: { up: number; neutral: number; down: number };
}

export const configStatsFixo: ConfigStatsFixo = {
  data_dir_mb: 112.5,
  analyses: 721,
  inbox_new: 6,
  destinations: { up: 286, neutral: 186, down: 71 },
};

export function perfilFixo(id: string, name: string): Profile {
  return {
    id,
    name,
    inputDir: "/musicas/entrada",
    destDirs: {
      "-1": "/musicas/Trik Trik -1",
      neutra: "/musicas/Trik Trik",
      "+1": "/musicas/Trik Trik +1",
    },
    orgToggles: { create: false, move: false, copy: true },
    model: { retrainEvery: 10, minPerClass: 50 },
    complete: true,
  };
}

export const perfisFixos: Profile[] = [perfilFixo("default", "Padrão")];

export interface ChamadaPerfil {
  metodo: string;
  caminho: string;
  corpo: unknown;
}

export interface StubConfigHandle {
  /** Raws recebidos em POST /api/config/apply, em ordem. */
  aplicacoes: ConfigRaw[];
  /** Chamadas a /api/profiles/**, em ordem. */
  perfilChamadas: ChamadaPerfil[];
}

export interface StubConfigOpts {
  /** Handler custom para o apply (default: grava e devolve ok). */
  apply?: (route: Route, handle: StubConfigHandle) => Promise<void>;
  /** Resposta de /api/config/stats (default: configStatsFixo). */
  stats?: ConfigStatsFixo;
  /** true: stats responde 500 (degradacao da tela). */
  statsErro?: boolean;
  /** Perfis servidos por /api/profiles (default: so o "Padrão"). */
  perfis?: Profile[];
  /** Id do perfil ativo inicial (default: o primeiro). */
  ativo?: string;
  /** Faixas pendentes da fila de Revisao (default: 0). */
  pendentes?: number;
  /** Fase de scan entregue no connect do WS, como o servidor faz (default: nenhuma). */
  scanFase?: ScanPhase;
}

export async function stubConfig(
  page: Page,
  opts: StubConfigOpts = {}
): Promise<StubConfigHandle> {
  const handle: StubConfigHandle = { aplicacoes: [], perfilChamadas: [] };
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
  // Perfis em memoria: espelha as regras do servidor (nome unico, Padrão
  // nao sai, excluir o ativo passa para o proximo) para o spec exercitar os
  // dialogos de ponta a ponta sem backend.
  let perfis: Profile[] = JSON.parse(JSON.stringify(opts.perfis ?? perfisFixos));
  let ativo = opts.ativo ?? perfis[0].id;
  const estado = () => ({ active: ativo, profiles: perfis });
  const nomeRepetido = (nome: string, ignorar?: string) =>
    perfis.some(
      (x) => x.id !== ignorar && x.name.trim().toLowerCase() === nome.trim().toLowerCase()
    );
  await page.route(/\/api\/profiles(\/.*)?$/, async (route) => {
    const req = route.request();
    const caminho = new URL(req.url()).pathname;
    const corpo = req.postDataJSON?.() ?? null;
    handle.perfilChamadas.push({ metodo: req.method(), caminho, corpo });
    const partes = caminho.replace("/api/profiles", "").split("/").filter(Boolean);
    const erro = (detail: string) =>
      route.fulfill({ status: 400, json: { detail } });

    if (req.method() === "GET") return route.fulfill({ json: estado() });
    if (partes[0] === "switch") {
      const id = (corpo as { id: string }).id;
      if (!perfis.some((x) => x.id === id)) return erro("Perfil desconhecido");
      ativo = id;
      return route.fulfill({ json: estado() });
    }
    if (req.method() === "POST" && partes.length === 0) {
      const { name, copyFolders } = corpo as { name: string; copyFolders: boolean };
      if (!name.trim() || nomeRepetido(name)) return erro("Nome invalido");
      const base = perfis.find((x) => x.id === ativo)!;
      const novo = copyFolders
        ? { ...base, id: name.toLowerCase().replace(/\W+/g, "-"), name }
        : {
            ...base,
            id: name.toLowerCase().replace(/\W+/g, "-"),
            name,
            inputDir: "",
            destDirs: { "-1": "", neutra: "", "+1": "" },
            complete: false,
          };
      perfis = [...perfis, novo];
      ativo = novo.id;
      return route.fulfill({ json: estado() });
    }
    const id = partes[0];
    if (req.method() === "PATCH") {
      const { name } = corpo as { name: string };
      if (!name.trim() || nomeRepetido(name, id)) return erro("Nome invalido");
      perfis = perfis.map((x) => (x.id === id ? { ...x, name } : x));
      return route.fulfill({ json: estado() });
    }
    if (req.method() === "POST" && partes[1] === "duplicate") {
      const base = perfis.find((x) => x.id === id)!;
      perfis = [...perfis, { ...base, id: `${id}-copia`, name: `${base.name} (cópia)` }];
      return route.fulfill({ json: estado() });
    }
    if (req.method() === "DELETE") {
      if (id === "default") return erro("O perfil Padrão não pode ser excluído.");
      const i = perfis.findIndex((x) => x.id === id);
      perfis = perfis.filter((x) => x.id !== id);
      if (ativo === id) ativo = perfis[Math.min(i, perfis.length - 1)].id;
      return route.fulfill({ json: estado() });
    }
    return route.fulfill({ status: 404, json: { detail: "rota" } });
  });
  await page.route("**/api/review/state", (route) =>
    route.fulfill({ json: { ...reviewFixa, remaining: opts.pendentes ?? 0 } })
  );
  // Registrado depois do /api/config: o Playwright resolve rotas em ordem
  // inversa de registro, e "**/api/config" nao casa com .../stats mesmo assim.
  await page.route("**/api/config/stats", (route) => {
    if (opts.statsErro) {
      return route.fulfill({ status: 500, json: { detail: "erro" } });
    }
    return route.fulfill({ json: opts.stats ?? configStatsFixo });
  });

  const statesChanged = {
    type: "states_changed",
    review: reviewFixa,
    library: libraryFixa,
    model: modeloFixo,
  };

  // Mensagens entregues no connect: o servidor manda o states_changed e, logo
  // depois, a fase atual do scan.
  const aoConectar: unknown[] = [statesChanged];
  if (opts.scanFase) aoConectar.push({ type: "scan_phase", phase: opts.scanFase });

  await page.addInitScript((mensagens) => {
    const payloads = mensagens.map((m) => JSON.stringify(m));
    const abertos: FakeWebSocket[] = [];
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
          for (const payload of payloads) {
            if (self.onmessage) self.onmessage({ type: "message", data: payload });
          }
        }, 0);
        abertos.push(this);
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
    // Empurra uma mensagem do "servidor" depois do connect (scan_phase etc.).
    (window as any).__emitWS = (msg: unknown) => {
      const data = JSON.stringify(msg);
      for (const socket of abertos) {
        // deno-lint-ignore no-explicit-any
        const self = socket as any;
        if (self.readyState === 1 && self.onmessage) {
          self.onmessage({ type: "message", data });
        }
      }
    };
  }, aoConectar);

  return handle;
}
