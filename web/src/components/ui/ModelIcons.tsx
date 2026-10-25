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

//# Icones dos KPI cards (desenhados no tile 53x53 do mockup) -----------------

/** Exemplos rotulados: pilha de discos (banco de dados). */
export function IconeBanco({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        <ellipse cx="12" cy="5.5" rx="8" ry="3" />
        <path d="M4 8.6c1.6 1.4 4.6 2.2 8 2.2s6.4-.8 8-2.2v3.2c0 1.7-3.6 3-8 3s-8-1.3-8-3z" />
        <path d="M4 14.4c1.6 1.4 4.6 2.2 8 2.2s6.4-.8 8-2.2v3.6c0 1.7-3.6 3-8 3s-8-1.3-8-3z" />
      </g>
    </svg>
  );
}

/** Acuracia: alvo com seta. */
export function IconeAlvo({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none">
        <path d="M20.2 9.6A8.6 8.6 0 1 1 14.4 3.8" />
        <path d="M15.8 11.2a4 4 0 1 1-3-3" />
        <path d="M12 12l6.5-6.5" />
        <path d="M16.2 3.6v4.2h4.2" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/** Erro ordinal: tres barras verticais. */
export function IconeBarras({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        <rect x="3.5" y="10" width="4.2" height="11" rx="1.4" />
        <rect x="9.9" y="3" width="4.2" height="18" rx="1.4" />
        <rect x="16.3" y="8" width="4.2" height="13" rx="1.4" />
      </g>
    </svg>
  );
}

/** Score F1: raio. */
export function IconeRaio({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13.6 2 4.8 13.4h6.1L9.6 22l9.6-12.2h-6.3z" fill="currentColor" />
    </svg>
  );
}
