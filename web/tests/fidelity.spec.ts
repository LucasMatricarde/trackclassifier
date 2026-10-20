import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * Invariantes de fidelidade do mockup/design system, medidos no DOM e
 * comparados com design/design-tokens.json (a fonte da verdade).
 *
 * Por que nao diff de pixel contra o mockup: o mockup tem outra track,
 * outra capa e o chrome de janela do macOS -- o diff mediria conteudo, nao
 * layout. O baseline do screenshot.spec.ts cobre regressao visual; aqui
 * ficam os numeros que o mockup fixa (altura do header, capa, cards,
 * acento, fontes carregadas), lidos do JSON em vez de repetidos.
 */
const TOKENS = JSON.parse(
  fs.readFileSync(
    path.resolve(process.cwd(), "../design/design-tokens.json"),
    "utf8"
  )
);

// deno-lint-ignore no-explicit-any
function token(caminho: string): any {
  return caminho
    .split(".")
    .reduce((no: Record<string, unknown>, chave: string) => no[chave] as Record<string, unknown>, TOKENS)
    .value;
}

test.describe("Fidelidade ao design system", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  });

  test("alturas e tamanhos batem com os tokens", async ({ page }) => {
    const medidas = await page.evaluate(() => {
      const altura = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? el.getBoundingClientRect().height : null;
      };
      const largura = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? el.getBoundingClientRect().width : null;
      };
      return {
        header: altura(".app-header"),
        capa: largura(".review-header .cover-art"),
        cardClasse: altura(".class-action-card"),
        play: altura(".transport-play"),
        capaFila: largura(".queue-card .cover-art"),
      };
    });

    // tokens de size guardam a unidade ("62px"); a medicao e numero
    const px = (caminho: string) => parseFloat(token(caminho));

    expect(medidas.header).toBe(px("size.control.header"));
    expect(medidas.capa).toBe(px("size.art.review"));
    expect(medidas.cardClasse).toBe(px("size.control.class-card"));
    expect(medidas.play).toBe(px("size.control.transport-play"));
    expect(medidas.capaFila).toBe(px("size.art.queue"));
  });

  test("acento e superficies resolvem para os valores do JSON", async ({
    page,
  }) => {
    const cores = await page.evaluate(() => {
      const estilo = getComputedStyle(document.documentElement);
      const ler = (nome: string) => estilo.getPropertyValue(nome).trim();
      const play = document.querySelector(".transport-play");
      return {
        acento: ler("--color-accent-base"),
        fundo: ler("--color-bg"),
        play: play ? getComputedStyle(play).backgroundColor : null,
        cardAtual: (() => {
          const card = document.querySelector(".queue-card-current");
          return card ? getComputedStyle(card).borderColor : null;
        })(),
      };
    });

    // rgb() do computed style vs hex do JSON
    const rgb = (hex: string) => {
      const h = hex.replace("#", "");
      return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(h.slice(4, 6), 16)})`;
    };

    expect(cores.acento.toLowerCase()).toBe(token("color.accent.base").toLowerCase());
    expect(cores.fundo.toLowerCase()).toBe(token("color.surface.0").toLowerCase());
    expect(cores.play).toBe(rgb(token("color.accent.base")));
    expect(cores.cardAtual).toBe(rgb(token("color.accent.base")));
  });

  test("fontes do design system estao carregadas", async ({ page }) => {
    const carregadas = await page.evaluate(async () => {
      await document.fonts.ready;
      return {
        sans: document.fonts.check('12px "Space Grotesk"'),
        mono: document.fonts.check('12px "JetBrains Mono"'),
        body: getComputedStyle(document.body).fontFamily,
      };
    });

    expect(carregadas.sans).toBe(true);
    expect(carregadas.mono).toBe(true);
    expect(carregadas.body).toContain("Space Grotesk");
  });
});
