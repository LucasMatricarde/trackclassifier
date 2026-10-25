import { expect, test } from "@playwright/test";
import { draftFromRaw, rawFromDraft } from "../src/configDraft";

/**
 * Testes puros do draft de configuracao (web/src/configDraft.ts) -- nao
 * abrem pagina, rodam direto no worker do Playwright, como model-unit.
 *
 * Os toggles da secao "Organizacao automatica" precisam round-trippar pelo
 * TOML cru: o auto-save aplica o raw inteiro a cada edicao, e um valor que
 * nao sobrevive ao rawFromDraft/draftFromRaw seria silenciosamente zerado.
 */

const RAW = {
  folders: {
    inbox: "/musicas/entrada",
    up: "/musicas/+1",
    neutral: "/musicas/neutra",
    down: "/musicas/-1",
  },
  paths: { data_dir: "/dados" },
  model: { retrain_every: 10, min_examples: 50 },
};

test.describe("draftFromRaw", () => {
  test("le os toggles de organizacao automatica do model", () => {
    const draft = draftFromRaw(
      { ...RAW, model: { ...RAW.model, auto_move_enabled: true, create_under_root: true } },
      "default"
    );
    expect(draft.auto_move_enabled).toBe(true);
    expect(draft.create_under_root).toBe(true);
  });

  test("toggles ausentes caem em false", () => {
    const draft = draftFromRaw(RAW, "default");
    expect(draft.auto_move_enabled).toBe(false);
    expect(draft.create_under_root).toBe(false);
  });
});

test.describe("rawFromDraft", () => {
  test("grava os toggles em model e preserva as chaves que ja existiam", () => {
    const draft = draftFromRaw(RAW, "default");
    const raw = rawFromDraft(
      { ...RAW, model: { ...RAW.model, outra_chave: "preserva" } },
      "default",
      { ...draft, auto_move_enabled: true, create_under_root: true }
    );
    const model = raw.model as Record<string, unknown>;
    expect(model.auto_move_enabled).toBe(true);
    expect(model.create_under_root).toBe(true);
    expect(model.outra_chave).toBe("preserva");
    expect(model.retrain_every).toBe(10);
  });

  test("round-trip mantem os toggles", () => {
    const draft = draftFromRaw(RAW, "default");
    const ligado = { ...draft, auto_move_enabled: true, create_under_root: true };
    const de_volta = draftFromRaw(rawFromDraft(RAW, "default", ligado), "default");
    expect(de_volta.auto_move_enabled).toBe(true);
    expect(de_volta.create_under_root).toBe(true);
  });
});
