import { test, expect } from "@playwright/test";

/**
 * Screenshot da aba Revisao no tamanho do mockup (1512x1037), para comparar
 * lado a lado com design/mockup/TrackClassifier Music Review Dashboard.png.
 * Roda: e barato (sem scan).
 */
test.use({ viewport: { width: 1512, height: 1037 } });

async function abreReview(page: import("@playwright/test").Page) {
  test.setTimeout(60000);
  await page.goto("/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  // Buckets chegam por WS depois do states_changed; sem isso a onda sai
  // monocromatica (energy_curve) e o baseline vira outro desenho.
  await page.waitForTimeout(8000);
  await page.evaluate(() => document.fonts.ready);
}

test("screenshot da revisao", async ({ page }) => {
  await abreReview(page);
  await page.screenshot({ path: "screenshot-review.png" });
});

/**
 * Regressao visual com tolerancia de 2% dos pixels.
 *
 * Nao compara com o mockup: la o conteudo e outro (track, capa, chrome do
 * macOS). O baseline e o proprio app -- pega deslocamento de layout, fonte
 * que nao carregou, token errado. As regioes que mudam com o uso (contagens
 * do scan e a fila, que depende da biblioteca local) entram mascaradas.
 */
test("baseline visual da revisao", async ({ page }) => {
  await abreReview(page);
  await expect(page).toHaveScreenshot("review-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
    mask: [
      page.locator(".scan-status-text"),
      page.locator(".queue-strip"),
    ],
  });
});
