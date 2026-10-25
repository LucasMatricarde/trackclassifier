/**
 * Traducao entre o TOML cru e os campos do formulario.
 *
 * Espelha SettingsDraft.from_raw do Python. O raw pode ter dois formatos: o
 * legado plano ([folders] na raiz) e o multi-perfil ([profiles.<id>.folders],
 * [profiles.<id>.model], [profiles.<id>.organization]). O formulario edita o
 * perfil ativo; o raw devolvido preserva os demais perfis e as chaves que a
 * tela nao conhece. Modelo e organizacao sao POR PERFIL; so `paths` (cache,
 * capas, banco) e global.
 *
 * Sem React de proposito: e o que permite testar o round-trip so
 * com objetos.
 */

export interface ConfigDraftValues {
  inbox: string;
  up: string;
  neutral: string;
  down: string;
  data_dir: string;
  retrain_every: number;
  min_examples: number;
  /** "Mover arquivos apos classificacao" -- organization.move do perfil. */
  auto_move_enabled: boolean;
  /** "Criar pastas automaticamente" -- organization.create do perfil. */
  create_under_root: boolean;
  /** "Manter uma copia na entrada" -- organization.copy do perfil. */
  keep_copy: boolean;
}

type Dict = Record<string, unknown>;

const RETRAIN_PADRAO = 10;
const MIN_EXEMPLOS_PADRAO = 15;
const NUMERO_MINIMO = 1;
const NUMERO_MAXIMO = 1000;

function isRecord(value: unknown): value is Dict {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function dict(value: unknown): Dict {
  return isRecord(value) ? value : {};
}

function numero(value: unknown, padrao: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return padrao;
  return Math.max(NUMERO_MINIMO, Math.min(NUMERO_MAXIMO, Math.trunc(value)));
}

function booleano(value: unknown): boolean {
  return value === true;
}

/** `tabela[chave]` quando existe; senao o valor de heranca (o [model] global
 * do formato antigo). Mesma regra de _ajustes_do_perfil do Python. */
function ou(tabela: Dict, chave: string, heranca: unknown): unknown {
  return chave in tabela ? tabela[chave] : heranca;
}

export function draftFromRaw(raw: Dict, activeProfile: string): ConfigDraftValues {
  const profiles = dict(raw.profiles);
  const multi = Object.keys(profiles).length > 0;
  const perfil = multi ? dict(profiles[activeProfile]) : {};
  const pastas = multi ? dict(perfil.folders) : dict(raw.folders);
  const modeloGlobal = dict(raw.model);
  const modelo = dict(perfil.model);
  // Plano: [organization] na raiz faz o papel da tabela do perfil.
  const org = dict(multi ? perfil.organization : raw.organization);
  const caminhos = dict(raw.paths);

  return {
    inbox: String(pastas.inbox ?? ""),
    up: String(pastas.up ?? ""),
    neutral: String(pastas.neutral ?? ""),
    down: String(pastas.down ?? ""),
    data_dir: String(caminhos.data_dir ?? ""),
    retrain_every: numero(
      ou(modelo, "retrain_every", modeloGlobal.retrain_every),
      RETRAIN_PADRAO
    ),
    min_examples: numero(
      ou(modelo, "min_examples", modeloGlobal.min_examples),
      MIN_EXEMPLOS_PADRAO
    ),
    auto_move_enabled: booleano(ou(org, "move", modeloGlobal.auto_move_enabled)),
    create_under_root: booleano(ou(org, "create", modeloGlobal.create_under_root)),
    keep_copy: booleano(org.copy),
  };
}

export function rawFromDraft(
  raw: Dict,
  activeProfile: string,
  draft: ConfigDraftValues
): Dict {
  // structuredClone nao existe no node antigo do CI? JSON e suficiente: o
  // raw e so TOML (strings, numeros, listas e tabelas).
  const copia = JSON.parse(JSON.stringify(raw)) as Dict;
  const folders = {
    inbox: draft.inbox,
    up: draft.up,
    neutral: draft.neutral,
    down: draft.down,
  };

  const profiles = dict(copia.profiles);
  if (Object.keys(profiles).length > 0) {
    const atual = dict(profiles[activeProfile]);
    profiles[activeProfile] = {
      ...atual,
      folders,
      model: {
        ...dict(atual.model),
        retrain_every: draft.retrain_every,
        min_examples: draft.min_examples,
      },
      organization: {
        ...dict(atual.organization),
        create: draft.create_under_root,
        move: draft.auto_move_enabled,
        copy: draft.keep_copy,
      },
    };
    copia.profiles = profiles;
    copia.active_profile = activeProfile;
  } else {
    copia.folders = folders;
    copia.organization = {
      ...dict(copia.organization),
      create: draft.create_under_root,
      move: draft.auto_move_enabled,
      copy: draft.keep_copy,
    };
  }

  copia.paths = { ...dict(copia.paths), data_dir: draft.data_dir };
  // [model] global: no formato plano e a unica casa; no multi-perfil e so o
  // espelho do ativo (o servidor grava o mesmo), que ainda serve de heranca
  // para um perfil que nao tenha tabela propria.
  copia.model = {
    ...dict(copia.model),
    retrain_every: draft.retrain_every,
    min_examples: draft.min_examples,
    auto_move_enabled: draft.auto_move_enabled,
    create_under_root: draft.create_under_root,
  };
  return copia;
}

export function mudou(
  original: ConfigDraftValues,
  atual: ConfigDraftValues
): boolean {
  return (Object.keys(original) as (keyof ConfigDraftValues)[]).some(
    (chave) => original[chave] !== atual[chave]
  );
}
