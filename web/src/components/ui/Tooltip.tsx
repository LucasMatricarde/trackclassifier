import { useState, useRef, useEffect, type ReactNode } from "react";

interface TooltipProps {
  /** Texto do tooltip. Se omitido/undefined, o tooltip nao e renderizado. */
  text?: string;
  /** Conteudo filho (o elemento que dispara o tooltip). */
  children: ReactNode;
  /** Atraso em ms antes de mostrar. */
  delay?: number;
}

/**
 * Tooltip simples: mostra o texto ao passar o mouse sobre o filho.
 *
 * Usa um wrapper em vez de clonar o filho porque botao desabilitado nao
 * dispara evento de mouse no Chrome -- e o botao "Cards" da Biblioteca e
 * justamente desabilitado. O wrapper recebe o hover e posiciona o balao
 * acima do elemento, centralizado e preso dentro da viewport.
 */
export function Tooltip({ text, children, delay = 200 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<number | null>(null);

  const show = () => {
    if (!text) return;
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      const wrapper = wrapperRef.current;
      const tip = tooltipRef.current;
      if (!wrapper || !tip) return;
      const rect = wrapper.getBoundingClientRect();
      const tipRect = tip.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const left = rect.left + rect.width / 2 - tipRect.width / 2;
      const clampedLeft = Math.max(8, Math.min(left, viewportWidth - tipRect.width - 8));
      setPosition({
        top: rect.top - tipRect.height - 8,
        left: clampedLeft,
      });
      setVisible(true);
    }, delay);
  };

  const hide = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <span
      className="tooltip-wrapper"
      ref={wrapperRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && text && (
        <div
          ref={tooltipRef}
          className="tooltip"
          style={{ top: position.top, left: position.left }}
          role="tooltip"
        >
          {text}
        </div>
      )}
    </span>
  );
}
