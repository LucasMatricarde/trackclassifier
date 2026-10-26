// Tipos espelhando src/trackclassifier/viewmodel.py
// Gerados a mão para manter o contrato explícito.

export interface Key {
  pitch_class: number;
  mode: "A" | "B";
  camelot: string;
  classic: string;
  camelot_number: number;
}

/**
 * De onde veio a tonalidade: a tag do arquivo, a estimativa por audio, "none"
 * (a deteccao por audio foi tentada e nao achou) ou null (nunca tentada --
 * o unico caso em que a Revisao pede a deteccao).
 */
export type KeySource = "tag" | "audio" | "none";

export interface TrackRow {
  sha1: string;
  filename: string;
  label: string | null;
  predicted: string | null;
  score: number | null;
  confidence: number | null;
  bpm: number;
  duration_s: number;
  energy_curve: number[];
  peak_offset_s: number;
  path_hint: string;
  title: string | null;
  artist: string | null;
  genre: string | null;
  album: string | null;
  cover_path: string | null;
  peaks_path: string | null;
  key: Key | null;
  key_source: KeySource | null;
  display_title: string;
}

export interface ReviewState {
  current: TrackRow | null;
  upcoming: TrackRow[];
  low_confidence: boolean;
  remaining: number;
  profiles: string[];
  active_profile: string;
}

export interface LibraryState {
  rows: TrackRow[];
  class_counts: number[];
  total: number;
  genres: string[];
  keys: string[];
}

export interface TrainingHistoryEntry {
  ts: string;
  version: string;
  n_examples: number;
  accuracy: number;
  ordinal_mae: number;
  weighted_f1: number;
}

export interface ModelState {
  accuracy: number | null;
  ordinal_mae: number | null;
  confusion: number[][] | null;
  n_examples: number;
  /** F1 ponderado pelo suporte real; null sem treino. */
  weighted_f1: number | null;
  /** [precision, recall, f1] por classe; null sem treino. */
  per_class: number[][] | null;
  /** Versao do treino ativo ("v2.1.0"); null sem treino. */
  version: string | null;
  /** ISO local do ultimo treino; null sem treino. */
  last_trained_at: string | null;
  /** Treinos recentes primeiro, <= 12. */
  history: TrainingHistoryEntry[];
  /** Delta do treino ativo vs anterior na mesma era; ausente sem comparavel. */
  deltas: Partial<Record<"accuracy" | "ordinal_mae" | "weighted_f1", number>>;
  failures: [string, string, string][];
  class_counts: number[];
  decisions_since_train: number;
  retrain_every: number;
  min_examples: number;
  train_blocked_reason: string | null;
  low_confidence: boolean;
  alpha: number | null;
  thresholds: [number, number] | null;
  extractor_name: string;
}

// WebSocket messages
export type ScanPhase = "idle" | "analisando" | "processando";

export interface ScanStatus {
  phase: ScanPhase;
  running: boolean;
}

export type WSMessage =
  | { type: "scan_phase"; phase: ScanPhase }
  | { type: "scan_progress"; done: number; total: number; current: string }
  | { type: "scan_finished"; cancelled: boolean }
  | {
      type: "states_changed";
      review: ReviewState;
      library: LibraryState;
      model: ModelState;
    }
  | { type: "retrained" }
  | { type: "peaks_ready"; sha1: string; path: string }
  | { type: "peaks_failed"; sha1: string }
  | { type: "key_ready"; sha1: string; key: Key; key_source: KeySource | null }
  | { type: "key_failed"; sha1: string }
  | { type: "profile_changed"; name: string }
  | { type: "profiles_changed" }
  | { type: "error"; message: string }
  | { type: "config_reloaded" }
  | { type: "pong" };

// Config
export interface HealthState {
  ok: boolean;
  token: string;
  configured: boolean;
}

export interface ConfigDraft {
  raw: Record<string, unknown>;
}

export interface ConfigState {
  raw: Record<string, unknown>;
  active_profile: string;
  profiles: string[];
}

/** Perfil como o servidor devolve em /api/profiles. `destDirs` usa as chaves do
 * mockup ("-1", "neutra", "+1"); `complete` e false enquanto faltam pastas. */
export interface Profile {
  id: string;
  name: string;
  inputDir: string;
  destDirs: { "-1": string; neutra: string; "+1": string };
  orgToggles: { create: boolean; move: boolean; copy: boolean };
  model: { retrainEvery: number; minPerClass: number };
  complete: boolean;
}

export interface ProfilesState {
  active: string;
  profiles: Profile[];
}

export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}

export interface ConfigStats {
  data_dir_mb: number;
  analyses: number;
  inbox_new: number;
  destinations: { up: number; neutral: number; down: number };
}
