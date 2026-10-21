import { test, expect } from "@playwright/test";
import { stubAbaModelo, modeloFixo } from "./fixtures/modelo";

/**
 * E2E da aba Modelo — dashboard do mockup — com estado sintetico:
 * deterministico, nao depende da biblioteca local nem de treino real.
 * A fixture cobre treinado (com delta e historico), bloqueado com motivo,
 * nao treinado (metricas ausentes), falhas agrupadas e disclosure
 * avancado recolhido.
 */

async function abreModelo(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Modelo" }).click();
  await expect(page.getByTestId("model-tab")).toBeVisible();
  // Quando o primeiro card existe, o estado inteiro chegou (WS ou fetch).
  await expect(page.getByTestId("metric-exemplos")).toBeVisible();
}

test.describe("Aba Modelo — dashboard", () => {
  test("quatro cards com valores do estado fixo", async ({ page }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    await expect(page.getByTestId("metric-exemplos-valor")).toHaveText("30");
    await expect(page.getByTestId("metric-acc-valor")).toHaveText("92,3%");
    await expect(page.getByTestId("metric-mae-valor")).toHaveText("0,250");
    await expect(page.getByTestId("metric-f1-valor")).toHaveText("91,5%");

    // O banner informativo existe; o "Saiba mais" ficou de fora porque
    // nao ha alvo real (decisao do design).
    await expect(page.locator(".model-banner")).toContainText("O modelo analisa");
    await expect(page.locator(".model-banner a")).toHaveCount(0);
  });

  test("chips de delta contra o treino anterior aparecem com sinal", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    // accuracy +2.2% sobe; mae desce (e bom); f1 sobe.
    await expect(page.getByTestId("metric-acc-delta")).toContainText("+2,2%");
    await expect(page.getByTestId("metric-acc-delta")).toContainText("▲");
    await expect(page.getByTestId("metric-mae-delta")).toContainText("-0,022");
    await expect(page.getByTestId("metric-mae-delta")).toContainText("▼");
    await expect(page.getByTestId("metric-f1-delta")).toContainText("+1,7%");

    // Exemplos nao tem delta: contagem nao e comparacao de qualidade.
    await expect(page.getByTestId("metric-exemplos-delta")).toHaveCount(0);

    // Erro ordinal: descer e bom — o chip verde segue da classe, nao da
    // direcao da seta.
    await expect(page.getByTestId("metric-mae-delta")).toHaveClass(
      /metric-delta-bom/
    );
    await expect(page.getByTestId("metric-acc-delta")).toHaveClass(
      /metric-delta-bom/
    );
  });

  test("sem treino anterior nao existem chips", async ({ page }) => {
    await stubAbaModelo(page, {
      model: {
        history: [modeloFixo.history[0]],
        deltas: {},
        version: "v1.0.0",
      },
    });
    await abreModelo(page);

    await expect(page.getByTestId("metric-acc-delta")).toHaveCount(0);
    await expect(page.getByTestId("metric-mae-delta")).toHaveCount(0);
  });

  test("desempenho por classe mostra as tres barras da fixture", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    await expect(page.getByTestId("per-class")).toBeVisible();
    await expect(page.getByTestId("per-class-precision-0")).toContainText("1,000");
    await expect(page.getByTestId("per-class-recall-0")).toContainText("0,667");
    await expect(page.getByTestId("per-class-f1-1")).toContainText("0,963");
    await expect(page.getByTestId("per-class-f1-2")).toContainText("0,889");
    // Tres linhas; a primeira barra usa o recall 0,667 da (-1) da fixture.
    await expect(page.locator(".per-class-row")).toHaveCount(3);
    // Primeira linha = -1 (recall 0,667): a segunda barra da linha e o
    // recall; a primeira e precision (1,0 → 100%).
    await expect(
      page
        .locator(".per-class-row")
        .first()
        .locator(".per-class-bar-fill")
        .nth(1)
    ).toHaveAttribute("style", /width: 66\.7%/);
  });

  test("matriz de confusao renderiza contagens e nota de intensidade", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    await expect(page.getByTestId("confusion-panel")).toBeVisible();
    const celulas = page.locator(".confusion-cell");
    await expect(celulas).toHaveCount(9);
    await expect(celulas.nth(0)).toHaveText("2");
    await expect(celulas.nth(4)).toHaveText("13");
    await expect(celulas.nth(8)).toHaveText("12");
    await expect(page.locator(".confusion-legend-note")).toContainText(
      "Quanto mais escuro, maior a quantidade de exemplos."
    );
    // Intensidade: a celula 13 e mais "forte" que a 2 — inline style
    // materializa color-mix, entao conferimos que os valores divergem.
    const bg13 = await celulas.nth(4).evaluate((el) => getComputedStyle(el).backgroundColor);
    const bg2 = await celulas.nth(0).evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg13).not.toBe(bg2);
  });

  test("distribuicao com contagens e recomendacao da minoria", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    await expect(page.getByTestId("distribution-count-0")).toContainText("3");
    await expect(page.getByTestId("distribution-count-1")).toContainText("14");
    await expect(page.getByTestId("distribution-count-2")).toContainText("13");

    // lento tem 21% da maior (14): abaixo do limiar de 70%: recomendacao.
    await expect(page.getByTestId("distribution-recommendation")).toContainText(
      "-1 tem 21% dos exemplos de neutra"
    );
  });

  test("balanco equilibrado esconde a recomendacao", async ({ page }) => {
    await stubAbaModelo(page, {
      model: { class_counts: [12, 14, 13] },
    });
    await abreModelo(page);
    await expect(page.getByTestId("distribution-recommendation")).toHaveCount(0);
  });

  test("historico de treinamentos: recentes primeiro, ativo no topo", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    const linhas = page.getByTestId("history-row");
    await expect(linhas).toHaveCount(2);
    await expect(linhas.nth(0).getByTestId("history-ts")).toContainText("21/10/2026");
    await expect(linhas.nth(0).getByTestId("history-version")).toHaveText("v1.1.0");
    await expect(linhas.nth(0).getByTestId("history-status")).toHaveText("Ativo");
    await expect(linhas.nth(1).getByTestId("history-version")).toHaveText("v1.0.0");
    await expect(linhas.nth(1).getByTestId("history-status")).toHaveText("—");
  });

  test("settings carrega config e comita mudanca em POST", async ({ page }) => {
    let recebido: { retrain_every: number; min_examples: number } | null = null;
    await stubAbaModelo(page, {
      settings: async (route) => {
        recebido = JSON.parse(route.request().postData() ?? "{}");
        await route.fulfill({ json: { ok: true } });
      },
    });
    await abreModelo(page);

    await expect(page.getByTestId("settings-retrain-value")).toHaveValue("10");
    await expect(page.getByTestId("settings-min-value")).toHaveValue("5");

    await page
      .getByRole("button", { name: "Aumentar Retreinar a cada" })
      .click();
    await expect
      .poll(() => recebido)
      .toEqual({ retrain_every: 11, min_examples: 5 });
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
    await abreModelo(page);

    const botao = page.getByTestId("model-train-panel");
    // Dois cliques no MESMO turn de evento: os dois onClick rodam com a
    // closure antiga do hook, a janela exata onde o batching do React
    // nao salva. O guard por ref decide la dentro.
    await botao.evaluate((el) => {
      el.click();
      el.click();
    });
    await expect(botao).toBeDisabled();
    await expect(botao).toContainText("TREINANDO");

    // Assenta com a metrica nova e UM POST no total.
    await expect(page.getByTestId("metric-acc-valor")).toHaveText("95,0%");
    expect(treinos).toBe(1);
  });

  test("bloqueado de treino desabilita os dois gatilhos com motivo", async ({
    page,
  }) => {
    await stubAbaModelo(page, {
      model: {
        train_blocked_reason:
          "Falta exemplo na classe -1. Rotular mais -1 desbloqueia o treino.",
      },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("metric-exemplos")).toBeVisible();

    await expect(page.getByTestId("model-train-panel")).toBeDisabled();
    await expect(page.getByTestId("header-model-retrain")).toBeDisabled();
    await expect(page.getByTestId("settings-blocked-reason")).toContainText(
      "Falta exemplo na classe -1"
    );
  });

  test("isla do header mostra ultimo treinamento, versao e gera treino", async ({
    page,
  }) => {
    await stubAbaModelo(page, {
      stateAposTreino: { ...modeloFixo, accuracy: 0.95, version: "v1.2.0" },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    await expect(page.getByTestId("header-model-island")).toBeVisible();

    await expect(page.getByTestId("header-model-island")).toContainText(
      "Último treinamento 21/10/2026 13:24"
    );
    await expect(page.getByTestId("header-model-island")).toContainText(
      "Modelo ativo v1.1.0"
    );

    await page.getByTestId("header-model-retrain").click();
    // Refetch depois do POST trae a versao nova.
    await expect(page.getByTestId("header-model-island")).toContainText(
      "Modelo ativo v1.2.0"
    );
  });

  test("nao treinado: cards em --, sem chips, historico e por-classe vazios", async ({
    page,
  }) => {
    await stubAbaModelo(page, {
      model: {
        accuracy: null,
        ordinal_mae: null,
        confusion: null,
        weighted_f1: null,
        per_class: null,
        version: null,
        last_trained_at: null,
        history: [],
        deltas: {},
        alpha: null,
        thresholds: null,
      },
    });
    await abreModelo(page);

    await expect(page.getByTestId("metric-exemplos-valor")).toHaveText("30");
    await expect(page.getByTestId("metric-acc-valor")).toHaveText("--");
    await expect(page.getByTestId("metric-mae-valor")).toHaveText("--");
    await expect(page.getByTestId("metric-f1-valor")).toHaveText("--");
    await expect(page.getByTestId("metric-acc-delta")).toHaveCount(0);

    // Matriz some inteira; por classe fica com nota; historico vazio.
    await expect(page.getByTestId("confusion-panel")).toHaveCount(0);
    await expect(page.getByTestId("per-class-empty")).toBeVisible();
    await expect(page.getByTestId("history-empty")).toBeVisible();
    await expect(page.getByTestId("distribution-count-0")).toContainText("3");
    // Falhas: invariante do desktop (o mockup nao as desenha, mas a
    // falha real do scan nao pode sumir junto).
    await expect(page.locator(".failure-list")).toBeVisible();
  });

  test("falhas agrupadas: badge pedido por contagem e arquivos truncados", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    await expect(page.locator(".failure-list-summary")).toHaveText(
      "6 arquivos · 2 motivos"
    );
    const badges = page.locator(".failure-badge");
    await expect(badges.nth(0)).toHaveText("5");
    await expect(badges.nth(1)).toHaveText("1");
    await expect(page.locator(".failure-files").nth(0)).toContainText("a5.mp3");
  });

  test("falhas ausentes: secao some inteira (sem lista vazia)", async ({
    page,
  }) => {
    await stubAbaModelo(page, { model: { failures: [] } });
    await abreModelo(page);
    await expect(page.locator(".failure-list")).toHaveCount(0);
  });

  test("opcoes avancadas abre e mostra alpha, cortes e extrator", async ({
    page,
  }) => {
    await stubAbaModelo(page);
    await abreModelo(page);

    const gatilho = page.locator(".tech-detail-trigger");
    await expect(gatilho).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator(".tech-detail-summary")).toContainText(
      "alpha 0.80"
    );

    await gatilho.click();
    await expect(gatilho).toHaveAttribute("aria-expanded", "true");
    const valores = page.locator(".tech-detail-value");
    await expect(valores.nth(0)).toHaveText("0.80");
    await expect(valores.nth(1)).toHaveText("0.351 / 0.649");
    await expect(valores.nth(2)).toHaveText("handcrafted-v1");
  });

  test("treino com classe faltando degrada em um banner, derruba nada", async ({
    page,
  }) => {
    const motivo = "NotEnoughClassesError: falta exemplo na classe -1";
    await stubAbaModelo(page, {
      train: (route) => route.fulfill({ json: { detail: motivo }, status: 400 }),
    });
    await abreModelo(page);

    await page.getByTestId("model-train-panel").click();
    await expect(page.getByTestId("model-error")).toContainText(motivo);
    await expect(page.getByTestId("confusion-panel")).toBeVisible();
  });
});
