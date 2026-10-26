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

/**
 * Repetir: circulo aberto de duas setas curvas (mockup, ~17x16 px em x 668-684).
 * O desenho antigo (`M3 6v6h6M15 12v6h-6M3 6h6M15 12h-6`) eram dois "L" soltos,
 * sem curva nenhuma. Aqui cada seta e um arco de raio 7 (180 -> -40 graus) mais
 * a ponta em "L" no fim do arco, e a segunda e a primeira girada 180 graus em
 * torno do centro (9, 9). O contorno e o do VolumeIcon: traco 1,5, pontas e
 * juntas redondas.
 */
export function RepeatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <g
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      >
        <path d="M2 9a7 7 0 0 1 12.4-4.5M14.4 1.5v3h-3" />
        <path d="M16 9a7 7 0 0 1-12.4 4.5M3.6 16.5v-3h3" />
      </g>
    </svg>
  );
}
