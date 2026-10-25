import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { stubAbaModelo } from "./fixtures/modelo";

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

// rgb() do computed style vs hex do JSON
function rgb(hex: string): string {
  const h = hex.replace("#", "");
  return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(h.slice(4, 6), 16)})`;
}

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

    expect(cores.acento.toLowerCase()).toBe(token("color.accent.base").toLowerCase());
    expect(cores.fundo.toLowerCase()).toBe(token("color.surface.0").toLowerCase());
    expect(cores.play).toBe(rgb(token("color.accent.base")));
    expect(cores.cardAtual).toBe(rgb(token("color.accent.base")));
  });

  test("fontes do design system estao carregadas", async ({ page }) => {
    const carregadas = await page.evaluate(async () => {
      await document.fonts.ready;
      return {
        sans: document.fonts.check('12px "Inter"'),
        mono: document.fonts.check('12px "JetBrains Mono"'),
        body: getComputedStyle(document.body).fontFamily,
      };
    });

    expect(carregadas.sans).toBe(true);
    expect(carregadas.mono).toBe(true);
    expect(carregadas.body).toContain("Inter");
  });
});

/**
 * Aba Modelo: mesma ideia, rodando sobre o estado fixo da fixture -- os
 * numeros que o design fixa (paineis, tipografia, intensidade da matriz,
 * vocabulario de botao) medidos no DOM contra o JSON.
 */
test.describe("Fidelidade da aba Modelo", () => {
  test.beforeEach(async ({ page }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    // A fixture entrega o estado por WS no mesmo macrotask do connect:
    // quando o primeiro card existe, o estado inteiro chegou.
    await page.waitForSelector("[data-testid='metric-exemplos']", {
      timeout: 10000,
    });
  });

  test("paineis usam o trio surface.panel / border.panel / radius.panel", async ({
    page,
  }) => {
    const painel = await page.evaluate(() => {
      const estiloDe = (sel: string, selFallback?: string) => {
        const el = document.querySelector(sel) ?? (selFallback ? document.querySelector(selFallback) : null);
        return el ? getComputedStyle(el) : null;
      };
      const card = estiloDe(".metric-card");
      const painelSecao = estiloDe(".model-panel");
      const botao = estiloDe(".btn-solid");
      return {
        bgCard: card?.backgroundColor,
        bordaCard: card?.borderColor,
        raioCard: card?.borderTopLeftRadius,
        bgPainel: painelSecao?.backgroundColor,
        bordaPainel: painelSecao?.borderColor,
        raioPainel: painelSecao?.borderTopLeftRadius,
        bgBotao: botao?.backgroundColor,
      };
    });

    expect(painel.bgCard).toBe(rgb(token("color.surface.panel")));
    expect(painel.bordaCard).toBe("rgba(164, 188, 224, 0.14)");
    expect(painel.raioCard).toBe(token("radius.panel"));
    expect(painel.bgPainel).toBe(rgb(token("color.surface.panel")));
    expect(painel.bordaPainel).toBe("rgba(164, 188, 224, 0.14)");
    expect(painel.raioPainel).toBe(token("radius.panel"));
    // Botao solido e acao primaria: accent cru (o hover usa o token
    // accent.hover, mas o repouso e o base).
    expect(painel.bgBotao).toBe(rgb(token("color.accent.base")));
  });

  test("cabecalho e metrica seguem a tipografia do design", async ({
    page,
  }) => {
    const medidas = await page.evaluate(() => {
      const estiloDe = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el) : null;
      };
      const titulo = estiloDe(".model-title");
      const valor = estiloDe(".metric-card-value");
      const rotulo = estiloDe(".metric-card-label");
      return {
        titulo: titulo
          ? { size: titulo.fontSize, weight: titulo.fontWeight }
          : null,
        valor: valor
          ? { size: valor.fontSize, family: valor.fontFamily, weight: valor.fontWeight }
          : null,
        rotulo: rotulo
          ? { size: rotulo.fontSize, transform: rotulo.textTransform }
          : null,
      };
    });

    expect(medidas.titulo?.size).toBe(token("font.size.headline"));
    expect(medidas.titulo?.weight).toBe("600");
    // Valor do KPI: 30px medido no mockup (~25px de altura de maiuscula),
    // acima do font.size.display (22) de proposito.
    expect(medidas.valor?.size).toBe("30px");
    expect(medidas.valor?.family).toContain("JetBrains Mono");
    expect(medidas.valor?.weight).toBe("600");
    // Rotulo do card no mockup e sans 13px em caixa normal, nao micro-label.
    expect(medidas.rotulo?.size).toBe(token("font.size.body"));
    expect(medidas.rotulo?.transform).toBe("none");
  });

  test("bases da matriz sao os tokens amostrados do mockup", async ({ page }) => {
    // A maior contagem da matriz pinta o token cru (fixture: 13 na
    // diagonal); a cor fora da diagonal segue a distancia, nao a coluna.
    const bg = await page.evaluate(() =>
      [...document.querySelectorAll(".confusion-cell")].map((el) => getComputedStyle(el).backgroundColor)
    );
    // color-mix resolve para color(srgb r g b) em fracao 0..1.
    const canais = (bg[4].match(/[\d.]+/g) ?? []).map(Number).slice(-3);
    const alvo = token("color.model.cm-diag").replace("#", "");
    [0, 2, 4].forEach((k, c) => {
      expect(canais[c]).toBeCloseTo(parseInt(alvo.slice(k, k + 2), 16) / 255, 2);
    });
    // (0,2) e (2,0)... na fixture (0,2)=1 e extremo, (1,2)=1 e adjacente:
    // mesma contagem, distancias diferentes, cores diferentes.
    expect(bg[2]).not.toBe(bg[5]);
  });

  test("intensidade da matriz sombreia a severidade pela contagem", async ({
    page,
  }) => {
    // Com color-mix o computed style devolve rgb resolvido -- comparar
    // com o token hex deixa de ser possivel. O contrato medido: celula
    // vazia fica na superficie, celulas com contagens iguais compartilham
    // cor e mais exemplos escurece dentro da severidade.
    const celulas = await page.evaluate(() => {
      const bgDe = (i: number, j: number) => {
        const el = document.querySelectorAll(".confusion-cell")[i * 3 + j];
        return el ? getComputedStyle(el).backgroundColor : null;
      };
      // fixture: [[2,0,1],[0,13,1],[0,1,12]]
      return {
        zero: bgDe(0, 1),
        acerto2: bgDe(0, 0),
        acerto13: bgDe(1, 1),
        erroGrave12: bgDe(2, 2),
        erroLeve12: bgDe(2, 1),
      };
    });
    const fundo = rgb(token("color.surface.2"));

    expect(celulas.zero).toBe(fundo);
    // Mais exemplos na diagonal: cor mais forte (nao e a superficie).
    expect(celulas.acerto13).not.toBe(celulas.acerto2);
    expect(celulas.acerto13).not.toBe(fundo);
    // Mesma contagem (12), severidades diferentes: hue diferente,
    // pura cor-mix aplicada em ambos.
    expect(celulas.erroGrave12).not.toBe(celulas.erroLeve12);
    expect(celulas.erroGrave12).not.toBe(fundo);
  });

  test("nota e amostras da legenda ficam no micromapa", async ({ page }) => {
    const legenda = await page.evaluate(() => {
      const el = document.querySelector(".confusion-legend-swatch");
      const nota = document.querySelector(".confusion-legend-note");
      const swatchW = el ? getComputedStyle(el).width : null;
      return {
        swatchW,
        notaSize: nota ? getComputedStyle(nota).fontSize : null,
        notaColor: nota ? getComputedStyle(nota).color : null,
      };
    });

    expect(legenda.swatchW).toBe("10px");
    expect(legenda.notaSize).toBe(token("font.size.small"));
    expect(legenda.notaColor).toBe(rgb(token("color.text.secondary")));
  });

  test("vocabulario de botao: sans, caixa alta, wide no painel", async ({
    page,
  }) => {
    const botao = await page.evaluate(() => {
      const el = document.querySelector(".btn-solid");
      if (!el) return null;
      const s = getComputedStyle(el);
      return { family: s.fontFamily, transform: s.textTransform, tracking: s.letterSpacing };
    });

    expect(botao?.family).toContain("Space Grotesk");
    expect(botao?.transform).toBe("uppercase");
    // letter-spacing computa em px: 0.06em de 12px.
    expect(botao?.tracking).toBe("0.72px");
  });

  test("cores das sparklines usam os tokens por card", async ({ page }) => {
    const cores = await page.evaluate(() => {
      const ler = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el).color : null;
      };
      return {
        exemplos: ler(".metric-card-spark-exemplos"),
        acc: ler(".metric-card-spark-acc"),
        mae: ler(".metric-card-spark-mae"),
        f1: ler(".metric-card-spark-f1"),
      };
    });

    // A sparkline herda currentColor da cor do card (tokens color.model.kpi-*).
    expect(cores.exemplos).toBe(rgb(token("color.model.kpi-exemplos")));
    expect(cores.acc).toBe(rgb(token("color.model.kpi-acc")));
    expect(cores.mae).toBe(rgb(token("color.model.kpi-erro")));
    expect(cores.f1).toBe(rgb(token("color.model.kpi-f1")));
  });
});
