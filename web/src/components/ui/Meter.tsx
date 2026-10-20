interface MeterProps {
  value: number; // 0..1
  color?: string;
  height?: number;
  label?: string;
}

/**
 * Trilho com preenchimento proporcional.
 * Port de meter.py — mesmo comportamento, agora com CSS.
 */
export function Meter({
  value,
  color = "var(--color-text-secondary)",
  height = 8,
  label,
}: MeterProps) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      className="meter"
      role="meter"
      aria-label={label}
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ height }}
    >
      <div
        className="meter-fill"
        style={{
          width: `${clamped * 100}%`,
          background: color,
          height: "100%",
        }}
      />
    </div>
  );
}
