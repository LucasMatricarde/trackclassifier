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
    key_source: null,
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
      peaks_path: "/cache/peaks/sha-alpha.npy",
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
/**
 * Gera um .npy float16 (shape (N, 3)) com bandas sinteticas, para as rotas
 * mockadas servirem uma onda valida. Sem isso a mini-onda da tabela fica
 * vazia nos testes e o screenshot nao mostra a coluna ONDA.
 */
function npyFloat16(bandas: number[][]): Buffer {
  const N = bandas.length;
  const header = `{'descr': '<f2', 'fortran_order': False, 'shape': (${N}, 3), }`;
  const base = 10 + header.length + 1;
  const padding = (64 - (base % 64)) % 64;
  const headerFinal = header + " ".repeat(padding) + "\n";

  const buf = Buffer.alloc(10 + headerFinal.length + N * 3 * 2);
  buf.write("\x93NUMPY", 0, "latin1");
  buf.writeUInt8(1, 6); // versao 1.0
  buf.writeUInt16LE(headerFinal.length, 8);
  buf.write(headerFinal, 10, "latin1");

  // Codificacao float16 (IEEE 754 half) correta para valores em [0, 1].
  // halfToFloat do npy.ts espera formato nativo; aqui escrevemos little-endian.
  function float32ToHalf(v: number): number {
    if (v <= 0) return 0x0000;
    if (v >= 1) return 0x3c00; // 1.0 em half
    // Encontra expoente e mantissa
    const e = Math.floor(Math.log2(v));
    const exp = Math.max(-14, Math.min(15, e)); // clamp para half normalizado
    const mantissa = Math.round((v / Math.pow(2, exp) - 1) * 1024);
    return ((exp + 15) << 10) | (mantissa & 0x03ff);
  }

  let offset = 10 + headerFinal.length;
  for (const banda of bandas) {
    for (const valor of banda) {
      const bits = float32ToHalf(Math.max(0, Math.min(1, valor)));
      buf.writeUInt16LE(bits, offset);
      offset += 2;
    }
  }
  return buf;
}

/**
 * Ondas sinteticas por track.
 *
 * O mockup mostra duas coisas ao mesmo tempo na coluna ONDA:
 * 1. envelope COMUM (a onda cresce, sustenta e cai) -> define a ALTURA
 * 2. blocos de COR PURA (verde, azul, rosa, magenta) -> define a MATIZ
 *
 * Para ter as duas, os valores por banda sao (balancoio de cor) escalados
 * de forma que a soma ponderada (0.55 low + 0.30 mid + 0.15 high) siga
 * exatamente o envelope global. Assim a altura e governada pelo envelope
 * e a cor pelo balancoio independente de cada banda.
 *
 * Buckets: 2000 (igual ao backend real) para densidade correta ao comprimir
 * em ~240px.
 */
function ondasFake(sha1: string): Buffer {
  const semente = sha1.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const buckets = 2000;
  const bandas: number[][] = [];
  // Tres geradores LCG independentes para low/mid/high
  let sLow = (semente * 1664525 + 1013904223) >>> 0;
  let sMid = (semente * 48271 + 1) >>> 0;
  let sHigh = (semente * 69069 + 12345) >>> 0;
  const m = 4294967296;
  // Fases aleatorias do balancoio de cor de cada banda (diferentes por track)
  const faseCorLow = (sLow % 1000) / 1000 * Math.PI * 2;
  const faseCorMid = (sMid % 1000) / 1000 * Math.PI * 2;
  const faseCorHigh = (sHigh % 1000) / 1000 * Math.PI * 2;
  // Cada banda domina em 1-3 segmentos ao longo da faixa
  const ciclosLow = 2 + (sLow % 3);
  const ciclosMid = 2 + (sMid % 3);
  const ciclosHigh = 2 + (sHigh % 3);
  // Pesos da envoltoria: os mesmos do RowWaveform/WaveformCanvas
  const WL = 0.55;
  const WM = 0.3;
  const WH = 0.15;

  for (let i = 0; i < buckets; i++) {
    const fase = i / buckets;
    // Envelope global: sino elevado -> 0 nas pontas, 1 no meio
    const envGlobal = Math.pow(Math.sin(fase * Math.PI), 0.8);
    // Balancoio de cor independente por banda
    const balLow = 0.5 + 0.5 * Math.sin(fase * Math.PI * ciclosLow + faseCorLow);
    const balMid = 0.5 + 0.5 * Math.sin(fase * Math.PI * ciclosMid + faseCorMid);
    const balHigh = 0.5 + 0.5 * Math.sin(fase * Math.PI * ciclosHigh + faseCorHigh);
    const somaBal = balLow + balMid + balHigh;
    let l = (balLow / somaBal) * envGlobal;
    let md = (balMid / somaBal) * envGlobal;
    let h = (balHigh / somaBal) * envGlobal;
    // Escala para que a soma ponderada bata com o envelope global
    const ponderada = WL * l + WM * md + WH * h;
    if (ponderada > 1e-6) {
      const k = envGlobal / ponderada;
      l *= k;
      md *= k;
      h *= k;
    }
    // Jitter forte e independente por banda (textura densa)
    sLow = (sLow * 1103515245 + 12345) >>> 0;
    sMid = (sMid * 1103515245 + 12345) >>> 0;
    sHigh = (sHigh * 1103515245 + 12345) >>> 0;
    l += (sLow / m) * 0.12;
    md += (sMid / m) * 0.12;
    h += (sHigh / m) * 0.12;
    bandas.push([Math.min(1, l), Math.min(1, md), Math.min(1, h)]);
  }
  return npyFloat16(bandas);
}

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

  // Mock dos .npy de peaks para a mini-onda da tabela (coluna ONDA)
  for (const row of state.rows) {
    await page.route(`**/api/peaks/${row.sha1}*`, async (route) => {
      const buf = ondasFake(row.sha1);
      await route.fulfill({ body: buf, contentType: "application/octet-stream" });
    });
  }
}
