/**
 * Chip da classe no inspetor da Biblioteca.
 * Usa cores via tokens CSS — nenhum hex no codigo.
 * label null vira "—" (mesmo comportamento do KeyChip).
 */
interface ClassChipProps {
  label: string | null;
}

export function ClassChip({ label }: ClassChipProps) {
  if (!label) {
    return (
      <span className="class-chip class-chip-empty" aria-label="Classe">
        —
      </span>
    );
  }

  const classeMap: Record<string, { css: string; aria: string }> = {
    "-1": { css: "class-chip-down", aria: "Lento" },
    neutra: { css: "class-chip-neutral", aria: "Neutro" },
    "+1": { css: "class-chip-up", aria: "Animado" },
  };

  const { css, aria } = classeMap[label] ?? { css: "", aria: "Desconhecido" };

  return (
    <span className={`class-chip ${css}`} aria-label={`Classe: ${aria}`}>
      {label}
    </span>
  );
}