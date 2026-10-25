/**
 * Decisoes de ciclo de vida do shell que nao dependem do Electron.
 *
 * Moram aqui, e nao inline no main.js, porque o main.js nao tem como rodar sem
 * o Electron e foi justamente nelas que a revisao achou erro: o aviso de saida
 * disparava em qualquer fase do fluxo de update, e um backend que caiu era
 * diagnosticado como "servidor reaproveitado". Como funcoes puras, o
 * `node --test` pega regressao.
 */

/**
 * Sair durante a TROCA do .app deixa o ditto orfao e um temporario oculto ao
 * lado do app. A primeira tentativa so avisa; a segunda sai, para um backend
 * travado nao prender o usuario num app que nao fecha.
 *
 * `instalando` e so a instalacao (download + troca), nao a checagem nem o
 * dialogo de oferta aberto: bloquear a saida ali dava um aviso falso e deixava
 * o app vivo sem janela.
 */
function bloqueiaSaida({ instalando, jaAvisou }) {
  return Boolean(instalando) && !jaAvisou;
}

/**
 * O que o menu "Buscar atualizacoes..." faz.
 *  - "reaproveitado": o shell achou um servidor que ja estava no ar (ex.:
 *    `npm start` com outro app aberto) e nao e dono dele; atualizar trocaria o
 *    .app do outro processo.
 *  - "parou": o backend DESTE shell morreu; nenhum update funciona ate reabrir.
 *  - "checar": o caso normal.
 */
function acaoDoMenu({ reaproveitado, backendVivo }) {
  if (reaproveitado) return "reaproveitado";
  if (!backendVivo) return "parou";
  return "checar";
}

/** A checagem automatica do boot so faz sentido com backend proprio e vivo. */
function checaNoBoot({ smoke, reaproveitado, backendVivo }) {
  return !smoke && !reaproveitado && Boolean(backendVivo);
}

module.exports = { bloqueiaSaida, acaoDoMenu, checaNoBoot };
