/**
 * Icones do transporte da Revisao. Mesmo desenho (viewBox 18, traco 1.5) dos
 * que a Biblioteca usa inline em LibraryTransport: a Biblioteca e tela
 * congelada, entao ela continua com a copia dela ate alguem pedir o refactor.
 */
export function VolumeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="M5 14v-4l6-6v12l-6-6ZM14 4v10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
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
