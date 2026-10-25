import { useEffect, useRef } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Trava o dialogo enquanto a acao corre (evita POST em duplicado). */
  busy?: boolean;
  /** Falha da acao confirmada: o dialogo segue aberto e mostra o motivo, e
   * Confirmar serve de "tentar de novo". Sem a prop, nada muda. */
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Dialogo de confirmacao modal.
 *
 * Port do QMessageBox.question do Qt para acoes em bloco. Foco inicial no
 * cancelar: a acao confirmada mexe em varios arquivos de uma vez, e o
 * teclado e o caminho mais rapido para dispará-la por engano.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  busy = false,
  error = null,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelarRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    cancelarRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      className="dialog-backdrop"
      // So o clique no fundo fecha: clicar dentro do dialogo nao pode
      // cancelar a acao.
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        data-testid="confirm-dialog"
      >
        <h2 className="dialog-title" id="dialog-title">
          {title}
        </h2>
        <p className="dialog-message">{message}</p>
        {error && (
          <p
            className="dialog-error"
            role="alert"
            data-testid="confirm-dialog-error"
          >
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            ref={cancelarRef}
            type="button"
            className="btn-secondary"
            onClick={onCancel}
            disabled={busy}
            data-testid="confirm-dialog-cancel"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={onConfirm}
            disabled={busy}
            data-testid="confirm-dialog-confirm"
          >
            {busy ? "Aprovando…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
