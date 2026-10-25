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

// Respostas seguidas sem estado util (conexao recusada, 401, "idle" depois de o
// install ter comecado). O download roda numa thread propria do backend e nao
// trava a API, entao isto nao e "ocupado": o backend morreu ou reiniciou. 20
// passos de 500ms sao 10s, bem mais que qualquer soluco de GC ou de disco.
const MAX_FALHAS_SEGUIDAS = 20;

/**
 * GET/POST JSON no backend local. O token vem de /api/health (o mesmo caminho
 * que o front usa) e fica em cache; um 401 invalida o cache e tenta uma vez
 * de novo, porque um backend reiniciado sob o mesmo shell troca de token.
 */
function criaRequisicao(porta) {
  let token = null;

  function bruto(metodo, caminho, tokenDaChamada, corpo) {
    return new Promise((resolve, reject) => {
      const dados = corpo === undefined ? null : JSON.stringify(corpo);
      const headers = {};
      if (tokenDaChamada) headers["x-auth-token"] = tokenDaChamada;
      if (dados !== null) {
        headers["content-type"] = "application/json";
        headers["content-length"] = Buffer.byteLength(dados);
      }
      const req = http.request(
        {
          host: "127.0.0.1",
          port: porta,
          method: metodo,
          path: caminho,
          headers,
          // A checagem pode esperar a resposta do GitHub (ate 10s no backend).
          timeout: 30000,
        },
        (res) => {
          let texto = "";
          res.setEncoding("utf8");
          res.on("data", (pedaco) => {
            texto += pedaco;
          });
          res.on("end", () => {
            let json = null;
            try {
              json = JSON.parse(texto);
            } catch {
              // corpo nao-JSON: o status basta
            }
            resolve({ status: res.statusCode, corpo: json });
          });
        }
      );
      req.on("error", reject);
      req.on("timeout", () => req.destroy(new Error("tempo esgotado")));
      if (dados !== null) req.write(dados);
      req.end();
    });
  }

  async function obtemToken() {
    const saude = await bruto("GET", "/api/health", null);
    token = saude.corpo && saude.corpo.token;
    return token;
  }

  return async (metodo, caminho, corpo) => {
    if (!token) await obtemToken();
    const resposta = await bruto(metodo, caminho, token, corpo);
    if (resposta.status !== 401) return resposta;
    await obtemToken();
    return bruto(metodo, caminho, token, corpo);
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
  // Um fluxo por vez: a checagem do boot, o clique no menu e a instalacao
  // dividem este flag. Sem ele, um clique durante a instalacao abria uma
  // segunda oferta cujo "Atualizar" voltava 409 num dialogo de falha, e dois
  // loops brigavam pela barra do dock.
  let ocupado = false;

  // Mais estreito que `ocupado`: so a instalacao (download + troca do .app).
  // E o que o aviso de saida do main.js precisa: usar `ocupado` bloqueava o
  // Sair com a oferta aberta e deixava o app vivo sem janela.
  let instalando = false;

  async function caixa(opcoes) {
    const alvo = janela();
    return alvo ? dialog.showMessageBox(alvo, opcoes) : dialog.showMessageBox(opcoes);
  }

  async function aviso(tipo, titulo, detalhe) {
    await caixa({ type: tipo, buttons: ["OK"], title: titulo, message: titulo, detail: detalhe });
  }

  async function perdeuOServidor() {
    progresso(-1);
    await aviso(
      "error",
      "Falha na atualizacao",
      "O servidor local deixou de responder durante a atualizacao. " +
        "Feche e abra o app para conferir a versao instalada."
    );
  }

  async function instala(versao) {
    let inicio;
    try {
      inicio = await requisicao("POST", "/api/update/install", { version: versao });
    } catch (erro) {
      inicio = { status: 0, corpo: { detail: String(erro.message || erro) } };
    }
    if (inicio.status !== 200) {
      // 409 e o servidor dizendo "ja estou nisso" ou "ja instalei": informativo,
      // nao uma falha da atualizacao.
      if (inicio.status === 409) {
        await aviso("info", "Atualizacao", detalheDe(inicio));
      } else {
        await aviso("error", "Falha na atualizacao", detalheDe(inicio));
      }
      return;
    }

    instalando = true;
    try {
      await acompanha();
    } finally {
      instalando = false;
    }
  }

  // O laco de status. Separado de instala() so para o flag `instalando` cobrir
  // exatamente isto e nada mais.
  async function acompanha() {
    let falhasSeguidas = 0;
    for (let tentativa = 0; tentativa < MAX_TENTATIVAS_DE_STATUS; tentativa += 1) {
      await esperar(500);
      let resposta = null;
      try {
        resposta = await requisicao("GET", "/api/update/status");
      } catch {
        resposta = null;
      }
      const estado = (resposta && resposta.status === 200 && resposta.corpo) || {};

      if (estado.state === "downloading") {
        falhasSeguidas = 0;
        progresso(estado.total > 0 ? estado.done / estado.total : 0);
      } else if (estado.state === "installing") {
        falhasSeguidas = 0;
        progresso(1);
      } else if (estado.state === "done") {
        progresso(-1);
        // A troca ja acabou: durante o dialogo "Atualizado" nao ha nada a proteger.
        instalando = false;
        await aviso("info", "Atualizado", "A versao nova foi instalada. O app vai reabrir.");
        relancar();
        return;
      } else if (estado.state === "failed") {
        progresso(-1);
        instalando = false;
        await aviso("error", "Falha na atualizacao", estado.error || "Erro desconhecido.");
        return;
      } else {
        // Sem resposta, 401 ou "idle": o install ja foi aceito, entao nenhum
        // destes e um estado de verdade.
        falhasSeguidas += 1;
        if (falhasSeguidas >= MAX_FALHAS_SEGUIDAS) {
          instalando = false;
          await perdeuOServidor();
          return;
        }
      }
    }
    progresso(-1);
    await aviso(
      "error",
      "Falha na atualizacao",
      "A atualizacao nao terminou. Feche e abra o app para conferir a versao."
    );
  }

  async function fluxo(manual) {
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
    if (corpo.in_progress) {
      if (manual) {
        await aviso("info", "Buscar atualizacoes", "Uma atualizacao ja esta em andamento.");
      }
      return;
    }
    if (corpo.installed) {
      if (manual) {
        await aviso(
          "info",
          "Buscar atualizacoes",
          "A versao nova ja foi instalada. Feche e abra o app para usa-la."
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

    // "Depois" so fecha; "Dispensar esta versao" e o que impede a pergunta de
    // voltar todo dia. Eram um botao so ("Agora nao" que dispensava para
    // sempre), e quem so queria adiar nunca mais via a oferta. Na checagem
    // pedida pelo menu nao ha dispensa: quem clicou pode querer ver de novo.
    const botoes = manual
      ? ["Atualizar", "Fechar"]
      : ["Atualizar", "Depois", "Dispensar esta versao"];
    const escolha = await caixa({
      type: "question",
      buttons: botoes,
      defaultId: 0,
      cancelId: 1,
      title: "Atualizar o TrackClassifier",
      message: `A versao ${corpo.version} esta disponivel`,
      detail: corpo.text,
    });
    if (escolha.response === 0) {
      await instala(corpo.version);
      return;
    }
    if (!manual && escolha.response === 2) {
      try {
        await requisicao("POST", "/api/update/dismiss");
      } catch {
        // dispensar e acessorio; no pior caso a pergunta volta amanha
      }
    }
  }

  /**
   * `manual` e o clique no menu: responde mesmo sem novidade e mostra erro de
   * rede. A checagem do boot e silenciosa, exceto quando ha versao nova.
   */
  async function checa(manual) {
    if (ocupado) {
      if (manual) {
        await aviso("info", "Buscar atualizacoes", "Uma atualizacao ja esta em andamento.");
      }
      return;
    }
    ocupado = true;
    try {
      await fluxo(manual);
    } finally {
      ocupado = false;
    }
  }

  return { checa, emAndamento: () => ocupado, instalando: () => instalando };
}

module.exports = { criaAtualizador, criaRequisicao };
