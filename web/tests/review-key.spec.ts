import { test, expect } from "@playwright/test";
import {
  TRACK_ALPHA,
  TRACK_BETA,
  emitirWs,
  estado,
  mockRevisaoCompleta,
} from "./review-fixtures";
import type { Key } from "../src/api/types";

/**
 * Tonalidade estimada pelo audio (fallback quando a track nao tem tag).
 *
 * Tudo mockado: a fila vem de rota, o WebSocket e falso (emitirWs empurra
 * key_ready/key_failed) e o POST de deteccao e contado numa rota -- o backend
 * real nunca decodifica nada nem grava no presentation.parquet.
 */

const LA_MENOR: Key = {
  pitch_class: 9,
  mode: "A",
  camelot: "8A",
  classic: "Am",
  camelot_number: 8,
};

const TITULO_ESTIMADA = "Tonalidade estimada pelo áudio";

/** Conta os POST de deteccao por sha1 (rota registrada por ultimo = precedencia). */
async function contaDeteccoes(page: import("@playwright/test").Page) {
  const pedidos: string[] = [];
  await page.route("**/api/key/*/detect*", (route) => {
    pedidos.push(route.request().url().match(/\/api\/key\/([^/]+)\/detect/)![1]);
    return route.fulfill({ json: { ok: true, queued: true } });
  });
  return pedidos;
}

/** O pedido de peaks sai no mesmo commit do React que o de key: serve de marco. */
async function esperaPedidoDePeaks(page: import("@playwright/test").Page) {
  await page.waitForRequest("**/api/peaks/*/compute*");
}

test.describe("Tonalidade por audio na Revisao", () => {
  test("track sem key pede a deteccao e mostra o resultado do key_ready", async ({
    page,
  }) => {
    await mockRevisaoCompleta(page, estado(TRACK_ALPHA, [TRACK_BETA]));
    const pedidos = await contaDeteccoes(page);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });

    await expect.poll(() => pedidos).toEqual(["sha-alpha"]);
    await expect(page.locator(".review-header .key-chip")).toHaveText("—");

    await emitirWs(page, {
      type: "key_ready",
      sha1: "sha-alpha",
      key: LA_MENOR,
      key_source: "audio",
    });

    await expect(page.locator(".review-header .key-chip")).toHaveText("8A");
    await expect(
      page.locator(".review-header .key-chip-trigger")
    ).toHaveAttribute("title", TITULO_ESTIMADA);
    // Mesmo visual de uma key de tag: o alternador de notacao continua valendo.
    await page.locator(".review-header .key-chip-trigger").click();
    await expect(page.locator(".review-header .key-chip")).toHaveText("Am");
  });

  test("key_ready de outra track nao muda o chip da exibida", async ({ page }) => {
    await mockRevisaoCompleta(page, estado(TRACK_ALPHA, [TRACK_BETA]));
    await contaDeteccoes(page);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });

    await emitirWs(page, {
      type: "key_ready",
      sha1: "sha-beta",
      key: LA_MENOR,
      key_source: "audio",
    });

    await expect(page.locator(".review-header .key-chip")).toHaveText("—");
  });

  test("key da tag nao dispara deteccao nem leva o aviso de estimativa", async ({
    page,
  }) => {
    const comTag = { ...TRACK_ALPHA, key: LA_MENOR, key_source: "tag" as const };
    await mockRevisaoCompleta(page, estado(comTag, [TRACK_BETA]));
    const pedidos = await contaDeteccoes(page);
    const peaks = esperaPedidoDePeaks(page);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });
    await peaks;

    expect(pedidos).toEqual([]);
    await expect(page.locator(".review-header .key-chip")).toHaveText("8A");
    await expect(
      page.locator(".review-header .key-chip-trigger")
    ).not.toHaveAttribute("title", TITULO_ESTIMADA);
  });

  test("key_source none (ja tentada) nao pede de novo", async ({ page }) => {
    const tentada = { ...TRACK_ALPHA, key_source: "none" as const };
    await mockRevisaoCompleta(page, estado(tentada, [TRACK_BETA]));
    const pedidos = await contaDeteccoes(page);
    const peaks = esperaPedidoDePeaks(page);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });
    await peaks;

    expect(pedidos).toEqual([]);
    await expect(page.locator(".review-header .key-chip")).toHaveText("—");
  });

  test("key_failed mantem o travessao e nao entra em loop de pedidos", async ({
    page,
  }) => {
    await mockRevisaoCompleta(page, estado(TRACK_ALPHA, [TRACK_BETA]));
    const pedidos = await contaDeteccoes(page);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });
    await expect.poll(() => pedidos).toEqual(["sha-alpha"]);

    await emitirWs(page, { type: "key_failed", sha1: "sha-alpha" });
    // Outra mensagem que mexe no estado do hook (e muda a identidade dos
    // callbacks): sem a guarda de falha, o efeito da tela pediria de novo.
    await emitirWs(page, { type: "peaks_failed", sha1: "sha-alpha" });
    await page.evaluate(
      () =>
        new Promise<void>((ok) =>
          requestAnimationFrame(() => requestAnimationFrame(() => ok()))
        )
    );

    expect(pedidos).toEqual(["sha-alpha"]);
    await expect(page.locator(".review-header .key-chip")).toHaveText("—");
  });
});
