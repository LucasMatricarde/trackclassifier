import type { Page } from "@playwright/test";
import type { Key, LibraryState, ModelState, TrackRow } from "../src/api/types";
import { fakeWebSocket } from "./review-fixtures";

/**
 * Fixtures da aba Biblioteca para os testes deterministicos.
 *
 * Mesmo contrato das fixtures de Revisao: o WebSocket e falso e o estado
 * vem de rotas mockadas, entao o backend real nao participa do teste.
 */

const MODELO_VAZIO: ModelState = {
  accuracy: null,
  ordinal_mae: null,
  confusion: null,
  n_examples: 0,
  failures: [],
  class_counts: [0, 0, 0],
  decisions_since_train: 0,
  retrain_every: 20,
  train_blocked_reason: null,
  low_confidence: false,
  alpha: null,
  thresholds: null,
  extractor_name: "teste",
};

export const FIXTURE_VAZIA: LibraryState = {
  rows: [],
  class_counts: [0, 0, 0],
  total: 0,
  genres: [],
  keys: [],
};

/**
 * Constroi uma Key de mentira para os fixtures: so camelot/classic/numero
 * importam para a tela (chip, filtro e cor); pitch_class e mode sao carga
 * do contrato que o backend preenche de verdade.
 */
export function key(camelot: string, classic: string, numero: number): Key {
  return { pitch_class: 0, mode: "A", camelot, classic, camelot_number: numero };
}

function row(parcial: Partial<TrackRow> & Pick<TrackRow, "sha1" | "filename" | "display_title">): TrackRow {
  return {
    label: null,
    predicted: "+1",
    score: 0.9,
    confidence: 0.9,
    bpm: 128,
    duration_s: 180,
    energy_curve: [0.1, 0.4, 0.2, 0.8, 0.5, 0.3, 0.6, 0.2],
    peak_offset_s: 30,
    path_hint: "",
    title: null,
    artist: null,
    genre: null,
    album: null,
    cover_path: null,
    peaks_path: null,
    key: null,
    ...parcial,
  };
}

/**
 * Tres tracks, uma de cada classe, sustentando os testes da tabela:
 * titulos com caso misto (ordenacao sem caso), uma sem capa/key/artista
 * (Gamma) e a Alpha com key 8A/Am para o toggle de notacao.
 */
export const FIXTURE_TRES: LibraryState = {
  rows: [
    row({
      sha1: "sha-alpha",
      filename: "alpha.mp3",
      display_title: "Alpha",
      title: "Alpha",
      artist: "Artista Um",
      album: "Album Um",
      genre: "House",
      label: "-1",
      bpm: 128,
      duration_s: 200,
      cover_path: "/tmp/cover-alpha.jpg",
      key: key("8A", "Am", 8),
    }),
    row({
      sha1: "sha-beta",
      filename: "beta.mp3",
      display_title: "beta",
      title: "beta",
      artist: "Artista Dois",
      album: "Album Dois",
      genre: "Techno",
      label: "neutra",
      bpm: 124,
      duration_s: 190,
      cover_path: "/tmp/cover-beta.jpg",
      key: key("6A", "Gm", 6),
    }),
    row({
      sha1: "sha-gamma",
      filename: "gamma.mp3",
      display_title: "Gamma",
      title: "Gamma",
      genre: "House",
      label: "+1",
      bpm: 130,
      duration_s: 180,
    }),
  ],
  class_counts: [1, 1, 1],
  total: 3,
  genres: ["House", "Techno"],
  keys: ["6A", "8A"],
};

/**
 * Manda o app para a aba Biblioteca sem depender do backend: o health
 * responde "configurado" e o estado da biblioteca vem do fixture.
 */
export async function mockLibrary(page: Page, state: LibraryState) {
  await fakeWebSocket(page);
  // Sem health configurada o App cai na tela de setup antes da aba existir;
  // sem model/state o AppHeader depende do backend real (teste nao hermetico).
  await page.route("**/api/health*", async (route) => {
    await route.fulfill({ json: { ok: true, token: "token-teste", configured: true } })
  });
  await page.route("**/api/library/state*", async (route) => {
    await route.fulfill({ json: state })
  });
  await page.route("**/api/model/state*", async (route) => {
    await route.fulfill({ json: MODELO_VAZIO })
  });
  // Acoes da biblioteca usam os mesmos endpoints da revisao
  await page.route("**/api/review/decide*", async (route) => {
    await route.fulfill({ json: { ok: true, next: null, remaining: 0 } })
  });
  await page.route("**/api/review/remove*", async (route) => {
    await route.fulfill({ json: { ok: true } })
  });
}
