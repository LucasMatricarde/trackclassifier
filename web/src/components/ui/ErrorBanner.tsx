interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  /** Prefixo dos testids: "review-error" e "review-error-dismiss". */
  testId?: string;
}

/**
 * Banner de erro das acoes da aba.
 *
 * Antes o erro ficava guardado no hook e nunca aparecia: uma decisao que
 * falhava no backend sumia em silencio. O banner e o unico lugar onde a
 * falha chega ao usuario.
 */
export function ErrorBanner({
  message,
  onDismiss,
  testId = "review-error",
}: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert" data-testid={testId}>
      <span className="error-banner-text">{message}</span>
      {onDismiss && (
        <button
          type="button"
          className="error-banner-dismiss"
          onClick={onDismiss}
          data-testid={`${testId}-dismiss`}
          aria-label="Fechar aviso"
        >
          ×
        </button>
      )}
    </div>
  );
}
