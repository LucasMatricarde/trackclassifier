import { useCallback, useEffect, useRef, useState } from "react";
import { getPeaksUrl } from "../../api/client";
import { parseNpy, resampleBands } from "../../lib/npy";
import { lerTokens, pintaBandas } from "./waveform-bands";

interface RowWaveformProps {
  trackSha1: string;
  /** Largura em px da onda na celula (aprox 240 no mockup). */
  width?: number;
  /** Altura em px. */
  height?: number;
  /** Offset do pico em segundos (para a linha branca do pico). */
  peakOffset?: number;
  /** Duracao total em segundos (para normalizar o pico). */
  duration?: number;
}

/**
 * Mini-waveform da linha da tabela: MESMO renderizador da onda grande da
 * Revisao (pintaBandas de waveform-bands.ts) -- uma cor RGB por coluna,
 * dada pela energia das tres bandas (graves=R, medios=G, agudos=B),
 * espelhada no centro. O fundo fica transparente para a cor da <tr>
 * (hover/selecao) aparecer atras das barras.
 *
 * Carregamento preguiçoso via IntersectionObserver: so busca e decodifica o
 * .npy quando a linha entra no viewport. Isso evita estourar a rede/memoria
 * em bibliotecas grandes.
 *
 * Opcionalmente desenha a linha branca do pico (peakOffset / duration).
 */
export function RowWaveform({
  trackSha1,
  width = 240,
  height = 40,
  peakOffset,
  duration,
}: RowWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const [peaks, setPeaks] = useState<Float32Array | null>(null);
  const [error, setError] = useState(false);

  const fetchPeaks = useCallback(async () => {
    if (peaks || error) return;
    try {
      const url = getPeaksUrl(trackSha1);
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const buffer = await res.arrayBuffer();
      const data = parseNpy(buffer);
      if (!data) throw new Error("Parse falhou");
      setPeaks(data);
    } catch {
      setError(true);
    }
  }, [trackSha1, peaks, error]);

  // IntersectionObserver para lazy load
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            fetchPeaks();
            observerRef.current?.unobserve(canvas);
            break;
          }
        }
      },
      { rootMargin: "100px" } // comeca a carregar 100px antes de entrar
    );

    observerRef.current.observe(canvas);
    return () => observerRef.current?.disconnect();
  }, [fetchPeaks]);

  // Render no canvas quando peaks chegam
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks) return;

    const ctx = canvas.getContext("2d", { willReadFrequently: false });
    if (!ctx) return;

    // Render em pixels FISICOS via ImageData, como a onda grande: em tela
    // retina, desenhar em unidades CSS com ctx.scale sairia borrado.
    const dpr = window.devicePixelRatio || 1;
    const W = Math.max(1, Math.round(width * dpr));
    const H = Math.max(1, Math.round(height * dpr));
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    // ImageData novo vem transparente: o fundo da <tr> aparece atras.
    const imageData = ctx.createImageData(W, H);

    // 1px CSS por barra (a mesma densidade que a celula sempre teve; a
    // onda grande usa 2px porque tem largura de sobra).
    const barW = Math.max(1, Math.round(dpr));
    const barras = Math.max(1, Math.floor(W / barW));
    const bandas = resampleBands(peaks, barras);
    pintaBandas(imageData.data, W, H, bandas, barras, barW, barW, lerTokens());

    ctx.putImageData(imageData, 0, 0);

    // Linha do pico (peak marker) - mesma cor do WaveformCanvas (branco 35%)
    if (
      typeof peakOffset === "number" &&
      typeof duration === "number" &&
      duration > 0
    ) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const fracaoPico = Math.min(1, Math.max(0, peakOffset / duration));
      const xPico = Math.round(fracaoPico * width);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xPico + 0.5, 0);
      ctx.lineTo(xPico + 0.5, height);
      ctx.stroke();
    }
  }, [peaks, width, height, peakOffset, duration]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="row-waveform"
      aria-label={error ? "Erro ao carregar onda" : "Mini onda da faixa"}
    />
  );
}