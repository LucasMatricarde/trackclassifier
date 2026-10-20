import { expect, test } from "@playwright/test";
import { FIXTURE_VAZIA, mockLibrary } from "./library-fixtures";

test("abre a Biblioteca e mostra o total", async ({ page }) => {
  await mockLibrary(page, FIXTURE_VAZIA);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-tab")).toBeVisible();
  await expect(page.getByTestId("library-count")).toHaveText(
    "0 tracks classificadas"
  );
});
