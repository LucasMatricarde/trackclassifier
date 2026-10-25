import { test, expect } from "@playwright/test";
import {
  ESTADO_ALPHA,
  TRACK_ALPHA,
  TRACK_BETA,
  estado,
  mockRevisaoCompleta,
} from "./review-fixtures";

/**
 * Revisao de fidelidade da tela Revisao contra o mockup. Fila mockada
 * (regra 8 do AGENTS.md) e janela do shell Electron (1512x1037): em 1280x720
 * o painel de classificacao ja nasce cortado, de proposito (alturas fixas).
 */
test.use({ viewport: { width: 1512, height: 1037 } });

async function abre(page: import("@playwright/test").Page, fila = ESTADO_ALPHA) {
  await mockRevisaoCompleta(page, fila);
  await page.goto("/");
  await page.waitForSelector(".review-header", { timeout: 30000 });
}

test.describe("Revisao: fidelidade ao mockup", () => {
  test("um perfil so nao mostra a pill DEFAULT; dois mostram o seletor", async ({ page }) => {
    await abre(page);
    await expect(page.locator(".profile-bar")).toHaveCount(0);
    await expect(page.getByText("default", { exact: false })).toHaveCount(0);

    const dois = { ...ESTADO_ALPHA, profiles: ["default", "festa"] };
    await page.unroute("**/api/review/state*");
    await page.route("**/api/review/state*", (route) => route.fulfill({ json: dois }));
    await page.reload();
    await page.waitForSelector(".review-header", { timeout: 30000 });
    await expect(page.locator(".profile-bar .segment")).toHaveCount(2);
  });

  test("sem tonalidade mostra so o traco, sem rotulo CAMELOT", async ({ page }) => {
    await abre(page);
    await expect(page.locator(".review-header .key-chip")).toHaveText("—");
    await expect(page.locator(".review-header .key-chip-trigger")).toHaveCount(0);
    await expect(page.locator(".review-header")).not.toContainText(/camelot/i);
  });

  test("rotulos em sentence case sans; valores seguem mono", async ({ page }) => {
    await abre(page);
    const lidos = await page.evaluate(() =>
      [...document.querySelectorAll(".label-sentence")].map((el) => {
        const s = getComputedStyle(el);
        return { texto: el.textContent, caixa: s.textTransform, familia: s.fontFamily };
      })
    );
    expect(lidos.map((l) => l.texto)).toEqual([
      "Previsão do modelo",
      "Confiança",
      "Progresso da revisão",
      "Ações",
      "Atalhos do teclado",
    ]);
    for (const l of lidos) {
      expect(l.caixa).toBe("none");
      expect(l.familia).toContain("Inter");
    }
    // Nenhum rotulo da Revisao sobrou em .micro-label (mono, caixa alta).
    await expect(page.locator(".review-tab .micro-label")).toHaveCount(0);
    const valor = await page.evaluate(
      () => getComputedStyle(document.querySelector(".guess-confidence-value")!).fontFamily
    );
    expect(valor).not.toContain("Inter");
  });

  test("player: icone de volume, loop e 1x entre o tempo e as Acoes", async ({ page }) => {
    await abre(page);
    await expect(page.locator("[data-testid='player-volume-icon'] svg")).toHaveCount(1);
    await expect(page.locator(".player-bar")).not.toContainText("Volume");
    await expect(page.locator("[data-testid='player-speed']")).toHaveText("1x");

    const x = await page.evaluate(() => {
      const esq = (s: string) => document.querySelector(s)!.getBoundingClientRect().left;
      return {
        tempo: esq(".time-display"),
        loop: esq("[data-testid='player-loop']"),
        chip: esq("[data-testid='player-speed']"),
        acoes: esq(".player-bar .label-sentence"),
      };
    });
    expect(x.tempo).toBeLessThan(x.loop);
    expect(x.loop).toBeLessThan(x.chip);
    expect(x.chip).toBeLessThan(x.acoes);
  });

  test("loop e velocidade agem no <audio>", async ({ page }) => {
    // O <audio> nasce com `new Audio()` e nunca entra no DOM: guarda a
    // instancia para ler o que o player gravou nela.
    await page.addInitScript(() => {
      const Original = window.Audio;
      (window as unknown as { Audio: unknown }).Audio = function (...args: unknown[]) {
        const el = new (Original as unknown as new (...a: unknown[]) => HTMLAudioElement)(...args);
        (window as unknown as { __audio: HTMLAudioElement }).__audio = el;
        return el;
      };
    });
    await abre(page);
    const audio = (campo: "loop" | "playbackRate") =>
      page.evaluate(
        (c) => (window as unknown as { __audio: HTMLAudioElement }).__audio[c],
        campo
      );

    expect(await audio("loop")).toBe(false);
    await page.locator("[data-testid='player-loop']").click();
    expect(await audio("loop")).toBe(true);
    await expect(page.locator("[data-testid='player-loop']")).toHaveAttribute("aria-pressed", "true");
    await page.locator("[data-testid='player-loop']").click();
    expect(await audio("loop")).toBe(false);

    const chip = page.locator("[data-testid='player-speed']");
    for (const [texto, taxa] of [["1.25x", 1.25], ["1.5x", 1.5], ["0.75x", 0.75], ["1x", 1]] as const) {
      await chip.click();
      await expect(chip).toHaveText(texto);
      expect(await audio("playbackRate")).toBe(taxa);
    }
  });

  test("Aprovar em bloco segue no player (feature, fora do mockup)", async ({ page }) => {
    await abre(page);
    await expect(page.getByRole("button", { name: /Aprovar em bloco/ })).toBeVisible();
  });

  test("a onda absorve a folga; classificacao compacta; sem vazio entre regioes", async ({ page }) => {
    await abre(page, estado(TRACK_ALPHA, [TRACK_BETA]));
    const m = await page.evaluate(() => {
      const r = (s: string) => document.querySelector(s)!.getBoundingClientRect();
      const cards = [...document.querySelectorAll(".class-action-card")].map(
        (el) => el.getBoundingClientRect().height
      );
      const painel = r(".decision-bar");
      const aba = r(".review-tab");
      return {
        cards,
        secao: painel.height,
        topoAteTitulo: r(".decision-heading").top - painel.top,
        canvasPrincipal: r(".waveform-main canvas").height,
        painelOnda: r(".wave-panel").height,
        gaps: {
          headerOnda: r(".wave-panel").top - r(".review-header").bottom,
          ondaPlayer: r(".player-bar").top - r(".wave-panel").bottom,
          playerClassificacao: painel.top - r(".player-bar").bottom,
          classificacaoFila: r(".queue-strip").top - painel.bottom,
        },
        filaFundo: r(".queue-strip").bottom,
        abaFundo: aba.bottom,
      };
    });
    expect(m.cards).toHaveLength(3);
    expect(new Set(m.cards).size).toBe(1);
    expect(m.cards[0]).toBeGreaterThanOrEqual(90);
    expect(m.cards[0]).toBeLessThanOrEqual(100);
    // secao hug: ~205 no alvo
    expect(m.secao).toBeGreaterThanOrEqual(185);
    expect(m.secao).toBeLessThanOrEqual(215);
    // titulo colado no topo: padding do painel (8) mais a borda
    expect(m.topoAteTitulo).toBeLessThanOrEqual(12);
    // a onda cresceu alem dos 240 do contrato antigo
    expect(m.canvasPrincipal).toBeGreaterThan(240);
    expect(m.gaps).toEqual({
      headerOnda: 16,
      ondaPlayer: 16,
      playerClassificacao: 16,
      classificacaoFila: 16,
    });
    expect(Math.abs(m.filaFundo - m.abaFundo)).toBeLessThanOrEqual(1);
  });

  test("irmaos diretos do container da pagina, na ordem do mockup", async ({ page }) => {
    await abre(page);
    const filhos = await page.evaluate(() =>
      [...document.querySelector(".review-tab")!.children].map((el) => el.className)
    );
    expect(filhos).toEqual([
      "review-header",
      "wave-panel",
      "player-bar",
      "decision-bar",
      "queue-strip",
    ]);
  });

  test("volume: fill accent da origem ate o knob", async ({ page }) => {
    await abre(page);
    const v = await page.evaluate(() => {
      const fill = document.querySelector(".player-bar .volume-fill")!;
      const marker = document.querySelector(".player-bar .volume-marker")!.getBoundingClientRect();
      const rail = document.querySelector(".player-bar .volume-rail")!.getBoundingClientRect();
      const f = fill.getBoundingClientRect();
      return {
        cor: getComputedStyle(fill).backgroundColor,
        trilho: getComputedStyle(document.querySelector(".player-bar .volume-track")!).backgroundColor,
        fillLargura: f.width,
        knobX: marker.left + marker.width / 2 - rail.left,
      };
    });
    // --color-accent-base (#6979FB)
    expect(v.cor).toBe("rgb(105, 121, 251)");
    expect(v.cor).not.toBe(v.trilho);
    expect(Math.abs(v.fillLargura - v.knobX)).toBeLessThanOrEqual(2);
  });

  test("capa da Revisao mede 132 e o header cabe", async ({ page }) => {
    await abre(page);
    const m = await page.evaluate(() => {
      const c = document.querySelector(".review-header .cover-art")!.getBoundingClientRect();
      return { w: c.width, h: c.height };
    });
    expect(m).toEqual({ w: 132, h: 132 });
  });
});
