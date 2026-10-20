import { test, expect } from "@playwright/test";

test.describe("Configuração", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
  });

  test("carrega os caminhos atuais e mantém Salvar desabilitado", async ({
    page,
  }) => {
    await expect(page.getByTestId("config-inbox")).not.toHaveValue("");
    await expect(page.getByTestId("config-up")).not.toHaveValue("");
    await expect(page.getByTestId("config-neutral")).not.toHaveValue("");
    await expect(page.getByTestId("config-down")).not.toHaveValue("");
    await expect(page.getByTestId("config-data_dir")).not.toHaveValue("");
    await expect(page.getByTestId("config-save")).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Configuração" })
    ).toHaveAttribute("aria-current", "page");
  });

  test("pasta de entrada vazia mostra erro sem gravar", async ({ page }) => {
    const inbox = page.getByTestId("config-inbox");
    const original = await inbox.inputValue();

    await inbox.fill("");
    await expect(page.getByText("Escolha a pasta de entrada.")).toBeVisible();
    await expect(page.getByTestId("config-save")).toBeDisabled();

    // Restaura o valor sem clicar em Salvar: o teste nunca toca no
    // config.toml real do usuario.
    await inbox.fill(original);
    await expect(page.getByText("Escolha a pasta de entrada.")).toHaveCount(0);
    await expect(page.getByTestId("config-save")).toBeDisabled();
  });
});
