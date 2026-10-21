import { test, expect, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { ModelState } from "../src/api/types";

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

// computed style sempre devolve "rgb[a](r, g, b[, a])"; o JSON mistura hex
// e rgba(). Normaliza os dois lados para a forma canonica do browser.
function rgb(cor: string) {
  const v = cor.trim();
  const partes = v.startsWith("#")
    ? [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16))
    : v.match(/[\d.]+/g)!.map(Number);
  const [r, g, b, a] = partes;
  return a === undefined || a === 1
    ? `rgb(${r}, ${g}, ${b})`
    : `rgba(${r}, ${g}, ${b}, ${a})`;
}

async function estadoModelo(request: APIRequestContext): Promise<ModelState> {
  const health = await request.get("/api/health");
  const { token } = await health.json();
  const res = await request.get("/api/model/state", {
    headers: { "X-Auth-Token": token },
  });
  expect(res.ok()).toBe(true);
  return res.json();
}

test.describe("Fidelidade da aba Modelo", () => {
  let estado: ModelState;

  test.beforeEach(async ({ page, request }) => {
    estado = await estadoModelo(request);
    // Sem exemplos rotulados a aba mostra so o empty state -- nao ha o que
    // medir. Os numeros deste describe precisam do conteudo montado.
    test.skip(estado.n_examples === 0, "biblioteca sem exemplos rotulados");
    await page.goto("/");
    await page.locator(".app-tab", { hasText: "Modelo" }).click();
    await page.waitForSelector(".model-metrics-row", { timeout: 30000 });
  });

  test("botao retreinar usa o token de acao e o acento", async ({ page }) => {
    const botao = page.locator(".model-action-btn");
    const medidas = await botao.evaluate((el) => {
      const cs = getComputedStyle(el);
      return {
        altura: el.getBoundingClientRect().height,
        borda: cs.borderColor,
        fundo: cs.backgroundColor,
        fonte: cs.fontFamily,
        caixa: cs.textTransform,
      };
    });

    const px = (caminho: string) => parseFloat(token(caminho));
    expect(medidas.altura).toBe(px("size.control.action"));
    expect(medidas.borda).toBe(rgb(token("color.accent.base")));
    // contorno, nao preenchido: o fundo fica transparente
    expect(medidas.fundo).toBe("rgba(0, 0, 0, 0)");
    expect(medidas.fonte).toContain("JetBrains Mono");
    expect(medidas.caixa).toBe("uppercase");
  });

  test("cards e trilho de progresso seguem os tokens", async ({ page }) => {
    const medidas = await page.evaluate(() => {
      const card = document.querySelector(".metric-card");
      const trilho = document.querySelector(".model-progress-track");
      return {
        raioCard: card ? getComputedStyle(card).borderRadius : null,
        fundoCard: card ? getComputedStyle(card).backgroundColor : null,
        alturaTrilho: trilho ? trilho.getBoundingClientRect().height : null,
      };
    });

    const px = (caminho: string) => parseFloat(token(caminho));
    expect(medidas.raioCard).toBe(`${px("radius.control")}px`);
    expect(medidas.fundoCard).toBe(rgb(token("color.surface.panel-raised")));
    // O trilho de 3px vem do mockup e nao tem token dedicado -- fica
    // literal aqui ate o JSON ganhar um.
    expect(medidas.alturaTrilho).toBe(3);
  });

  test("severidade da matriz resolve para os tokens de classe", async ({
    page,
  }) => {
    test.skip(estado.confusion === null, "modelo ainda nao treinado");

    // metrics-row monta antes da matriz (ConfusionMatrix devolve null sem
    // dados); com a suite em paralelo um retreino concorrente pode trocar o
    // estado entre o fetch do beforeEach e o render.
    await page.waitForSelector(".confusion-cell", { timeout: 30000 });

    const cores = await page.evaluate(() => {
      const ler = (sel: string) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const cs = getComputedStyle(el);
        return { fundo: cs.backgroundColor, texto: cs.color, borda: cs.borderColor };
      };
      return {
        acerto: ler(".confusion-cell.severity-0"),
        leve: ler(".confusion-cell.severity-1"),
        fonteRotulo: (() => {
          const el = document.querySelector(".confusion-label.col");
          return el ? getComputedStyle(el).fontFamily : null;
        })(),
      };
    });

    expect(cores.leve?.fundo).toBe(rgb(token("color.classification.neutro.bg")));
    expect(cores.leve?.texto).toBe(rgb(token("color.classification.neutro.text")));
    expect(cores.acerto?.borda).toBe(rgb(token("color.border.default")));
    expect(cores.fonteRotulo).toContain("JetBrains Mono");
  });
});

test.describe("Fidelidade ao design system", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Espera a tela de verdade, nao o placeholder: o data-testid
    // "review-tab" tambem marca o estado de carregamento, e medir durante
    // ele devolve null para tudo que este teste confere. A classe
    // .review-header so existe com a fila montada.
    await page.waitForSelector(".review-header", { timeout: 30000 });
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
    // Capa 96 e play 40 sao valores do mockup (instrucao de layout): os
    // tokens size.art.review/size.control.transport-play pertencem ao Qt e
    // a web divergiu de proposito -- se um dia o token andar, esta medida
    // NAO deve andar junto.
    expect(medidas.capa).toBe(96);
    expect(medidas.cardClasse).toBe(px("size.control.class-card"));
    expect(medidas.play).toBe(40);
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

    // rgb() do computed style vs hex do JSON (helper no topo do arquivo)

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
