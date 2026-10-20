import { test } from "@playwright/test";

/**
 * Screenshot da aba Revisao no tamanho do mockup (1512x1037), para comparar
 * lado a lado com design/mockup/TrackClassifier Music Review Dashboard.png.
 * Nao roda com `npx playwright test` por padrao? Roda: e barato (sem scan).
 */
test.use({ viewport: { width: 1512, height: 1037 } });

test("screenshot da revisao", async ({ page }) => {
  test.setTimeout(60000);
  await page.goto("http://127.0.0.1:5173/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  // Espera os buckets chegarem (computo assincrono) para a onda espectral
  await page.waitForTimeout(8000);
  await page.screenshot({ path: "screenshot-review.png" });
});
