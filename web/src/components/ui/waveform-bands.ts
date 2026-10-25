/**
 * Pintor compartilhado da onda RGB, extraido de WaveformCanvas para que a
 * mini-onda da Biblioteca (RowWaveform) renderize EXATAMENTE como a onda
 * grande da Revisao: a cor de cada coluna E a energia das tres bandas --
 * graves no canal R, medios no G, agudos no B, com piso e ganhos dos
 * tokens waveband.* (port de _cores/render_bands do waveform_render.py da UI Qt
 * antiga). A mistura por coluna e o que da o matiz proprio de
 * cada track do mockup (grave+medio puxa laranja, agudo puxa azul/violeta,
 * grave+agudo puxa rosa) -- em vez da paleta fixa por banda, que pintava
 * toda track com os mesmos verde/vermelho/azul.
 *
 * O pintor escreve so os pixels das barras: o fundo (cor ou transparencia)
 * e decisao de quem chama -- a Revisao preenche com surface-waveform, a
 * linha da tabela deixa transparente para o fundo da <tr> aparecer.
 */

export interface WaveTokens {
  accent: [number, number, number];
  bg: [number, number, number];
  playhead: string;
  grid: string;
  scrim: string;
  textoSecundario: string;
  textoPrimario: string;
  floor: number;
  gainLow: number;
  gainMid: number;
  gainHigh: number;
  saturation: number;
}

function hexRgb(valor: string, fallback: [number, number, number]) {
  const hex = valor.trim().replace("#", "");
  if (hex.length !== 6) return fallback;
  return [
    parseInt(hex.slice(0, 2), 16),
    parseInt(hex.slice(2, 4), 16),
    parseInt(hex.slice(4, 6), 16),
  ] as [number, number, number];
}

let tokensCache: WaveTokens | null = null;

export function lerTokens(): WaveTokens {
  if (tokensCache) return tokensCache;
  const css = getComputedStyle(document.documentElement);
  const v = (nome: string, fallback: string) =>
    css.getPropertyValue(nome).trim() || fallback;
  tokensCache = {
    accent: hexRgb(v("--color-accent-base", "#6979fb"), [105, 121, 251]),
    bg: hexRgb(v("--color-surface-waveform", "#0c151f"), [12, 21, 31]),
    playhead: v("--color-waveband-playhead", "#ffffff"),
    grid: v("--color-waveband-grid", "rgba(255,255,255,0.08)"),
    scrim: v("--color-bg", "#0a1119"),
    textoSecundario: v("--color-text-secondary", "#afbcd2"),
    textoPrimario: v("--color-text-primary", "#f0f4ff"),
    floor: Number(v("--color-waveband-floor", "0.06")),
    gainLow: Number(v("--color-waveband-low-gain", "1")),
    gainMid: Number(v("--color-waveband-mid-gain", "0.92")),
    gainHigh: Number(v("--color-waveband-high-gain", "1")),
    saturation: Number(v("--color-waveband-saturation", "1.25")),
  };
  return tokensCache;
}

// Constantes do render (port de waveform_render.py)
const WEIGHTS = [0.55, 0.3, 0.15];
const GAIN_HEIGHT = 1.5;

/**
 * Desenha a onda RGB: cada coluna recebe UMA cor, a energia das tres
 * bandas mapeada nos canais R/G/B (port de _cores). A altura continua
 * sendo a envoltoria ponderada de waveform_render.py (0.55/0.30/0.15 x
 * 1.5): graves pesam mais porque e o que da a silhueta reconhecivel de
 * uma track.
 *
 * O piso (waveband.floor) existe para uma banda zerada nao virar preto
 * absoluto: uma coluna so de graves ficaria vermelho puro sobre fundo
 * escuro e sumiria nas bordas -- com o piso ela mantem um minimo de
 * presenca nos outros canais.
 */
export function pintaBandas(
  data: Uint8ClampedArray,
  W: number,
  H: number,
  bandas: Float32Array,
  barras: number,
  passo: number,
  barW: number,
  tok: WaveTokens
) {
  const canal = (valor: number, ganho: number) =>
    Math.round(
      Math.min(1, tok.floor + (1 - tok.floor) * Math.min(1, Math.max(0, valor)) * ganho) * 255
    );

  for (let i = 0; i < barras; i++) {
    const l = bandas[i * 3];
    const m = bandas[i * 3 + 1];
    const h = bandas[i * 3 + 2];

    const amp = Math.min(
      1,
      Math.max(0, (l * WEIGHTS[0] + m * WEIGHTS[1] + h * WEIGHTS[2]) * GAIN_HEIGHT)
    );
    const barH = Math.max(1, amp * H);
    if (l + m + h <= 1e-6) continue;

    const r = canal(l, tok.gainLow);
    const g = canal(m, tok.gainMid);
    const b = canal(h, tok.gainHigh);

    // +25% de saturacao preservando o matiz: Y + s*(c-Y), clip 0..255.
    // Plano mais escuro (l m h desequilibrados) nao muda o matiz por track,
    // so afasta o RGB do cinavo do piso -- sobe a diferenca dos canais
    // dominantes, atraindo os picos a tons de ciano e rosa do mockup.
    const s = tok.saturation;
    const y = 0.299 * r + 0.587 * g + 0.114 * b;
    const rp = Math.round(Math.min(255, Math.max(0, y + s * (r - y))));
    const gp = Math.round(Math.min(255, Math.max(0, y + s * (g - y))));
    const bp = Math.round(Math.min(255, Math.max(0, y + s * (b - y))));

    // Barra espelhada no centro vertical, como o render mono.
    const y0 = Math.max(0, Math.floor((H - barH) / 2));
    const y1 = Math.min(H, y0 + Math.ceil(barH));
    const x0 = i * passo;
    const x1 = Math.min(W, x0 + barW);
    for (let py = y0; py < y1; py++) {
      for (let px = x0; px < x1; px++) {
        const idx = (py * W + px) * 4;
        data[idx] = rp;
        data[idx + 1] = gp;
        data[idx + 2] = bp;
        data[idx + 3] = 255;
      }
    }
  }
}
