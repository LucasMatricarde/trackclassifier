/**
 * Shell desktop do TrackClassifier.
 *
 * O front nao sabe quem o hospeda: fala HTTP/WS com 127.0.0.1:8765. Este
 * processo sobe o backend Python (o mesmo `dj serve`), espera o health e
 * abre a janela nessa origem. Nao ha IPC nem Node na janela -- o contrato
 * continua sendo a API.
 *
 * Dev: `npm start`, que roda o backend do checkout via `uv run dj serve`.
 * Empacotado: o backend vem em `resources/backend` (onedir do PyInstaller).
 */

const { app, BrowserWindow, Menu, dialog, ipcMain } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const http = require("node:http");
const { criaAtualizador, criaRequisicao } = require("./updater");

const PORTA = 8765;
const URL_APP = `http://127.0.0.1:${PORTA}`;
const SMOKE = process.argv.includes("--smoke");

let backend = null;

// Unico canal de IPC da janela: escolher pasta e revelar arquivo no gerenciador.
ipcMain.handle("trackclassifier:select-folder", async (_evento, atual) => {
  const opcoes = {
    title: "Escolher pasta",
    buttonLabel: "Escolher",
    properties: ["openDirectory", "createDirectory"],
    defaultPath:
      typeof atual === "string" && atual.length > 0 ? atual : undefined,
  };
  const janela = BrowserWindow.getFocusedWindow();
  const resultado = janela
    ? await dialog.showOpenDialog(janela, opcoes)
    : await dialog.showOpenDialog(opcoes);
  return resultado.canceled ? null : resultado.filePaths[0];
});

// Revelar arquivo no gerenciador de arquivos do SO (Finder no macOS, Explorer no Windows)
const { shell } = require("electron");
ipcMain.handle("trackclassifier:reveal-item", async (_evento, caminho) => {
  if (typeof caminho !== "string" || !caminho) return false;
  shell.showItemInFolder(caminho);
  return true;
});

function health() {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: PORTA, path: "/api/health", timeout: 1000 },
      (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      }
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function esperaServidor(limiteMs = 30000) {
  const limite = Date.now() + limiteMs;
  while (Date.now() < limite) {
    if (await health()) return true;
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

function comandoDoBackend() {
  if (!app.isPackaged) {
    // Checkout: o uv resolve o venv e o console-script `dj`.
    return {
      cmd: "uv",
      args: ["run", "dj", "serve", "--no-browser"],
      cwd: path.resolve(app.getAppPath(), ".."),
    };
  }
  const pasta = path.join(process.resourcesPath, "backend");
  const nome = process.platform === "win32" ? "TrackClassifier.exe" : "TrackClassifier";
  return { cmd: path.join(pasta, nome), args: ["serve", "--no-browser"], cwd: pasta };
}

async function garanteBackend() {
  // Dev: se ja existe um `dj serve` no ar, reaproveita -- evita duas
  // instancias brigando pela porta e poupa o scan de abertura.
  if (await health()) return true;

  const { cmd, args, cwd } = comandoDoBackend();
  backend = spawn(cmd, args, {
    cwd,
    stdio: app.isPackaged ? "ignore" : "inherit",
  });
  backend.on("exit", () => {
    backend = null;
  });

  return esperaServidor();
}

function sai(codigo, relancar) {
  // relaunch() agenda a nova instancia para DEPOIS que esta sair, e e por isso
  // que a atualizacao passa por aqui: abrir o app novo (`open -n`) com este
  // ainda vivo perderia o requestSingleInstanceLock e a janela nova fecharia
  // na hora, deixando o usuario sem app. Tambem exige o backend ja morto: se
  // ele ainda atendesse na porta, o app novo reaproveitaria o servidor velho.
  if (relancar) app.relaunch();
  app.exit(codigo);
}

function encerra(codigo, { relancar = false } = {}) {
  // app.exit() nao dispara before-quit; sem isto o backend spawnado no modo
  // smoke (ou num erro de startup) ficaria orfao segurando a porta. Espera o
  // SIGTERM terminar para o proximo smoke nao encontrar um servidor morrendo
  // e reutiliza-lo por engano.
  if (!backend) {
    sai(codigo, relancar);
    return;
  }
  const processo = backend;
  backend = null;
  const limite = setTimeout(() => {
    try {
      processo.kill("SIGKILL");
    } catch {
      // ja morreu
    }
    sai(codigo, relancar);
  }, 3000);
  processo.once("exit", () => {
    clearTimeout(limite);
    sai(codigo, relancar);
  });
  processo.kill("SIGTERM");
}

function primeiraJanela() {
  return BrowserWindow.getAllWindows()[0] || null;
}

const atualizador = criaAtualizador({
  requisicao: criaRequisicao(PORTA),
  dialog,
  janela: primeiraJanela,
  progresso: (fracao) => {
    const janela = primeiraJanela();
    if (janela) janela.setProgressBar(fracao);
  },
  relancar: () => encerra(0, { relancar: true }),
});

// Menu do app no macOS, com "Buscar atualizacoes..." no lugar que o Qt usava
// (menu "TrackClassifier", junto de Sobre e Sair). Fora do mockup de
// proposito: e menu nativo, nao tela.
function montaMenuDoMac() {
  const modelo = [
    {
      label: app.name,
      submenu: [
        { role: "about" },
        {
          label: "Buscar atualizacoes...",
          click: () => {
            atualizador.checa(true).catch(() => {});
          },
        },
        { type: "separator" },
        { role: "services" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    { role: "editMenu" },
    { role: "viewMenu" },
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(modelo));
}

function criaJanela() {
  const janela = new BrowserWindow({
    width: 1512,
    height: 1037,
    minWidth: 1100,
    minHeight: 760,
    backgroundColor: "#0A1119",
    title: "TrackClassifier",
    show: !SMOKE,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  janela.loadURL(URL_APP);
  return janela;
}

if (!SMOKE) {
  // Uma instancia por vez. Sem isso, dois apps subiriam dois backends e o
  // segundo morreria na porta ocupada com uma janela vazia.
  if (!app.requestSingleInstanceLock()) {
    app.quit();
  } else {
    app.on("second-instance", () => {
      const [janela] = BrowserWindow.getAllWindows();
      if (janela) {
        if (janela.isMinimized()) janela.restore();
        janela.focus();
      }
    });
  }
}

app.whenReady().then(async () => {
  if (process.platform === "darwin") montaMenuDoMac();
  else Menu.setApplicationMenu(null);

  const ok = await garanteBackend();
  if (!ok) {
    if (SMOKE) {
      console.error(`SMOKE FAIL: backend nao respondeu em ${URL_APP}`);
      encerra(1);
      return;
    }
    dialog.showErrorBox(
      "TrackClassifier",
      `O servidor local nao respondeu em ${URL_APP}.\n\n` +
        "Rode `uv run dj serve` manualmente para ver o erro."
    );
    encerra(1);
    return;
  }

  const janela = criaJanela();

  if (!SMOKE) {
    // Checagem do boot. Fora do smoke porque ali nao pode haver dialogo, e com
    // folga depois de carregar para a oferta nao aparecer sobre uma janela em
    // branco. Em dev (`npm start`) o backend responde "nao suportado" e nada
    // aparece.
    janela.webContents.once("did-finish-load", () => {
      setTimeout(() => {
        atualizador.checa(false).catch(() => {});
      }, 3000);
    });
  }

  if (SMOKE) {
    // Teste de fumaca: a janela nao aparece, mas o app real renderiza. Se a
    // aba Revisao nao aparecer (WS quebrado, build ausente), sai != 0.
    const prazo = Date.now() + 40000;
    janela.webContents.on("did-finish-load", async () => {
      // Sem o preload o seletor de pasta some e o primeiro uso volta a
      // exigir caminho digitado; falhar aqui pega um `files` incompleto do
      // electron-builder antes de distribuir.
      try {
        const ponte = await janela.webContents.executeJavaScript(
          "typeof window.trackclassifier?.selectFolder === 'function' && typeof window.trackclassifier?.revealItem === 'function'"
        );
        if (!ponte) {
          console.error("SMOKE FAIL: preload sem selectFolder ou revealItem");
          encerra(1);
          return;
        }
      } catch {
        console.error("SMOKE FAIL: nao consegui ler o preload");
        encerra(1);
        return;
      }

      while (Date.now() < prazo) {
        try {
          const estado = await janela.webContents.executeJavaScript(
            "({ review: !!document.querySelector(\"[data-testid='review-tab']\"), " +
              "setup: !!document.querySelector(\"[data-testid='setup-tab']\"), " +
              "library: !!document.querySelector(\"[data-testid='library-tab']\"), " +
              "picks: document.querySelectorAll('.config-pick').length })"
          );
          if (estado.setup) {
            // 5 campos de pasta (inbox, 3 destinos, data_dir): sem o
            // preload o React esconde os botoes e o primeiro uso volta a
            // exigir caminho digitado.
            if (estado.picks < 5) {
              console.error(
                `SMOKE FAIL: setup com ${estado.picks} botoes de pasta (esperado 5)`
              );
              encerra(1);
              return;
            }
            console.log("SMOKE OK");
            encerra(0);
            return;
          }
          if (estado.review || estado.library) {
            console.log("SMOKE OK");
            encerra(0);
            return;
          }
        } catch {
          // pagina ainda navegando; tenta de novo
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      console.error("SMOKE FAIL: nem review-tab nem setup-tab nem library-tab renderizaram");
      encerra(1);
    });
  }
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  if (backend) {
    backend.kill("SIGTERM");
    backend = null;
  }
});
