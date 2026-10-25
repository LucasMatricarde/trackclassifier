/**
 * Testes do fluxo de atualizacao do shell. Rodam com `npm test` (node --test),
 * sem Electron e sem rede externa: o dialogo e falso, e o HTTP e falso ou um
 * servidor local em porta efemera.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");

const { criaAtualizador, criaRequisicao } = require("./updater");

/** Monta um atualizador com respostas roteirizadas por "METODO caminho". */
function monta({ rotas, respostasDoDialogo = [] }) {
  const chamadas = [];
  const corpos = [];
  const dialogos = [];
  const barras = [];
  let relancou = 0;
  const fila = [...respostasDoDialogo];

  const requisicao = async (metodo, caminho, corpo) => {
    chamadas.push(`${metodo} ${caminho}`);
    corpos.push(corpo);
    const rota = rotas[`${metodo} ${caminho}`] ?? rotas[`${metodo} ${caminho.split("?")[0]}`];
    if (!rota) throw new Error(`rota nao roteirizada: ${metodo} ${caminho}`);
    const resposta = typeof rota === "function" ? rota() : rota;
    if (resposta instanceof Error) throw resposta;
    return resposta;
  };

  const dialog = {
    showMessageBox: async (...args) => {
      const opcoes = args[args.length - 1];
      dialogos.push(opcoes);
      return { response: fila.length > 0 ? fila.shift() : 0 };
    },
  };

  const atualizador = criaAtualizador({
    requisicao,
    dialog,
    janela: () => null,
    progresso: (valor) => barras.push(valor),
    relancar: () => {
      relancou += 1;
    },
    esperar: async () => {},
  });

  return {
    atualizador,
    chamadas,
    corpos,
    dialogos,
    barras,
    relancamentos: () => relancou,
  };
}

const NOVA = {
  status: 200,
  corpo: { supported: true, available: true, version: "0.9.0", text: "texto do dialogo" },
};
const SEM_NOVIDADE = { status: 200, corpo: { supported: true, available: false } };
const INSTALA_OK = { status: 200, corpo: { ok: true } };
const CONCLUIDO = { status: 200, corpo: { state: "done", done: 1, total: 1, error: null } };

test("manual sem bundle explica que so funciona no app instalado", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": { status: 200, corpo: { supported: false, available: false } } },
  });

  await t.atualizador.checa(true);

  assert.equal(t.dialogos.length, 1);
  assert.match(t.dialogos[0].detail, /app instalado/);
});

test("automatica sem bundle fica em silencio", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": { status: 200, corpo: { supported: false, available: false } } },
  });

  await t.atualizador.checa(false);

  assert.equal(t.dialogos.length, 0);
});

test("manual sem novidade avisa que ja esta na versao mais recente", async () => {
  const t = monta({ rotas: { "GET /api/update/check": SEM_NOVIDADE } });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].detail, /mais recente/);
});

test("automatica sem novidade nao incomoda", async () => {
  const t = monta({ rotas: { "GET /api/update/check": SEM_NOVIDADE } });

  await t.atualizador.checa(false);

  assert.equal(t.dialogos.length, 0);
});

test("o parametro manual vai para o backend", async () => {
  const t = monta({ rotas: { "GET /api/update/check": SEM_NOVIDADE } });

  await t.atualizador.checa(true);
  await t.atualizador.checa(false);

  assert.deepEqual(t.chamadas, [
    "GET /api/update/check?manual=true",
    "GET /api/update/check?manual=false",
  ]);
});

test("erro de rede: manual mostra, automatica engole", async () => {
  const rotas = { "GET /api/update/check": new Error("sem rede") };

  const manual = monta({ rotas });
  await manual.atualizador.checa(true);
  assert.equal(manual.dialogos.length, 1);
  assert.match(manual.dialogos[0].detail, /sem rede/);

  const automatica = monta({ rotas });
  await automatica.atualizador.checa(false);
  assert.equal(automatica.dialogos.length, 0);
});

test("502 do backend na checagem manual mostra o motivo", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": { status: 502, corpo: { detail: "GitHub fora do ar" } },
    },
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].detail, /GitHub fora do ar/);
});

test("checagem manual com instalacao em andamento avisa em vez de oferecer", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": {
        status: 200,
        corpo: { supported: true, available: false, in_progress: true },
      },
    },
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].detail, /em andamento/);
});

test("checagem manual depois de instalar diz para reabrir o app", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": {
        status: 200,
        corpo: { supported: true, available: false, installed: true },
      },
    },
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].detail, /ja foi instalada/);
});

test("checagem automatica com instalacao em andamento fica em silencio", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": {
        status: 200,
        corpo: { supported: true, available: false, in_progress: true },
      },
    },
  });

  await t.atualizador.checa(false);

  assert.equal(t.dialogos.length, 0);
});

test("oferta automatica tem tres botoes; a manual so atualizar e fechar", async () => {
  const automatica = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });
  await automatica.atualizador.checa(false);
  assert.deepEqual(automatica.dialogos[0].buttons, [
    "Atualizar",
    "Depois",
    "Dispensar esta versao",
  ]);

  const manual = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });
  await manual.atualizador.checa(true);
  assert.deepEqual(manual.dialogos[0].buttons, ["Atualizar", "Fechar"]);
});

test("o dialogo de oferta traz a versao e o texto do backend", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].message, /0\.9\.0/);
  assert.equal(t.dialogos[0].detail, "texto do dialogo");
});

test("dispensar esta versao na checagem automatica grava a dispensa", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/dismiss": { status: 200, corpo: { ok: true } },
    },
    respostasDoDialogo: [2],
  });

  await t.atualizador.checa(false);

  assert.ok(t.chamadas.includes("POST /api/update/dismiss"));
  assert.ok(!t.chamadas.includes("POST /api/update/install"));
});

test("depois na checagem automatica NAO dispensa: a oferta volta no proximo intervalo", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(false);

  assert.ok(!t.chamadas.includes("POST /api/update/dismiss"));
  assert.ok(!t.chamadas.includes("POST /api/update/install"));
});

test("fechar na checagem manual NAO dispensa", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(true);

  assert.ok(!t.chamadas.includes("POST /api/update/dismiss"));
});

test("o install leva a versao que o usuario viu no dialogo", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": CONCLUIDO,
    },
    respostasDoDialogo: [0, 0],
  });

  await t.atualizador.checa(true);

  const i = t.chamadas.indexOf("POST /api/update/install");
  assert.deepEqual(t.corpos[i], { version: "0.9.0" });
});

test("atualizar acompanha o progresso, avisa e relanca", async () => {
  const estados = [
    { status: 200, corpo: { state: "downloading", done: 50, total: 200 } },
    { status: 200, corpo: { state: "installing", done: 200, total: 200 } },
    CONCLUIDO,
  ];
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": () => estados.shift(),
    },
    respostasDoDialogo: [0, 0],
  });

  await t.atualizador.checa(true);

  assert.deepEqual(t.barras, [0.25, 1, -1]);
  assert.match(t.dialogos[1].message, /Atualizado/);
  assert.equal(t.relancamentos(), 1);
});

test("falha de instalacao mostra o erro do backend e nao relanca", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": {
        status: 200,
        corpo: { state: "failed", error: "O macOS abriu o app de uma copia temporaria." },
      },
    },
    respostasDoDialogo: [0],
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[1].detail, /copia temporaria/);
  assert.equal(t.dialogos[1].type, "error");
  assert.equal(t.relancamentos(), 0);
  assert.equal(t.barras.at(-1), -1);
});

test("install recusado (409) mostra o motivo e nao consulta o status", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": {
        status: 409,
        corpo: { detail: "Atualizacao ja em andamento" },
      },
    },
    respostasDoDialogo: [0],
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[1].detail, /ja em andamento/);
  assert.ok(!t.chamadas.includes("GET /api/update/status"));
});

test("um erro de rede isolado no polling nao derruba a instalacao", async () => {
  const respostas = [new Error("ocupado"), CONCLUIDO];
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": () => respostas.shift(),
    },
    respostasDoDialogo: [0, 0],
  });

  await t.atualizador.checa(true);

  assert.equal(t.relancamentos(), 1);
});

test("backend que some durante a instalacao falha em segundos, nao em uma hora", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": () => new Error("ECONNREFUSED"),
    },
    respostasDoDialogo: [0],
  });

  await t.atualizador.checa(true);

  const consultas = t.chamadas.filter((c) => c === "GET /api/update/status").length;
  assert.equal(consultas, 20);
  assert.match(t.dialogos[1].detail, /deixou de responder/);
  assert.equal(t.relancamentos(), 0);
  assert.equal(t.barras.at(-1), -1);
});

test("estado idle depois de o install ser aceito conta como backend perdido", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": INSTALA_OK,
      "GET /api/update/status": {
        status: 200,
        corpo: { state: "idle", done: 0, total: 0, error: null },
      },
    },
    respostasDoDialogo: [0],
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[1].detail, /deixou de responder/);
});

test("clique no menu durante a instalacao avisa e nao abre uma segunda oferta", async () => {
  const liberaDialogo = {};
  const aberto = new Promise((resolve) => {
    liberaDialogo.resolve = resolve;
  });
  const mostrados = [];
  let primeira = true;
  const dialog = {
    showMessageBox: async (...args) => {
      const opcoes = args[args.length - 1];
      mostrados.push(opcoes);
      if (primeira) {
        primeira = false;
        await aberto; // o dialogo da oferta fica aberto
        return { response: 1 };
      }
      return { response: 0 };
    },
  };
  const chamadas = [];
  const atualizador = criaAtualizador({
    requisicao: async (metodo, caminho) => {
      chamadas.push(`${metodo} ${caminho}`);
      return NOVA;
    },
    dialog,
    janela: () => null,
    progresso: () => {},
    relancar: () => {},
    esperar: async () => {},
  });

  const primeiro = atualizador.checa(false); // a oferta do boot, com dialogo aberto
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(atualizador.emAndamento(), true);

  await atualizador.checa(true); // o clique no menu no meio

  assert.match(mostrados[1].detail, /ja esta em andamento/);
  assert.equal(chamadas.length, 1, "o segundo fluxo nem chegou ao backend");

  liberaDialogo.resolve();
  await primeiro;
  assert.equal(atualizador.emAndamento(), false);
});

/** Servidor local em porta efemera para testar o cliente HTTP de verdade. */
function sobeServidor() {
  const estado = { token: "t1", pedidos: [] };
  const servidor = http.createServer((req, res) => {
    let corpo = "";
    req.on("data", (pedaco) => {
      corpo += pedaco;
    });
    req.on("end", () => {
      estado.pedidos.push({
        metodo: req.method,
        caminho: req.url,
        token: req.headers["x-auth-token"],
        tipo: req.headers["content-type"],
        corpo,
      });
      res.setHeader("content-type", "application/json");
      if (req.url === "/api/health") {
        res.end(JSON.stringify({ ok: true, token: estado.token }));
      } else if (req.headers["x-auth-token"] !== estado.token) {
        res.statusCode = 401;
        res.end(JSON.stringify({ detail: "Token invalido" }));
      } else {
        res.end(JSON.stringify({ eco: corpo ? JSON.parse(corpo) : null }));
      }
    });
  });
  return new Promise((resolve) => {
    servidor.listen(0, "127.0.0.1", () => {
      resolve({ servidor, estado, porta: servidor.address().port });
    });
  });
}

test("cliente HTTP: o token de /api/health e buscado uma vez e reaproveitado", async () => {
  const { servidor, estado, porta } = await sobeServidor();
  try {
    const requisicao = criaRequisicao(porta);

    await requisicao("GET", "/api/update/status");
    await requisicao("GET", "/api/update/status");

    const saude = estado.pedidos.filter((p) => p.caminho === "/api/health");
    assert.equal(saude.length, 1);
    assert.ok(estado.pedidos.filter((p) => p.caminho !== "/api/health").every((p) => p.token === "t1"));
  } finally {
    servidor.close();
  }
});

test("cliente HTTP: 401 renova o token e repete o pedido uma vez", async () => {
  const { servidor, estado, porta } = await sobeServidor();
  try {
    const requisicao = criaRequisicao(porta);
    await requisicao("GET", "/api/update/status");

    estado.token = "t2"; // backend reiniciado: token novo

    const resposta = await requisicao("GET", "/api/update/status");

    assert.equal(resposta.status, 200);
    assert.equal(estado.pedidos.filter((p) => p.caminho === "/api/health").length, 2);
  } finally {
    servidor.close();
  }
});

test("cliente HTTP: o corpo vai como JSON com content-type", async () => {
  const { servidor, estado, porta } = await sobeServidor();
  try {
    const requisicao = criaRequisicao(porta);

    const resposta = await requisicao("POST", "/api/update/install", { version: "0.9.0" });

    assert.deepEqual(resposta.corpo, { eco: { version: "0.9.0" } });
    const pedido = estado.pedidos.find((p) => p.caminho === "/api/update/install");
    assert.equal(pedido.tipo, "application/json");
    assert.equal(pedido.metodo, "POST");
  } finally {
    servidor.close();
  }
});
