import { useEffect, useRef, useState } from "react";
import { getPeaksUrl } from "../../api/client";
import { parseNpy, resampleBands } from "../../lib/npy";

interface InspectorWaveformProps {
  trackSha1: string;
  /** Largura em px da onda (full card width ~236). */
  width?: number;
  /** Altura em px. Mockup: ~68px. */
  height?: number;
  /** Offset do pico em segundos (para a linha branca do pico). */
  peakOffset?: number;
  /** Duracao total em segundos (para normalizar o pico e labels de tempo). */
  duration?: number;
  /** Progresso atual 0..1 (para o playhead branco). */
  progress?: number;
}

/**
 * Waveform do inspetor: barras densas estilo RowWaveform + playhead de progresso
 * + marker de pico + labels de tempo 0:00 / duracao.
 *
 * Diferente do RowWaveform da tabela: nao usa IntersectionObserver (o inspetor
 * ja esta visivel), e desenha a linha de progresso + labels de tempo.
 */
export function InspectorWaveform({
  trackSha1,
  width = 236,
  height = 68,
  peakOffset,
  duration,
  progress = 0,
}: InspectorWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Resultado do fetch junto do sha1 de origem (data null = falhou). O
  // LibraryInspector reaproveita esta instancia ao trocar a linha selecionada
  // (nao ha `key`), entao o state sobrevive a troca de track: o fetch antigo
  // saia cedo por `if (peaks)` e o inspetor ficava com a onda da primeira
  // faixa selecionada. Resultado de outro sha1 vale como "ainda nao chegou".
  const [carga, setCarga] = useState<{
    sha1: string;
    data: Float32Array | null;
  } | null>(null);
  const daTrack = carga?.sha1 === trackSha1;
  const peaks = daTrack ? carga.data : null;
  const error = daTrack && carga.data === null;

  // Carrega imediatamente (sem lazy load, pois o inspetor ja esta na tela).
  // Refaz a cada sha1; `cancelled` descarta resposta de uma selecao ja trocada.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let data: Float32Array | null = null;
      try {
        const res = await fetch(getPeaksUrl(trackSha1));
        data = res.ok ? parseNpy(await res.arrayBuffer()) : null;
      } catch {
        data = null;
      }
      if (!cancelled) setCarga({ sha1: trackSha1, data });
    })();
    return () => {
      cancelled = true;
    };
  }, [trackSha1]);

  // Render no canvas quando peaks chegam
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (!peaks) {
      // Entre uma selecao e a chegada dos peaks dela, o desenho anterior seria
      // a onda de OUTRA faixa: limpa em vez de deixar o resto na tela.
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    const ctx = canvas.getContext("2d", { willReadFrequently: false });
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Fundo transparente
    ctx.clearRect(0, 0, width, height);

    if (!peaks || peaks.length === 0) return;

    // Resample para a largura do canvas (1 barra por px = mockup density)
    const barras = Math.max(1, width);
    const bandas = resampleBands(peaks, barras);

    // Ler tokens CSS das cores das bandas
    const style = getComputedStyle(canvas);
    const lowColor = style.getPropertyValue("--color-waveband-low").trim() || "#F4556D";
    const midColor = style.getPropertyValue("--color-waveband-mid").trim() || "#3DD68C";
    const highColor = style.getPropertyValue("--color-waveband-high").trim() || "#45B7E0";

    const hexToRgb = (hex: string): [number, number, number] => {
      const h = hex.replace("#", "");
      return [
        parseInt(h.slice(0, 2), 16),
        parseInt(h.slice(2, 4), 16),
        parseInt(h.slice(4, 6), 16),
      ];
    };

    const lowRgb = hexToRgb(lowColor);
    const midRgb = hexToRgb(midColor);
    const highRgb = hexToRgb(highColor);

    // Pesos da envoltoria (iguais a RowWaveform)
    const WEIGHTS = [0.55, 0.30, 0.15];
    const GAIN_HEIGHT = 1.3;
    const center = height / 2;
    const barWidth = width / barras;

    for (let i = 0; i < barras; i++) {
      const l = bandas[i * 3];
      const m = bandas[i * 3 + 1];
      const h = bandas[i * 3 + 2];

      const amp = Math.min(
        1,
        Math.max(0, (l * WEIGHTS[0] + m * WEIGHTS[1] + h * WEIGHTS[2]) * GAIN_HEIGHT)
      );
      const barH = Math.max(1, amp * height);

      const soma = l + m + h;
      let r: number, g: number, b: number;
      if (soma > 1e-6) {
        r = (l * lowRgb[0] + m * midRgb[0] + h * highRgb[0]) / soma;
        g = (l * lowRgb[1] + m * midRgb[1] + h * highRgb[1]) / soma;
        b = (l * lowRgb[2] + m * midRgb[2] + h * highRgb[2]) / soma;
      } else {
        [r, g, b] = midRgb;
      }
      const maxC = Math.max(r, g, b);
      const minC = Math.min(r, g, b);
      const saturacao = maxC - minC;
      if (saturacao < 40) {
        if (l >= m && l >= h) {
          [r, g, b] = lowRgb;
        } else if (m >= h) {
          [r, g, b] = midRgb;
        } else {
          [r, g, b] = highRgb;
        }
      }

      const x = i * barWidth;
      const yTop = Math.max(0, Math.floor(center - barH / 2));
      const yBot = Math.min(height, Math.ceil(center + barH / 2));

      ctx.fillStyle = `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
      ctx.fillRect(x, yTop, barWidth, yBot - yTop);
    }

    // Linha do pico (peak marker) - mesma cor do WaveformCanvas (branco 35%)
    if (
      typeof peakOffset === "number" &&
      typeof duration === "number" &&
      duration > 0
    ) {
      const fracaoPico = Math.min(1, Math.max(0, peakOffset / duration));
      const xPico = Math.round(fracaoPico * width);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xPico + 0.5, 0);
      ctx.lineTo(xPico + 0.5, height);
      ctx.stroke();
    }

    // Playhead de progresso (linha branca continua — mockup mostra linha solida)
    if (progress > 0 && progress < 1) {
      const xProgress = Math.round(progress * width);
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xProgress + 0.5, 0);
      ctx.lineTo(xProgress + 0.5, height);
      ctx.stroke();
    }
  }, [peaks, width, height, peakOffset, duration, progress]);

  // Labels de tempo (renderizados como DOM abaixo do canvas para melhor qualidade)
  const timeLabels = duration
    ? { start: "0:00", end: formatTime(duration) }
    : { start: "0:00", end: "—" };

  return (
    <div className="inspector-waveform">
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="inspector-waveform-canvas"
        aria-label={error ? "Erro ao carregar onda" : "Onda da faixa"}
      />
      <div className="inspector-waveform-times">
        <span className="inspector-time-start">{timeLabels.start}</span>
        <span className="inspector-time-end">{timeLabels.end}</span>
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}