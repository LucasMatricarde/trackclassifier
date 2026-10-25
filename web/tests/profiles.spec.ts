import { test, expect, type Page } from "@playwright/test";
import { perfilFixo, stubConfig, type StubConfigOpts } from "./fixtures/config";

/**
 * Perfis na Configuracao. Parte visual (fase A): evidencia por valor
 * COMPUTADO, nao por CSS escrito (regra 1 de docs/ui/fidelidade.md). Parte de fluxo
 * (fase B, front): dialogos e chamadas contra o servidor de mentira da
 * fixture -- o backend real e coberto por tests/test_serve.py e pelo
 * profiles-flow.spec.ts.
 */

const MUITOS = [
  perfilFixo("default", "Padrão"),
  perfilFixo("set-trance", "Set Trance"),
  perfilFixo("set-techno", "Set Techno"),
  perfilFixo("producoes", "Produções"),
  perfilFixo("festival-2024", "Festival 2024"),
  perfilFixo("p6", "Perfil 6"),
  perfilFixo("p7", "Perfil 7"),
  perfilFixo("p8", "Perfil 8"),
  perfilFixo("p9", "Perfil 9"),
  perfilFixo("p10", "Perfil 10"),
];

async function abreConfiguracao(page: Page, opts: StubConfigOpts = {}) {
  const handle = await stubConfig(page, opts);
  await page.setViewportSize({ width: 1512, height: 982 });
  await page.goto("/");
  await page.getByRole("button", { name: "Configuração" }).click();
  await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
  await expect(page.getByTestId("profile-switcher")).toBeVisible();
  return handle;
}

test.describe("Perfis — visual (fase A)", () => {
  test("so a aba Configuracao tem o seletor de perfil no header", async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await expect(page.getByTestId("profile-switcher")).toHaveCount(0);
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("profile-switcher")).toBeVisible();
    await page.getByRole("button", { name: "Biblioteca" }).click();
    await expect(page.getByTestId("profile-switcher")).toHaveCount(0);
  });

  test("header cabe numa linha a 1512px, com o rotulo Perfil", async ({ page }) => {
    await abreConfiguracao(page, { perfis: MUITOS });
    const m = await page.evaluate(() => {
      const caixa = (sel: string) =>
        document.querySelector(sel)!.getBoundingClientRect();
      const header = document.querySelector(".app-header") as HTMLElement;
      return {
        altura: caixa(".app-header").height,
        scrollW: header.scrollWidth,
        clientW: header.clientWidth,
        tabs: caixa(".app-tabs"),
        perfil: caixa(".app-perfil"),
        scan: caixa(".app-scan"),
        btnNovo: caixa("[data-testid=profile-new]"),
        dropdown: caixa("[data-testid=profile-dropdown]"),
      };
    });
    expect(m.altura).toBe(62);
    expect(m.scrollW).toBeLessThanOrEqual(m.clientW);
    // Sem sobreposicao nem quebra: perfil entre as abas e o scan, tudo na
    // mesma faixa vertical do header.
    expect(m.perfil.left).toBeGreaterThanOrEqual(m.tabs.right);
    expect(m.perfil.right).toBeLessThanOrEqual(m.scan.left);
    expect(m.dropdown.top).toBeGreaterThanOrEqual(0);
    expect(m.btnNovo.bottom).toBeLessThanOrEqual(62);
    expect(Math.abs(m.dropdown.height - m.btnNovo.height)).toBeLessThanOrEqual(1);
    await expect(page.locator(".app-perfil-rotulo")).toHaveText("Perfil");
  });

  test("lista aberta: max-height 280px com scroll e check no accent do ativo", async ({
    page,
  }) => {
    await abreConfiguracao(page, { perfis: MUITOS });
    await page.getByTestId("profile-dropdown").click();
    const lista = page.getByTestId("profile-list");
    await expect(lista).toBeVisible();

    const c = await lista.evaluate((el) => {
      const cs = getComputedStyle(el);
      return {
        maxHeight: cs.maxHeight,
        overflowY: cs.overflowY,
        altura: el.clientHeight,
        conteudo: el.scrollHeight,
      };
    });
    expect(c.maxHeight).toBe("280px");
    expect(c.overflowY).toBe("auto");
    expect(c.altura).toBeLessThanOrEqual(280);
    expect(c.conteudo).toBeGreaterThan(c.altura); // 10 perfis rolam

    await expect(page.getByTestId("profile-option")).toHaveCount(10);
    const ativo = page.locator("[data-testid=profile-option][aria-selected=true]");
    await expect(ativo).toHaveCount(1);
    await expect(ativo).toContainText("Padrão");

    const cores = await page.evaluate(() => {
      const check = document.querySelector(".perfil-item-check") as HTMLElement;
      const sonda = document.createElement("i");
      sonda.style.color = "var(--color-accent-base)";
      document.body.appendChild(sonda);
      const accent = getComputedStyle(sonda).color;
      sonda.remove();
      return { check: getComputedStyle(check).color, accent };
    });
    expect(cores.check).toBe(cores.accent);
    // So o ativo tem check.
    await expect(page.locator(".perfil-item-check")).toHaveCount(1);
  });

  test("lista fecha com Esc e com clique fora", async ({ page }) => {
    await abreConfiguracao(page, { perfis: MUITOS });
    await page.getByTestId("profile-dropdown").click();
    await expect(page.getByTestId("profile-list")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("profile-list")).toHaveCount(0);

    await page.getByTestId("profile-dropdown").click();
    await page.getByTestId("config-tab").click({ position: { x: 5, y: 400 } });
    await expect(page.getByTestId("profile-list")).toHaveCount(0);
  });

  test("overlay da lista cobre o conteudo: pai relativo e dentro da viewport", async ({
    page,
  }) => {
    await abreConfiguracao(page, { perfis: MUITOS });
    await page.getByTestId("profile-dropdown").click();
    const r = await page.evaluate(() => {
      const painel = document.querySelector(".popover-panel") as HTMLElement;
      const raiz = painel.parentElement as HTMLElement;
      const caixa = painel.getBoundingClientRect();
      const topo = document.elementFromPoint(caixa.left + 20, caixa.top + 20);
      return {
        posRaiz: getComputedStyle(raiz).position,
        posPainel: getComputedStyle(painel).position,
        dentro: caixa.right <= window.innerWidth && caixa.bottom <= window.innerHeight,
        cobre: !!topo && painel.contains(topo),
      };
    });
    expect(r.posRaiz).toBe("relative");
    expect(r.posPainel).toBe("absolute");
    expect(r.dentro).toBe(true);
    expect(r.cobre).toBe(true);
  });

  test("card de info com o texto novo", async ({ page }) => {
    await abreConfiguracao(page);
    await expect(page.getByTestId("config-info-card")).toContainText(
      "Cada perfil possui suas próprias pastas, organização e preferências. " +
        "Troque de perfil ou crie um novo para diferentes fluxos de trabalho."
    );
    // Medido no render: 2 linhas (2 x 15px) e card de 65px, como o mockup.
    const m = await page.evaluate(() => {
      const p = document.querySelector(".config-info-card p") as HTMLElement;
      const card = document.querySelector(".config-info-card") as HTMLElement;
      return {
        fonte: getComputedStyle(p).fontSize,
        linhas: Math.round(p.getBoundingClientRect().height / parseFloat(getComputedStyle(p).lineHeight)),
        card: card.getBoundingClientRect().height,
      };
    });
    expect(m.fonte).toBe("10px");
    expect(m.linhas).toBe(2);
    expect(m.card).toBe(65);
  });

  test("sidebar: bloco Perfil ativo e o primeiro grupo, com ··· e Editar", async ({
    page,
  }) => {
    await abreConfiguracao(page, {
      perfis: [perfilFixo("default", "Padrão"), perfilFixo("set-trance", "Set Trance")],
      ativo: "set-trance",
    });
    const grupos = page.locator(".config-sidebar > section");
    await expect(grupos.first()).toHaveAttribute("data-testid", "config-resumo-perfil");
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Set Trance");
    await expect(page.locator(".config-perfil-titulo")).toHaveText("Perfil ativo");
    await expect(page.getByTestId("profile-menu")).toBeVisible();
    await expect(page.getByTestId("profile-edit")).toHaveText("Editar");

    // Hairline: o primeiro grupo nao tem borda, o seguinte (Pastas) tem.
    const bordas = await page.evaluate(() => {
      const [perfil, pastas] = Array.from(
        document.querySelectorAll(".config-sidebar > section")
      ) as HTMLElement[];
      return {
        perfil: getComputedStyle(perfil).borderTopWidth,
        pastas: getComputedStyle(pastas).borderTopWidth,
      };
    });
    expect(bordas.perfil).toBe("0px");
    expect(bordas.pastas).toBe("1px");
  });
});

test.describe("Perfis — dialogos e fluxos (front)", () => {
  test("criar: nome vazio/repetido bloqueia, valido cria copiando pastas e ativa", async ({
    page,
  }) => {
    const h = await abreConfiguracao(page);
    await page.getByTestId("profile-new").click();
    const confirmar = page.getByTestId("confirm-dialog-confirm");
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();
    await expect(page.getByTestId("profile-copy-folders")).toBeChecked();
    await expect(confirmar).toBeDisabled();
    // Foco no campo de nome, nao no Cancelar.
    await expect(page.getByTestId("profile-name-input")).toBeFocused();

    await page.getByTestId("profile-name-input").fill("  ");
    await expect(page.getByTestId("profile-name-error")).toContainText("Informe um nome");
    await page.getByTestId("profile-name-input").fill("padrão");
    await expect(page.getByTestId("profile-name-error")).toContainText("Já existe");
    await expect(confirmar).toBeDisabled();

    await page.getByTestId("profile-name-input").fill("Set Trance");
    await expect(confirmar).toBeEnabled();
    await confirmar.click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);

    const post = h.perfilChamadas.find((c) => c.metodo === "POST");
    expect(post?.corpo).toEqual({ name: "Set Trance", copyFolders: true });
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Set Trance");
    await expect(page.locator(".app-perfil-nome")).toHaveText("Set Trance");
  });

  test("criar sem copiar pastas envia copyFolders false", async ({ page }) => {
    const h = await abreConfiguracao(page);
    await page.getByTestId("profile-new").click();
    await page.getByTestId("profile-name-input").fill("Vazio");
    await page.getByTestId("profile-copy-folders").uncheck();
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
    expect(h.perfilChamadas.find((c) => c.metodo === "POST")?.corpo).toEqual({
      name: "Vazio",
      copyFolders: false,
    });
  });

  test("criar com fila pendente avisa no dialogo", async ({ page }) => {
    await abreConfiguracao(page, { pendentes: 7 });
    await page.getByTestId("profile-new").click();
    await expect(page.getByTestId("profile-pending-warning")).toContainText(
      "7 faixas pendentes em Padrão"
    );
  });

  test("Editar renomeia; nome repetido bloqueia", async ({ page }) => {
    const h = await abreConfiguracao(page, {
      perfis: [perfilFixo("default", "Padrão"), perfilFixo("festa", "Festa")],
      ativo: "festa",
    });
    await page.getByTestId("profile-edit").click();
    const campo = page.getByTestId("profile-name-input");
    await expect(campo).toHaveValue("Festa");
    await campo.fill("Padrão");
    await expect(page.getByTestId("profile-name-error")).toContainText("Já existe");
    await campo.fill("Festa 2024");
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
    expect(h.perfilChamadas.find((c) => c.metodo === "PATCH")?.corpo).toEqual({
      name: "Festa 2024",
    });
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Festa 2024");
  });

  test("menu ···: Renomear / Duplicar / Excluir; Excluir desabilitado no Padrão", async ({
    page,
  }) => {
    const h = await abreConfiguracao(page);
    await page.getByTestId("profile-menu").click();
    await expect(page.getByRole("menuitem")).toHaveText(["Renomear", "Duplicar", "Excluir"]);
    await expect(page.getByTestId("profile-menu-delete")).toBeDisabled();

    await page.getByTestId("profile-menu-duplicate").click();
    await expect.poll(() => h.perfilChamadas.some((c) => c.caminho.endsWith("/duplicate"))).toBe(true);
    // Duplicar nao ativa a copia.
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Padrão");
    await page.getByTestId("profile-dropdown").click();
    await expect(page.getByTestId("profile-option")).toHaveCount(2);
  });

  test("excluir o ativo pede confirmacao e passa para o proximo", async ({ page }) => {
    const h = await abreConfiguracao(page, {
      perfis: [
        perfilFixo("default", "Padrão"),
        perfilFixo("a", "Alfa"),
        perfilFixo("b", "Beta"),
      ],
      ativo: "a",
    });
    await page.getByTestId("profile-menu").click();
    await page.getByTestId("profile-menu-delete").click();
    await expect(page.getByTestId("confirm-dialog")).toContainText("passa a ser Padrão");
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
    expect(h.perfilChamadas.some((c) => c.metodo === "DELETE" && c.caminho.endsWith("/a"))).toBe(true);
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Beta");
  });

  test("trocar sem fila pendente troca direto", async ({ page }) => {
    const h = await abreConfiguracao(page, {
      perfis: [perfilFixo("default", "Padrão"), perfilFixo("a", "Alfa")],
    });
    await page.getByTestId("profile-dropdown").click();
    await page.getByTestId("profile-option").filter({ hasText: "Alfa" }).click();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Alfa");
    expect(h.perfilChamadas.find((c) => c.caminho.endsWith("/switch"))?.corpo).toEqual({
      id: "a",
    });
  });

  test("trocar com fila pendente exige confirmacao; cancelar nao troca", async ({
    page,
  }) => {
    const h = await abreConfiguracao(page, {
      perfis: [perfilFixo("default", "Padrão"), perfilFixo("a", "Alfa")],
      pendentes: 3,
    });
    await page.getByTestId("profile-dropdown").click();
    await page.getByTestId("profile-option").filter({ hasText: "Alfa" }).click();
    await expect(page.getByTestId("confirm-dialog")).toContainText("3 faixas pendentes");
    expect(h.perfilChamadas.some((c) => c.caminho.endsWith("/switch"))).toBe(false);

    await page.getByTestId("confirm-dialog-cancel").click();
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Padrão");
    expect(h.perfilChamadas.some((c) => c.caminho.endsWith("/switch"))).toBe(false);

    await page.getByTestId("profile-dropdown").click();
    await page.getByTestId("profile-option").filter({ hasText: "Alfa" }).click();
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("config-perfil-nome")).toHaveText("Alfa");
  });

  test("falha do servidor fica no dialogo, que segue aberto", async ({ page }) => {
    await abreConfiguracao(page);
    await page.route(/\/api\/profiles$/, (route) =>
      route.request().method() === "POST"
        ? route.fulfill({ status: 409, json: { detail: "Scan em andamento." } })
        : route.fallback()
    );
    await page.getByTestId("profile-new").click();
    await page.getByTestId("profile-name-input").fill("Qualquer");
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("confirm-dialog-error")).toHaveText("Scan em andamento.");
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  });
});
