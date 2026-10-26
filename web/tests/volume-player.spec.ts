import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { FIXTURE_TRES, mockLibrary } from "./library-fixtures";
import { ESTADO_ALPHA, mockRevisaoCompleta } from "./review-fixtures";

/**
 * Volume do player nas duas telas. Tudo mockado (regra 8 do AGENTS.md): a fila
 * da Revisao e a biblioteca vem de fixtures e o <audio> real nunca toca nada.
 *
 * O useAudioPlayer cria o elemento com `new Audio()` e nao o poe no DOM, entao
 * o teste so enxerga o `audio.volume` se registrar as instancias na criacao.
 */
test.use({ viewport: { width: 1512, height: 1037 } });

async function espiaAudio(page: Page) {
  await page.addInitScript(() => {
    const Original = window.Audio;
    const criados: HTMLAudioElement[] = [];
    (window as unknown as { __audios: HTMLAudioElement[] }).__audios = criados;
    // Function (nao classe) para o `new Audio()` do hook seguir valendo.
    window.Audio = function (this: unknown, src?: string) {
      const el = new Original(src);
      criados.push(el);
      return el;
    } as unknown as typeof Audio;
  });
}

// O vivo e o ultimo criado: o StrictMode do dev monta o efeito duas vezes e
// o primeiro <audio> fica orfao (pausado, com o volume do nascimento).
const volumeDoAudio = (page: Page) =>
  page.evaluate(
    () => (window as unknown as { __audios: HTMLAudioElement[] }).__audios.at(-1)?.volume ?? null
  );

/** Clica no trilho a `fracao` da largura, no mesmo x que o VolumeRail le. */
async function clicaNoTrilho(page: Page, seletor: string, fracao: number) {
  const rail = page.locator(seletor);
  const box = (await rail.boundingBox())!;
  // O rail converte com (width - 1): o clique tem de usar a mesma conta. O x
  // vai arredondado porque o Chromium entrega clientX inteiro (35,7 virava 35
  // e o trilho lia 29, nao 30).
  const x = Math.round(box.x + fracao * (box.width - 1));
  await page.mouse.click(x, box.y + box.height / 2);
}

test.describe("volume do player", () => {
  async function abreRevisao(page: Page) {
    await espiaAudio(page);
    await mockRevisaoCompleta(page, ESTADO_ALPHA);
    await page.goto("/");
    await page.waitForSelector(".player-bar", { timeout: 30000 });
    return page.locator(".player-bar").getByRole("slider", { name: "Volume" });
  }

  async function abreBiblioteca(page: Page) {
    await espiaAudio(page);
    await mockLibrary(page, FIXTURE_TRES);
    await page.goto("/");
    await page.getByRole("button", { name: "Biblioteca" }).click();
    await page.getByTestId("library-row").first().click();
    return page.getByTestId("library-player").getByRole("slider", { name: "Volume" });
  }

  test("Revisao: clique a 30% muda o slider e o audio", async ({ page }) => {
    const slider = await abreRevisao(page);
    await clicaNoTrilho(page, ".player-bar .volume-rail", 0.3);
    await expect(slider).toHaveAttribute("aria-valuenow", "30");
    expect(await volumeDoAudio(page)).toBeCloseTo(0.3, 2);
  });

  test("Biblioteca: clique a 30% muda o slider e o audio", async ({ page }) => {
    const slider = await abreBiblioteca(page);
    await clicaNoTrilho(page, ".library-player .volume-rail", 0.3);
    await expect(slider).toHaveAttribute("aria-valuenow", "30");
    expect(await volumeDoAudio(page)).toBeCloseTo(0.3, 2);
  });

  test("Revisao: o padrao 80 do trilho e o do audio sao a mesma coisa", async ({ page }) => {
    const slider = await abreRevisao(page);
    await expect(slider).toHaveAttribute("aria-valuenow", "80");
    expect(await volumeDoAudio(page)).toBeCloseTo(0.8, 2);
  });

  test("Biblioteca: o padrao 80 do trilho e o do audio sao a mesma coisa", async ({ page }) => {
    const slider = await abreBiblioteca(page);
    await expect(slider).toHaveAttribute("aria-valuenow", "80");
    expect(await volumeDoAudio(page)).toBeCloseTo(0.8, 2);
  });

  test("Biblioteca: o volume escolhido sobrevive a troca de track", async ({ page }) => {
    const slider = await abreBiblioteca(page);
    await clicaNoTrilho(page, ".library-player .volume-rail", 0.3);
    await expect(slider).toHaveAttribute("aria-valuenow", "30");

    // Trocar de track recarrega o <audio>; o trilho e o elemento nao podem voltar atras.
    await page.getByTestId("library-row").nth(1).click();
    await expect(slider).toHaveAttribute("aria-valuenow", "30");
    expect(await volumeDoAudio(page)).toBeCloseTo(0.3, 2);
  });

  test("os dois transportes usam o mesmo alto-falante com ondas (3 tracos)", async ({ page }) => {
    await mockRevisaoCompleta(page, ESTADO_ALPHA);
    await page.goto("/");
    await page.waitForSelector(".player-bar", { timeout: 30000 });
    const revisao = page.locator("[data-testid='player-volume-icon'] svg");
    // Corpo do alto-falante + duas ondas: o path antigo era um so, malformado.
    await expect(revisao.locator("path")).toHaveCount(3);
    const htmlRevisao = await revisao.innerHTML();

    await page.getByRole("button", { name: "Biblioteca" }).click();
    const biblioteca = page.locator("[data-testid='library-volume-icon'] svg");
    await biblioteca.waitFor();
    expect(await biblioteca.innerHTML()).toBe(htmlRevisao);
  });

  test("Revisao: knob do trilho e um circulo de 9px (mockup)", async ({ page }) => {
    await abreRevisao(page);
    const knob = await page.evaluate(() => {
      const el = document.querySelector(".player-bar .volume-marker")!;
      const r = el.getBoundingClientRect();
      return { w: r.width, h: r.height, raio: parseFloat(getComputedStyle(el).borderTopLeftRadius) };
    });
    expect(knob.w).toBe(9);
    expect(knob.h).toBe(9);
    // Raio >= metade do lado = circulo (o token --radius-full vale 9999px).
    expect(knob.raio).toBeGreaterThanOrEqual(4.5);
  });
});
