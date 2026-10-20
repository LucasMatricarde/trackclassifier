import { test, expect } from "@playwright/test";
import {
  ESTADO_ALPHA,
  ESTADO_BETA,
  fakeWebSocket,
  mockApi,
} from "./review-fixtures";

/**
 * Robustez da aba Revisao: erro visivel, fila que atualiza sem WebSocket e
 * confirmacao no Aprovar em bloco.
 *
 * Tudo e deterministico: estado da fila vem de rota mockada, o WebSocket e
 * falso e nenhuma acao chega no backend -- nenhuma track real e decidida.
 */
test.describe("Revisao -- robustez", () => {
  test("abre a aba mesmo com o WebSocket fora", async ({ page }) => {
    await fakeWebSocket(page, "quebrado");
    await mockApi(page, ESTADO_ALPHA);

    await page.goto("/");

    await expect(page.getByTestId("review-tab")).toBeVisible();
    await expect(page.locator(".review-title")).toHaveText("Alpha");
    await expect(page.getByTestId("review-offline")).toBeVisible();
  });

  test("reconecta depois de uma queda", async ({ page }) => {
    await fakeWebSocket(page, "quebra-depois");
    await mockApi(page, ESTADO_ALPHA);

    await page.goto("/");

    await expect(page.getByTestId("review-offline")).toBeVisible();
    await expect(page.getByTestId("review-offline")).toHaveCount(0, {
      timeout: 10000,
    });
  });

  test("erro de acao aparece e a fila continua", async ({ page }) => {
    await fakeWebSocket(page);
    await mockApi(page, ESTADO_ALPHA);
    await page.route("**/api/review/decide*", (route) =>
      route.fulfill({ status: 500, json: { detail: "falha proposital" } })
    );

    await page.goto("/");
    await expect(page.locator(".review-title")).toHaveText("Alpha");

    await page.keyboard.press("1");

    await expect(page.getByTestId("review-error")).toContainText(
      "falha proposital"
    );
    // A acao falhou: a fila nao muda e a track continua na tela.
    await expect(page.locator(".review-title")).toHaveText("Alpha");

    await page.getByTestId("review-error-dismiss").click();
    await expect(page.getByTestId("review-error")).toHaveCount(0);
  });

  test("recarrega a fila depois da acao sem WebSocket", async ({ page }) => {
    await fakeWebSocket(page, "quebrado");
    let chamadas = 0;
    await page.route("**/api/health*", (route) =>
      route.fulfill({
        json: { ok: true, token: "token-teste", configured: true },
      })
    );
    await page.route("**/api/review/state*", (route) => {
      chamadas += 1;
      route.fulfill({ json: chamadas === 1 ? ESTADO_ALPHA : ESTADO_BETA });
    });
    await page.route("**/api/review/decide*", (route) =>
      route.fulfill({ json: { ok: true } })
    );

    await page.goto("/");
    await expect(page.locator(".review-title")).toHaveText("Alpha");

    await page.keyboard.press("3");

    // Sem WebSocket nao ha states_changed: quem avanca a fila e o reload
    // que a acao dispara.
    await expect(page.locator(".review-title")).toHaveText("Beta");
  });

  test("aprovar em bloco pede confirmacao", async ({ page }) => {
    await fakeWebSocket(page);
    await mockApi(page, ESTADO_ALPHA);
    let bulk = 0;
    await page.route("**/api/review/bulk*", (route) => {
      bulk += 1;
      route.fulfill({ json: { ok: true, count: 2 } });
    });

    await page.goto("/");

    await page.getByRole("button", { name: /Aprovar em bloco/ }).click();
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();
    await page.getByTestId("confirm-dialog-cancel").click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
    expect(bulk).toBe(0);

    await page.getByRole("button", { name: /Aprovar em bloco/ }).click();
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect.poll(() => bulk).toBe(1);
    await expect(page.getByTestId("review-status")).toContainText("2");
  });

  test("nao dispara o bloco duas vezes", async ({ page }) => {
    await fakeWebSocket(page);
    await mockApi(page, ESTADO_ALPHA);
    let bulk = 0;
    await page.route("**/api/review/bulk*", async (route) => {
      bulk += 1;
      // Demora de proposito: e durante a request que um segundo clique
      // poderia escapar.
      await new Promise((r) => setTimeout(r, 800));
      await route.fulfill({ json: { ok: true, count: 2 } });
    });

    await page.goto("/");
    await page.getByRole("button", { name: /Aprovar em bloco/ }).click();

    const confirmar = page.getByTestId("confirm-dialog-confirm");
    await confirmar.click();
    await expect(confirmar).toBeDisabled();

    await expect.poll(() => bulk).toBe(1);
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
  });

  test("erro no carregamento inicial oferece tentar de novo", async ({ page }) => {
    await fakeWebSocket(page);
    let chamadas = 0;
    await page.route("**/api/health*", (route) =>
      route.fulfill({
        json: { ok: true, token: "token-teste", configured: true },
      })
    );
    await page.route("**/api/review/state*", (route) => {
      chamadas += 1;
      if (chamadas === 1) {
        route.fulfill({ status: 500, json: { detail: "servico fora" } });
      } else {
        route.fulfill({ json: ESTADO_ALPHA });
      }
    });

    await page.goto("/");

    await expect(page.getByTestId("review-error")).toContainText(
      "servico fora"
    );
    await page.getByTestId("review-retry").click();
    await expect(page.locator(".review-title")).toHaveText("Alpha");
  });
});
