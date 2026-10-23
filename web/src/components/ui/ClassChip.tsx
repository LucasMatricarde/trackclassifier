import type { TrackRow } from "../../api/types";

interface ClassChipProps {
  /** Label da classe: "-1", "neutra", "+1" ou null. */
  label: TrackRow["label"];
}

/**
 * Chip de classe da tabela: badge preenchido com a cor da classe.
 *
 * Cores (conforme mockup e tokens):
 * - neutra: bg = --color-classification-neutro-base (#FFC652), texto escuro
 * - +1:     bg = --color-classification-animada-bg (#3B202C), texto = --color-classification-animada-text (#FF8795)
 * - -1:     bg = --color-classification-lento-bg (#1A2E50), texto = --color-classification-lento-text (#91B1FF)
 */
export function ClassChip({ label }: ClassChipProps) {
  if (!label) {
    return (
      <span className="class-chip class-chip-empty" aria-label="Sem classe">
        —
      </span>
    );
  }

  let className = "class-chip";
  let ariaLabel = `Classe: ${label}`;

  if (label === "neutra") {
    className += " class-chip-neutral";
    ariaLabel = "Classe: neutra";
  } else if (label === "+1") {
    className += " class-chip-up";
    ariaLabel = "Classe: animada";
  } else if (label === "-1") {
    className += " class-chip-down";
    ariaLabel = "Classe: lenta";
  }

  return (
    <span className={className} aria-label={ariaLabel}>
      {label}
    </span>
  );
}