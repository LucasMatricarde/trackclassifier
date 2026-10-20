import { useCallback, useEffect, useRef, useState } from "react";
import type { TrackRow } from "../api/types";
import { getPeaksUrl } from "../api/client";

interface WaveformCanvasProps {
  track: TrackRow | null;
  progress: number; // 0..1
  onSeek?: (fraction: number) => void;
  height?: number;
  className?: string;
  /** Regua de tempo, grade e marca de pico (so na onda grande da Revisao). */
  ruler?: boolean;
  /** Buckets ficaram prontos depois do ultimo states_changed. */
  peaksReady?: boolean;
  /** So energy_curve: nao pede nem busca buckets (linhas da fila). */
  energyOnly?: boolean;
  /** Mini-onda do overview: imagem a 55% + retangulo da janela corrente,
   * sem grade/regua/playhead (port de _MiniOnda do waveform_overview.py). */
  windowBox?: boolean;
}

// ---------------------------------------------------------------------------
// Tokens (lidos do CSS uma vez; o CSS e a fonte da verdade)
// ---------------------------------------------------------------------------

interface WaveTokens {
  low: [number, number, number];
  mid: [number, number, number];
  high: [number, number, number];
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

function lerTokens(): WaveTokens {
  if (tokensCache) return tokensCache;
  const css = getComputedStyle(document.documentElement);
  const v = (nome: string, fallback: string) =>
    css.getPropertyValue(nome).trim() || fallback;
  tokensCache = {
    low: hexRgb(v("--color-waveband-low", "#f4556d"), [244, 85, 109]),
    mid: hexRgb(v("--color-waveband-mid", "#3dd68c"), [61, 214, 140]),
    high: hexRgb(v("--color-waveband-high", "#45b7e0"), [69, 183, 224]),
    accent: hexRgb(v("--color-accent-base", "#7887ff"), [120, 135, 255]),
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
  };
  return tokensCache;
}

// Constantes do render (port de waveform_render.py)
const WEIGHTS = [0.55, 0.3, 0.15];
const GAIN_HEIGHT = 1.5;
const BAR_WIDTH = 2;

// Cache LRU de ImageData por (sha1, largura física, altura física)
const cache = new Map<string, ImageData>();
const CACHE_MAX = 256;

function cacheKey(sha1: string, w: number, h: number, temBandas: boolean) {
  // O modo (mono -> bandas) entra na chave: o primeiro render acontece
  // antes dos buckets chegarem, e sem ele a imagem mono ficaria cacheada
  // para sempre -- a onda nunca sairia do fallback.
  return `${sha1}:${w}:${h}:${temBandas ? "b" : "m"}`;
}

function cacheGet(key: string): ImageData | undefined {
  const v = cache.get(key);
  if (v) {
    cache.delete(key);
    cache.set(key, v); // move to end
  }
  return v;
}

function cacheSet(key: string, value: ImageData) {
  cache.set(key, value);
  if (cache.size > CACHE_MAX) {
    const first = cache.keys().next().value;
    if (first) cache.delete(first);
  }
}

/** Resample mono: máximo por bucket, interpolação quando a curva é menor. */
function resample(curve: Float32Array, bars: number): Float32Array {
  if (bars <= 0 || curve.length === 0) return new Float32Array(bars);
  if (curve.length <= bars) {
    const out = new Float32Array(bars);
    if (curve.length === 1) {
      out.fill(curve[0]);
      return out;
    }
    // np.interp: estica, não repete a borda (ver waveform_render.py)
    for (let i = 0; i < bars; i++) {
      const pos = (i / (bars - 1)) * (curve.length - 1);
      const lo = Math.floor(pos);
      const hi = Math.min(lo + 1, curve.length - 1);
      const t = pos - lo;
      out[i] = curve[lo] * (1 - t) + curve[hi] * t;
    }
    return out;
  }
  const out = new Float32Array(bars);
  for (let i = 0; i < bars; i++) {
    const start = Math.floor((i / bars) * curve.length);
    const end = Math.floor(((i + 1) / bars) * curve.length);
    let max = 0;
    for (let j = start; j < end; j++) {
      if (curve[j] > max) max = curve[j];
    }
    out[i] = max;
  }
  return out;
}

/** Resample de bandas: (N,3) → (bars,3) pelo máximo; edge quando menor. */
function resampleBands(peaks: Float32Array, bars: number): Float32Array {
  const n = peaks.length / 3;
  if (bars <= 0 || n === 0) return new Float32Array(bars * 3);
  if (n <= bars) {
    const out = new Float32Array(bars * 3);
    for (let i = 0; i < bars; i++) {
      const srcIdx = Math.min(i, n - 1);
      out[i * 3] = peaks[srcIdx * 3];
      out[i * 3 + 1] = peaks[srcIdx * 3 + 1];
      out[i * 3 + 2] = peaks[srcIdx * 3 + 2];
    }
    return out;
  }
  const out = new Float32Array(bars * 3);
  for (let i = 0; i < bars; i++) {
    const start = Math.floor((i / bars) * n);
    const end = Math.floor(((i + 1) / bars) * n);
    let maxL = 0, maxM = 0, maxH = 0;
    for (let j = start; j < end; j++) {
      const l = peaks[j * 3], m = peaks[j * 3 + 1], h = peaks[j * 3 + 2];
      if (l > maxL) maxL = l;
      if (m > maxM) maxM = m;
      if (h > maxH) maxH = h;
    }
    out[i * 3] = maxL;
    out[i * 3 + 1] = maxM;
    out[i * 3 + 2] = maxH;
  }
  return out;
}

/** Parse .npy file (float16, shape (N,3)) → Float32Array */
function parseNpy(buffer: ArrayBuffer): Float32Array | null {
  try {
    const view = new DataView(buffer);
    if (view.getUint8(0) !== 0x93) return null;
    const major = view.getUint8(6);
    // v1: header_len uint16 em 8; v2+: uint32 em 8
    const headerLen = major >= 2 ? view.getUint32(8, true) : view.getUint16(8, true);
    const headerStart = major >= 2 ? 12 : 10;
    const headerEnd = headerStart + headerLen;
    const headerStr = new TextDecoder().decode(
      new Uint8Array(buffer, headerStart, headerLen)
    );

    const shapeMatch = headerStr.match(/'shape':\s*\((\d+),\s*(\d+)\)/);
    if (!shapeMatch) return null;
    const rows = parseInt(shapeMatch[1], 10);
    const cols = parseInt(shapeMatch[2], 10);
    const fortran = /'fortran_order':\s*True/.test(headerStr);

    const dataView = new DataView(buffer, headerEnd);
    const total = rows * cols;
    const out = new Float32Array(total);
    for (let i = 0; i < total; i++) {
      const bits = dataView.getUint16(i * 2, true);
      const sign = (bits & 0x8000) ? -1 : 1;
      const exp = (bits & 0x7c00) >> 10;
      const frac = bits & 0x03ff;
      let valor: number;
      if (exp === 0) {
        valor = sign * frac * Math.pow(2, -24);
      } else if (exp === 31) {
        valor = frac ? NaN : sign * Infinity;
      } else {
        valor = sign * (1 + frac / 1024) * Math.pow(2, exp - 15);
      }
      if (fortran) {
        const linha = i % rows;
        const coluna = Math.floor(i / rows);
        out[linha * cols + coluna] = valor;
      } else {
        out[i] = valor;
      }
    }
    return out;
  } catch {
    return null;
  }
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Pintura
// ---------------------------------------------------------------------------

/**
 * Desenha a onda espectral empilhada: dentro de cada coluna, os graves
 * ocupam a base, os medios o meio e os agudos o topo, com cor fixa por
 * banda (design-tokens waveband.*). O brilho de cada segmento escala com a
 * energia, para que banda fraca nao pinte colorido: vira quase-preto.
 *
 * A altura total continua sendo a envoltoria ponderada de
 * waveform_render.py (0.55/0.30/0.15 x 1.5), mas em vez de misturar as
 * bandas num RGB unico por coluna, cada uma vira um segmento proprio --
 * e o que o mockup mostra e o que o token descreve para a v0.5.
 */
function pintaBandas(
  data: Uint8ClampedArray,
  W: number,
  H: number,
  bandas: Float32Array,
  barras: number,
  passo: number,
  barW: number,
  tok: WaveTokens
) {
  const metade = H / 2;
  for (let i = 0; i < barras; i++) {
    const l = bandas[i * 3];
    const m = bandas[i * 3 + 1];
    const h = bandas[i * 3 + 2];

    const amp = Math.min(
      1,
      Math.max(0, (l * WEIGHTS[0] + m * WEIGHTS[1] + h * WEIGHTS[2]) * GAIN_HEIGHT)
    );
    const barH = Math.max(1, amp * H);
    const soma = l + m + h;
    if (soma <= 1e-6) continue;

    // Segmentos proporcionais: banda forte ganha mais altura na coluna.
    const hLow = (barH * l) / soma;
    const hMid = (barH * m) / soma;
    const hHigh = (barH * h) / soma;

    const brilho = (valor: number, ganho: number) =>
      Math.min(1, tok.floor + (1 - tok.floor) * Math.min(1, valor * ganho));

    const cores: Array<[number, number, number, number]> = [
      [hLow, tok.low[0], tok.low[1], tok.low[2]],
      [hMid, tok.mid[0], tok.mid[1], tok.mid[2]],
      [hHigh, tok.high[0], tok.high[1], tok.high[2]],
    ];
    const brilhos = [
      brilho(l, tok.gainLow),
      brilho(m, tok.gainMid),
      brilho(h, tok.gainHigh),
    ];

    // Base do segmento: fundo da coluna; sobe desenhando low -> mid -> high.
    let yBase = metade + barH / 2;
    const x0 = i * passo;
    const x1 = Math.min(W, x0 + barW);

    for (let seg = 0; seg < 3; seg++) {
      const alturaSeg = cores[seg][0];
      if (alturaSeg <= 0) continue;
      const b = brilhos[seg];
      const r = Math.round(cores[seg][1] * b);
      const g = Math.round(cores[seg][2] * b);
      const bl = Math.round(cores[seg][3] * b);
      const yTop = Math.max(0, Math.floor(yBase - alturaSeg));
      const yBot = Math.min(H, Math.ceil(yBase));
      for (let py = yTop; py < yBot; py++) {
        for (let px = x0; px < x1; px++) {
          const idx = (py * W + px) * 4;
          data[idx] = r;
          data[idx + 1] = g;
          data[idx + 2] = bl;
          data[idx + 3] = 255;
        }
      }
      yBase -= alturaSeg;
    }
  }
}

function pintaMono(
  data: Uint8ClampedArray,
  W: number,
  H: number,
  curva: Float32Array,
  barras: number,
  passo: number,
  barW: number,
  cor: [number, number, number]
) {
  const amostras = resample(curva, barras);
  let maxVal = 1e-9;
  for (let i = 0; i < amostras.length; i++) {
    if (amostras[i] > maxVal) maxVal = amostras[i];
  }
  for (let i = 0; i < barras; i++) {
    const amp = Math.min(1, Math.max(0, amostras[i] / maxVal));
    const barH = Math.max(1, amp * H);
    const y = Math.floor((H - barH) / 2);
    const x0 = i * passo;
    const x1 = Math.min(W, x0 + barW);
    for (let py = y; py < y + barH && py < H; py++) {
      for (let px = x0; px < x1; px++) {
        const idx = (py * W + px) * 4;
        data[idx] = cor[0];
        data[idx + 1] = cor[1];
        data[idx + 2] = cor[2];
        data[idx + 3] = 255;
      }
    }
  }
}

/**
 * Canvas de waveform com bandas empilhadas e fallback mono.
 * Port de waveform_render.py + waveform_view.py (regua, grade, pico).
 */
export function WaveformCanvas({
  track,
  progress,
  onSeek,
  height = 120,
  className,
  ruler = false,
  peaksReady = false,
  energyOnly = false,
  windowBox = false,
}: WaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [peaks, setPeaks] = useState<Float32Array | null>(null);

  const hasPeaks = !energyOnly && (Boolean(track?.peaks_path) || peaksReady);

  // Observer de tamanho
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(Math.floor(entry.contentRect.width));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Carrega peaks quando ficam disponiveis para a track
  useEffect(() => {
    if (!track || !hasPeaks) {
      setPeaks(null);
      return;
    }
    let cancelled = false;
    fetch(getPeaksUrl(track.sha1))
      .then((r) => (r.ok ? r.arrayBuffer() : null))
      .then((buf) => {
        if (!cancelled) setPeaks(buf ? parseNpy(buf) : null);
      })
      .catch(() => {
        if (!cancelled) setPeaks(null);
      });
    return () => {
      cancelled = true;
    };
  }, [track?.sha1, hasPeaks]);

  // Render
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !track || width === 0) return;
    const tok = lerTokens();

    const dpr = window.devicePixelRatio || 1;
    const W = Math.max(1, Math.round(width * dpr));
    const H = Math.max(1, Math.round(height * dpr));
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const key = cacheKey(track.sha1, W, H, Boolean(peaks && peaks.length > 0));
    let imageData = cacheGet(key);

    if (!imageData) {
      imageData = ctx.createImageData(W, H);
      const data = imageData.data;

      for (let i = 0; i < W * H; i++) {
        data[i * 4] = tok.bg[0];
        data[i * 4 + 1] = tok.bg[1];
        data[i * 4 + 2] = tok.bg[2];
        data[i * 4 + 3] = 255;
      }

      // Largura de barra em pixels FÍSICOS: o render é 1:1 com o canvas,
      // senão em tela retina a onda sairia no quadrante superior esquerdo.
      const barW = Math.max(1, Math.round(BAR_WIDTH * dpr));
      const barras = Math.max(1, Math.floor(W / barW));

      if (peaks && peaks.length > 0) {
        const bandas = resampleBands(peaks, barras);
        pintaBandas(data, W, H, bandas, barras, barW, barW, tok);
      } else if (track.energy_curve.length > 0) {
        const curva = new Float32Array(track.energy_curve);
        pintaMono(data, W, H, curva, barras, barW, barW, tok.accent);
      }

      cacheSet(key, imageData);
    }

    if (windowBox) {
      // putImageData ignora globalAlpha (substitui pixels), entao a opacidade
      // de 55% da mini-onda sai via canvas offscreen + drawImage sobre o
      // fundo repintado.
      const off = document.createElement("canvas");
      off.width = W;
      off.height = H;
      off.getContext("2d")!.putImageData(imageData, 0, 0);
      ctx.fillStyle = `rgb(${tok.bg[0]},${tok.bg[1]},${tok.bg[2]})`;
      ctx.fillRect(0, 0, W, H);
      ctx.globalAlpha = 0.55;
      ctx.drawImage(off, 0, 0);
      ctx.globalAlpha = 1;

      // Retangulo da janela corrente: largura de 1/6 da track (min 24px),
      // centrado no playhead e preso nas bordas, acento a 18% + borda
      // secundaria -- mesmo desenho do _MiniOnda.paintEvent.
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const wbox = Math.max(24, width / 6);
      const esquerda = Math.min(
        Math.max(0, width - wbox),
        Math.max(0, progress * width - wbox / 2)
      );
      ctx.fillStyle = `rgba(${tok.accent[0]},${tok.accent[1]},${tok.accent[2]},0.18)`;
      ctx.fillRect(esquerda, 1, wbox, height - 2);
      ctx.strokeStyle = tok.textoSecundario;
      ctx.lineWidth = 1;
      ctx.strokeRect(esquerda + 0.5, 1.5, wbox - 1, height - 3);
      return;
    }

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.putImageData(imageData, 0, 0);

    // Overlays em unidades CSS
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Grade de compasso (32 barras de 2px)
    const passoGrade = BAR_WIDTH * 32;
    if (passoGrade > 0) {
      ctx.strokeStyle = tok.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = passoGrade; x < width; x += passoGrade) {
        ctx.moveTo(x + 0.5, 0);
        ctx.lineTo(x + 0.5, height);
      }
      ctx.stroke();
    }

    const duracao = track.duration_s;

    if (ruler && duracao > 0) {
      // Régua de tempo no topo, sobre scrim
      const fonte = '11px "JetBrains Mono", "SF Mono", Consolas, monospace';
      ctx.font = fonte;
      ctx.textBaseline = "top";
      const alturaScrim = 17;
      ctx.fillStyle = `rgba(10, 17, 25, 0.82)`;
      ctx.fillRect(0, 0, width, alturaScrim);

      // Canvas nao resolve var() -- fillStyle com var() e ignorado
      // silenciosamente. Usa a cor ja resolvida via getComputedStyle.
      ctx.fillStyle = tok.textoSecundario;
      const slots = Math.max(1, Math.floor(width / 75));
      const intervalo = Math.max(
        60,
        (Math.floor(Math.floor(duracao / slots) / 60) + 1) * 60
      );
      for (let s = 0; s <= duracao; s += intervalo) {
        const texto = formatDuration(s);
        const larguraTexto = ctx.measureText(texto).width;
        let x = Math.round((s / duracao) * width);
        x = Math.min(Math.max(3, x), Math.max(3, width - larguraTexto - 3));
        ctx.fillText(texto, x, 3);
      }

      // Marca do pico (branco a 35%: referência, não compete com o playhead)
      const fracaoPico = Math.min(1, Math.max(0, track.peak_offset_s / duracao));
      const xPico = Math.round(fracaoPico * width);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.beginPath();
      ctx.moveTo(xPico + 0.5, 0);
      ctx.lineTo(xPico + 0.5, height);
      ctx.stroke();

      const textoPico = `PICO ${formatDuration(fracaoPico * duracao)}`;
      const larguraPico = ctx.measureText(textoPico).width;
      let esquerda = xPico + 5;
      if (esquerda + larguraPico + 10 > width) {
        esquerda = xPico - 5 - larguraPico - 10;
      }
      ctx.fillStyle = "rgba(10, 17, 25, 0.82)";
      ctx.fillRect(esquerda - 5, height - 21, larguraPico + 10, 17);
      ctx.fillStyle = tok.textoPrimario;
      ctx.fillText(textoPico, esquerda, height - 18);
    }

    // Playhead + tempo corrente
    const x = Math.round(progress * width);
    ctx.strokeStyle = tok.playhead;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, height);
    ctx.stroke();

    if (ruler && duracao > 0) {
      const texto = formatDuration(progress * duracao);
      ctx.font = '11px "JetBrains Mono", "SF Mono", Consolas, monospace';
      ctx.textBaseline = "top";
      const larguraTexto = ctx.measureText(texto).width;
      let esquerda = x + 5;
      if (esquerda + larguraTexto > width) esquerda = x - 5 - larguraTexto;
      ctx.fillStyle = tok.playhead;
      ctx.fillText(texto, esquerda, 3);
    }
  }, [track, peaks, width, height, progress, ruler, windowBox]);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!onSeek || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const fraction = (e.clientX - rect.left) / rect.width;
      onSeek(Math.max(0, Math.min(1, fraction)));
    },
    [onSeek]
  );

  return (
    <div ref={containerRef} className={`waveform-canvas ${className || ""}`}>
      <canvas ref={canvasRef} onClick={handleClick} />
    </div>
  );
}
