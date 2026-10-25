import { useEffect, useRef, type ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Trava o dialogo enquanto a acao corre (evita POST em duplicado). */
  busy?: boolean;
  /** Rotulo do Confirmar enquanto `busy`; o padrao e o da Revisao. */
  busyLabel?: string;
  /** Falha da acao confirmada: o dialogo segue aberto e mostra o motivo, e
   * Confirmar serve de "tentar de novo". Sem a prop, nada muda. */
  error?: string | null;
  /** Corpo extra entre a mensagem e o erro (campo de nome, checkbox...). */
  children?: ReactNode;
  /** Com `children` que tem campo, o foco inicial vai para ele em vez do
   * Cancelar. Padrao: Cancelar (acao em bloco nao se dispara por engano). */
  focoInicial?: "cancelar" | "conteudo";
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Dialogo de confirmacao modal, para acoes em bloco. Foco inicial no
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
  busyLabel = "Aprovando…",
  error = null,
  children,
  focoInicial = "cancelar",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelarRef = useRef<HTMLButtonElement | null>(null);
  const corpoRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const campo =
      focoInicial === "conteudo"
        ? corpoRef.current?.querySelector<HTMLElement>("input, button, select")
        : null;
    (campo ?? cancelarRef.current)?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // focoInicial so vale na abertura: refocar a cada render roubaria o foco
    // do campo que a pessoa esta digitando.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        {children && (
          <div className="dialog-body" ref={corpoRef}>
            {children}
          </div>
        )}
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
            disabled={busy || confirmDisabled}
            data-testid="confirm-dialog-confirm"
          >
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
