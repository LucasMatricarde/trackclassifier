import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";

const INBOX = "/Users/lucasmatricarde/Music/Tracks";
const NOME = "TESTFLOW - Spike E2E.mp3";
const TEST_FILE = `${INBOX}/${NOME}`;
const NEUTRAL_DIR = "/Users/lucasmatricarde/Music/Tracks/Trik Trik";
const MOVED_FILE = `${NEUTRAL_DIR}/${NOME}`;

/**
 * E2E do fluxo de revisao contra o backend real.
 *
 * Gera uma track sintetica (sine) para ter sha1 inedito -- copiar uma track
 * ja analisada nao serviria: o cache a reconhece e ela nao entra na fila.
 * A posicao na fila e por confianca crescente, entao navegamos com "s" ate
 * achar a track em vez de contar posicoes.
 */
test.beforeAll(async ({ request }) => {
  execFileSync("ffmpeg", [
    "-y",
    "-f", "lavfi",
    "-i", "sine=frequency=440:duration=180",
    "-c:a", "libmp3lame",
    "-q:a", "5",
    TEST_FILE,
  ]);

  const health = await request.get("http://127.0.0.1:8765/api/health");
  const { token } = await health.json();
  const scan = await request.post(
    `http://127.0.0.1:8765/api/scan?token=${token}`
  );
  expect(scan.ok()).toBe(true);
});

test.afterAll(() => {
  for (const caminho of [TEST_FILE, MOVED_FILE]) {
    if (fs.existsSync(caminho)) fs.unlinkSync(caminho);
  }
});

test("fluxo completo: play, skip, decide, undo", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto("/");
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });

  // O scan do beforeAll roda assincrono: quando termina, o backend faz
  // broadcast de states_changed e o player reseta para a posicao inicial
  // (pico). Interagir antes disso perde o play -- espera o scan concluir.
  await expect(page.locator(".scan-status-text")).toContainText(
    "Scan concluído",
    { timeout: 60000 }
  );

  // 1. Play avanca o tempo
  const time = page.locator(".time-display");
  const antes = await time.textContent();
  await page.keyboard.press("Space");
  // Espera ativa em vez de timeout fixo: o display tem granularidade de
  // segundos, entao 1.5s podem cair no mesmo segundo e falhar o teste.
  await expect
    .poll(async () => time.textContent(), { timeout: 10000 })
    .not.toBe(antes);
  await page.keyboard.press("Space"); // pausa

  // 2. Skip ate a track de teste (fila ordenada por confianca)
  const titulo = page.locator(".review-title");
  for (let i = 0; i < 10; i++) {
    if ((await titulo.textContent())?.includes("TESTFLOW")) break;
    await page.keyboard.press("s");
    await page.waitForTimeout(200);
  }
  await expect(titulo).toContainText("TESTFLOW");

  // 3. Decide neutra (tecla 2) -> arquivo vai para Trik Trik
  await page.keyboard.press("2");
  await expect.poll(() => fs.existsSync(MOVED_FILE), { timeout: 10000 }).toBe(true);
  expect(fs.existsSync(TEST_FILE)).toBe(false);

  // 4. Undo (Backspace) -> arquivo volta pra inbox
  await page.keyboard.press("Backspace");
  await expect.poll(() => fs.existsSync(TEST_FILE), { timeout: 10000 }).toBe(true);
  expect(fs.existsSync(MOVED_FILE)).toBe(false);
});
