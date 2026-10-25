import { useEffect, useRef, type ReactNode } from "react";

interface PopoverProps {
  open: boolean;
  onClose: () => void;
  /** Botao que abre; o Popover so posiciona o painel embaixo dele. */
  trigger: ReactNode;
  children: ReactNode;
  /** Lado do trigger com o qual o painel alinha a borda. */
  align?: "left" | "right";
  className?: string;
  panelClassName?: string;
}

/**
 * Painel ancorado num botao (dropdown de perfil, menu "···").
 *
 * A raiz e `position: relative` e o painel absoluto dentro dela: o overlay
 * nunca fica solto na pagina (regra 6 do AGENTS.md). Fecha com clique fora
 * ou Esc; o foco volta para o botao que abriu.
 */
export function Popover({
  open,
  onClose,
  trigger,
  children,
  align = "left",
  className = "",
  panelClassName = "",
}: PopoverProps) {
  const raizRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const onMouseDown = (e: MouseEvent) => {
      if (raizRef.current && !raizRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      onClose();
      raizRef.current?.querySelector<HTMLElement>("[data-popover-trigger]")?.focus();
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  return (
    <div ref={raizRef} className={`popover-root ${className}`.trim()}>
      {trigger}
      {open && (
        <div
          className={`popover-panel popover-panel-${align} ${panelClassName}`.trim()}
        >
          {children}
        </div>
      )}
    </div>
  );
}
