/**
 * Traducao entre o TOML cru e os campos do formulario.
 *
 * Espelha SettingsDraft.from_raw do Python. O raw pode ter dois formatos: o
 * legado plano ([folders] na raiz) e o multi-perfil ([profiles.<nome>.folders]).
 * O formulario edita o perfil ativo; o raw devolvido preserva os demais
 * perfis e as chaves que a tela nao conhece.
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
  /** "Mover arquivos apos classificacao" -- persiste em model.auto_move_enabled. */
  auto_move_enabled: boolean;
  /** "Criar pastas automaticamente" -- persiste em model.create_under_root. */
  create_under_root: boolean;
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

export function draftFromRaw(raw: Dict, activeProfile: string): ConfigDraftValues {
  const profiles = dict(raw.profiles);
  const pastas =
    Object.keys(profiles).length > 0
      ? dict(dict(profiles[activeProfile]).folders)
      : dict(raw.folders);
  const modelo = dict(raw.model);
  const caminhos = dict(raw.paths);

  return {
    inbox: String(pastas.inbox ?? ""),
    up: String(pastas.up ?? ""),
    neutral: String(pastas.neutral ?? ""),
    down: String(pastas.down ?? ""),
    data_dir: String(caminhos.data_dir ?? ""),
    retrain_every: numero(modelo.retrain_every, RETRAIN_PADRAO),
    min_examples: numero(modelo.min_examples, MIN_EXEMPLOS_PADRAO),
    auto_move_enabled: booleano(modelo.auto_move_enabled),
    create_under_root: booleano(modelo.create_under_root),
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
    profiles[activeProfile] = {
      ...dict(profiles[activeProfile]),
      folders,
    };
    copia.profiles = profiles;
    copia.active_profile = activeProfile;
  } else {
    copia.folders = folders;
  }

  copia.paths = { ...dict(copia.paths), data_dir: draft.data_dir };
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
