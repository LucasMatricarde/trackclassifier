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

/**
 * Multi-perfil: modelo e organizacao sao do PERFIL. O auto-save aplica o raw
 * inteiro, entao editar o perfil ativo nao pode vazar valor para os outros.
 */
const RAW_MULTI = {
  active_profile: "b",
  profiles: {
    a: {
      name: "Alfa",
      folders: { inbox: "/a/in", up: "/a/+1", neutral: "/a/0", down: "/a/-1" },
      model: { retrain_every: 11, min_examples: 12 },
      organization: { create: true, move: false, copy: false },
    },
    b: {
      name: "Beta",
      folders: { inbox: "/b/in", up: "/b/+1", neutral: "/b/0", down: "/b/-1" },
      model: { retrain_every: 21, min_examples: 22 },
      organization: { create: false, move: true, copy: true },
    },
  },
  paths: { data_dir: "/dados" },
  model: { retrain_every: 21, min_examples: 22 },
};

test.describe("multi-perfil", () => {
  test("draftFromRaw le modelo e organizacao do perfil pedido", () => {
    const a = draftFromRaw(RAW_MULTI, "a");
    const b = draftFromRaw(RAW_MULTI, "b");
    expect([a.retrain_every, a.min_examples]).toEqual([11, 12]);
    expect([b.retrain_every, b.min_examples]).toEqual([21, 22]);
    expect([a.create_under_root, a.auto_move_enabled, a.keep_copy]).toEqual([true, false, false]);
    expect([b.create_under_root, b.auto_move_enabled, b.keep_copy]).toEqual([false, true, true]);
    expect(a.inbox).toBe("/a/in");
    expect(b.data_dir).toBe("/dados"); // paths e global
  });

  test("perfil sem tabela propria herda o [model] global, chave a chave", () => {
    const raw = {
      profiles: {
        a: {
          folders: { inbox: "/i", up: "/u", neutral: "/n", down: "/d" },
          model: { retrain_every: 3 },
        },
      },
      model: { retrain_every: 50, min_examples: 8, auto_move_enabled: true },
    };
    const d = draftFromRaw(raw, "a");
    expect(d.retrain_every).toBe(3);
    expect(d.min_examples).toBe(8);
    expect(d.auto_move_enabled).toBe(true);
    expect(d.keep_copy).toBe(false);
  });

  test("rawFromDraft grava so no perfil ativo e preserva nome e o outro perfil", () => {
    const draft = { ...draftFromRaw(RAW_MULTI, "b"), retrain_every: 99, keep_copy: false };
    const raw = rawFromDraft(RAW_MULTI, "b", draft) as typeof RAW_MULTI;
    expect(raw.profiles.b.model).toEqual({ retrain_every: 99, min_examples: 22 });
    expect(raw.profiles.b.organization).toEqual({ create: false, move: true, copy: false });
    expect(raw.profiles.b.name).toBe("Beta");
    expect(raw.profiles.a).toEqual(RAW_MULTI.profiles.a); // intocado
    expect(raw.active_profile).toBe("b");
  });

  test("round-trip por perfil nao vaza entre perfis", () => {
    const editado = rawFromDraft(RAW_MULTI, "a", {
      ...draftFromRaw(RAW_MULTI, "a"),
      min_examples: 77,
      keep_copy: true,
    });
    expect(draftFromRaw(editado, "a").min_examples).toBe(77);
    expect(draftFromRaw(editado, "a").keep_copy).toBe(true);
    expect(draftFromRaw(editado, "b").min_examples).toBe(22);
    expect(draftFromRaw(editado, "b").keep_copy).toBe(true);
  });

  test("formato plano: keep_copy da a volta pela [organization] da raiz", () => {
    const ligado = { ...draftFromRaw(RAW, "default"), keep_copy: true };
    const raw = rawFromDraft(RAW, "default", ligado);
    expect(draftFromRaw(raw, "default").keep_copy).toBe(true);
  });
});
