import { test, expect } from "@playwright/test";
import { stubConfig, configRawFixo, type ConfigRaw } from "./fixtures/config";

test.describe("Configuração", () => {
  test.beforeEach(async ({ page }) => {
    await stubConfig(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
  });

  test("carrega os caminhos e valores atuais", async ({ page }) => {
    await expect(page.getByTestId("config-inbox")).not.toHaveValue("");
    await expect(page.getByTestId("config-up")).not.toHaveValue("");
    await expect(page.getByTestId("config-neutral")).not.toHaveValue("");
    await expect(page.getByTestId("config-down")).not.toHaveValue("");
    await expect(page.getByTestId("config-data_dir")).not.toHaveValue("");
    await expect(page.getByTestId("config-retrain_every")).toHaveValue("10");
    await expect(page.getByTestId("config-min_examples")).toHaveValue("50");
    await expect(
      page.getByRole("button", { name: "Configuração" })
    ).toHaveAttribute("aria-current", "page");
  });

  test("auto-save: edita e aplica sozinho, sem botao Salvar", async ({
    page,
  }) => {
    // O mockup nao desenha Salvar: o apply sai do auto-save.
    await expect(page.getByTestId("config-save")).toHaveCount(0);

    const aplicadas: ConfigRaw[] = [];
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-data_dir").fill("/dados/novo");
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });
    expect(aplicadas.length).toBeGreaterThanOrEqual(1);
    expect(aplicadas.at(-1)?.paths?.data_dir).toBe("/dados/novo");
  });

  test("pasta de entrada vazia mostra erro e nao aplica", async ({ page }) => {
    const aplicadas: ConfigRaw[] = [];
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      await route.fulfill({ json: { ok: true } });
    });

    const inbox = page.getByTestId("config-inbox");
    await inbox.fill("");
    await expect(page.getByText("Escolha a pasta de entrada.")).toBeVisible();
    await page.waitForTimeout(1500);
    expect(aplicadas).toHaveLength(0);

    // Volta com um valor valido DIFERENTE: igual ao original nao teria o
    // que salvar (rascunho == salvo). O erro some e o auto-save aplica.
    await inbox.fill("/musicas/outra-entrada");
    await expect(page.getByText("Escolha a pasta de entrada.")).toHaveCount(0);
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });
    expect(aplicadas.length).toBeGreaterThanOrEqual(1);
    expect(aplicadas.at(-1)?.folders?.inbox).toBe("/musicas/outra-entrada");
  });

  test("secao 1: pill de novas, badge de tracks e linhas de destino", async ({
    page,
  }) => {
    // Stats do stub: 6 novas; destinos 286 + 186 + 71 = 543 tracks.
    await expect(page.getByTestId("config-pill-novas")).toHaveText("6 NOVAS");
    await expect(page.getByTestId("config-pill-tracks")).toHaveText(
      "543 TRACKS"
    );

    const linhas = page.getByTestId("config-destino-row");
    await expect(linhas).toHaveCount(3);
    await expect(linhas.nth(0)).toContainText("-1");
    await expect(linhas.nth(0)).toContainText("Energia baixa");
    await expect(linhas.nth(1)).toContainText("neutra");
    await expect(linhas.nth(1)).toContainText("Energia equilibrada");
    await expect(linhas.nth(2)).toContainText("+1");
    await expect(linhas.nth(2)).toContainText("Energia alta");

    // Hairline entre entrada e destinos; acoes de escolher por campo.
    await expect(page.getByTestId("config-hairline")).toBeVisible();
    await expect(page.getByTestId("config-escolher-inbox")).toBeVisible();
    await expect(page.getByTestId("config-icone-up")).toBeVisible();
    await expect(page.getByTestId("config-escolher-down")).toBeVisible();
  });

  test("stats indisponivel: pills somem e a tela continua funcional", async ({
    page,
  }) => {
    await page.route("**/api/config/stats", (route) =>
      route.fulfill({ status: 500, json: { detail: "erro" } })
    );
    await page.reload();
    // O reload reseta a aba ativa: volta para a Configuracao antes de medir.
    await page.getByRole("button", { name: "Configuração" }).click();
    await expect(page.getByTestId("config-tab")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("config-pill-novas")).toHaveCount(0);
    await expect(page.getByTestId("config-pill-tracks")).toHaveCount(0);
    await expect(page.getByTestId("config-inbox")).not.toHaveValue("");
  });

  test("secao 2: os tres toggles sao reais e fazem round-trip", async ({ page }) => {
    // Stub de apply que TAMBEM atualiza o raw servido pelo GET: e o que o
    // servidor real faz e o que para o ciclo de auto-save (sem a atualizacao
    // o rascunho nunca iguala o salvo e o apply re-dispara a cada 800ms).
    const aplicadas: ConfigRaw[] = [];
    let atual: ConfigRaw = JSON.parse(JSON.stringify(configRawFixo));
    await page.route("**/api/config", (route) =>
      route.fulfill({
        json: { raw: atual, active_profile: "default", profiles: ["default"] },
      })
    );
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      atual = aplicadas.at(-1)!;
      await route.fulfill({ json: { ok: true } });
    });

    const criar = page.getByTestId("config-toggle-create_under_root");
    const mover = page.getByTestId("config-toggle-auto_move_enabled");
    const copia = page.getByTestId("config-toggle-keep_copy");

    // Dados reais do stub: os tres toggles comecam desligados. O de copia
    // era so visual (fixo ligado, issue #59); agora e por perfil, como os
    // outros dois.
    await expect(criar).toHaveAttribute("aria-checked", "false");
    await expect(mover).toHaveAttribute("aria-checked", "false");
    await expect(copia).toHaveAttribute("aria-checked", "false");
    await expect(copia).not.toHaveAttribute("aria-disabled", "true");

    await criar.click();
    await mover.click();
    await copia.click();
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });

    const gravado = aplicadas.at(-1);
    expect(gravado?.model?.create_under_root).toBe(true);
    expect(gravado?.model?.auto_move_enabled).toBe(true);
    expect((gravado?.organization as { copy: boolean }).copy).toBe(true);
    await expect(copia).toHaveAttribute("aria-checked", "true");

    // Desligar de novo tambem persiste.
    await copia.click();
    await expect.poll(() => (aplicadas.at(-1)?.organization as { copy: boolean }).copy).toBe(false);
  });

  test("secao 3: pill de analises, uso de armazenamento e abrir pasta", async ({
    page,
  }) => {
    // Stats do stub: 721 analises, 112.5 MB (mockup: 112.5 -> "112").
    await expect(page.getByTestId("config-pill-dados")).toHaveText(
      "721 ANÁLISES · 112 MB"
    );
    await expect(page.getByTestId("config-storage-titulo")).toHaveText(
      "Uso de armazenamento"
    );
    await expect(page.getByTestId("config-storage-usado")).toHaveText(
      "112 MB utilizados"
    );
    await expect(page.getByTestId("config-storage-total")).toHaveText(
      "de 2 GB"
    );
    // Barra proporcional ao real: 112.5 / 2048 MB ~= 5.5%.
    const preenchimento = await page
      .getByTestId("config-storage-fill")
      .evaluate((el) => (el as HTMLElement).style.width);
    expect(preenchimento).toBe("5.5%");
    // O valor acessivel segue o mesmo inteiro do texto (floor), nao o round.
    await expect(page.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "112"
    );
    // Sem Electron (preload), ABRIR PASTA fica desabilitado.
    await expect(page.getByTestId("config-abrir-pasta")).toHaveAttribute(
      "aria-disabled",
      "true"
    );
  });

  test("secao 4: campos numericos com dados reais e card de recomendacao", async ({
    page,
  }) => {
    // Valores reais do stub: 10/50 (o mockup desenha 30/20, mas dado real
    // vence por especificacao). Escopo ao card: a sidebar repete os rotulos.
    const secao4 = page.getByTestId("config-section-4");
    await expect(secao4.getByTestId("config-retrain_every")).toHaveValue("10");
    await expect(secao4.getByTestId("config-min_examples")).toHaveValue("50");
    await expect(secao4.getByText("Retreinar a cada")).toBeVisible();
    await expect(secao4.getByText("Mínimo de exemplos por classe")).toBeVisible();
    await expect(secao4.getByText("músicas classificadas")).toBeVisible();
    await expect(secao4.getByText("músicas", { exact: true })).toBeVisible();

    const recomendacao = page.getByTestId("config-recomendacao");
    await expect(recomendacao).toContainText("Recomendação");
    await expect(recomendacao).toContainText(
      "Use pelo menos 20 exemplos por classe para obter um modelo mais estável e preciso."
    );
  });

  test("sidebar: grupos com dados reais e status do sistema", async ({
    page,
  }) => {
    const pastas = page.getByTestId("config-resumo-pastas");
    await expect(pastas).toContainText("Pastas");
    await expect(pastas).toContainText("Entrada");
    await expect(pastas).toContainText("Energia baixa");
    await expect(pastas).toContainText("Energia equilibrada");
    await expect(pastas).toContainText("Energia alta");

    // Valores reais: fixture usa 2 segmentos por caminho, exibidos inteiros.
    await expect(page.getByTestId("config-resumo-entrada")).toHaveText(
      "/musicas/entrada"
    );

    const modelo = page.getByTestId("config-resumo-modelo");
    await expect(modelo).toContainText("Retreinar a cada");
    await expect(modelo).toContainText("10 músicas");
    await expect(modelo).toContainText("50 músicas");

    const dados = page.getByTestId("config-resumo-dados");
    await expect(dados).toContainText("Pasta de dados");
    await expect(dados).toContainText("Análises realizadas");
    await expect(dados).toContainText("721");
    await expect(dados).toContainText("112 MB");

    // Sistema: os tres toggles desligados no stub ("Desativado" nao contem
    // "Ativado", que tem A maiusculo); ligar a copia acende o status.
    const sistema = page.getByTestId("config-resumo-sistema");
    await expect(sistema).toContainText("Criação automática de pastas");
    await expect(sistema).toContainText("Mover arquivos após classificação");
    await expect(sistema).toContainText("Manter cópia na entrada");
    await expect(sistema).toContainText("Desativado");
    await expect(sistema).not.toContainText("Ativado");
    await page.getByTestId("config-toggle-keep_copy").click();
    await expect(sistema).toContainText("Ativado");
  });

  test("sidebar: escanear dispara POST /api/scan", async ({ page }) => {
    let chamadas = 0;
    await page.route("**/api/scan", async (route) => {
      chamadas++;
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-scan-btn").click();
    await expect
      .poll(() => chamadas, { timeout: 5000 })
      .toBe(1);
  });

  test("sidebar: escanear com falha nao gera rejeicao nao tratada", async ({
    page,
  }) => {
    const erros: string[] = [];
    page.on("pageerror", (erro) => erros.push(erro.message));
    let chamadas = 0;
    await page.route("**/api/scan", async (route) => {
      chamadas++;
      await route.abort();
    });

    await page.getByTestId("config-scan-btn").click();
    await expect.poll(() => chamadas, { timeout: 5000 }).toBe(1);
    await page.waitForTimeout(300);
    expect(erros).toEqual([]);
  });

  test("reset: auto-save fica pausado enquanto o dialogo esta aberto", async ({
    page,
  }) => {
    // Sem a pausa, o apply agendado pelo rascunho sujo dispara com o
    // dialogo aberto e pode regravar os valores antigos depois do reset.
    const aplicadas: ConfigRaw[] = [];
    await page.route("**/api/config/apply", async (route) => {
      aplicadas.push((route.request().postDataJSON() as { raw: ConfigRaw }).raw);
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-data_dir").fill("/dados/pendente");
    await page.getByTestId("config-reset-btn").click();
    await page.waitForTimeout(1500);
    expect(aplicadas).toHaveLength(0);
  });

  test("reset: falha mostra o erro no dialogo e permite tentar de novo", async ({
    page,
  }) => {
    let falhar = true;
    await page.route("**/api/config/reset", async (route) => {
      if (falhar) {
        await route.fulfill({
          status: 500,
          json: { detail: "Falha ao restaurar padrões: disco cheio" },
        });
      } else {
        await route.fulfill({ json: { ok: true } });
      }
    });

    const dialogo = page.getByTestId("confirm-dialog");
    const erro = page.getByTestId("confirm-dialog-error");
    const confirmar = page.getByTestId("confirm-dialog-confirm");

    await page.getByTestId("config-reset-btn").click();
    await expect(erro).toHaveCount(0);
    await confirmar.click();

    // Falha: o dialogo fica aberto, diz o motivo e deixa tentar de novo.
    await expect(erro).toBeVisible();
    await expect(erro).toContainText("disco cheio");
    await expect(dialogo).toBeVisible();
    await expect(confirmar).toBeEnabled();
    // Render, nao CSS: a cor computada e a do token de perigo.
    const cores = await erro.evaluate((el) => {
      const sonda = document.createElement("span");
      sonda.style.color = "var(--color-state-danger)";
      document.body.appendChild(sonda);
      const esperada = getComputedStyle(sonda).color;
      sonda.remove();
      return { atual: getComputedStyle(el).color, esperada };
    });
    expect(cores.atual).toBe(cores.esperada);

    // Cancelar e reabrir nao herda o erro velho.
    await page.getByTestId("confirm-dialog-cancel").click();
    await expect(dialogo).toHaveCount(0);
    await page.getByTestId("config-reset-btn").click();
    await expect(erro).toHaveCount(0);

    // Segunda tentativa com o servidor de volta: fecha sem erro.
    falhar = false;
    await confirmar.click();
    await expect(dialogo).toHaveCount(0);
    await expect(erro).toHaveCount(0);
  });

  test("reset: recarga falhando deixa o dialogo aberto com o motivo e Confirmar tenta de novo", async ({
    page,
  }) => {
    // O reset em si funciona, mas o GET /api/config que recarrega o rascunho
    // cai: fechar o dialogo aqui deixaria a tela com os valores antigos como
    // se nada tivesse acontecido (recarrega() engolia o erro).
    let recargaFalha = true;
    let recargas = 0;
    await page.route("**/api/config/reset", (route) =>
      route.fulfill({ json: { ok: true } })
    );
    await page.route("**/api/config", async (route) => {
      recargas++;
      if (recargaFalha) {
        await route.fulfill({ status: 500, json: { detail: "servidor fora" } });
      } else {
        // Cai no stub do beforeEach.
        await route.fallback();
      }
    });

    const dialogo = page.getByTestId("confirm-dialog");
    const erro = page.getByTestId("confirm-dialog-error");
    const confirmar = page.getByTestId("confirm-dialog-confirm");

    await page.getByTestId("config-reset-btn").click();
    await confirmar.click();

    await expect(erro).toBeVisible();
    await expect(erro).toContainText("não foi possível recarregar");
    await expect(dialogo).toBeVisible();
    await expect(confirmar).toBeEnabled();
    expect(recargas).toBe(1);

    // Servidor de volta: Confirmar repete o reset (idempotente), a recarga
    // passa e o dialogo fecha sem erro.
    recargaFalha = false;
    await confirmar.click();
    await expect(dialogo).toHaveCount(0);
    await expect(erro).toHaveCount(0);
    expect(recargas).toBe(2);
    await expect(page.getByTestId("config-tab")).toBeVisible();
  });

  test("reset: botao mostra Restaurando… enquanto o servidor responde", async ({
    page,
  }) => {
    let liberar!: () => void;
    const portao = new Promise<void>((resolve) => (liberar = resolve));
    await page.route("**/api/config/reset", async (route) => {
      await portao;
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-reset-btn").click();
    const confirmar = page.getByTestId("confirm-dialog-confirm");
    await expect(confirmar).toHaveText("Confirmar");
    await confirmar.click();

    // O rotulo "Aprovando…" e o padrao da Revisao; aqui a acao e outra.
    await expect(confirmar).toHaveText("Restaurando…");
    await expect(confirmar).toBeDisabled();

    liberar();
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
  });

  test("sidebar: restaurar padroes pede confirmacao e chama reset", async ({
    page,
  }) => {
    let chamadas = 0;
    await page.route("**/api/config/reset", async (route) => {
      chamadas++;
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-reset-btn").click();
    // Cancelar nao chama o reset.
    await page.getByRole("button", { name: "Cancelar" }).click();
    expect(chamadas).toBe(0);

    await page.getByTestId("config-reset-btn").click();
    await page.getByRole("button", { name: "Confirmar" }).click();
    await expect.poll(() => chamadas, { timeout: 5000 }).toBe(1);
  });

  test("auto-save nao reaplica quando o servidor normaliza o caminho", async ({
    page,
  }) => {
    // O servidor expande '~' e resolve data_dir relativo, entao o raw
    // recarregado difere do digitado. Sem reconciliar o rascunho, o
    // auto-save veria o rascunho 'sujo' para sempre e reaplicaria a cada
    // 800ms -- aqui o stub simula essa normalizacao.
    const aplicadas: ConfigRaw[] = [];
    let atual: ConfigRaw = JSON.parse(JSON.stringify(configRawFixo));
    await page.route("**/api/config", (route) =>
      route.fulfill({
        json: { raw: atual, active_profile: "default", profiles: ["default"] },
      })
    );
    await page.route("**/api/config/apply", async (route) => {
      const body = route.request().postDataJSON() as { raw: ConfigRaw };
      aplicadas.push(body.raw);
      atual = JSON.parse(JSON.stringify(body.raw)) as ConfigRaw;
      atual.folders!.inbox = "/home/usuario/musicas/entrada";
      await route.fulfill({ json: { ok: true } });
    });

    await page.getByTestId("config-inbox").fill("~/musicas/entrada");
    await expect(page.getByText("Configuração salva.")).toBeVisible({
      timeout: 10000,
    });
    // O campo mostra o caminho normalizado pelo servidor.
    await expect(page.getByTestId("config-inbox")).toHaveValue(
      "/home/usuario/musicas/entrada"
    );

    // Um apply so: o rascunho foi reconciliado e nao re-dispara.
    await page.waitForTimeout(2000);
    expect(aplicadas).toHaveLength(1);
  });
});
