import { test, expect } from "@playwright/test";
import {
  ESTADO_ALPHA,
  TRACK_ALPHA,
  TRACK_BETA,
  estado,
  mockRevisaoCompleta,
} from "./review-fixtures";
import { npyFloat16, ondaPorBanda } from "./fixtures/peaks";

test.describe("Review Tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
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

  test("status do scan mostra contagens", async ({ page }) => {
    await expect(page.locator(".scan-status-text")).toContainText(
      /\d+ tracks · \d+ analisadas/,
      { timeout: 15000 }
    );
  });
});

test.describe("Review Tab (fila mockada)", () => {
  test("onda espectral renderiza as tres bandas", async ({ page }) => {
    // Peaks mockados: sem eles o canvas cai no fallback mono e este teste nao
    // teria o que medir. Registrada depois do mockRevisaoCompleta (as rotas
    // mais novas tem precedencia), a rota de peaks devolve o npy com uma banda dominante por terco.
    // peaks_path so precisa ser truthy: e ele que liga o render de bandas.
    const trackComPeaks = { ...TRACK_ALPHA, peaks_path: "stub" };
    await mockRevisaoCompleta(page, estado(trackComPeaks, [TRACK_BETA]));
    await page.route("**/api/peaks/**", (route) =>
      route.fulfill({ body: npyFloat16(ondaPorBanda()) })
    );
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });

    // Espera ativa pelas bandas pintadas em toda a largura, nao um turno fixo.
    await page.waitForFunction(
      () => {
        const c = document.querySelector(".waveform-main canvas") as HTMLCanvasElement | null;
        const ctx = c?.getContext("2d");
        if (!c || !ctx) return false;
        for (const px of [0.6, 0.75, 0.9, 0.98]) {
          let achou = false;
          for (let py = 0.05; py < 0.95; py += 0.05) {
            const d = ctx.getImageData(
              Math.floor(px * c.width),
              Math.floor(py * c.height),
              1,
              1
            ).data;
            if (d[3] === 255 && (d[0] > 30 || d[1] > 30 || d[2] > 30)) {
              achou = true;
              break;
            }
          }
          if (!achou) return false;
        }
        return true;
      },
      undefined,
      { timeout: 10000, polling: 120 }
    );

    const cores = await page.evaluate(() => {
      const canvas = document.querySelector(".waveform-main canvas") as HTMLCanvasElement;
      const ctx = canvas.getContext("2d")!;
      // Amostra a faixa central onde a onda desenha
      const h = canvas.height;
      const yStart = Math.floor(h / 3);
      const yEnd = Math.floor((h * 2) / 3);
      const strip = ctx.getImageData(0, yStart, canvas.width, yEnd - yStart).data;
      let rosa = 0, verde = 0, azul = 0;
      for (let i = 0; i < strip.length; i += 4 * 7) {
        const r = strip[i], g = strip[i + 1], b = strip[i + 2];
        if (r > 90 && r > g * 1.6) rosa++;
        if (g > 80 && g > r * 1.25 && g > b * 1.1) verde++;
        if (b > 80 && b > r * 1.3) azul++;
      }
      return { rosa, verde, azul };
    });

    expect(cores.rosa).toBeGreaterThan(20);
    expect(cores.verde).toBeGreaterThan(20);
    expect(cores.azul).toBeGreaterThan(20);
  });

  test("waveform canvas renders with correct dimensions", async ({ page }) => {
    // Precisa de track na fila para existir canvas: mockada, nao a real.
    await mockRevisaoCompleta(page, ESTADO_ALPHA);
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });

    // Aguarda o canvas ter tamanho (ResizeObserver precisa disparar)
    await page.waitForFunction(() => {
      const canvas = document.querySelector(".waveform-main canvas");
      return canvas && canvas.width > 50 && canvas.height > 50;
    }, { timeout: 15000 });

    const dims = await page.evaluate(() => {
      const canvas = document.querySelector(".waveform-main canvas") as HTMLCanvasElement | null;
      if (!canvas) return null;
      return { width: canvas.width, height: canvas.height, styleWidth: canvas.style.width, styleHeight: canvas.style.height };
    });
    expect(dims).not.toBeNull();
    expect(dims!.width).toBeGreaterThan(100);
    expect(dims!.height).toBeGreaterThan(100);
    // Canvas deve ter altura > 120 (era o fixo) pois agora preenche o container
    expect(dims!.height).toBeGreaterThan(120);
  });

  test("toggle de notacao persiste no localStorage", async ({ page }) => {
    // Fila mockada com tonalidade: a fila real pode estar vazia, e sem track
    // nao ha header nem chip para alternar.
    const comTom = {
      ...TRACK_ALPHA,
      key: {
        pitch_class: 9,
        mode: "A" as const,
        camelot: "8A",
        classic: "Am",
        camelot_number: 8,
      },
    };
    await mockRevisaoCompleta(page, estado(comTom, [TRACK_BETA]));
    await page.goto("/");
    await page.waitForSelector(".review-header", { timeout: 30000 });

    const toggle = page.locator(".key-notation-toggle");
    const chip = page.locator(".review-header .key-chip");
    await expect(toggle).toHaveText("Camelot");
    await expect(chip).toHaveText("8A");

    await toggle.click();
    await expect(toggle).toHaveText("Tom");
    await expect(chip).toHaveText("Am");
    expect(
      await page.evaluate(() =>
        localStorage.getItem("trackclassifier-key-notation")
      )
    ).toBe("classic");

    await page.reload();
    await page.waitForSelector(".review-header", { timeout: 30000 });
    await expect(page.locator(".key-notation-toggle")).toHaveText("Tom");
    await expect(page.locator(".review-header .key-chip")).toHaveText("Am");
    // O localStorage do contexto e descartavel: nao ha estado a devolver.
  });
});
