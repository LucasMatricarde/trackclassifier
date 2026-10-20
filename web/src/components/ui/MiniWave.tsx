interface MiniWaveProps {
  energy: number[];
}

const PONTOS = 40;
const LARGURA = 120;
const ALTURA = 26;

/**
 * Miniatura da curva de energia para a linha da tabela.
 *
 * Desenha da energy_curve que ja vem no TrackRow -- sem request de peaks,
 * que e o caminho caro reservado para o waveform da Revisao. A polyline
 * amostra 40 pontos da curva normalizada pelo proprio pico.
 */
export function MiniWave({ energy }: MiniWaveProps) {
  let pico = 0;
  for (const v of energy) {
    if (v > pico) pico = v;
  }

  const pontos: string[] = [];
  for (let i = 0; i < PONTOS; i++) {
    const fracao = i / (PONTOS - 1);
    // Sem curva (track velha sem extracao nova) a linha fica reta no chao
    // em vez de quebrar o SVG com NaN.
    const indice = energy.length > 0 ? Math.floor(fracao * (energy.length - 1)) : 0;
    const valor = pico > 0 ? energy[indice] / pico : 0;
    const x = fracao * LARGURA;
    const y = ALTURA - valor * (ALTURA - 2) - 1;
    pontos.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }

  return (
    <svg
      className="mini-wave"
      viewBox={`0 0 ${LARGURA} ${ALTURA}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={pontos.join(" ")} />
    </svg>
  );
}
