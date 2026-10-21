import { test, expect } from "@playwright/test";
import { stubAbaModelo, modeloFixo } from "./fixtures/modelo";

/**
 * E2E da aba Modelo com estado sintetico: deterministico, nao depende da
 * biblioteca local nem de treino real. A fixture cobre todos os ramos da
 * spec: treinado com aviso de baixa confianca, bloqueado com motivo,
 * nao treinado (metricas ausentes), biblioteca vazia, falhas agrupadas e
 * detalhe tecnico recolhido.
 */
test.describe("Aba Modelo", () => {
  test("navegacao abre com metricas, matriz e balanco do estado fixo", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();
    await expect(page.locator(".model-title")).toHaveText(
      "Modelo de Classificacao"
    );

    await expect(page.locator(".metric-value").nth(0)).toHaveText(
      String(modeloFixo.n_examples)
    );
    await expect(page.locator(".metric-value").nth(1)).toHaveText("92.3%");
    await expect(page.locator(".metric-value").nth(2)).toHaveText("0.250");

    await expect(page.locator(".confusion-cell").nth(0)).toHaveText("2");
    await expect(page.getByRole("grid", { name: /Matriz de confus/ })).toBeVisible();
    await expect(page.locator(".class-balance-count").nth(0)).toHaveText("3");
    await expect(page.locator(".class-balance-count").nth(1)).toHaveText("14");
    await expect(page.locator(".class-balance-count").nth(2)).toHaveText("13");
  });

  test("balanco mostra a recomendacao da classe minoritaria", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    // class_counts [3,14,13]: 21% da maior, abaixo do limiar de 70%.
    await expect(page.locator(".class-balance-recommendation")).toContainText(
      "-1 tem 21%"
    );
  });

  test("aviso de low confidence e progresso ate o retreino visiveis", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    await expect(page.locator(".model-action-warning")).toContainText(
      "acuracia LOO ainda ruidosa"
    );
    // getComputedStyle resolve % em px: trilho no teto de 340px * 50%.
    await expect(page.locator(".model-progress-fill")).toHaveCSS(
      "width",
      "170px"
    );
    await expect(page.locator(".model-progress-label")).toContainText(
      "5 / 10 ate o retreino automatico"
    );
    await expect(page.getByRole("button", { name: "RETREINAR" })).toBeEnabled();
  });

  test("bloqueado de treino desabilita o botao com motivo", async ({ page }) => {
    await stubAbaModelo(page, {
      model: {
        train_blocked_reason:
          "Falta exemplo na classe -1. Rotular mais -1 desbloqueia o retreino.",
      },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    const botao = page.getByRole("button", { name: "RETREINAR" });
    await expect(botao).toBeDisabled();
    await expect(page.locator(".model-action-reason")).toContainText(
      "Falta exemplo na classe -1"
    );
    // Bloqueado nao mostra progresso: o motivo ocupa o lugar dele.
    await expect(page.locator(".model-action-progress")).toHaveCount(0);
  });

  test("modelo nao treinado: painel no lugar das metricas, balanco e falhas ficam", async ({
    page,
  }) => {
    await stubAbaModelo(page, {
      model: {
        accuracy: null,
        ordinal_mae: null,
        confusion: null,
        alpha: null,
        thresholds: null,
      },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    // Port de model_tab._card_metricas: os cards de metrica dao lugar ao
    // painel "ainda nao treinado" — mesmo slot, e nao card com "—".
    await expect(page.locator(".model-metrics-row")).toHaveCount(0);
    await expect(page.locator(".model-sem-treino-title")).toHaveText(
      "Modelo ainda nao treinado."
    );
    await expect(page.locator(".model-sem-treino-note")).toHaveText(
      "Metricas aparecem depois do primeiro retreino."
    );
    await expect(page.locator(".confusion-matrix")).toHaveCount(0);
    // Balanco, contador e falhas continuam visiveis: estado normal no
    // inicio (spec), nao um erro.
    await expect(page.locator(".class-balance")).toBeVisible();
    await expect(page.locator(".model-progress-label")).toContainText("5 / 10");
    await expect(page.locator(".failure-list")).toBeVisible();
    // Detalhe tecnico so mostra o extrator quando nao ha treino.
    await expect(page.locator(".tech-detail-summary")).toContainText(
      "handcrafted-v1"
    );
  });

  test("biblioteca vazia mostra empty state e leva para a Revisao", async ({
    page,
  }) => {
    await stubAbaModelo(page, {
      model: { n_examples: 0, class_counts: [0, 0, 0] },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-empty")).toBeVisible();

    // Falhas e detalhe tecnico ficam for a do early-return: acervo fresco
    // escaneado com arquivos corrompidos tem zero exemplos, e o aviso de
    // falha nao pode sumir junto (port do comentario de model_tab).
    await expect(page.locator(".failure-list")).toBeVisible();
    await expect(page.locator(".tech-detail")).toBeVisible();
    await expect(page.locator(".model-action-bar")).toHaveCount(0);
    await expect(page.locator(".class-balance")).toHaveCount(0);

    await page
      .getByRole("button", { name: "Ir para a revisao" })
      .click();
    await expect(
      page.getByRole("button", { name: "Revisão" })
    ).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("review-tab")).toBeVisible();
  });

  test("falhas agrupadas: badge pedido por contagem e arquivos truncados", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    await expect(page.locator(".failure-list-summary")).toHaveText(
      "6 arquivos · 2 motivos"
    );
    const badges = page.locator(".failure-badge");
    await expect(badges.nth(0)).toHaveText("5");
    await expect(badges.nth(1)).toHaveText("1");
    await expect(page.locator(".failure-files").nth(0)).toContainText(
      "a5.mp3"
    );
  });

  test("falhas ausentes: secao some inteira (sem lista vazia)", async ({
    page,
  }) => {
    await stubAbaModelo(page, { model: { failures: [] } });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();
    await expect(page.locator(".failure-list")).toHaveCount(0);
  });

  test("detalhe tecnico abre e mostra alpha, cortes e extrator", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    const gatilho = page.locator(".tech-detail-trigger");
    await expect(gatilho).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator(".tech-detail-summary")).toContainText(
      "alpha 0.80 · cortes 0.351 / 0.649 · handcrafted-v1"
    );

    await gatilho.click();
    await expect(gatilho).toHaveAttribute("aria-expanded", "true");
    const valores = page.locator(".tech-detail-value");
    await expect(valores.nth(0)).toHaveText("0.80");
    await expect(valores.nth(1)).toHaveText("0.351 / 0.649");
    await expect(valores.nth(2)).toHaveText("handcrafted-v1");

    await gatilho.click();
    await expect(gatilho).toHaveAttribute("aria-expanded", "false");
  });

  test("treino com classe faltando degrada em um banner, derruba nada", async ({
    page,
  }) => {
    const motivo = "NotEnoughClassesError: falta exemplo na classe -1";
    await stubAbaModelo(page, {
      train: (route) => route.fulfill({ json: { detail: motivo }, status: 400 }),
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    await page.getByRole("button", { name: "RETREINAR" }).click();
    await expect(page.getByTestId("model-error")).toContainText(motivo);
    // A aba continua de pe: o resto na tela navega de igual forma.
    await expect(page.locator(".confusion-matrix")).toBeVisible();
  });

  test("treino com sucesso atualiza a metrica via refetch", async ({ page }) => {
    await stubAbaModelo(page, {
      stateAposTreino: { ...modeloFixo, accuracy: 0.95, n_examples: 21 },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();
    await expect(page.locator(".metric-value").nth(1)).toHaveText("92.3%");

    await page.getByRole("button", { name: "RETREINAR" }).click();
    await expect(page.locator(".metric-value").nth(1)).toHaveText("95.0%");
  });

  test("retreino em andamento: cliques repetidos viram um POST so", async ({
    page,
  }) => {
    let treinos = 0;
    await stubAbaModelo(page, {
      train: async (route) => {
        treinos += 1;
        // Resposta devagar abre a janela onde o segundo clique cairia.
        await new Promise((r) => setTimeout(r, 300));
        await route.fulfill({ json: { ok: true } });
      },
      stateAposTreino: { ...modeloFixo, accuracy: 0.95 },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("model-tab")).toBeVisible();

    const botao = page.getByRole("button", { name: "RETREINAR" });
    // Dois cliques no MESMO turn de evento, com o botao habilitado: os dois
    // onClick rodam com a closure antiga do hook, a janela exata onde o
    // batching do React nao salva. O guard por ref decide la dentro.
    await botao.evaluate((el) => {
      el.click();
      el.click();
    });
    // Em voo: desabilitado na tela enquanto a resposta vem.
    await expect(botao).toBeDisabled();

    // Assenta com a metrica nova e UM POST no total.
    await expect(page.locator(".metric-value").nth(1)).toHaveText("95.0%");
    expect(treinos).toBe(1);
  });
});
