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

const { app, BrowserWindow, Menu, dialog } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const http = require("node:http");

const PORTA = 8765;
const URL_APP = `http://127.0.0.1:${PORTA}`;
const SMOKE = process.argv.includes("--smoke");

let backend = null;

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

function encerra(codigo) {
  // app.exit() nao dispara before-quit; sem isto o backend spawnado no modo
  // smoke (ou num erro de startup) ficaria orfao segurando a porta.
  if (backend) {
    backend.kill("SIGTERM");
    backend = null;
  }
  app.exit(codigo);
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
  if (process.platform !== "darwin") Menu.setApplicationMenu(null);

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

  if (SMOKE) {
    // Teste de fumaca: a janela nao aparece, mas o app real renderiza. Se a
    // aba Revisao nao aparecer (WS quebrado, build ausente), sai != 0.
    const prazo = Date.now() + 40000;
    janela.webContents.on("did-finish-load", async () => {
      while (Date.now() < prazo) {
        try {
          // Review pronta OU tela de primeiro uso: um app recem-instalado
          // nao tem config.toml e o backend sobe em modo de setup. Exigir
          // review-tab faria o smoke falhar justamente na primeira abertura.
          const pronto = await janela.webContents.executeJavaScript(
            "!!document.querySelector(\"[data-testid='review-tab']\") || " +
              "!!document.querySelector(\"[data-testid='setup-tab']\")"
          );
          if (pronto) {
            console.log("SMOKE OK");
            encerra(0);
            return;
          }
        } catch {
          // pagina ainda navegando; tenta de novo
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      console.error("SMOKE FAIL: nem review-tab nem setup-tab renderizaram");
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
