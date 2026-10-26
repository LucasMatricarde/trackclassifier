import { expect, test } from "@playwright/test";
import type { TrackRow } from "../src/api/types";
import {
  applyLibraryView,
  CLASS_CHIPS,
  DEFAULT_LIBRARY_VIEW,
  formatDuration,
} from "../src/library";
import { key } from "./library-fixtures";

/**
 * Testes puros de applyLibraryView/formatDuration -- nao abrem pagina,
 * rodam direto no worker do Playwright.
 */

function row(
  parcial: Partial<TrackRow> & Pick<TrackRow, "sha1" | "filename" | "display_title" | "bpm">
): TrackRow {
  return {
    label: null,
    predicted: null,
    score: null,
    confidence: null,
    duration_s: 180,
    energy_curve: [],
    peak_offset_s: 0,
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

// Quatro tracks cobrindo as bordas: uma sem capa/key (Zulu), uma sem
// artista (Gamma), titulos com caso misto para a ordenacao pt-BR.
const ROWS: TrackRow[] = [
  row({
    sha1: "sha-alpha",
    filename: "alpha.mp3",
    display_title: "Alpha",
    bpm: 128,
    artist: "Artista A",
    album: "album-x",
    genre: "House",
    label: "+1",
    key: key("6A", "Gm", 6),
    duration_s: 200,
  }),
  row({
    sha1: "sha-beta",
    filename: "arquivo-y.mp3",
    display_title: "beta",
    bpm: 124,
    artist: "Artista B",
    album: "Album B",
    genre: "House",
    label: "neutra",
    duration_s: 190,
  }),
  row({
    sha1: "sha-gamma",
    filename: "gamma.mp3",
    display_title: "Gamma",
    bpm: 130,
    genre: "Techno",
    label: "-1",
  }),
  row({
    sha1: "sha-zulu",
    filename: "zulu.mp3",
    display_title: "Zulu",
    bpm: 120,
    genre: "Techno",
    duration_s: 170,
  }),
];

test("busca cobre titulo, artista, album e arquivo", () => {
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "BETA" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "album-x" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "arquivo-y" })).toHaveLength(1);
});

test("filtra label, genero e key e ordena bpm", () => {
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, label: "+1" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, genre: "House" })).toHaveLength(2);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, key: "6A" })).toHaveLength(1);
  const bpm = applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, sort: "bpm", direction: "asc" });
  expect(bpm.map((r) => r.bpm)).toEqual([120, 124, 128, 130]);
});

test("ordena titulo sem caso e inverte em desc", () => {
  const asc = applyLibraryView(ROWS, DEFAULT_LIBRARY_VIEW);
  expect(asc.map((r) => r.display_title)).toEqual(["Alpha", "beta", "Gamma", "Zulu"]);
  const desc = applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, direction: "desc" });
  expect(desc[0].display_title).not.toBe("Alpha");
});

test("desempata por filename em minusculas", () => {
  const duas = [
    row({ sha1: "sha-1", filename: "b.mp3", display_title: "Mesmo", bpm: 128 }),
    row({ sha1: "sha-2", filename: "A.mp3", display_title: "Mesmo", bpm: 128 }),
  ];
  const ordem = applyLibraryView(duas, DEFAULT_LIBRARY_VIEW);
  expect(ordem.map((r) => r.filename)).toEqual(["A.mp3", "b.mp3"]);
});

test("nao muta a entrada", () => {
  const antes = ROWS.map((r) => r.sha1);
  applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, sort: "bpm", direction: "desc" });
  expect(ROWS.map((r) => r.sha1)).toEqual(antes);
});

test("formatDuration segue o viewmodel: floor, clamp em zero, m:ss", () => {
  expect(formatDuration(0)).toBe("0:00");
  expect(formatDuration(65.9)).toBe("1:05");
  expect(formatDuration(600)).toBe("10:00");
  expect(formatDuration(-3)).toBe("0:00");
});

test("CLASS_CHIPS na ordem Todos, -1, neutra, +1 com indices de class_counts", () => {
  expect(CLASS_CHIPS.map((c) => c.rotulo)).toEqual(["Todos", "-1", "neutra", "+1"]);
  expect(CLASS_CHIPS.map((c) => c.valor)).toEqual([null, "-1", "neutra", "+1"]);
  expect(CLASS_CHIPS.map((c) => c.indice)).toEqual([null, 0, 1, 2]);
});
