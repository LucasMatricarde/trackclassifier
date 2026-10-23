import { useCallback, useEffect, useRef, useState } from "react";
import type { TrackRow } from "../api/types";
import { getPeaksUrl } from "../api/client";
import { parseNpy, resampleBands } from "../lib/npy";
import { lerTokens, pintaBandas } from "./ui/waveform-bands";

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
// Tokens e o pintor de bandas moram em ui/waveform-bands.ts (compartilhado
// com a mini-onda da Biblioteca): aqui ficam so o fallback mono e o cache
// de ImageData da onda grande.
// ---------------------------------------------------------------------------

// Constantes do render (port de waveform_render.py)
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


function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Pintura
// ---------------------------------------------------------------------------

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
 * Canvas de waveform RGB por energia (graves=R, medios=G, agudos=B) com
 * fallback mono. Port de waveform_render.py + waveform_view.py (regua,
 * grade, pico).
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

      // Marca do pico (branco a 35%: referência, não compete com o playhead).
      // Sem rotulo "PICO m:ss": o mockup nao tem esse texto, so a linha.
      const fracaoPico = Math.min(1, Math.max(0, track.peak_offset_s / duracao));
      const xPico = Math.round(fracaoPico * width);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.beginPath();
      ctx.moveTo(xPico + 0.5, 0);
      ctx.lineTo(xPico + 0.5, height);
      ctx.stroke();
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
      // Scrim proprio: sem ele o tempo do playhead se mistura com o rotulo
      // da regua quando os dois caem no mesmo minuto.
      ctx.fillStyle = "rgba(10, 17, 25, 0.85)";
      ctx.fillRect(esquerda - 3, 0, larguraTexto + 6, 16);
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
