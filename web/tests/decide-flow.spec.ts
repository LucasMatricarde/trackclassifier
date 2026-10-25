import { test, expect } from "@playwright/test";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Porta propria: este spec nao usa TC_WEB_URL nem o backend do app.
const PORTA = 8799;
const BASE = `http://127.0.0.1:${PORTA}`;
const RAIZ_DO_REPO = path.resolve(process.cwd(), "..");
// O sufixo _0.500 e a energia que o ExtratorFalso le do nome do arquivo.
const NOME = "TESTFLOW_0.500.mp3";

let backend: ChildProcess | null = null;
let raiz = "";
let testFile = "";
let movedFile = "";

/**
 * E2E do fluxo de revisao contra um backend DESCARTAVEL.
 *
 * Antes este spec usava o backend e a inbox reais: cada rodada deixava
 * linhas TESTFLOW no analyses.parquet, no sha1.json, nos peaks e nas capas do
 * app, e a track entrava na fila do app em uso. Agora tests/e2e_backend.py
 * sobe a API real sobre pastas e data_dir temporarios (ExtratorFalso, modelo
 * ja treinado) e tudo some no afterAll.
 *
 * Gera uma track sintetica (sine) com sha1 inedito -- copiar uma track ja
 * analisada nao serviria: o cache a reconhece e ela nao entra na fila. A
 * posicao na fila e por confianca crescente, entao navegamos com "s" ate
 * achar a track em vez de contar posicoes.
 */
test.beforeAll(async ({ request }) => {
  test.setTimeout(120000);
  raiz = fs.mkdtempSync(path.join(os.tmpdir(), "tc-e2e-"));
  testFile = path.join(raiz, "inbox", NOME);
  movedFile = path.join(raiz, "neutral", NOME);

  let saida = "";
  let saiu = false;
  // detached: o processo vira lider de grupo e o afterAll mata o `uv run` e o
  // python juntos, sem deixar a porta presa para a proxima rodada.
  backend = spawn(
    "uv",
    ["run", "python", "-m", "tests.e2e_backend", "--dir", raiz, "--port", String(PORTA)],
    { cwd: RAIZ_DO_REPO, detached: true, stdio: ["ignore", "ignore", "pipe"] }
  );
  backend.stderr?.on("data", (trecho) => (saida += String(trecho)));
  backend.on("exit", () => (saiu = true));

  let token = "";
  await expect
    .poll(
      async () => {
        if (saiu) throw new Error(`backend de teste saiu cedo:\n${saida}`);
        try {
          const resposta = await request.get(`${BASE}/api/health`);
          if (!resposta.ok()) return false;
          token = (await resposta.json()).token;
          return true;
        } catch {
          return false;
        }
      },
      { timeout: 90000, intervals: [500] }
    )
    .toBe(true);

  execFileSync("ffmpeg", [
    "-y",
    "-loglevel", "error",
    "-f", "lavfi",
    "-i", "sine=frequency=440:duration=180",
    "-c:a", "libmp3lame",
    "-q:a", "5",
    testFile,
  ]);

  const scan = await request.post(`${BASE}/api/scan?token=${token}`);
  expect(scan.ok()).toBe(true);
});

test.afterAll(() => {
  if (backend?.pid) {
    try {
      process.kill(-backend.pid, "SIGTERM");
    } catch {
      // ja encerrou
    }
  }
  if (raiz) fs.rmSync(raiz, { recursive: true, force: true });
});

test("fluxo completo: play, skip, decide, undo", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${BASE}/`);
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

  // 3. Decide neutra (tecla 2) -> arquivo vai para a pasta neutral
  await page.keyboard.press("2");
  await expect.poll(() => fs.existsSync(movedFile), { timeout: 10000 }).toBe(true);
  expect(fs.existsSync(testFile)).toBe(false);

  // 4. Undo (Backspace) -> arquivo volta pra inbox
  await page.keyboard.press("Backspace");
  await expect.poll(() => fs.existsSync(testFile), { timeout: 10000 }).toBe(true);
  expect(fs.existsSync(movedFile)).toBe(false);
});
