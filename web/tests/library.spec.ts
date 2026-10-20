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
  // No teste as imagens nao sao servidas, entao todas mostram placeholder.
  const table = page.getByTestId("library-table");
  await expect(table.locator(".library-cover-empty")).toHaveCount(3);
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

test("seleciona a primeira linha e mostra a ficha tecnica", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-inspector-title")).toHaveText("Alpha");
  await expect(page.getByTestId("library-inspector-bpm")).toHaveText("128");
  await page.getByTestId("library-row").nth(1).click();
  await expect(page.getByTestId("library-inspector-title")).toHaveText("beta");
});

test("biblioteca vazia mostra inspector vazio com mensagem", async ({ page }) => {
  await mockLibrary(page, FIXTURE_VAZIA);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-inspector-empty")).toContainText(
    "Nenhuma track selecionada"
  );
});

test("linha sem key mostra traco no inspector", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  const gamma = page.getByTestId("library-row").filter({ hasText: "Gamma" });
  await gamma.click();
  await expect(page.getByTestId("library-inspector-key")).toContainText("—");
});

test("linha sem capa mostra placeholder no inspector", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  const gamma = page.getByTestId("library-row").filter({ hasText: "Gamma" });
  await gamma.click();
  const inspector = page.locator(".library-inspector");
  await expect(inspector.locator(".library-inspector-cover-empty")).toHaveCount(1);
});
