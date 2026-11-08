import { test, expect } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Porta propria (8798 e do profiles-flow, 8799 do decide-flow): os specs de
// fluxo podem rodar em paralelo sem disputar porta nem data_dir. Duas worktrees
// ao mesmo tempo: TC_E2E_PORT_SCAN=<outra> em uma delas.
const PORTA = Number(process.env.TC_E2E_PORT_SCAN ?? 8797);
const BASE = `http://127.0.0.1:${PORTA}`;
const RAIZ_DO_REPO = path.resolve(process.cwd(), "..");
// Folga sobre a subida medida (~70 s com a maquina carregada).
const SUBIDA_MS = 180000;

let backend: ChildProcess | null = null;
let raiz = "";
let portao = "";
let token = "";

/**
 * E2E do status de scan contra um backend DESCARTAVEL (tests/e2e_backend.py
 * --segura-scan): o header mostra "Processando…" enquanto a apresentacao roda,
 * e as operacoes de perfil respondem 409 exatamente nesse intervalo -- o header
 * e o 409 acabam no mesmo instante. Quem decide quanto dura a fase e o teste,
 * por um arquivo-sinal (portao), nao um sleep: sob carga o PATCH podia chegar
 * depois da janela fixa e voltar 200. Nunca toca no config.toml nem no data_dir
 * do app (regra 9 do AGENTS.md); tudo some no afterAll.
 */
test.beforeAll(async ({ request }) => {
  test.setTimeout(SUBIDA_MS + 60000);
  raiz = fs.mkdtempSync(path.join(os.tmpdir(), "tc-scan-status-"));
  portao = path.join(raiz, "segura-scan");

  // Algo ja respondendo na porta e outro backend (outro run, outra worktree): o
  // poll abaixo acharia que o nosso subiu e o teste falaria com o errado.
  const ocupada = await request.get(`${BASE}/api/health`).then(
    () => true,
    () => false
  );
  if (ocupada) {
    throw new Error(`porta ${PORTA} ocupada; rode com TC_E2E_PORT_SCAN=<outra porta>`);
  }

  let saida = "";
  let saiu = false;
  backend = spawn(
    "uv",
    [
      "run", "python", "-m", "tests.e2e_backend",
      "--dir", raiz, "--port", String(PORTA), "--segura-scan", portao,
    ],
    { cwd: RAIZ_DO_REPO, detached: true, stdio: ["ignore", "ignore", "pipe"] }
  );
  backend.stderr?.on("data", (trecho) => (saida += String(trecho)));
  backend.on("exit", () => (saiu = true));

  try {
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
        { timeout: SUBIDA_MS, intervals: [500] }
      )
      .toBe(true);
  } catch (erro) {
    throw new Error(
      `backend de teste nao respondeu em ${SUBIDA_MS / 1000}s na porta ${PORTA}:\n${saida}\n${erro}`
    );
  }
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

test("header mostra Processando… enquanto o scan segura o 409 de perfil", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const status = page.locator(".scan-status-text");
  const botao = page.locator(".btn-scan");
  const renomeia = (name: string) =>
    request.patch(`${BASE}/api/profiles/default?token=${token}`, { data: { name } });

  await page.goto(`${BASE}/`);
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  // O scan de abertura roda sem portao; espera ele acabar para o proximo ser o
  // do clique.
  await expect(status).toContainText("Scan concluído", { timeout: 60000 });
  await expect(botao).toBeEnabled();

  // Fecha o portao antes do clique: a fase "processando" so acaba quando o
  // teste o abrir, quanto tempo a maquina carregada levar.
  fs.writeFileSync(portao, "");
  await botao.click();
  await expect(status).toContainText("Processando…", { timeout: 15000 });
  await expect(status).not.toContainText("Scan concluído");
  await expect(botao).toBeDisabled();

  // Mesmo instante do header: renomear perfil e 409 enquanto ele diz Processando….
  const durante = await renomeia("Casa");
  expect(durante.status()).toBe(409);

  fs.rmSync(portao, { force: true });
  await expect(status).toContainText("Scan concluído", { timeout: 60000 });
  await expect(botao).toBeEnabled();

  // E passa de primeira assim que o header diz concluido, sem retry.
  const depois = await renomeia("Casa");
  expect(depois.status()).toBe(200);
});
