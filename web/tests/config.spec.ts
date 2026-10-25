import { test, expect } from "@playwright/test";
import { stubConfig, configRawFixo, type ConfigRaw } from "./fixtures/config";

test.describe("Configuração", () => {
  test.beforeEach(async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
  });

  test("carrega os caminhos e valores atuais", async ({ page }) => {
    await expect(page.getByTestId("config-inbox")).not.toHaveValue("");
    await expect(page.getByTestId("config-up")).not.toHaveValue("");
    await expect(page.getByTestId("config-neutral")).not.toHaveValue("");
    await expect(page.getByTestId("config-down")).not.toHaveValue("");
    await expect(page.getByTestId("config-data_dir")).not.toHaveValue("");
    await expect(page.getByTestId("config-retrain_every")).toHaveValue("10");
    await expect(page.getByTestId("config-min_examples")).toHaveValue("50");
    await expect(
      page.getByRole("button", { name: "Configuração" })
    ).toHaveAttribute("aria-current", "page");
  });

  test("auto-save: edita e aplica sozinho, sem botao Salvar", async ({
    page,
  }) => {
    // O mockup nao desenha Salvar: o apply sai do auto-save.
    await expect(page.getByTestId("config-save")).toHaveCount(0);

    const aplicadas: ConfigRaw[] = [];
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-data_dir").fill("/dados/novo");
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });
    expect(aplicadas.length).toBeGreaterThanOrEqual(1);
    expect(aplicadas.at(-1)?.paths?.data_dir).toBe("/dados/novo");
  });

  test("pasta de entrada vazia mostra erro e nao aplica", async ({ page }) => {
    const aplicadas: ConfigRaw[] = [];
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      await route.fulfill({ json: { ok: true } });
    });

    const inbox = page.getByTestId("config-inbox");
    await inbox.fill("");
    await expect(page.getByText("Escolha a pasta de entrada.")).toBeVisible();
    await page.waitForTimeout(1500);
    expect(aplicadas).toHaveLength(0);

    // Volta com um valor valido DIFERENTE: igual ao original nao teria o
    // que salvar (rascunho == salvo). O erro some e o auto-save aplica.
    await inbox.fill("/musicas/outra-entrada");
    await expect(page.getByText("Escolha a pasta de entrada.")).toHaveCount(0);
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });
    expect(aplicadas.length).toBeGreaterThanOrEqual(1);
    expect(aplicadas.at(-1)?.folders?.inbox).toBe("/musicas/outra-entrada");
  });

  test("secao 1: pill de novas, badge de tracks e linhas de destino", async ({
    page,
  }) => {
    // Stats do stub: 6 novas; destinos 286 + 186 + 71 = 543 tracks.
    await expect(page.getByTestId("config-pill-novas")).toHaveText("6 NOVAS");
    await expect(page.getByTestId("config-pill-tracks")).toHaveText(
      "543 TRACKS"
    );

    const linhas = page.getByTestId("config-destino-row");
    await expect(linhas).toHaveCount(3);
    await expect(linhas.nth(0)).toContainText("-1");
    await expect(linhas.nth(0)).toContainText("Energia baixa");
    await expect(linhas.nth(1)).toContainText("neutra");
    await expect(linhas.nth(1)).toContainText("Energia equilibrada");
    await expect(linhas.nth(2)).toContainText("+1");
    await expect(linhas.nth(2)).toContainText("Energia alta");

    // Hairline entre entrada e destinos; acoes de escolher por campo.
    await expect(page.getByTestId("config-hairline")).toBeVisible();
    await expect(page.getByTestId("config-escolher-inbox")).toBeVisible();
    await expect(page.getByTestId("config-icone-up")).toBeVisible();
    await expect(page.getByTestId("config-escolher-down")).toBeVisible();
  });

  test("stats indisponivel: pills somem e a tela continua funcional", async ({
    page,
  }) => {
    await page.route("**/api/config/stats", (route) =>
      route.fulfill({ status: 500, json: { detail: "erro" } })
    );
    await page.reload();
    // O reload reseta a aba ativa: volta para a Configuracao antes de medir.
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("config-pill-novas")).toHaveCount(0);
    await expect(page.getByTestId("config-pill-tracks")).toHaveCount(0);
    await expect(page.getByTestId("config-inbox")).not.toHaveValue("");
  });

  test("secao 2: toggles reais fazem round-trip e o de copia e so visual", async ({
    page,
  }) => {
    // Stub de apply que TAMBEM atualiza o raw servido pelo GET: e o que o
    // servidor real faz e o que para o ciclo de auto-save (sem a atualizacao
    // o rascunho nunca iguala o salvo e o apply re-dispara a cada 800ms).
    const aplicadas: ConfigRaw[] = [];
    let atual: ConfigRaw = JSON.parse(JSON.stringify(configRawFixo));
    await page.route("**/api/config", (route) =>
      route.fulfill({
        json: { raw: atual, active_profile: "default", profiles: ["default"] },
      })
    );
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      atual = aplicadas.at(-1)!;
      await route.fulfill({ json: { ok: true } });
    });

    const criar = page.getByTestId("config-toggle-create_under_root");
    const mover = page.getByTestId("config-toggle-auto_move_enabled");
    const copia = page.getByTestId("config-toggle-copia_entrada");

    // Dados reais do stub: os dois toggles comecam desligados.
    await expect(criar).toHaveAttribute("aria-checked", "false");
    await expect(mover).toHaveAttribute("aria-checked", "false");
    // O de copia nao existe no backend: so visual, como no mockup. O
    // aria-disabled faz o Playwright trata-lo como desabilitado -- o force
    // simula a tentativa de clique de uma pessoa (o elemento nem tem
    // handler, entao nada acontece).
    await expect(copia).toHaveAttribute("aria-disabled", "true");
    await expect(copia).toHaveAttribute("aria-checked", "true");

    await criar.click();
    await mover.click();
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });

    const gravado = aplicadas.at(-1);
    expect(gravado?.model?.create_under_root).toBe(true);
    expect(gravado?.model?.auto_move_enabled).toBe(true);

    // Clicar no so-visual nao altera estado nem dispara apply.
    const antes = aplicadas.length;
    await copia.click({ force: true });
    await expect(copia).toHaveAttribute("aria-checked", "true");
    await page.waitForTimeout(1200);
    expect(aplicadas.length).toBe(antes);
  });
});
