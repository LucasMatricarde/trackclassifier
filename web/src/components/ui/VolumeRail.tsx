import { useCallback, useRef } from "react";

interface VolumeRailProps {
  value: number; // 0-100
  onChange: (v: number) => void;
  /** Largura em px; sem ela quem manda e o CSS (`.volume-rail`, a da Revisao). */
  width?: number;
}

/**
 * Trilho de volume: traço de 2px com marcador, clicável e arrastável.
 * Port de volume_rail.py.
 */
export function VolumeRail({ value, onChange, width }: VolumeRailProps) {
  const ref = useRef<HTMLDivElement>(null);

  const valueFromX = useCallback(
    (clientX: number) => {
      const rect = ref.current?.getBoundingClientRect();
      if (!rect || rect.width <= 1) return 0;
      const x = clientX - rect.left;
      return Math.max(0, Math.min(100, Math.round((x / (rect.width - 1)) * 100)));
    },
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      onChange(valueFromX(e.clientX));

      const onMove = (ev: MouseEvent) => {
        if (ev.buttons & 1) onChange(valueFromX(ev.clientX));
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [onChange, valueFromX]
  );

  // Arredonda: quem controla o trilho guarda 0..1 e multiplica por 100, e
  // 0.3 * 100 vale 30.000000000000004 -- iria parar no aria-valuenow.
  const clamped = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div
      ref={ref}
      className="volume-rail"
      role="slider"
      aria-label="Volume"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      // Inline so quando a tela pede uma largura propria (a Biblioteca passa 100).
      // Um padrao inline aqui vencia o CSS e prendia a Revisao em 100 px.
      style={width === undefined ? undefined : { width }}
      onMouseDown={handleMouseDown}
    >
      <div className="volume-track" />
      <div className="volume-fill" style={{ width: `${clamped}%` }} />
      <div
        className="volume-marker"
        style={{ left: Math.min(clamped, 100) + "%" }}
      />
    </div>
  );
}
