import { useEffect } from "react";

/**
 * Mapeamento de teclado da aba Revisão (window.py):
 * 1/2/3 → decide, Backspace/Ctrl+Z → undo, Space → play/pause,
 * S/→ → skip, ← → back, D → remove.
 *
 * Só captura quando o foco NÃO está num input/textarea (mesmo motivo
 * do Qt: não roubar digitação da busca).
 *
 * Todos os handlers sao opcionais para que cada aba passe so o que precisa.
 */
export interface KeyboardHandlers {
  onDecide?: (label: number) => void;
  onUndo?: () => void;
  onTogglePlay?: () => void;
  onSkip?: () => void;
  onBack?: () => void;
  onRemove?: () => void;
}

export function useKeyboard(handlers: KeyboardHandlers, enabled = true) {
  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (e: KeyboardEvent) => {
      // Não rouba teclas de inputs
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      // Ctrl+Z / Cmd+Z (undo) — funciona em qualquer lugar
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        handlers.onUndo?.();
        return;
      }

      switch (e.key) {
        case "1":
          handlers.onDecide?.(-1);
          break;
        case "2":
          handlers.onDecide?.(0);
          break;
        case "3":
          handlers.onDecide?.(1);
          break;
        case "Backspace":
          handlers.onUndo?.();
          break;
        case " ":
          e.preventDefault();
          handlers.onTogglePlay?.();
          break;
        case "s":
        case "S":
        case "ArrowRight":
          handlers.onSkip?.();
          break;
        case "ArrowLeft":
          handlers.onBack?.();
          break;
        case "d":
        case "D":
          handlers.onRemove?.();
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handlers, enabled]);
}