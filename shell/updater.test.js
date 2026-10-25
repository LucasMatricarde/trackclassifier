/**
 * Testes do fluxo de atualizacao do shell. Rodam com `npm test` (node --test),
 * sem Electron e sem rede: HTTP e dialogos sao falsos.
 */

const test = require("node:test");
const assert = require("node:assert/strict");

const { criaAtualizador } = require("./updater");

/** Monta um atualizador com respostas roteirizadas por "METODO caminho". */
function monta({ rotas, respostasDoDialogo = [] }) {
  const chamadas = [];
  const dialogos = [];
  const barras = [];
  let relancou = 0;
  const fila = [...respostasDoDialogo];

  const requisicao = async (metodo, caminho) => {
    chamadas.push(`${metodo} ${caminho}`);
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
    dialogos,
    barras,
    relancamentos: () => relancou,
  };
}

const NOVA = {
  status: 200,
  corpo: { supported: true, available: true, version: "0.9.0", text: "texto do dialogo" },
};

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
  const t = monta({
    rotas: { "GET /api/update/check": { status: 200, corpo: { supported: true, available: false } } },
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].detail, /mais recente/);
});

test("automatica sem novidade nao incomoda", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": { status: 200, corpo: { supported: true, available: false } } },
  });

  await t.atualizador.checa(false);

  assert.equal(t.dialogos.length, 0);
});

test("o parametro manual vai para o backend", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": { status: 200, corpo: { supported: true, available: false } } },
  });

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

test("agora nao na checagem automatica dispensa a versao", async () => {
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/dismiss": { status: 200, corpo: { ok: true } },
    },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(false);

  assert.ok(t.chamadas.includes("POST /api/update/dismiss"));
  assert.ok(!t.chamadas.includes("POST /api/update/install"));
});

test("agora nao na checagem manual NAO dispensa", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(true);

  assert.ok(!t.chamadas.includes("POST /api/update/dismiss"));
});

test("o dialogo de oferta traz a versao e o texto do backend", async () => {
  const t = monta({
    rotas: { "GET /api/update/check": NOVA },
    respostasDoDialogo: [1],
  });

  await t.atualizador.checa(true);

  assert.match(t.dialogos[0].message, /0\.9\.0/);
  assert.equal(t.dialogos[0].detail, "texto do dialogo");
  assert.deepEqual(t.dialogos[0].buttons, ["Atualizar", "Agora nao"]);
});

test("atualizar acompanha o progresso, avisa e relanca", async () => {
  const estados = [
    { status: 200, corpo: { state: "downloading", done: 50, total: 200 } },
    { status: 200, corpo: { state: "installing", done: 200, total: 200 } },
    { status: 200, corpo: { state: "done", done: 200, total: 200, error: null } },
  ];
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": { status: 200, corpo: { ok: true } },
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
      "POST /api/update/install": { status: 200, corpo: { ok: true } },
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

test("um erro de rede no polling nao derruba a instalacao", async () => {
  const respostas = [
    new Error("ocupado"),
    { status: 200, corpo: { state: "done", done: 1, total: 1, error: null } },
  ];
  const t = monta({
    rotas: {
      "GET /api/update/check": NOVA,
      "POST /api/update/install": { status: 200, corpo: { ok: true } },
      "GET /api/update/status": () => respostas.shift(),
    },
    respostasDoDialogo: [0, 0],
  });

  await t.atualizador.checa(true);

  assert.equal(t.relancamentos(), 1);
});
