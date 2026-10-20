// Tipos espelhando src/trackclassifier/ui/viewmodel.py
// Gerados a mão para manter o contrato explícito.

export interface Key {
  pitch_class: number;
  mode: "A" | "B";
  camelot: string;
  classic: string;
  camelot_number: number;
}

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

export interface ModelState {
  accuracy: number | null;
  ordinal_mae: number | null;
  confusion: number[][] | null;
  n_examples: number;
  failures: [string, string, string][];
  class_counts: number[];
  decisions_since_train: number;
  retrain_every: number;
  train_blocked_reason: string | null;
  low_confidence: boolean;
  alpha: number | null;
  thresholds: [number, number] | null;
  extractor_name: string;
}

// WebSocket messages
export type WSMessage =
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
  | { type: "profile_changed"; name: string }
  | { type: "error"; message: string }
  | { type: "config_reloaded" }
  | { type: "pong" };

// Config
export interface ConfigDraft {
  raw: Record<string, unknown>;
}

export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}
