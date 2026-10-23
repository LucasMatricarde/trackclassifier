/**
 * Leitura dos .npy de peaks.
 *
 * O arquivo e gravado pelo backend em float16 com shape (N, 3): uma linha por
 * bucket de tempo e tres colunas (grave, medio, agudo). O header do formato
 * numpy carrega o shape, entao o leitor precisa decodificar float16 -- que
 * `DataView` nao faz nativamente.
 *
 * Extraido do WaveformCanvas para que a mini-onda da tabela e a onda grande
 * da Revisao leiam o mesmo arquivo do mesmo jeito: um so lugar muda quando o
 * formato dos peaks muda.
 */

/** Header do .npy: shape (N, cols) e a ordem em que os dados vem. */
interface NpyHeader {
  rows: number;
  cols: number;
  fortranOrder: boolean;
}

/**
 * Decodifica o header do .npy. Retorna null quando o arquivo nao tem a
 * assinatura magica do numpy ou o header nao traz shape.
 */
function parseHeader(buffer: ArrayBuffer): NpyHeader | null {
  const view = new DataView(buffer);
  if (view.getUint8(0) !== 0x93) return null;
  const major = view.getUint8(6);
  // v1: header_len uint16 em 8; v2+: uint32 em 8
  const headerLen = major >= 2 ? view.getUint32(8, true) : view.getUint16(8, true);
  const headerStart = major >= 2 ? 12 : 10;
  const headerEnd = headerStart + headerLen;
  if (headerEnd > buffer.byteLength) return null;
  const headerStr = new TextDecoder().decode(new Uint8Array(buffer, headerStart, headerLen));

  const shapeMatch = headerStr.match(/'shape':\s*\((\d+),\s*(\d+)\)/);
  if (!shapeMatch) return null;
  return {
    rows: parseInt(shapeMatch[1], 10),
    cols: parseInt(shapeMatch[2], 10),
    fortranOrder: /'fortran_order':\s*True/.test(headerStr),
  };
}

/** Converte um half (16 bits) em float, cobrindo subnormal, normal e infinito. */
function halfToFloat(bits: number): number {
  const sign = bits & 0x8000 ? -1 : 1;
  const exp = (bits & 0x7c00) >> 10;
  const frac = bits & 0x03ff;
  if (exp === 0) return sign * frac * Math.pow(2, -24);
  if (exp === 31) return frac ? NaN : sign * Infinity;
  return sign * (1 + frac / 1024) * Math.pow(2, exp - 15);
}

/**
 * Parse .npy (float16, shape (N, cols)) -> Float32Array em ordem C.
 * Retorna null quando o arquivo nao e um .npy valido ou o shape nao bate.
 */
export function parseNpy(buffer: ArrayBuffer): Float32Array | null {
  try {
    const header = parseHeader(buffer);
    if (!header) return null;
    const { rows, cols, fortranOrder } = header;

    const headerStart = new DataView(buffer).getUint8(6) >= 2 ? 12 : 10;
    const headerLen = new DataView(buffer).getUint8(6) >= 2
      ? new DataView(buffer).getUint32(8, true)
      : new DataView(buffer).getUint16(8, true);
    const dataView = new DataView(buffer, headerStart + headerLen);

    const total = rows * cols;
    if (dataView.byteLength < total * 2) return null;

    const out = new Float32Array(total);
    for (let i = 0; i < total; i++) {
      const valor = halfToFloat(dataView.getUint16(i * 2, true));
      if (fortranOrder) {
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

/**
 * Resample de bandas: (N,3) -> (bars,3) pelo maximo; edge quando menor.
 * Agrupa buckets vizinhos e fica com o maior valor de cada banda, que e o
 * que a onda grande ja faz.
 */
export function resampleBands(peaks: Float32Array, bars: number): Float32Array {
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
