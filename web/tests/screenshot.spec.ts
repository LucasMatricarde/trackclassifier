import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { stubAbaModelo, modeloFixo } from "./fixtures/modelo";
import {
  estado,
  fakeWebSocket,
  TRACK_ALPHA,
  TRACK_BETA,
} from "./review-fixtures";
import type { ReviewState, TrackRow } from "../src/api/types";

/**
 * Screenshot da aba Revisao no tamanho do mockup (1512x1037), para comparar
 * lado a lado com design/mockup/TrackClassifier Music Review Dashboard.png.
 * Roda: e barato (sem scan).
 */
test.use({ viewport: { width: 1512, height: 1037 } });

async function abreReview(page: import("@playwright/test").Page) {
  test.setTimeout(60000);
  await page.goto("/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  // Buckets chegam por WS depois do states_changed; sem isso a onda sai
  // monocromatica (energy_curve) e o screenshot vira outro desenho.
  await page.waitForTimeout(8000);
  await page.evaluate(() => document.fonts.ready);
}

test("screenshot da revisao", async ({ page }) => {
  await abreReview(page);
  await page.screenshot({ path: "screenshot-review.png" });
});

/**
 * PNG 1x1 transparente: capa/thumb stubadas nunca mudam de pixel e o
 * placeholder do app pode resmungar com a rota ausente.
 */
const PNG_1PX = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64"
);

/**
 * Codifica um float16 (metade IEEE 754) no padrao de 16 bits.
 * A fixture so tem valores modestos; subnormal e infinito nao acontecem.
 */
function f16(valor: number): number {
  if (valor === 0) return 0;
  const mag = Math.abs(valor);
  let expoente = Math.floor(Math.log2(mag));
  let fracao = Math.round((mag / Math.pow(2, expoente) - 1) * 1024);
  if (fracao === 1024) {
    fracao = 0;
    expoente += 1;
  }
  const bits =
    ((valor < 0 ? 1 : 0) << 15) | ((expoente + 15) << 10) | fracao;
  return bits;
}

/**
 * .npy float16 2D (linhas = bandas) que o parser do WaveformCanvas le:
 * o formato real do backend e esse (o descmath vem de waveform_render).
 */
function npyFloat16(linhas: number[][]): Buffer {
  const rows = linhas.length;
  const cols = linhas[0].length;
  const header = `{'descr': '<f2', 'fortran_order': False, 'shape': (${rows}, ${cols}), }`;
  // numpy: magic 6 bytes + versao 2 bytes + header_len u16 LE, e o par
  // `10 + headerLen` multiplo de 64 (header terminado em \n).
  const alvo = Math.ceil((header.length + 1 + 10) / 64) * 64;
  const headerLen = alvo - 10;
  const headerPreenchido = header + " ".repeat(headerLen - header.length - 1) + "\n";

  const out = Buffer.alloc(10 + headerLen + rows * cols * 2);
  Buffer.from([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 0x01, 0x00]).copy(out, 0);
  out.writeUInt16LE(headerLen, 8);
  Buffer.from(headerPreenchido, "ascii").copy(out, 10);
  const dados = 10 + headerLen;
  let pos = dados;
  for (const linha of linhas) {
    for (const valor of linha) {
      out.writeUInt16LE(f16(valor), pos);
      pos += 2;
    }
  }
  return out;
}

/** WAV PCM mono/silencioso de 8 kHz: o player abre e fica em pause. */
function wavSilencioso(segundos: number): Buffer {
  const sr = 8000;
  const n = segundos * sr;
  const buf = Buffer.alloc(44 + n * 2);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + n * 2, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sr, 24);
  buf.writeUInt32LE(sr * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(n * 2, 40);
  return buf; // amostras zeradas: silencio
}

/**
 * Onda fixa padrao (na curva do TRACK_ALPHA): 64 buckets — cada LINHA do
 * npy e (grave, medio, agudo) do bucket, o shape (N, 3) que o backend
 * real produz (o parser do canvas exige esse layout intercalado).
 * As tres bandas sao a mesma curva com brilho decrescente, que e onde as
 * cores das waveband.* aparecem no baseline.
 */
function ondaFixa(): number[][] {
  const base = [0.1, 0.4, 0.2, 0.8, 0.5, 0.3, 0.6, 0.2];
  // 2048 buckets: mais que as ~700 barras de 1512px (BAR_WIDTH=2), para o
  // resample (maximo por segmento) ser o mesmo caminho do backend real --
  // com menos buckets o clamp do fim repete o ultimo bucket e a metade
  // direita do canvas nasce achatada.
  return Array.from({ length: 2048 }, (_, i) => {
    const v = base[i % 8];
    return [v, v * 0.7, v * 0.45];
  });
}

/**
 * Regressao visual com tolerancia de 2% dos pixels.
 *
 * O baseline da REVISAO nao roda no backend: as rotas que a tela toca
 * (fila, biblioteca, modelo, peaks, audio, capa, thumbs) sao stubadas e o
 * WebSocket e falso — ideias de "acervo local" nao existem aqui: nenhuma
 * regiao da tela muda com o disco. O caste antigo deixou de existir
 * (comparava a fila real e quebrava a cada biblioteca nova).
 */
async function stubRevisaoVisual(page: Page, reviewState: ReviewState) {
  await page.route("**/api/health*", (route) =>
    route.fulfill({ json: { ok: true, token: "stub", configured: true } })
  );
  await page.route("**/api/review/state*", (route) =>
    route.fulfill({ json: reviewState })
  );
  await page.route("**/api/library/state*", (route) =>
    route.fulfill({
      json: {
        rows: [],
        class_counts: [3, 14, 13],
        total: 30,
        genres: [],
        keys: [],
      },
    })
  );
  await page.route("**/api/model/state*", (route) =>
    route.fulfill({ json: modeloFixo })
  );
  await page.route("**/api/peaks/**", (route) =>
    route.fulfill({ body: npyFloat16(ondaFixa()) })
  );
  await page.route("**/api/audio/**", (route) =>
    route.fulfill({ body: wavSilencioso(1), contentType: "audio/wav" })
  );
  await page.route("**/api/cover/**", (route) =>
    route.fulfill({ body: PNG_1PX, contentType: "image/png" })
  );
  await page.route("**/api/thumb/**", (route) =>
    route.fulfill({ body: PNG_1PX, contentType: "image/png" })
  );
  await fakeWebSocket(page);
}

test("baseline visual da revisao", async ({ page }) => {
  // A track do baseline tem peaks_path: e ele que liga o render de bandas
  // (o stub de /api/peaks responde o npy fixo); sem isso o canvas cai no
  // fallback mono e o spectral design nao entra na regressao.
  const trackComPeaks: TrackRow = { ...TRACK_ALPHA, peaks_path: "stub" };
  const fila: ReviewState = estado(trackComPeaks, [TRACK_BETA]);
  await stubRevisaoVisual(page, fila);
  await page.goto("/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 10000 });
  // Espera os peaks estarem pintados (bandas em toda a largura), nao um
  // turno fixo: screenshot cedo captura o mono e o baseline vira outra
  // coisa que lembranca.
  await page.waitForFunction(
    () => {
      const c = document.querySelectorAll("canvas")[0] as HTMLCanvasElement | null;
      if (!c) return false;
      const ctx = c.getContext("2d");
      if (!ctx) return false;
      for (const px of [0.6, 0.75, 0.9, 0.98]) {
        let achou = false;
        for (let py = 0.05; py < 0.95; py += 0.05) {
          const d = ctx.getImageData(
            Math.floor(px * c.width),
            Math.floor(py * c.height),
            1,
            1
          ).data;
          // Banda pintada: pixel opaco sobreescrevendo o fundo do canvas,
          // que e quase preto (qualquer canal > 30 ja e pinta).
          if (d[3] === 255 && (d[0] > 30 || d[1] > 30 || d[2] > 30)) {
            achou = true;
            break;
          }
        }
        if (!achou) return false;
      }
      return true;
    },
    { timeout: 8000, polling: 120 }
  );
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
  await expect(page).toHaveScreenshot("review-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
  });
});

/**
 * Baseline visual da aba Modelo.
 *
 * Roda sobre o estado fixo da fixture (stub de health/state/WS em
 * tests/fixtures/modelo.ts): nenhuma regiao da tela depende do acervo
 * local, entao nao entra regiao mascarada. O header tambem vem da fixture
 * (states_changed sintetico), por isso a contagem do scan e estavel.
 */

async function abreModelo(page: import("@playwright/test").Page) {
  test.setTimeout(60000);
  await stubAbaModelo(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Modelo" }).click();
  await page.waitForSelector(".confusion-cell", { timeout: 10000 });
  await page.evaluate(() => document.fonts.ready);
}

test("screenshot do modelo", async ({ page }) => {
  await abreModelo(page);
  await page.screenshot({ path: "screenshot-modelo.png" });
});

test("baseline visual do modelo", async ({ page }) => {
  await abreModelo(page);
  await expect(page).toHaveScreenshot("model-baseline.png", {
    maxDiffPixelRatio: 0.02,
    animations: "disabled",
  });
});
