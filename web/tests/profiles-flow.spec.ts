import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Porta propria (a do decide-flow e 8799): os dois specs podem rodar em
// paralelo sem disputar a porta nem o data_dir.
const PORTA = 8798;
const BASE = `http://127.0.0.1:${PORTA}`;
const RAIZ_DO_REPO = path.resolve(process.cwd(), "..");

let backend: ChildProcess | null = null;
let raiz = "";
let token = "";

/**
 * E2E dos perfis contra um backend DESCARTAVEL (tests/e2e_backend.py): cria,
 * troca, renomeia, duplica e exclui pela UI e confere o config.toml gravado
 * no diretorio temporario. Nunca toca no config.toml nem no data_dir do app
 * (regra 9 do AGENTS.md); tudo some no afterAll.
 */
test.beforeAll(async ({ request }) => {
  test.setTimeout(120000);
  raiz = fs.mkdtempSync(path.join(os.tmpdir(), "tc-perfis-"));

  let saida = "";
  let saiu = false;
  backend = spawn(
    "uv",
    ["run", "python", "-m", "tests.e2e_backend", "--dir", raiz, "--port", String(PORTA)],
    { cwd: RAIZ_DO_REPO, detached: true, stdio: ["ignore", "ignore", "pipe"] }
  );
  backend.stderr?.on("data", (trecho) => (saida += String(trecho)));
  backend.on("exit", () => (saiu = true));

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

interface RawConfig {
  active_profile: string;
  profiles: Record<
    string,
    {
      name: string;
      folders: Record<string, string>;
      model: { retrain_every: number; min_examples: number };
      organization: { create: boolean; move: boolean; copy: boolean };
    }
  >;
}

/** O que esta GRAVADO no config.toml do tmp (GET /api/config le do disco). */
async function gravado(request: APIRequestContext): Promise<RawConfig> {
  const r = await request.get(`${BASE}/api/config?token=${token}`);
  expect(r.ok()).toBe(true);
  return (await r.json()).raw as RawConfig;
}

/** Confirma o dialogo ate ele fechar: o servidor responde 409 enquanto o scan
 * roda, o dialogo segue aberto com o motivo e Confirmar tenta de novo. */
async function confirmaAteFecharDialogo(page: Page) {
  const dialogo = page.getByTestId("confirm-dialog");
  await expect(async () => {
    if ((await dialogo.count()) > 0) {
      await page.getByTestId("confirm-dialog-confirm").click();
    }
    await expect(dialogo).toHaveCount(0, { timeout: 1500 });
  }).toPass({ timeout: 45000, intervals: [500, 1000] });
}

test("perfis: criar, trocar, renomear, duplicar, excluir e independencia", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  await page.goto(`${BASE}/`);
  await page.waitForSelector("[data-testid='review-tab']", { timeout: 30000 });
  await expect(page.locator(".scan-status-text")).toContainText("Scan concluído", {
    timeout: 60000,
  });

  await page.getByRole("button", { name: "Configuração" }).click();
  await expect(page.getByTestId("config-tab")).toBeVisible();
  const nomeAtivo = page.getByTestId("config-perfil-nome");
  const dropdown = page.getByTestId("profile-dropdown");
  await expect(dropdown).toContainText("Padrão");
  await expect(nomeAtivo).toHaveText("Padrão");

  // Ativar um perfil escaneia a pasta dele; criar/renomear/duplicar/excluir
  // respondem 409 enquanto o scan roda (o dialogo mostra o motivo e Confirmar
  // serve de "tentar de novo"). O header NAO serve de sinal: o scan segue
  // preenchendo peaks/capas sem emitir progresso e o texto ja diz "Scan
  // concluido". Entao as operacoes estruturais repetem como uma pessoa faria.
  const esperaScan = async () => {
    await expect(page.locator(".scan-status-text")).toContainText("Scan concluído", {
      timeout: 60000,
    });
  };
  const confirmaAteFechar = () => confirmaAteFecharDialogo(page);
  const trocaPara = async (nome: string) => {
    await dropdown.click();
    await page.getByTestId("profile-option").filter({ hasText: nome }).click();
    await expect(nomeAtivo).toHaveText(nome);
    await esperaScan();
  };
  const espera = async () => {
    await expect(page.getByText("Configuração salva.")).toBeVisible({ timeout: 15000 });
  };

  // --- Criar (copia as pastas do ativo; o novo vira o ativo) ---------------
  await page.getByTestId("profile-new").click();
  await expect(page.getByTestId("profile-copy-folders")).toBeChecked();
  await page.getByTestId("profile-name-input").fill("Set Trance");
  await page.getByTestId("confirm-dialog-confirm").click();
  await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
  await expect(nomeAtivo).toHaveText("Set Trance");
  await expect(page.getByTestId("config-inbox")).toHaveValue(path.join(raiz, "inbox"));
  await esperaScan();

  let cfg = await gravado(request);
  expect(cfg.active_profile).toBe("set-trance");
  expect(Object.keys(cfg.profiles)).toEqual(["default", "set-trance"]);
  expect(cfg.profiles["set-trance"].name).toBe("Set Trance");
  expect(cfg.profiles["set-trance"].folders.inbox).toBe(cfg.profiles.default.folders.inbox);

  // --- Independencia: edita o MODELO do perfil novo ------------------------
  await page.getByTestId("config-retrain_every").fill("25");
  await espera();
  cfg = await gravado(request);
  expect(cfg.profiles["set-trance"].model.retrain_every).toBe(25);
  expect(cfg.profiles.default.model.retrain_every).toBe(1000); // intocado

  // --- Trocar de volta: a troca PERSISTE (regressao do bug do switch) ------
  await trocaPara("Padrão");
  expect((await gravado(request)).active_profile).toBe("default");
  await expect(page.getByTestId("config-retrain_every")).toHaveValue("1000");
  await trocaPara("Set Trance");
  await expect(page.getByTestId("config-retrain_every")).toHaveValue("25");
  expect((await gravado(request)).active_profile).toBe("set-trance");

  // --- Pill da Revisao: mesmo estado global (agora ha 2 perfis) ------------
  await page.getByRole("button", { name: "Revisão" }).click();
  const pill = page.locator(".profile-bar .segment");
  await expect(pill).toHaveCount(2);
  await expect(pill.nth(1)).toHaveText("Set Trance");
  await expect(pill.nth(1)).toHaveClass(/active|selected/);
  await pill.nth(0).click();
  await expect.poll(async () => (await gravado(request)).active_profile).toBe("default");
  await page.getByRole("button", { name: "Configuração" }).click();
  await expect(nomeAtivo).toHaveText("Padrão");
  await esperaScan();

  // --- Renomear o Padrao (id continua default) -----------------------------
  await page.getByTestId("profile-edit").click();
  await page.getByTestId("profile-name-input").fill("Casa");
  await confirmaAteFechar();
  await expect(nomeAtivo).toHaveText("Casa");
  await expect(dropdown).toContainText("Casa");
  cfg = await gravado(request);
  expect(cfg.profiles.default.name).toBe("Casa");

  // --- Padrao nao pode ser excluido ---------------------------------------
  await page.getByTestId("profile-menu").click();
  await expect(page.getByTestId("profile-menu-delete")).toBeDisabled();
  await page.keyboard.press("Escape");

  // --- Duplicar (nao ativa a copia) ---------------------------------------
  await expect(async () => {
    await page.getByTestId("profile-menu").click();
    await page.getByTestId("profile-menu-duplicate").click();
    expect(Object.keys((await gravado(request)).profiles).length).toBe(3);
  }).toPass({ timeout: 45000, intervals: [1000] });
  await expect(nomeAtivo).toHaveText("Casa");
  cfg = await gravado(request);
  expect(cfg.active_profile).toBe("default");
  expect(cfg.profiles["casa-copia"].name).toBe("Casa (cópia)");
  expect(cfg.profiles["casa-copia"].model.retrain_every).toBe(1000);

  // --- Excluir o ativo troca para o proximo --------------------------------
  await trocaPara("Set Trance");
  await page.getByTestId("profile-menu").click();
  await page.getByTestId("profile-menu-delete").click();
  await expect(page.getByTestId("confirm-dialog")).toContainText("passa a ser");
  await confirmaAteFechar();
  await expect(nomeAtivo).toHaveText("Casa (cópia)");
  cfg = await gravado(request);
  expect(Object.keys(cfg.profiles)).toEqual(["default", "casa-copia"]);
  expect(cfg.active_profile).toBe("casa-copia");
});

test("perfil criado sem copiar pastas nasce incompleto e nao quebra o scan", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  await page.goto(`${BASE}/`);
  await page.getByRole("button", { name: "Configuração" }).click();
  await expect(page.getByTestId("config-tab")).toBeVisible();

  await page.getByTestId("profile-new").click();
  await page.getByTestId("profile-name-input").fill("Vazio");
  await page.getByTestId("profile-copy-folders").uncheck();
  await confirmaAteFecharDialogo(page);
  await expect(page.getByTestId("config-perfil-nome")).toHaveText("Vazio");
  await expect(page.locator(".scan-status-text")).toContainText("Scan concluído", {
    timeout: 60000,
  });

  // Pastas vazias com o erro de validacao do servidor, sem apply.
  await expect(page.getByTestId("config-inbox")).toHaveValue("");
  await expect(page.getByText("Escolha a pasta de entrada.")).toBeVisible();
  const cfg = await gravado(request);
  expect(cfg.profiles.vazio.folders).toEqual({});

  // O scan que a criacao disparou termina sem derrubar nada (o perfil
  // incompleto e ignorado) e a fila dele e vazia, nao um erro.
  await expect(async () => {
    const r = await request.get(`${BASE}/api/review/state?token=${token}`);
    expect(r.ok()).toBe(true);
    const estado = await r.json();
    expect(estado.active_profile).toBe("Vazio");
    expect(estado.remaining).toBe(0);
  }).toPass({ timeout: 30000 });
  const falhas = await request.get(`${BASE}/api/model/state?token=${token}`);
  expect(falhas.ok()).toBe(true);

  // Volta para o Padrao para nao deixar o estado do teste anterior preso.
  await page.getByTestId("profile-dropdown").click();
  await page.getByTestId("profile-option").filter({ hasText: /Casa|Padrão/ }).first().click();
});
