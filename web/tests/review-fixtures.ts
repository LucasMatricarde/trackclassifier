import type { Page } from "@playwright/test";
import type { ReviewState, TrackRow } from "../src/api/types";
import { PNG_1PX, wavSilencioso } from "./fixtures/midia";
import { libraryFixa, modeloFixo } from "./fixtures/modelo";

/**
 * Fixtures da aba Revisao para os testes deterministicos.
 *
 * Nenhum teste aqui decide, move ou remove arquivo real: o estado da fila
 * vem de uma rota mockada e o WebSocket e substituido por um falso, entao o
 * backend nem chega a saber que a tela existe.
 */

export function track(sha1: string, title: string): TrackRow {
  return {
    sha1,
    filename: `${title}.mp3`,
    label: null,
    predicted: "+1",
    score: 0.82,
    confidence: 0.82,
    bpm: 128,
    duration_s: 180,
    energy_curve: [0.1, 0.4, 0.2, 0.8, 0.5, 0.3, 0.6, 0.2],
    peak_offset_s: 30,
    path_hint: `/tmp/${title}.mp3`,
    title,
    artist: "Artista Teste",
    genre: "House",
    album: "Album Teste",
    cover_path: null,
    peaks_path: null,
    key: null,
    key_source: null,
    display_title: title,
  };
}

export const TRACK_ALPHA = track("sha-alpha", "Alpha");
export const TRACK_BETA = track("sha-beta", "Beta");

export function estado(current: TrackRow, upcoming: TrackRow[] = []): ReviewState {
  return {
    current,
    upcoming,
    low_confidence: false,
    remaining: 1 + upcoming.length,
    profiles: ["default"],
    active_profile: "default",
  };
}

export const ESTADO_ALPHA = estado(TRACK_ALPHA, [TRACK_BETA]);
export const ESTADO_BETA = estado(TRACK_BETA);

/**
 * Substitui o WebSocket do navegador por um falso.
 *
 * "aberto"         -- abre de primeira (comportamento normal).
 * "quebrado"       -- sempre falha: simula o backend fora do ar.
 * "quebra-depois"  -- a primeira tentativa falha, a segunda abre: simula
 *                     uma queda de conexao que o cliente precisa recuperar.
 */
export async function fakeWebSocket(page: Page, modo: "aberto" | "quebrado" | "quebra-depois" = "aberto") {
  await page.addInitScript((modo) => {
    class FakeWebSocket {
      static OPEN = 1;
      static CONNECTING = 0;
      static CLOSED = 3;
      static tentativas = 0;

      readyState = 0;
      onopen: (() => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;

      constructor() {
        // Expoe a instancia para emitirWs: o teste empurra mensagens do
        // servidor (key_ready, peaks_ready...) sem backend nenhum.
        (window as unknown as { __fakeWs: unknown }).__fakeWs = this;
        const tentativa = FakeWebSocket.tentativas++;
        const falha =
          modo === "quebrado" || (modo === "quebra-depois" && tentativa === 0);
        setTimeout(() => {
          if (falha) {
            this.readyState = 3;
            this.onerror?.(new Event("error"));
            this.onclose?.();
          } else {
            this.readyState = 1;
            this.onopen?.();
          }
        }, 0);
      }

      send() {}

      close() {
        this.readyState = 3;
        this.onclose?.();
      }
    }

    (window as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;
  }, modo);
}

/**
 * Entrega ao app uma mensagem como se viesse do servidor pelo WebSocket falso.
 * Espera o socket abrir primeiro: antes disso nao ha listener para recebe-la.
 */
export async function emitirWs(page: Page, mensagem: unknown) {
  await page.waitForFunction(() => {
    const ws = (window as unknown as { __fakeWs?: { readyState: number } }).__fakeWs;
    return ws?.readyState === 1;
  });
  await page.evaluate((msg) => {
    const ws = (
      window as unknown as {
        __fakeWs: { onmessage: (e: { data: string }) => void };
      }
    ).__fakeWs;
    ws.onmessage({ data: JSON.stringify(msg) });
  }, mensagem);
}

/**
 * Manda o app para a aba Revisao sem depender do backend: o health responde
 * "configurado" e o estado da fila vem do fixture.
 */
export async function mockApi(page: Page, estadoFila: ReviewState) {
  await page.route("**/api/health*", (route) =>
    route.fulfill({
      json: { ok: true, token: "token-teste", configured: true },
    })
  );
  await page.route("**/api/review/state*", (route) =>
    route.fulfill({ json: estadoFila })
  );
  // A Revisao pede a tonalidade por audio de toda track sem key: sem este
  // stub o POST iria ao backend real, que decodificaria o arquivo e gravaria
  // no presentation.parquet do acervo.
  await page.route("**/api/key/*/detect*", (route) =>
    route.fulfill({ json: { ok: true, queued: true } })
  );
}

/**
 * A tela de Revisao inteira sobre a fila `estadoFila`, sem tocar no backend:
 * alem de health/fila (mockApi) e do WebSocket falso, estuba o que o header
 * e o player consultam (biblioteca, modelo, audio, capa, thumb). Para os
 * specs que medem ou interagem com a tela e precisam de uma track garantida
 * -- a fila real fica vazia quando o acervo todo ja foi classificado.
 */
export async function mockRevisaoCompleta(page: Page, estadoFila: ReviewState) {
  await fakeWebSocket(page);
  await mockApi(page, estadoFila);
  await page.route("**/api/library/state*", (route) =>
    route.fulfill({ json: libraryFixa })
  );
  await page.route("**/api/model/state*", (route) =>
    route.fulfill({ json: modeloFixo })
  );
  await page.route("**/api/audio/**", (route) =>
    route.fulfill({ body: wavSilencioso(0), contentType: "audio/wav" })
  );
  for (const rota of ["**/api/cover/**", "**/api/thumb/**"]) {
    await page.route(rota, (route) =>
      route.fulfill({ body: PNG_1PX, contentType: "image/png" })
    );
  }
}
