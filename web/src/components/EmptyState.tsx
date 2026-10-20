interface EmptyStateProps {
  title: string;
  subtitle: string;
  actionLabel: string;
  onAction: () => void;
}

/**
 * Estado vazio da aba Revisão.
 * Port de empty_state.py (simplificado).
 */
export function EmptyState({
  title,
  subtitle,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h2 className="empty-title">{title}</h2>
      <p className="empty-subtitle muted">{subtitle}</p>
      <button className="btn-primary" onClick={onAction}>
        {actionLabel}
      </button>
    </div>
  );
}
