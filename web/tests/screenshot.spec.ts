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

/**
 * Baseline visual da aba Modelo, mesmo criterio do da Revisao: o app e o
 * proprio baseline. Os contadores dinamicos (exemplos, acuracia, contagens
 * por classe e de falhas, progresso de retreino) mudam com o uso da
 * biblioteca e entram mascarados.
 */
test("baseline visual do modelo", async ({ page, request }) => {
  const health = await request.get("/api/health");
  const { token } = await health.json();
  const res = await request.get("/api/model/state", {
    headers: { "X-Auth-Token": token },
  });
  const estado = await res.json();
  test.skip(estado.n_examples === 0, "biblioteca sem exemplos rotulados");

  await page.goto("/");
  await page.locator(".app-tab", { hasText: "Modelo" }).click();
  await page.waitForSelector(".model-metrics-row", { timeout: 30000 });
  await page.evaluate(() => document.fonts.ready);

  await expect(page).toHaveScreenshot("model-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
    mask: [
      page.locator(".scan-status-text"),
      page.locator(".metric-value"),
      page.locator(".class-balance-count"),
      page.locator(".class-balance-recommendation"),
      page.locator(".confusion-cell"),
      page.locator(".model-progress-label"),
      page.locator(".model-progress-fill"),
      page.locator(".failure-badge"),
      page.locator(".failure-list-summary"),
      page.locator(".failure-files"),
      page.locator(".tech-detail-summary"),
      page.locator(".tech-detail-body"),
    ],
  });
});
