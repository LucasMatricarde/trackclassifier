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

/** Geometria e cores COMPUTADAS do chip (render, nao CSS escrito). */
async function medeChip(page: import("@playwright/test").Page) {
  // Sem esperar as webfonts, a altura varia 1 px conforme a fonte de reserva
  // ou a JetBrains Mono ja tenha carregado (flaky sob carga, medido).
  await page.evaluate(() => document.fonts.ready);
  return page.locator(".review-header .key-chip").evaluate((el) => {
    const css = getComputedStyle(el);
    const caixa = el.getBoundingClientRect();
    return {
      largura: Math.round(caixa.width),
      altura: Math.round(caixa.height),
      fundo: css.backgroundColor,
      cor: css.color,
      fonte: css.fontSize,
      familia: css.fontFamily,
      raio: css.borderRadius,
    };
  });
}

test.describe("Tonalidade por audio na Revisao", () => {
  test("chip da key estimada tem o mesmo visual do chip da tag", async ({
    browser,
  }) => {
    // Duas paginas, mesma key: so a fonte muda. Qualquer diferenca de render
    // seria um chip "inventado" para a estimativa (regra 5 de fidelidade.md).
    const comTag = await browser.newPage();
    const estimada = await browser.newPage();
    try {
      await mockRevisaoCompleta(
        comTag,
        estado({ ...TRACK_ALPHA, key: LA_MENOR, key_source: "tag" }, [TRACK_BETA])
      );
      await comTag.goto("/");
      await comTag.waitForSelector(".review-header .key-chip", { timeout: 30000 });

      await mockRevisaoCompleta(estimada, estado(TRACK_ALPHA, [TRACK_BETA]));
      await estimada.goto("/");
      await estimada.waitForSelector(".review-header", { timeout: 30000 });
      await emitirWs(estimada, {
        type: "key_ready",
        sha1: "sha-alpha",
        key: LA_MENOR,
        key_source: "audio",
      });
      await expect(estimada.locator(".review-header .key-chip")).toHaveText("8A");

      const medidaTag = await medeChip(comTag);
      const medidaEstimada = await medeChip(estimada);
      expect(medidaEstimada).toEqual(medidaTag);
      // Chip pintado de verdade com a cor da roda (8A), nao transparente.
      expect(medidaEstimada.fundo).not.toBe("rgba(0, 0, 0, 0)");
    } finally {
      await comTag.close();
      await estimada.close();
    }
  });

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
