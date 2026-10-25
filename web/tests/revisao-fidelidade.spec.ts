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

  test("classificacao compacta: titulo no topo do painel, fila no rodape", async ({ page }) => {
    await abre(page, estado(TRACK_ALPHA, [TRACK_BETA]));
    const m = await page.evaluate(() => {
      const r = (s: string) => document.querySelector(s)!.getBoundingClientRect();
      const painel = r(".decision-bar");
      return {
        topoAteTitulo: r(".decision-heading").top - painel.top,
        // o fundo do painel acompanha a coluna mais alta (cards ou atalhos)
        conteudoAteFundo:
          painel.bottom - Math.max(r(".decision-cards").bottom, r(".decision-shortcuts").bottom),
        filaFundo: r(".queue-strip").bottom,
        abaFundo: r(".review-tab").bottom,
      };
    });
    // padding do painel (space-4 = 8px) mais a borda: nada de vazio acima
    expect(m.topoAteTitulo).toBeLessThanOrEqual(12);
    expect(m.conteudoAteFundo).toBeLessThanOrEqual(16);
    expect(Math.abs(m.filaFundo - m.abaFundo)).toBeLessThanOrEqual(1);
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
