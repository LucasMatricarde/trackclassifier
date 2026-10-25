/**
 * Icones da aba Modelo, redesenhados a partir do mockup
 * (design/mockup/TrackClassifier Model Dashboard.png). Todos pintam com
 * currentColor: a cor vem do token aplicado pela classe do pai, nunca
 * daqui (nenhum hex fora de design-tokens.json).
 */

interface IconeProps {
  tamanho?: number;
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
