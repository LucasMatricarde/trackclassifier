import type { Page } from "@playwright/test";
import type { LibraryState, ModelState } from "../src/api/types";
import { fakeWebSocket } from "./review-fixtures";

/**
 * Fixtures da aba Biblioteca para os testes deterministicos.
 *
 * Mesmo contrato das fixtures de Revisao: o WebSocket e falso e o estado
 * vem de rotas mockadas, entao o backend real nao participa do teste.
 */

const MODELO_VAZIO: ModelState = {
  accuracy: null,
  ordinal_mae: null,
  confusion: null,
  n_examples: 0,
  failures: [],
  class_counts: [0, 0, 0],
  decisions_since_train: 0,
  retrain_every: 20,
  train_blocked_reason: null,
  low_confidence: false,
  alpha: null,
  thresholds: null,
  extractor_name: "teste",
};

export const FIXTURE_VAZIA: LibraryState = {
  rows: [],
  class_counts: [0, 0, 0],
  total: 0,
  genres: [],
  keys: [],
};

/**
 * Manda o app para a aba Biblioteca sem depender do backend: o health
 * responde "configurado" e o estado da biblioteca vem do fixture.
 */
export async function mockLibrary(page: Page, state: LibraryState) {
  await fakeWebSocket(page);
  // Sem health configurada o App cai na tela de setup antes da aba existir;
  // sem model/state o AppHeader depende do backend real (teste nao hermetico).
  await page.route("**/api/health*", (route) =>
    route.fulfill({ json: { ok: true, token: "token-teste", configured: true } })
  );
  await page.route("**/api/library/state*", (route) =>
    route.fulfill({ json: state })
  );
  await page.route("**/api/model/state*", (route) =>
    route.fulfill({ json: MODELO_VAZIO })
  );
}
