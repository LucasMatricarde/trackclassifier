import { test, expect, type Page, type Route } from "@playwright/test";
import {
  estado,
  mockRevisaoCompleta,
  track,
} from "./review-fixtures";
import { npyFloat16, ondaFixa, ondaPorBanda } from "./fixtures/peaks";
import { FIXTURE_TRES, mockLibrary } from "./library-fixtures";

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

/** Retem uma resposta ate `libera()`: tira o timing do teste. */
function portao() {
  let libera!: () => void;
  const espera = new Promise<void>((resolve) => (libera = resolve));
  let pediu!: () => void;
  const pedido = new Promise<void>((resolve) => (pediu = resolve));
  return { espera, libera, pedido, pediu };
}

/**
 * Libera os peaks retidos e espera a onda DE BANDAS assentar. "Duas leituras
 * iguais" sozinho nao basta: sob carga o mono (primeiro render) tambem fica
 * estavel por 300ms e seria tomado pela onda final. Por isso a leitura so
 * vale depois de o hash sair do mono capturado antes da liberacao.
 */
async function liberaEEsperaBandas(page: Page, liberar: () => void): Promise<string> {
  const mono = await esperaAssentar(page);
  liberar();
  await expect.poll(() => pixelsDaOnda(page), { timeout: 10000 }).not.toBe(mono);
  return esperaAssentar(page);
}

test.describe("WaveformCanvas: cache por faixa", () => {
  test("onda da faixa anterior nao envenena o cache da faixa nova", async ({ page, context }) => {
    // Referencia: a MESMA tela com a Beta como faixa atual e cache de pagina
    // limpo -- o que a onda da Beta deve ser pixel a pixel.
    const ref = await context.newPage();
    const portaoRef = portao();
    await abreRevisao(ref, BETA, [], async (route) => {
      await portaoRef.espera;
      await route.fulfill({ body: ONDA_BETA });
    });
    const pixelsBetaEsperados = await liberaEEsperaBandas(ref, portaoRef.libera);
    await ref.close();

    // Cenario real: Alpha atual, Beta na fila; peaks da Beta retidos.
    const portaoAlpha = portao();
    const portaoBeta = portao();
    await abreRevisao(page, ALPHA, [BETA], async (route) => {
      if (route.request().url().includes(BETA.sha1)) {
        portaoBeta.pediu();
        await portaoBeta.espera;
        await route.fulfill({ body: ONDA_BETA });
      } else {
        await portaoAlpha.espera;
        await route.fulfill({ body: ONDA_ALPHA });
      }
    });
    // As duas ondas precisam ser distinguiveis, senao o teste nao prova nada.
    const pixelsAlpha = await liberaEEsperaBandas(page, portaoAlpha.libera);
    expect(pixelsAlpha).not.toBe(pixelsBetaEsperados);

    // Vai para a Beta (skip local) e prende o fetch dela.
    await page.keyboard.press("s");
    await portaoBeta.pedido;
    await expect(page.locator(".review-header")).toContainText("Beta");

    // Libera o fetch: a onda final tem de ser a da Beta, nao a imagem que o
    // render intermediario gravou no cache.
    portaoBeta.libera();
    await expect
      .poll(() => pixelsDaOnda(page), { timeout: 10000, intervals: [300] })
      .toBe(pixelsBetaEsperados);
  });
});

/**
 * Inspetor da Biblioteca: o InspectorWaveform nao tem `key` no
 * LibraryInspector, entao trocar a linha selecionada reaproveita a instancia.
 * O fetch era guardado por `if (peaks || error) return`, e como `peaks` ja
 * estava preenchido pela faixa anterior, a onda nova nunca era buscada: o
 * inspetor ficava com a onda da primeira faixa selecionada.
 */
test.describe("InspectorWaveform: troca de faixa selecionada", () => {
  async function abreBiblioteca(page: Page, ondaAlpha: Buffer = ONDA_ALPHA) {
    await mockLibrary(page, FIXTURE_TRES);
    // Registradas depois do mockLibrary (rotas mais novas tem precedencia):
    // duas ondas distintas e conhecidas, sem depender do ondasFake.
    await page.route("**/api/peaks/sha-alpha*", (route) =>
      route.fulfill({ body: ondaAlpha })
    );
    await page.route("**/api/peaks/sha-beta*", (route) =>
      route.fulfill({ body: ONDA_BETA })
    );
    await page.goto("/");
    await page.getByRole("button", { name: "Biblioteca" }).click();
    await expect(page.getByTestId("library-row")).toHaveCount(3);
  }

  async function pixelsDoInspetor(page: Page): Promise<string> {
    return page.evaluate(() => {
      const canvas = document.querySelector(".inspector-waveform-canvas") as HTMLCanvasElement;
      const { data } = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height);
      let h = 2166136261;
      for (let i = 0; i < data.length; i++) h = Math.imul(h ^ data[i], 16777619) >>> 0;
      return `${canvas.width}x${canvas.height}:${h}`;
    });
  }

  /** O canvas do inspetor nasce vazio: so conta como onda depois de pintado. */
  async function inspetorPintado(page: Page): Promise<boolean> {
    return page.evaluate(() => {
      const canvas = document.querySelector(".inspector-waveform-canvas") as HTMLCanvasElement;
      const { data } = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;
      return false;
    });
  }

  async function selecionaEEspera(page: Page, titulo: string): Promise<string> {
    await page.getByTestId("library-row").filter({ hasText: titulo }).click();
    await expect.poll(() => inspetorPintado(page), { timeout: 10000 }).toBe(true);
    let anterior = "";
    await expect
      .poll(
        async () => {
          const atual = await pixelsDoInspetor(page);
          const igual = atual === anterior;
          anterior = atual;
          return igual;
        },
        { timeout: 10000, intervals: [300] }
      )
      .toBe(true);
    return anterior;
  }

  test("o inspetor mostra a onda da faixa selecionada, nao a da anterior", async ({ page, context }) => {
    // Referencia independente do historico de selecao: a primeira linha abre
    // auto-selecionada, entao uma referencia "Beta clicada depois" sofreria o
    // mesmo bug. Aqui TODA rota serve a onda da Beta; o que sobra de diferente
    // entre as faixas sao so os metadados (pico, duracao), que o render usa.
    const ref = await context.newPage();
    await abreBiblioteca(ref, ONDA_BETA);
    const pixelsBetaEsperados = await selecionaEEspera(ref, "Beta");
    await ref.close();

    await abreBiblioteca(page);
    const pixelsAlpha = await selecionaEEspera(page, "Alpha");
    expect(pixelsAlpha).not.toBe(pixelsBetaEsperados);

    await page.getByTestId("library-row").filter({ hasText: "Beta" }).click();
    await expect
      .poll(() => pixelsDoInspetor(page), { timeout: 10000, intervals: [300] })
      .toBe(pixelsBetaEsperados);
  });
});
