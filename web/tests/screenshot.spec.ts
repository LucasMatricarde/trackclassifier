import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { PNG_1PX, wavSilencioso } from "./fixtures/midia";
import { stubAbaModelo } from "./fixtures/modelo";
import { npyFloat16, ondaFixa } from "./fixtures/peaks";
import { FIXTURE_TRES, mockLibrary } from "./library-fixtures";
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

/**
 * Baseline visual da aba Biblioteca.
 *
 * Roda sobre FIXTURE_TRES (3 tracks, uma por classe): library/state, model/state
 * e o WebSocket vem de mockLibrary e os peaks sao determinsticos por sha1
 * (ondasFake), entao fila, acervo e timing reais nao entram. Nao ha regiao
 * mascarada: a tela inteira e estavel. O mockLibrary nao serve capa/thumb/audio
 * (os specs funcionais da Biblioteca contam placeholders), por isso o stub das
 * tres rotas fica aqui e nao no helper compartilhado.
 */
async function abreBiblioteca(page: Page) {
  test.setTimeout(60000);
  await mockLibrary(page, FIXTURE_TRES);
  // PNG transparente: o <img> da capa carrega (a Gamma, sem cover_path, segue
  // no placeholder) sem trazer pixel que dependa de arquivo real.
  for (const rota of ["**/api/cover/**", "**/api/thumb/**"]) {
    await page.route(rota, (route) =>
      route.fulfill({ body: PNG_1PX, contentType: "image/png" })
    );
  }
  await page.route("**/api/audio/**", (route) =>
    route.fulfill({ body: wavSilencioso(1), contentType: "audio/wav" })
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-row")).toHaveCount(3);
  // A mini-onda busca o .npy sob demanda (IntersectionObserver) e a onda do
  // inspetor chega depois: screenshot cedo captura canvas vazio e o baseline
  // viraria outra coisa. Espera todos os canvases com ao menos um pixel pintado.
  await page.waitForFunction(
    () => {
      const canvases = Array.from(document.querySelectorAll("canvas"));
      if (canvases.length < 4) return false;
      return canvases.every((c) => {
        const ctx = c.getContext("2d");
        if (!ctx || c.width === 0 || c.height === 0) return false;
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true;
        return false;
      });
    },
    undefined,
    { timeout: 8000, polling: 120 }
  );
  // A duracao do transporte vem do <audio> (WAV de 1 s do stub), que carrega
  // os metadados depois do clique: sem esperar, o relogio sai "0:00 / 0:00".
  await expect(page.getByTestId("library-time")).toHaveText("0:00 / 0:01");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
}

test("baseline visual da biblioteca", async ({ page }) => {
  await abreBiblioteca(page);
  await expect(page).toHaveScreenshot("library-baseline.png", {
    // Tolerancia em pixels, nao em razao: 2% (~31 mil px) engoliria a troca de
    // classe de uma linha, que muda ~50 px. Medido: ruido entre execucoes = 0.
    maxDiffPixels: 20,
    animations: "disabled",
  });
});
