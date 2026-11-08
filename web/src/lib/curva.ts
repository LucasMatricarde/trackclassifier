/**
 * Resample da energy_curve (mono) para as barras da onda.
 *
 * A curva tem UMA entrada por janela do extrator (features._window_plan:
 * janela = min(10s, duracao/3), salto = janela/2), e a entrada k descreve o
 * trecho de k*salto a k*salto + janela -- centrado em janela/2 + k*salto.
 * Esticar a curva de ponta a ponta (k/(N-1) * largura) punha a primeira
 * entrada em 0s e a ultima na duracao inteira, deslocando a onda em ate meia
 * janela (5s numa track normal) em relacao ao playhead. Aqui cada barra
 * pergunta a curva pelo valor no TEMPO dela.
 */

/** Espelha MAX_WINDOW_SECONDS de features.py. */
const MAX_JANELA_S = 10;

function planoDeJanelas(duracaoS: number): { janela: number; salto: number } {
  const janela = Math.min(MAX_JANELA_S, duracaoS / 3);
  return { janela, salto: janela / 2 };
}

export function resampleCurva(
  curve: Float32Array,
  bars: number,
  duracaoS: number
): Float32Array {
  if (bars <= 0) return new Float32Array(0);
  const out = new Float32Array(bars);
  const n = curve.length;
  if (n === 0) return out;
  if (n === 1) {
    out.fill(curve[0]);
    return out;
  }
  if (!(duracaoS > 0)) {
    // Sem duracao nao ha eixo de tempo: cai no esticamento de ponta a ponta.
    for (let i = 0; i < bars; i++) {
      const pos = bars === 1 ? 0 : (i / (bars - 1)) * (n - 1);
      const lo = Math.floor(pos);
      const hi = Math.min(lo + 1, n - 1);
      out[i] = curve[lo] * (1 - (pos - lo)) + curve[hi] * (pos - lo);
    }
    return out;
  }

  const { janela, salto } = planoDeJanelas(duracaoS);
  // Posicao fracionaria na curva do instante t, presa nas pontas: antes do
  // centro da primeira janela e depois do da ultima vale o valor da borda.
  const posicaoEm = (t: number) =>
    Math.min(n - 1, Math.max(0, (t - janela / 2) / salto));

  if (n <= bars) {
    for (let i = 0; i < bars; i++) {
      const pos = posicaoEm(((i + 0.5) / bars) * duracaoS);
      const lo = Math.floor(pos);
      const hi = Math.min(lo + 1, n - 1);
      out[i] = curve[lo] * (1 - (pos - lo)) + curve[hi] * (pos - lo);
    }
    return out;
  }

  // Mais pontos que barras: maximo das janelas cujo centro cai na barra
  // (mesma regra do render: media achataria o ataque). Barra sem centro
  // dentro usa a janela mais proxima.
  for (let i = 0; i < bars; i++) {
    const posIni = posicaoEm((i / bars) * duracaoS);
    const posFim = posicaoEm(((i + 1) / bars) * duracaoS);
    const ini = Math.ceil(posIni);
    const fim = Math.floor(posFim);
    if (ini > fim) {
      out[i] = curve[Math.round((posIni + posFim) / 2)];
      continue;
    }
    let max = 0;
    for (let j = ini; j <= fim; j++) if (curve[j] > max) max = curve[j];
    out[i] = max;
  }
  return out;
}
