import { useCallback, useRef } from "react";

interface VolumeRailProps {
  value: number; // 0-100
  onChange: (v: number) => void;
  width?: number;
}

/**
 * Trilho de volume: traço de 2px com marcador, clicável e arrastável.
 * Port de volume_rail.py.
 */
export function VolumeRail({ value, onChange, width = 100 }: VolumeRailProps) {
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
      style={{ width }}
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
