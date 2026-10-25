import { useId } from "react";

/**
 * Sparkline do card metrico: curva suave + area em degrade, a partir da
 * serie do historico. Sem biblioteca de grafico -- o pedido e puro shape.
 * A cor vem do card via currentColor; o degrade usa stop-color
 * currentColor (valido em SVG inline), entao um token so pinta linha e area.
 */
interface SparklineProps {
  /** Serie em ordem CRONOLOGICA (do mais antigo ao mais recente). */
  valores: number[];
  /** 0..1: altura do pico relativo, para comparar series de escala. */
  normaliza?: boolean;
  /** testId por card, para os testes acharem o desenho. */
  testId?: string;
}

export function Sparkline({ valores, normaliza = true, testId }: SparklineProps) {
  const gradId = `spark-${useId().replace(/:/g, "")}`;
  const largura = 100;
  const altura = 28;
  if (valores.length === 0) {
    return (
      <svg
        className="sparkline sparkline-vazio"
        data-testid={testId}
        viewBox={`0 0 ${largura} ${altura}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      />
    );
  }
  let maximo = Math.max(...valores);
  let minimo = Math.min(...valores);
  if (normaliza && maximo - minimo < 1e-9) {
    // Serie constante: desenha uma faixa no meio em vez de deturpar
    // max=min=0 (nao divisao explode no calculo do path).
    maximo += 0.5;
    minimo = minimo === maximo - 0.5 ? maximo - 1 : minimo - 0.5;
  }
  const pontos = valores.map((v, i) => ({
    x: valores.length === 1 ? largura : (i / (valores.length - 1)) * largura,
    y: altura - ((v - minimo) / (maximo - minimo)) * (altura - 4) - 2,
  }));
  const linha = curvaSuave(pontos);
  const area = `${linha} L${largura} ${altura} L${pontos[0].x.toFixed(2)} ${altura} Z`;

  return (
    <svg
      className="sparkline"
      data-testid={testId}
      viewBox={`0 0 ${largura} ${altura}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" className="sparkline-stop-topo" />
          <stop offset="100%" stopColor="currentColor" className="sparkline-stop-base" />
        </linearGradient>
      </defs>
      <path d={area} className="sparkline-area" fill={`url(#${gradId})`} />
      <path d={linha} className="sparkline-linha" />
    </svg>
  );
}

/**
 * Catmull-Rom -> Bezier: a curva do mockup e arredondada, e a polyline
 * crua quebrava em quina a cada treino. Tensao 1/6 (padrao), que passa
 * por todos os pontos sem estourar muito alem do min/max.
 */
function curvaSuave(p: { x: number; y: number }[]): string {
  const f = (n: number) => n.toFixed(2);
  if (p.length === 1) return `M${f(p[0].x)} ${f(p[0].y)}`;
  let d = `M${f(p[0].x)} ${f(p[0].y)}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] ?? p[i];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${f(c1x)} ${f(c1y)} ${f(c2x)} ${f(c2y)} ${f(p2.x)} ${f(p2.y)}`;
  }
  return d;
}
