const test = require("node:test");
const assert = require("node:assert/strict");

const { acaoDoMenu, bloqueiaSaida, checaNoBoot, devePerguntarMover } = require("./lifecycle");

test("sair durante a instalacao avisa na primeira tentativa e deixa sair na segunda", () => {
  assert.equal(bloqueiaSaida({ instalando: true, jaAvisou: false }), true);
  assert.equal(bloqueiaSaida({ instalando: true, jaAvisou: true }), false);
});

test("sair fora da instalacao nunca e bloqueado (checagem e oferta aberta nao contam)", () => {
  assert.equal(bloqueiaSaida({ instalando: false, jaAvisou: false }), false);
  assert.equal(bloqueiaSaida({ instalando: undefined, jaAvisou: false }), false);
});

test("menu: backend reaproveitado e backend proprio que morreu sao diagnosticos diferentes", () => {
  assert.equal(acaoDoMenu({ reaproveitado: true, backendVivo: false }), "reaproveitado");
  assert.equal(acaoDoMenu({ reaproveitado: true, backendVivo: true }), "reaproveitado");
  assert.equal(acaoDoMenu({ reaproveitado: false, backendVivo: false }), "parou");
  assert.equal(acaoDoMenu({ reaproveitado: false, backendVivo: true }), "checar");
});

test("checagem do boot: so com backend proprio e vivo, e nunca no smoke", () => {
  assert.equal(checaNoBoot({ smoke: false, reaproveitado: false, backendVivo: true }), true);
  assert.equal(checaNoBoot({ smoke: true, reaproveitado: false, backendVivo: true }), false);
  assert.equal(checaNoBoot({ smoke: false, reaproveitado: true, backendVivo: true }), false);
  assert.equal(checaNoBoot({ smoke: false, reaproveitado: false, backendVivo: false }), false);
});

test("oferta de mover pra Aplicativos: so empacotado, no macOS, fora do smoke e fora de Aplicativos", () => {
  assert.equal(
    devePerguntarMover({ plataforma: "darwin", empacotado: true, smoke: false, naPastaDeApps: false }),
    true
  );
  assert.equal(
    devePerguntarMover({ plataforma: "win32", empacotado: true, smoke: false, naPastaDeApps: false }),
    false
  );
  assert.equal(
    devePerguntarMover({ plataforma: "darwin", empacotado: false, smoke: false, naPastaDeApps: false }),
    false
  );
  assert.equal(
    devePerguntarMover({ plataforma: "darwin", empacotado: true, smoke: true, naPastaDeApps: false }),
    false
  );
  assert.equal(
    devePerguntarMover({ plataforma: "darwin", empacotado: true, smoke: false, naPastaDeApps: true }),
    false
  );
});
