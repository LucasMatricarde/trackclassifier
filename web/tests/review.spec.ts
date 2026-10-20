import { test, expect } from "@playwright/test";

test.describe("Review Tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://127.0.0.1:5173/");
  });

  test("header do app renderiza com a aba Revisao ativa", async ({ page }) => {
    await expect(page.locator(".app-logo-text")).toHaveText("TrackClassifier");
    await expect(page.locator(".app-tab-active")).toContainText("Revisão");
    await expect(page.locator(".btn-scan")).toContainText("Escanear", {
      timeout: 15000,
    });
  });

  test("sai do loading e mostra a revisão (ou fila vazia)", async ({ page }) => {
    await expect(page.locator(".review-loading")).toHaveCount(0, {
      timeout: 20000,
    });
    const painel = page.locator(
      "[data-testid='review-tab'], .empty-state"
    );
    await expect(painel.first()).toBeVisible({ timeout: 20000 });
  });

  test("onda espectral renderiza as três bandas", async ({ page }) => {
    test.setTimeout(60000);
    await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });

    // Os buckets chegam por WS depois do states_changed inicial
    await page.waitForTimeout(9000);

    const cores = await page.evaluate(() => {
      const canvas = document.querySelector(
        ".waveform-main canvas"
      ) as HTMLCanvasElement | null;
      if (!canvas) return null;
      const ctx = canvas.getContext("2d")!;
      const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let rosa = 0;
      let verde = 0;
      let azul = 0;
      for (let i = 0; i < d.length; i += 4 * 7) {
        const r = d[i];
        const g = d[i + 1];
        const b = d[i + 2];
        // Rosa baixa (#f4556d): R alto, G baixo. Verde: G dominante.
        // Azul da banda alta (#45b7e0): B dominante sobre R.
        if (r > 90 && r > g * 1.6) rosa++;
        if (g > 80 && g > r * 1.25 && g > b * 1.1) verde++;
        if (b > 80 && b > r * 1.3) azul++;
      }
      return { rosa, verde, azul };
    });

    expect(cores).not.toBeNull();
    expect(cores!.rosa).toBeGreaterThan(20);
    expect(cores!.verde).toBeGreaterThan(20);
    expect(cores!.azul).toBeGreaterThan(20);
  });

  test("status do scan mostra contagens", async ({ page }) => {
    await expect(page.locator(".scan-status-text")).toContainText(
      /\d+ tracks · \d+ analisadas/,
      { timeout: 15000 }
    );
  });

  test("toggle de notacao persiste no localStorage", async ({ page }) => {
    await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
    const toggle = page.locator(".key-notation-toggle");
    await expect(toggle).toHaveText("Camelot");

    await toggle.click();
    await expect(toggle).toHaveText("Tom");
    expect(
      await page.evaluate(() =>
        localStorage.getItem("trackclassifier-key-notation")
      )
    ).toBe("classic");

    await page.reload();
    await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
    await expect(page.locator(".key-notation-toggle")).toHaveText("Tom");

    // volta ao default para nao vazar estado para os outros testes
    await page.locator(".key-notation-toggle").click();
  });
});
