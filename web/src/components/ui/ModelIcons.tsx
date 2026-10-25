/**
 * Icones da aba Modelo, redesenhados a partir do mockup
 * (design/mockup/TrackClassifier Model Dashboard.png). Todos pintam com
 * currentColor: a cor vem do token aplicado pela classe do pai, nunca
 * daqui (nenhum hex fora de design-tokens.json).
 */

interface IconeProps {
  tamanho?: number;
}

/** Tres barras do titulo da aba: geometria medida no mockup (42x42,
 *  barras de 9px, alturas 26/42/27). */
export function IconeBarrasTitulo({ tamanho = 42 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 42 42" aria-hidden="true">
      <g fill="currentColor">
        <rect x="0" y="16" width="9" height="26" rx="4.5" />
        <rect x="16" y="0" width="9" height="42" rx="4.5" />
        <rect x="33" y="15" width="9" height="27" rx="4.5" />
      </g>
    </svg>
  );
}

/** Circulo com "i" dos cards informativos. */
export function IconeInfo({ tamanho = 20 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8.3" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M10 9v5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="10" cy="6.2" r="1" fill="currentColor" />
    </svg>
  );
}

/** Seta "abre fora" do link Saiba mais. */
export function IconeExterno({ tamanho = 12 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 12 12" aria-hidden="true">
      <path
        d="M7 1.5h3.5V5M10.5 1.5 5.5 6.5M9 7.5v2a1 1 0 0 1-1 1H2.5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h2"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Seta circular do RETREINAR (header e painel de configuracoes). */
export function IconeRefresh({ tamanho = 16 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M13.2 6.2A5.4 5.4 0 0 0 3.1 5M2.8 9.8a5.4 5.4 0 0 0 10.1 1.2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M3 2.2V5.2H6M13 13.8v-3h-3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}
