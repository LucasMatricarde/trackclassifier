import { test, expect, type Page } from "@playwright/test";
import type { WSMessage } from "../src/api/types";
import { stubConfig } from "./fixtures/config";

/**
 * Status de scan do header, com a API e o WebSocket stubados: o spec injeta
 * `scan_phase` pelo `window.__emitWS` do FakeWebSocket e confere o texto e o
 * botao. O E2E contra o backend real fica em scan-status-flow.spec.ts.
 */
const status = (page: Page) => page.locator(".scan-status-text");
const botao = (page: Page) => page.locator(".btn-scan");

const emite = (page: Page, msg: WSMessage) =>
  page.evaluate((m) => (window as unknown as { __emitWS: (x: unknown) => void }).__emitWS(m), msg);

test.describe("status de scan do header", () => {
  test("acompanha as fases do servidor: analisando, processando e idle", async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await expect(status(page)).toContainText("Scan concluído", { timeout: 20000 });
    await expect(botao(page)).toBeEnabled();

    await emite(page, { type: "scan_phase", phase: "analisando" });
    await expect(status(page)).toContainText("Escaneando");
    await expect(botao(page)).toBeDisabled();

    // A fase que faltava: o scan segue (tags, capa, tonalidade) sem progresso.
    await emite(page, { type: "scan_phase", phase: "processando" });
    await expect(status(page)).toContainText("Processando…");
    await expect(status(page)).not.toContainText("Scan concluído");
    await expect(botao(page)).toBeDisabled();

    await emite(page, { type: "scan_phase", phase: "idle" });
    await expect(status(page)).toContainText("Scan concluído");
    await expect(botao(page)).toBeEnabled();
  });

  test("subtitulo: progresso so na analise, contagem fora dela", async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await expect(status(page)).toContainText(/\d+ tracks · \d+ analisadas/, { timeout: 20000 });

    await emite(page, { type: "scan_progress", done: 3, total: 10, current: "a.mp3" });
    await expect(status(page)).toContainText("Escaneando");
    await expect(status(page)).toContainText(/3 \/ 10 · \d+ analisadas/);

    await emite(page, { type: "scan_phase", phase: "processando" });
    await expect(status(page)).toContainText("Processando…");
    await expect(status(page)).not.toContainText("3 / 10");
    await expect(status(page)).toContainText(/\d+ tracks · \d+ analisadas/);
  });

  test("scan_finished volta ao estado concluido", async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await expect(status(page)).toContainText("Scan concluído", { timeout: 20000 });

    await emite(page, { type: "scan_progress", done: 1, total: 2, current: "a.mp3" });
    await expect(status(page)).toContainText("Escaneando");
    await emite(page, { type: "scan_finished", cancelled: false });
    await expect(status(page)).toContainText("Scan concluído");
    await expect(botao(page)).toBeEnabled();
  });

  test("reload no meio do scan: a fase entregue no connect abre em Processando…", async ({
    page,
  }) => {
    await stubConfig(page, { scanFase: "processando" });
    await page.goto("/");

    await expect(status(page)).toContainText("Processando…", { timeout: 20000 });
    await expect(status(page)).not.toContainText("Scan concluído");
    await expect(botao(page)).toBeDisabled();
  });

  test("Escanear que volta com 409 adota a fase do servidor, nao 'concluido'", async ({
    page,
  }) => {
    await stubConfig(page);
    // Outro scan (o de abertura, por exemplo) ja esta na fase de processamento.
    await page.route("**/api/scan", (route) =>
      route.fulfill({ status: 409, json: { detail: "Scan já em andamento" } })
    );
    await page.route("**/api/scan/status", (route) =>
      route.fulfill({ json: { phase: "processando", running: true } })
    );
    await page.goto("/");
    await expect(botao(page)).toBeEnabled({ timeout: 20000 });

    await botao(page).click();

    await expect(status(page)).toContainText("Processando…");
    await expect(status(page)).not.toContainText("Scan concluído");
    await expect(botao(page)).toBeDisabled();
  });
});
