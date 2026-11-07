import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Garante que `TC_WEB_URL` serve o build que acabou de sair de `npm run build`.
 *
 * Por que existe: a 8765 e a porta do `dj serve` e do TrackClassifier.app
 * instalado. Se o app esta aberto, o `tests.e2e_backend` falha no bind
 * ("address already in use") e quem responde ao `/api/health` do script de
 * espera e o app, servindo o front empacotado -- antigo. Aconteceu na issue
 * #98: 18 specs "quebrados" (volume, key, onda, icone de repetir, baseline),
 * todos de features que o bundle velho nao tinha, sem nenhuma regressao real.
 * O sintoma era so falha de assercao sobre pixels e texto; a causa so
 * aparecia comparando o hash do bundle. Aqui essa comparacao vira o
 * primeiro erro da suite.
 *
 * Em dev (Vite, sem TC_WEB_URL) nao ha build servido para comparar. Para
 * apontar a suite de proposito para outro build (o shell empacotado, por
 * exemplo), `TC_WEB_SKIP_BUILD_CHECK=1`.
 */

const RAIZ_WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** O bundle principal referenciado pelo index.html (`/assets/index-<hash>.js`). */
function bundleDoIndex(html: string): string | null {
  return html.match(/\/assets\/index-[\w-]+\.js/)?.[0] ?? null;
}

export default async function globalSetup() {
  const url = process.env.TC_WEB_URL;
  if (!url || process.env.TC_WEB_SKIP_BUILD_CHECK === "1") return;

  let esperado: string | null;
  try {
    esperado = bundleDoIndex(readFileSync(resolve(RAIZ_WEB, "dist", "index.html"), "utf8"));
  } catch {
    throw new Error(
      "TC_WEB_URL esta definido mas web/dist/index.html nao existe: rode " +
        "`rm -rf web/dist web/.vite && (cd web && npm run build)` antes da suite."
    );
  }

  const resposta = await fetch(`${url}/`, { headers: { "Cache-Control": "no-cache" } });
  const servido = bundleDoIndex(await resposta.text());

  if (servido !== esperado) {
    throw new Error(
      `${url} serve o bundle ${servido ?? "(nenhum)"}, mas web/dist tem ${esperado}. ` +
        "Quase sempre e o TrackClassifier.app ou um `dj serve` antigo ocupando a porta " +
        "(`lsof -nP -iTCP:<porta> -sTCP:LISTEN`): suba o `tests.e2e_backend` numa porta livre " +
        "(ex.: 8766) e aponte TC_WEB_URL para ela."
    );
  }
}
