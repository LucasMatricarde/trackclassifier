import { test, expect, type Page, type Route } from "@playwright/test";
import {
  estado,
  mockRevisaoCompleta,
  track,
} from "./review-fixtures";
import { npyFloat16, ondaFixa, ondaPorBanda } from "./fixtures/peaks";

/**
 * Regressao: a onda da faixa anterior era gravada no cache LRU do
 * WaveformCanvas sob a chave da faixa nova.
 *
 * Ao trocar de track o efeito de fetch so dispara DEPOIS do commit, entao o
 * efeito de render roda uma vez com track nova + peaks antigos (ainda no
 * state) e grava `<sha1 novo>:W:H:b` com a onda da faixa anterior. Quando os
 * peaks certos chegam, a chave e a mesma (o modo "b" ja estava na chave) e o
 * cache devolve a imagem envenenada: a onda fica igual entre as faixas.
 *
 * O teste prende a race de forma deterministica: o fetch dos peaks da 2a
 * faixa fica retido ate o teste liberar, e as duas ondas sao fixtures
 * distintas. Nada toca a fila, a biblioteca nem o data_dir reais.
 */

// peaks_path so precisa ser truthy: e ele que liga o fetch de bandas.
const ALPHA = { ...track("sha-wave-alpha", "Alpha"), peaks_path: "stub" };
const BETA = { ...track("sha-wave-beta", "Beta"), peaks_path: "stub" };

const ONDA_ALPHA = npyFloat16(ondaPorBanda());
const ONDA_BETA = npyFloat16(ondaFixa());

/** Pixels do canvas da onda grande (RGBA bruto) como string comparavel. */
async function pixelsDaOnda(page: Page): Promise<string> {
  return page.evaluate(() => {
    const canvas = document.querySelector(".waveform-main canvas") as HTMLCanvasElement;
    const ctx = canvas.getContext("2d")!;
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    // Hash FNV-1a: comparar 2 imagens inteiras sem trafegar megabytes.
    let h = 2166136261;
    for (let i = 0; i < data.length; i++) {
      h = Math.imul(h ^ data[i], 16777619) >>> 0;
    }
    return `${canvas.width}x${canvas.height}:${h}`;
  });
}

/**
 * Revisao mockada com a rota de peaks de `rotaPeaks`. As rotas de peaks sao
 * registradas depois do mockRevisaoCompleta e antes do goto, entao valem desde
 * o primeiro fetch (sem reload).
 */
async function abreRevisao(
  page: Page,
  atual: typeof ALPHA,
  fila: (typeof ALPHA)[],
  rotaPeaks: (route: Route) => Promise<void>
) {
  await mockRevisaoCompleta(page, estado(atual, fila));
  await page.route("**/api/peaks/**", rotaPeaks);
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto("/");
  await page.waitForSelector(".review-header", { timeout: 30000 });
  await page.waitForFunction(
    () => {
      const c = document.querySelector(".waveform-main canvas") as HTMLCanvasElement | null;
      return Boolean(c && c.width > 50 && c.height > 50);
    },
    undefined,
    { timeout: 15000 }
  );
}

/** Espera duas leituras iguais seguidas: a onda de bandas assentou. */
async function esperaAssentar(page: Page): Promise<string> {
  let anterior = "";
  await expect
    .poll(
      async () => {
        const atual = await pixelsDaOnda(page);
        const igual = atual === anterior;
        anterior = atual;
        return igual;
      },
      { timeout: 10000, intervals: [300] }
    )
    .toBe(true);
  return anterior;
}

test.describe("WaveformCanvas: cache por faixa", () => {
  test("onda da faixa anterior nao envenena o cache da faixa nova", async ({ page, context }) => {
    // Referencia: a MESMA tela com a Beta como faixa atual, peaks sem atraso e
    // cache de pagina limpo -- o que a onda da Beta deve ser pixel a pixel.
    const ref = await context.newPage();
    await abreRevisao(ref, BETA, [], (route) => route.fulfill({ body: ONDA_BETA }));
    const pixelsBetaEsperados = await esperaAssentar(ref);
    await ref.close();

    // Cenario real: Alpha atual, Beta na fila; peaks da Beta retidos.
    let liberaBeta!: () => void;
    const retemBeta = new Promise<void>((resolve) => (liberaBeta = resolve));
    let betaPediu!: () => void;
    const pedidoBeta = new Promise<void>((resolve) => (betaPediu = resolve));

    await abreRevisao(page, ALPHA, [BETA], async (route) => {
      if (route.request().url().includes(BETA.sha1)) {
        betaPediu();
        await retemBeta;
        await route.fulfill({ body: ONDA_BETA });
      } else {
        await route.fulfill({ body: ONDA_ALPHA });
      }
    });
    // As duas ondas precisam ser distinguiveis, senao o teste nao prova nada.
    expect(await esperaAssentar(page)).not.toBe(pixelsBetaEsperados);

    // Vai para a Beta (skip local) e prende o fetch dela.
    await page.keyboard.press("s");
    await pedidoBeta;
    await expect(page.locator(".review-header")).toContainText("Beta");

    // Libera o fetch: a onda final tem de ser a da Beta, nao a imagem que o
    // render intermediario gravou no cache.
    liberaBeta();
    await expect
      .poll(() => pixelsDaOnda(page), { timeout: 10000, intervals: [300] })
      .toBe(pixelsBetaEsperados);
  });
});
