import { useKeyNotation } from "../../hooks/useKeyNotation";
import type { Key } from "../../api/types";

const CAMELOT_COLORS: Record<number, string> = {
  1: "var(--camelot-1)",
  2: "var(--camelot-2)",
  3: "var(--camelot-3)",
  4: "var(--camelot-4)",
  5: "var(--camelot-5)",
  6: "var(--camelot-6)",
  7: "var(--camelot-7)",
  8: "var(--camelot-8)",
  9: "var(--camelot-9)",
  10: "var(--camelot-10)",
  11: "var(--camelot-11)",
  12: "var(--camelot-12)",
};

interface KeyChipProps {
  keyData: Key | null;
}

/**
 * Chip da tonalidade, colorido pela roda de Camelot.
 * Port de key_chip.py.
 */
export function KeyChip({ keyData }: KeyChipProps) {
  const { notation } = useKeyNotation();

  if (!keyData) {
    return (
      <span className="key-chip key-chip-empty" aria-label="Tonalidade">
        —
      </span>
    );
  }

  const text = notation === "camelot" ? keyData.camelot : keyData.classic;
  const color = CAMELOT_COLORS[keyData.camelot_number] || "var(--color-text-secondary)";

  return (
    <span
      className="key-chip"
      aria-label={`Tonalidade: ${text}`}
      style={{ background: color }}
    >
      {text}
    </span>
  );
}
