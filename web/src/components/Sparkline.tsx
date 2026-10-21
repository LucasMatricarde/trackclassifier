/**
 * Sparkline do card metrico: linha + area em SVG, a partir da serie do
 * historico. Sem biblioteca de grafico -- o pedido e puro shape, e o
 * gradiente investiga a cor do card via CSS currentColor (whoelse nao
 * suporta CSS var em stop-color? Suporta mesmo, stop-color: var() e
 * valido em SVG inline).
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
  const pontos = valores.map((v, i) => {
    const x = valores.length === 1 ? largura : (i / (valores.length - 1)) * largura;
    const y = altura - ((v - minimo) / (maximo - minimo)) * (altura - 4) - 2;
    return `${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  const linha = `M${pontos.join(" L")}`;
  const area = `${linha} L${largura} ${altura} L0 ${altura} Z`;

  return (
    <svg
      className="sparkline"
      data-testid={testId}
      viewBox={`0 0 ${largura} ${altura}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={area} className="sparkline-area" />
      <path d={linha} className="sparkline-linha" />
    </svg>
  );
}

/**
 * Nota: `preserveAspectRatio="none"` estica o shape para o card, igual as
 * ondas do app. Com floats, o gradiente leva a cor via classe (.sparkline-*).
 */
