/**
 * Icones do transporte do player. O VolumeIcon e usado pela Revisao e pela
 * Biblioteca (uma copia so: as duas ja divergiram uma vez).
 */

/**
 * Alto-falante com duas ondas (mockup). O path antigo `M5 14v-4l6-6v12l-6-6Z`
 * voltava ao ponto de partida por um segmento diagonal e desenhava um triangulo
 * torto, nao um alto-falante; aqui o corpo e as ondas sao tracos separados.
 */
export function VolumeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <g
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      >
        <path d="M3 7.2v3.6h2.8L10 14.2V3.8L5.8 7.2H3Z" />
        <path d="M12.3 7a2.8 2.8 0 0 1 0 4" />
        <path d="M14.2 5a5.6 5.6 0 0 1 0 8" />
      </g>
    </svg>
  );
}

export function RepeatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="M3 6v6h6M15 12v6h-6M3 6h6M15 12h-6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
