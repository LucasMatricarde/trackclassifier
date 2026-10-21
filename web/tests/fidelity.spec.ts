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

/**
 * Aba Modelo: mesma ideia, rodando sobre o estado fixo da fixture -- os
 * numeros que o design fixa (paineis, severidades da matriz, vocabulario
 * de botao e micro-label) medidos no DOM contra o JSON.
 */
test.describe("Fidelidade da aba Modelo", () => {
  test.beforeEach(async ({ page }) => {
    await stubAbaModelo(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Modelo" }).click();
    // A fixture entrega o estado por WS no mesmo macrotask do connect:
    // quando a matriz existe, o estado inteiro chegou.
    await page.waitForSelector(".confusion-cell", { timeout: 10000 });
  });

  test("paineis usam o trio surface.panel / border.panel / radius.panel", async ({
    page,
  }) => {
    const painel = await page.evaluate(() => {
      const card = document.querySelector(".metric-card");
      const estilo = card ? getComputedStyle(card) : null;
      const btn = document.querySelector(".model-action-btn");
      return {
        bg: estilo ? estilo.backgroundColor : null,
        borda: estilo ? estilo.borderColor : null,
        raio: estilo ? estilo.borderTopLeftRadius : null,
        alturaBotao: btn ? btn.getBoundingClientRect().height : null,
      };
    });

    expect(painel.bg).toBe(rgb(token("color.surface.panel")));
    expect(painel.borda).toBe("rgba(164, 188, 224, 0.14)");
    expect(painel.raio).toBe(token("radius.panel"));
    expect(painel.alturaBotao).toBe(parseFloat(token("size.control.action")));
  });

  test("cabecalho e metrica seguem a tipografia fechada no QSS", async ({
    page,
  }) => {
    const medidas = await page.evaluate(() => {
      const estiloDe = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el) : null;
      };
      const titulo = estiloDe(".model-title");
      const valor = estiloDe(".metric-value");
      const rotulo = estiloDe(".metric-label");
      return {
        titulo: titulo
          ? { size: titulo.fontSize, weight: titulo.fontWeight }
          : null,
        valor: valor
          ? { size: valor.fontSize, weight: valor.fontWeight }
          : null,
        rotulo: rotulo
          ? { size: rotulo.fontSize, family: rotulo.fontFamily }
          : null,
      };
    });

    expect(medidas.titulo?.size).toBe(token("font.size.headline"));
    expect(medidas.titulo?.weight).toBe("600");
    // DashboardValue: 17px/500 nao tem token -- e medida do QSS.
    expect(medidas.valor?.size).toBe("17px");
    expect(medidas.valor?.weight).toBe("500");
    // O rotulo do card e sans sentence case: "Exemplos rotulados" no
    // desktop nao passa por estiliza_label.
    expect(medidas.rotulo?.size).toBe(token("font.size.caption"));
    expect(medidas.rotulo?.family).toContain("Space Grotesk");
  });

  test("severidades da matriz resolvem para os valores do JSON", async ({
    page,
  }) => {
    const cores = await page.evaluate(() => {
      const estiloDe = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el) : null;
      };
      const acerto = estiloDe(".confusion-cell.severity-0");
      // :not(.zero): celula zerada devolve text.disabled por cima da cor
      // de severidade (o fundo e que carrega a severidade). O fixture tem
      // severidade-1 zerada antes da nao zerada na ordem do DOM.
      const leve = estiloDe(".confusion-cell.severity-1:not(.zero)");
      const grave = estiloDe(".confusion-cell.severity-2:not(.zero)");
      const zero = estiloDe(".confusion-cell.zero");
      return {
        acertoBg: acerto?.backgroundColor,
        acertoBorda: acerto?.borderColor,
        leveBg: leve?.backgroundColor,
        leveTexto: leve?.color,
        graveTexto: grave?.color,
        zeroTexto: zero?.color,
      };
    });

    expect(cores.acertoBg).toBe(rgb(token("color.surface.2")));
    expect(cores.acertoBorda).toBe("rgba(255, 255, 255, 0.1)");
    expect(cores.leveBg).toBe(rgb(token("color.classification.neutro.bg")));
    expect(cores.leveTexto).toBe(rgb(token("color.classification.neutro.text")));
    expect(cores.graveTexto).toBe(rgb(token("color.state.danger")));
    expect(cores.zeroTexto).toBe(rgb(token("color.text.disabled")));
  });

  test("vocabulario de botao: mono, micro, caixa alta, widest", async ({
    page,
  }) => {
    const botao = await page.evaluate(() => {
      const el = document.querySelector(".model-action-btn");
      if (!el) return null;
      const s = getComputedStyle(el);
      return {
        family: s.fontFamily,
        size: s.fontSize,
        transform: s.textTransform,
        tracking: s.letterSpacing,
      };
    });

    expect(botao?.family).toContain("JetBrains Mono");
    expect(botao?.size).toBe(token("font.size.micro"));
    expect(botao?.transform).toBe("uppercase");
    // letter-spacing computa em px: 0.09em de 10px.
    expect(botao?.tracking).toBe("0.9px");
  });

  test("micro-labels de secao em mono/muted/caixa alta", async ({ page }) => {
    const rotulos = await page.evaluate(() => {
      const estiloDe = (sel: string) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el) : null;
      };
      const matriz = estiloDe(".confusion-title");
      const contador = estiloDe(".model-progress-label");
      const aviso = estiloDe(".model-action-warning");
      return {
        matriz: matriz
          ? {
              size: matriz.fontSize,
              color: matriz.color,
              transform: matriz.textTransform,
            }
          : null,
        contador: contador ? { size: contador.fontSize, color: contador.color } : null,
        aviso: aviso ? { color: aviso.color } : null,
      };
    });

    const micro = token("font.size.micro");
    const muted = rgb(token("color.text.muted"));
    expect(rotulos.matriz?.size).toBe(micro);
    expect(rotulos.matriz?.color).toBe(muted);
    expect(rotulos.matriz?.transform).toBe("uppercase");
    expect(rotulos.contador?.size).toBe(micro);
    expect(rotulos.contador?.color).toBe(muted);
    // Aviso low-confidence e neutro (MicroLabel), nao cor de classe: o
    // estado discreto por escolha da spec.
    expect(rotulos.aviso?.color).toBe(muted);
  });

  test("legenda da matriz usa amostra de 10px", async ({ page }) => {
    const amostra = await page.evaluate(() => {
      const el = document.querySelector(".confusion-legend-swatch");
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return { w: rect.width, h: rect.height };
    });

    expect(amostra?.w).toBe(10);
    expect(amostra?.h).toBe(10);
  });
});
