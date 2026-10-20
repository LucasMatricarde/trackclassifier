const LABELS = ["-1", "neutra", "+1"] as const;
const CLASS_NAMES = ["lento", "neutro", "animada"] as const;

interface OrdinalScaleProps {
  label: string | null;
  size?: "line" | "guess";
}

/**
 * Escala ordinal de 3 segmentos.
 * Port de ordinal_scale.py — line: 9×9 quadrados, guess: 5×20 barras.
 */
export function OrdinalScale({ label, size = "guess" }: OrdinalScaleProps) {
  const activeIndex = label ? LABELS.indexOf(label as (typeof LABELS)[number]) : -1;
  const segW = size === "guess" ? 5 : 9;
  const segH = size === "guess" ? 20 : 9;
  const gap = 3;

  return (
    <div
      className="ordinal-scale"
      role="img"
      aria-label={`Escala de classificação: ${label || "sem classificação"}`}
      style={{ gap }}
    >
      {LABELS.map((l, i) => (
        <div
          key={l}
          className={`ordinal-segment ${i === activeIndex ? `active ${CLASS_NAMES[i]}` : ""}`}
          style={{ width: segW, height: segH }}
        />
      ))}
    </div>
  );
}
