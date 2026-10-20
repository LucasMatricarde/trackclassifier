interface ClassActionCardProps {
  label: string;
  detail: string;
  digit: string;
  tone: string;
  enabled: boolean;
  onClick: () => void;
}

/**
 * Card grande de decisão com atalho de teclado.
 * Port de class_action_card.py.
 */
export function ClassActionCard({
  label,
  detail,
  digit,
  tone,
  enabled,
  onClick,
}: ClassActionCardProps) {
  return (
    <button
      className={`class-action-card ${tone}`}
      disabled={!enabled}
      onClick={onClick}
      aria-label={`${digit} — Classificar como ${label}: ${detail}`}
    >
      <span className="class-action-value">{label}</span>
      <span className="class-action-detail">{detail}</span>
      <span className="class-action-kbd">{digit}</span>
    </button>
  );
}
