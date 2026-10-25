import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { wavSilencioso } from "./fixtures/midia";
import { stubAbaModelo } from "./fixtures/modelo";
import { npyFloat16, ondaFixa } from "./fixtures/peaks";
import {
  estado,
  mockRevisaoCompleta,
  TRACK_ALPHA,
  TRACK_BETA,
} from "./review-fixtures";
import type { ReviewState, TrackRow } from "../src/api/types";

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
  // monocromatica (energy_curve) e o screenshot vira outro desenho.
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
 * O baseline da REVISAO nao roda no backend: as rotas que a tela toca
 * (fila, biblioteca, modelo, peaks, audio, capa, thumbs) sao stubadas e o
 * WebSocket e falso — ideias de "acervo local" nao existem aqui: nenhuma
 * regiao da tela muda com o disco. O caste antigo deixou de existir
 * (comparava a fila real e quebrava a cada biblioteca nova).
 */
async function stubRevisaoVisual(page: Page, reviewState: ReviewState) {
  // health/fila/biblioteca/modelo/capa/thumb e o WebSocket falso vem de
  // mockRevisaoCompleta: a libraryFixa e o mesmo JSON que este spec montava
  // a mao (rows vazio, class_counts 3/14/13). So peaks e audio sao do
  // baseline; a rota de audio abaixo, registrada depois, vence a do helper
  // porque o Playwright consulta a ultima rota registrada primeiro.
  await mockRevisaoCompleta(page, reviewState);
  await page.route("**/api/peaks/**", (route) =>
    route.fulfill({ body: npyFloat16(ondaFixa()) })
  );
  // 1 s de silencio, nao o WAV de 0 s do mockRevisaoCompleta. Medido: 0 s
  // tambem passa no baseline (a duracao do <audio> nao entra no pixel), mas
  // a refatoracao mantem a resposta byte a byte igual a que o baseline
  // sempre recebeu, para nao depender dessa folga.
  await page.route("**/api/audio/**", (route) =>
    route.fulfill({ body: wavSilencioso(1), contentType: "audio/wav" })
  );
}

test("baseline visual da revisao", async ({ page }) => {
  // A track do baseline tem peaks_path: e ele que liga o render de bandas
  // (o stub de /api/peaks responde o npy fixo); sem isso o canvas cai no
  // fallback mono e o spectral design nao entra na regressao.
  const trackComPeaks: TrackRow = { ...TRACK_ALPHA, peaks_path: "stub" };
  const fila: ReviewState = estado(trackComPeaks, [TRACK_BETA]);
  await stubRevisaoVisual(page, fila);
  await page.goto("/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 10000 });
  // Espera os peaks estarem pintados (bandas em toda a largura), nao um
  // turno fixo: screenshot cedo captura o mono e o baseline vira outra
  // coisa que lembranca.
  await page.waitForFunction(
    () => {
      const c = document.querySelectorAll("canvas")[0] as HTMLCanvasElement | null;
      if (!c) return false;
      const ctx = c.getContext("2d");
      if (!ctx) return false;
      for (const px of [0.6, 0.75, 0.9, 0.98]) {
        let achou = false;
        for (let py = 0.05; py < 0.95; py += 0.05) {
          const d = ctx.getImageData(
            Math.floor(px * c.width),
            Math.floor(py * c.height),
            1,
            1
          ).data;
          // Banda pintada: pixel opaco sobreescrevendo o fundo do canvas,
          // que e quase preto (qualquer canal > 30 ja e pinta).
          if (d[3] === 255 && (d[0] > 30 || d[1] > 30 || d[2] > 30)) {
            achou = true;
            break;
          }
        }
        if (!achou) return false;
      }
      return true;
    },
    { timeout: 8000, polling: 120 }
  );
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
  await expect(page).toHaveScreenshot("review-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
  });
});

/**
 * Baseline visual da aba Modelo.
 *
 * Roda sobre o estado fixo da fixture (stub de health/state/WS em
 * tests/fixtures/modelo.ts): nenhuma regiao da tela depende do acervo
 * local, entao nao entra regiao mascarada. O header tambem vem da fixture
 * (states_changed sintetico), por isso a contagem do scan e estavel.
 */

async function abreModelo(page: import("@playwright/test").Page) {
  test.setTimeout(60000);
  await stubAbaModelo(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Modelo" }).click();
  await page.waitForSelector(".confusion-cell", { timeout: 10000 });
  await page.evaluate(() => document.fonts.ready);
}

test("screenshot do modelo", async ({ page }) => {
  await abreModelo(page);
  await page.screenshot({ path: "screenshot-modelo.png" });
});

test("baseline visual do modelo", async ({ page }) => {
  await abreModelo(page);
  await expect(page).toHaveScreenshot("model-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
  });
});
