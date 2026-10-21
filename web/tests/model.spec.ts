import { test, expect, type APIRequestContext } from "@playwright/test";
import type { ModelState } from "../src/api/types";

/**
 * E2E da aba Modelo contra o backend real.
 *
 * A biblioteca do usuario e o dado: os testes leem /api/model/state e
 * ramificam pelo estado real (com ou sem exemplos rotulados) em vez de
 * assumir um dos dois -- a mesma abordagem de review.spec.ts, que aceita
 * fila montada ou vazia.
 */

async function estadoModelo(request: APIRequestContext): Promise<ModelState> {
  const health = await request.get("/api/health");
  const { token } = await health.json();
  const res = await request.get("/api/model/state", {
    headers: { "X-Auth-Token": token },
  });
  expect(res.ok()).toBe(true);
  return res.json();
}

test.describe("Aba Modelo", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.locator(".app-tab", { hasText: "Modelo" }).click();
    // Saiu do loading quando o empty state ou o conteudo aparece
    await page.waitForSelector("[data-testid='model-empty'], .model-metrics-row", {
      timeout: 30000,
    });
  });

  test("navega pelo header e marca a aba ativa", async ({ page }) => {
    await expect(page.locator(".app-tab-active")).toContainText("Modelo");
    await expect(page.locator("[data-testid='model-tab']")).toBeVisible();
    await expect(page.locator(".model-title")).toHaveText(
      "Modelo de Classificacao"
    );
  });

  test("com exemplos rotulados mostra metricas, matriz, balanco e acao", async ({
    page,
    request,
  }) => {
    const estado = await estadoModelo(request);
    test.skip(estado.n_examples === 0, "biblioteca sem exemplos rotulados");

    await expect(page.locator(".model-metrics-row .metric-card")).toHaveCount(3);
    await expect(page.locator(".class-balance-bar")).toHaveCount(3);
    await expect(page.locator(".model-action-btn")).toHaveText("RETREINAR");

    if (estado.confusion !== null) {
      await expect(page.locator(".confusion-cell")).toHaveCount(9);
      await expect(page.locator(".confusion-legend-item")).toHaveCount(3);
    }

    if (estado.failures.length > 0) {
      const categorias = new Set(estado.failures.map((f) => f[2]));
      await expect(page.locator(".failure-group")).toHaveCount(categorias.size);
    } else {
      await expect(page.locator(".failure-list")).toHaveCount(0);
    }
  });

  test("detalhe tecnico abre, mostra os valores e fecha", async ({
    page,
    request,
  }) => {
    const estado = await estadoModelo(request);
    test.skip(estado.n_examples === 0, "biblioteca sem exemplos rotulados");

    const gatilho = page.locator(".tech-detail-trigger");
    await expect(gatilho).toContainText(estado.extractor_name);
    await expect(page.locator(".tech-detail-body")).toBeHidden();

    await gatilho.click();
    await expect(page.locator(".tech-detail-body")).toBeVisible();
    await expect(page.locator(".tech-detail-value").last()).toHaveText(
      estado.extractor_name
    );

    await gatilho.click();
    await expect(page.locator(".tech-detail-body")).toBeHidden();
  });

  test("retreinar zera o contador de decisoes sem reload", async ({
    page,
    request,
  }) => {
    const estado = await estadoModelo(request);
    test.skip(
      estado.n_examples === 0 || estado.train_blocked_reason !== null,
      `retreino bloqueado: ${estado.train_blocked_reason ?? "sem exemplos"}`
    );

    const rotulo = page.locator(".model-progress-label");
    await page.locator(".model-action-btn").click();
    // O WS states_changed atualiza o hook: decisions_since_train volta a 0
    // sem reload da pagina.
    await expect(rotulo).toHaveText(/^0 \/ \d+ até o retreino automático$/, {
      timeout: 30000,
    });
    await expect(page.locator("[data-testid='model-tab']")).toBeVisible();
  });

  test("sem exemplos mostra empty state que leva a revisao", async ({
    page,
    request,
  }) => {
    const estado = await estadoModelo(request);
    test.skip(estado.n_examples > 0, "biblioteca tem exemplos rotulados");

    const vazio = page.locator("[data-testid='model-empty']");
    await expect(vazio).toContainText("Nenhum exemplo rotulado");
    await vazio.locator("button", { hasText: "Ir para a revisao" }).click();
    await expect(page.locator(".app-tab-active")).toContainText("Revisão");
  });
});
