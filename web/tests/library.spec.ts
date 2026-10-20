import { expect, test } from "@playwright/test";
import { FIXTURE_TRES, FIXTURE_VAZIA, mockLibrary } from "./library-fixtures";

test("abre a Biblioteca e mostra o total", async ({ page }) => {
  await mockLibrary(page, FIXTURE_VAZIA);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-tab")).toBeVisible();
  await expect(page.getByTestId("library-count")).toHaveText(
    "0 tracks classificadas"
  );
});

test("biblioteca vazia mostra EmptyState com Escanear e chips desabilitados", async ({
  page,
}) => {
  await mockLibrary(page, FIXTURE_VAZIA);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-empty")).toContainText("Biblioteca vazia");
  await expect(
    page.getByTestId("library-empty").getByRole("button", { name: "Escanear" })
  ).toBeVisible();
  // Sem tracks nao ha o que filtrar: os quatro chips ficam desabilitados.
  await expect(page.getByTestId("library-chip-todos")).toBeDisabled();
  await expect(page.getByTestId("library-chip-down")).toBeDisabled();
  await expect(page.getByTestId("library-chip-neutral")).toBeDisabled();
  await expect(page.getByTestId("library-chip-up")).toBeDisabled();
});

test("busca, chips e ordenacao filtram a tabela", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-row")).toHaveCount(3);

  await page.getByTestId("library-search").fill("alpha");
  await expect(page.getByTestId("library-row")).toHaveCount(1);
  await page.getByTestId("library-search").fill("");

  await page.getByTestId("library-chip-up").click();
  await expect(page.getByTestId("library-row")).toHaveCount(1);

  await page.getByTestId("library-chip-todos").click();
  await page.getByTestId("library-sort").selectOption("title:desc");
  await expect(page.getByTestId("library-row").first()).toContainText("Gamma");
});

test("toggle de notacao muda o KeyChip da tabela", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-row").first()).toContainText("8A");
  await page.getByTestId("library-notation").click();
  await expect(page.getByTestId("library-row").first()).toContainText("Am");
});

test("linha sem capa mostra placeholder e linha sem key mostra traco", async ({
  page,
}) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  // So a Gamma nao tem cover_path no fixture.
  await expect(page.locator(".library-cover-empty")).toHaveCount(1);
  const gamma = page.getByTestId("library-row").filter({ hasText: "Gamma" });
  await expect(gamma.locator(".key-chip-empty")).toHaveText("—");
});

test("busca sem resultado mostra aviso e botao de limpar", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await page.getByTestId("library-search").fill("zzz-inexistente");
  await expect(page.getByTestId("library-row")).toHaveCount(0);
  await expect(page.getByTestId("library-sem-resultado")).toContainText(
    "Nenhuma track encontrada."
  );
  await page.getByRole("button", { name: "Limpar busca" }).click();
  await expect(page.getByTestId("library-row")).toHaveCount(3);
});
