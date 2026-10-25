/**
 * Atualizacao do app, do lado do shell.
 *
 * Quem checa, baixa e troca o .app e o backend (`/api/update/*`, sem Qt). Este
 * modulo so conversa com ele e mostra dialogos NATIVOS. Nao ha tela React para
 * isso de proposito: o mockup nao tem "Buscar atualizacoes", e a regra do
 * projeto e nao inventar elemento na tela.
 *
 * Tudo que toca o mundo (HTTP, dialogo, relancar, esperar) entra por
 * parametro, para o teste rodar sem Electron, sem rede e sem dormir.
 */

const http = require("node:http");

// Mais que isso (1h em passos de 500ms) e um backend que sumiu no meio da
// troca: melhor avisar do que ficar com a barra do dock girando para sempre.
const MAX_TENTATIVAS_DE_STATUS = 7200;

/**
 * GET/POST JSON no backend local. O token vem de /api/health (o mesmo caminho
 * que o front usa) e fica em cache: ele vale para a vida do processo.
 */
function criaRequisicao(porta) {
  let token = null;

  function bruto(metodo, caminho, tokenDaChamada) {
    return new Promise((resolve, reject) => {
      const req = http.request(
        {
          host: "127.0.0.1",
          port: porta,
          method: metodo,
          path: caminho,
          headers: tokenDaChamada ? { "x-auth-token": tokenDaChamada } : {},
          // A checagem pode esperar a resposta do GitHub (ate 10s no backend).
          timeout: 30000,
        },
        (res) => {
          let dados = "";
          res.setEncoding("utf8");
          res.on("data", (pedaco) => {
            dados += pedaco;
          });
          res.on("end", () => {
            let corpo = null;
            try {
              corpo = JSON.parse(dados);
            } catch {
              // corpo nao-JSON: o status basta
            }
            resolve({ status: res.statusCode, corpo });
          });
        }
      );
      req.on("error", reject);
      req.on("timeout", () => req.destroy(new Error("tempo esgotado")));
      req.end();
    });
  }

  return async (metodo, caminho) => {
    if (!token) {
      const saude = await bruto("GET", "/api/health", null);
      token = saude.corpo && saude.corpo.token;
    }
    return bruto(metodo, caminho, token);
  };
}

function detalheDe(resposta) {
  const corpo = resposta && resposta.corpo;
  if (corpo && typeof corpo.detail === "string") return corpo.detail;
  return `O servidor local respondeu ${resposta ? resposta.status : "sem resposta"}.`;
}

function criaAtualizador({
  requisicao,
  dialog,
  janela,
  progresso,
  relancar,
  esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  async function caixa(opcoes) {
    const alvo = janela();
    return alvo ? dialog.showMessageBox(alvo, opcoes) : dialog.showMessageBox(opcoes);
  }

  async function aviso(tipo, titulo, detalhe) {
    await caixa({ type: tipo, buttons: ["OK"], title: titulo, message: titulo, detail: detalhe });
  }

  async function instala() {
    let inicio;
    try {
      inicio = await requisicao("POST", "/api/update/install");
    } catch (erro) {
      inicio = { status: 0, corpo: { detail: String(erro.message || erro) } };
    }
    if (inicio.status !== 200) {
      await aviso("error", "Falha na atualizacao", detalheDe(inicio));
      return;
    }

    for (let tentativa = 0; tentativa < MAX_TENTATIVAS_DE_STATUS; tentativa += 1) {
      await esperar(500);
      let resposta;
      try {
        resposta = await requisicao("GET", "/api/update/status");
      } catch {
        continue; // backend ocupado com o download; tenta no proximo passo
      }
      const estado = resposta.corpo || {};

      if (estado.state === "downloading") {
        progresso(estado.total > 0 ? estado.done / estado.total : 0);
      } else if (estado.state === "installing") {
        progresso(1);
      } else if (estado.state === "done") {
        progresso(-1);
        await aviso("info", "Atualizado", "A versao nova foi instalada. O app vai reabrir.");
        relancar();
        return;
      } else if (estado.state === "failed") {
        progresso(-1);
        await aviso("error", "Falha na atualizacao", estado.error || "Erro desconhecido.");
        return;
      }
    }
    progresso(-1);
    await aviso(
      "error",
      "Falha na atualizacao",
      "A atualizacao nao terminou. Feche e abra o app para conferir a versao."
    );
  }

  /**
   * `manual` e o clique no menu: responde mesmo sem novidade e mostra erro de
   * rede. A checagem do boot e silenciosa, exceto quando ha versao nova.
   */
  async function checa(manual) {
    let resposta;
    try {
      resposta = await requisicao("GET", `/api/update/check?manual=${manual}`);
    } catch (erro) {
      if (manual) {
        await aviso("error", "Nao foi possivel verificar", String(erro.message || erro));
      }
      return;
    }
    if (resposta.status !== 200) {
      if (manual) {
        await aviso("error", "Nao foi possivel verificar atualizacoes", detalheDe(resposta));
      }
      return;
    }

    const corpo = resposta.corpo || {};
    if (!corpo.supported) {
      if (manual) {
        await aviso(
          "info",
          "Buscar atualizacoes",
          "A atualizacao automatica so funciona no app instalado (macOS)."
        );
      }
      return;
    }
    if (!corpo.available) {
      if (manual) {
        await aviso("info", "Buscar atualizacoes", "Voce ja esta na versao mais recente.");
      }
      return;
    }

    const escolha = await caixa({
      type: "question",
      buttons: ["Atualizar", "Agora nao"],
      defaultId: 0,
      cancelId: 1,
      title: "Atualizar o TrackClassifier",
      message: `A versao ${corpo.version} esta disponivel`,
      detail: corpo.text,
    });
    if (escolha.response !== 0) {
      // So a checagem automatica dispensa: e o que impede de perguntar de novo
      // todo dia pela mesma versao. Quem clicou no menu e disse "agora nao"
      // pode querer ver de novo.
      if (!manual) {
        try {
          await requisicao("POST", "/api/update/dismiss");
        } catch {
          // dispensar e acessorio; no pior caso a pergunta volta amanha
        }
      }
      return;
    }
    await instala();
  }

  return { checa };
}

module.exports = { criaAtualizador, criaRequisicao };
