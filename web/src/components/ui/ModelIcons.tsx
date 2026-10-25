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

//# Icones dos titulos de painel (~26px no mockup, cor do accent) ------------

/** Desempenho por classe: tres barras finas. */
export function IconePainelBarras({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        <rect x="3" y="9" width="4" height="13" rx="2" />
        <rect x="10" y="2" width="4" height="20" rx="2" />
        <rect x="17" y="11" width="4" height="11" rx="2" />
      </g>
    </svg>
  );
}

/** Matriz de confusao: grade 2x2 de quadrados vazados. */
export function IconeGrade({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor" fillRule="evenodd">
        <path d="M2 4a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2zm3.5 1.5v2h2v-2z" />
        <path d="M13 4a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-5a2 2 0 0 1-2-2zm3.5 1.5v2h2v-2z" />
        <path d="M2 15a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2zm3.5 1.5v2h2v-2z" />
        <path d="M13 15a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-5a2 2 0 0 1-2-2zm3.5 1.5v2h2v-2z" />
      </g>
    </svg>
  );
}

/** Distribuicao das classes: pizza com fatia destacada. */
export function IconePizza({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        <path d="M11 3.1A9 9 0 1 0 20.9 13H11z" />
        <path d="M13 1.1V11h9.9A9.9 9.9 0 0 0 13 1.1z" />
      </g>
    </svg>
  );
}

/** Historico: relogio com aro aberto. */
export function IconeRelogio({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none">
        <path d="M4.2 7.5A9 9 0 1 1 3 12" />
        <path d="M3 4.5V8h3.5" strokeLinejoin="round" />
        <path d="M12 7v5.2l3.4 2.3" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/** Configuracoes: engrenagem cheia. */
export function IconeEngrenagem({ tamanho = 26 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        fillRule="evenodd"
        d="M10.3 1.8h3.4l.5 2.6a8 8 0 0 1 2 1.2l2.5-.9 1.7 3-2 1.7a8 8 0 0 1 0 2.3l2 1.7-1.7 3-2.5-.9a8 8 0 0 1-2 1.2l-.5 2.6h-3.4l-.5-2.6a8 8 0 0 1-2-1.2l-2.5.9-1.7-3 2-1.7a8 8 0 0 1 0-2.3l-2-1.7 1.7-3 2.5.9a8 8 0 0 1 2-1.2zM12 8.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8z"
      />
    </svg>
  );
}

/** Reticencias horizontais do menu de linha do historico. */
export function IconeReticencias({ tamanho = 16 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true">
      <g fill="currentColor">
        <circle cx="2.5" cy="8" r="1.5" />
        <circle cx="8" cy="8" r="1.5" />
        <circle cx="13.5" cy="8" r="1.5" />
      </g>
    </svg>
  );
}

/** Pasta dos botoes de escolher diretorio (Configuracao). */
export function IconePasta({ tamanho = 16 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M2.5 5.5A1.5 1.5 0 0 1 4 4h3.2a1.5 1.5 0 0 1 1.2.6L9.6 6.5h6.9A1.5 1.5 0 0 1 18 8v6a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 2 14V5.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Lista do titulo da sidebar de resumo (Configuracao). */
export function IconeLista({ tamanho = 20 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 20 20" aria-hidden="true">
      <g fill="currentColor">
        <rect x="2" y="3.5" width="3" height="3" rx="0.8" />
        <rect x="7" y="4" width="11" height="2" rx="1" />
        <rect x="2" y="8.5" width="3" height="3" rx="0.8" />
        <rect x="7" y="9" width="11" height="2" rx="1" />
        <rect x="2" y="13.5" width="3" height="3" rx="0.8" />
        <rect x="7" y="14" width="11" height="2" rx="1" />
      </g>
    </svg>
  );
}

/** Camadas do grupo Pastas do resumo (Configuracao). */
export function IconeCamadas({ tamanho = 18 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Disquete do item Tamanho no resumo (Configuracao). */
export function IconeDisquete({ tamanho = 14 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M5 3h8.5L18 7.5V16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M7 3v4.5h5.5V3M7 12.5h6V17H7v-4.5Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Cantos de scan do botao ESCANEAR NOVAS MUSICAS (Configuracao). */
export function IconeEscanear({ tamanho = 18 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M7 3H4a1 1 0 0 0-1 1v3M13 3h3a1 1 0 0 1 1 1v3M17 13v3a1 1 0 0 1-1 1h-3M3 13v3a1 1 0 0 0 1 1h3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}

/** Usuario: bloco "Perfil ativo" da sidebar da Configuracao. */
export function IconeUsuario({ tamanho = 22 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        <circle cx="12" cy="8" r="4.2" />
        <path d="M3.5 20.5a8.5 6.5 0 0 1 17 0z" />
      </g>
    </svg>
  );
}

/** Chevron para baixo do dropdown de perfil. */
export function IconeChevron({ tamanho = 14 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M3.5 6l4.5 4.5L12.5 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Check do item ativo da lista de perfis. */
export function IconeCheck({ tamanho = 14 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M3 8.5l3.2 3.2L13 4.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/** Mais: botao "+ Novo perfil". */
export function IconeMais({ tamanho = 14 }: IconeProps) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 3v10M3 8h10"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
