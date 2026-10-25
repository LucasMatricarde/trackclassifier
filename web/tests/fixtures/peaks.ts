/**
 * Peaks sinteticos para os specs que precisam da onda espectral pintada sem
 * backend: .npy float16 (N, 3) no formato que o WaveformCanvas le.
 *
 * Copia fiel dos helpers de screenshot.spec.ts, que nao foi refatorado de
 * proposito (baselines de pixel congelados) -- ver a issue de stubs
 * duplicados.
 */

/**
 * Codifica um float16 (metade IEEE 754) no padrao de 16 bits.
 * A fixture so tem valores modestos; subnormal e infinito nao acontecem.
 */
export function f16(valor: number): number {
  if (valor === 0) return 0;
  const mag = Math.abs(valor);
  let expoente = Math.floor(Math.log2(mag));
  let fracao = Math.round((mag / Math.pow(2, expoente) - 1) * 1024);
  if (fracao === 1024) {
    fracao = 0;
    expoente += 1;
  }
  const bits =
    ((valor < 0 ? 1 : 0) << 15) | ((expoente + 15) << 10) | fracao;
  return bits;
}

/**
 * .npy float16 2D (linhas = bandas) que o parser do WaveformCanvas le:
 * o formato real do backend e esse (o descmath vem de waveform_render).
 */
export function npyFloat16(linhas: number[][]): Buffer {
  const rows = linhas.length;
  const cols = linhas[0].length;
  const header = `{'descr': '<f2', 'fortran_order': False, 'shape': (${rows}, ${cols}), }`;
  // numpy: magic 6 bytes + versao 2 bytes + header_len u16 LE, e o par
  // `10 + headerLen` multiplo de 64 (header terminado em \n).
  const alvo = Math.ceil((header.length + 1 + 10) / 64) * 64;
  const headerLen = alvo - 10;
  const headerPreenchido = header + " ".repeat(headerLen - header.length - 1) + "\n";

  const out = Buffer.alloc(10 + headerLen + rows * cols * 2);
  Buffer.from([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 0x01, 0x00]).copy(out, 0);
  out.writeUInt16LE(headerLen, 8);
  Buffer.from(headerPreenchido, "ascii").copy(out, 10);
  const dados = 10 + headerLen;
  let pos = dados;
  for (const linha of linhas) {
    for (const valor of linha) {
      out.writeUInt16LE(f16(valor), pos);
      pos += 2;
    }
  }
  return out;
}

/**
 * Onda fixa padrao (na curva do TRACK_ALPHA): 64 buckets — cada LINHA do
 * npy e (grave, medio, agudo) do bucket, o shape (N, 3) que o backend
 * real produz (o parser do canvas exige esse layout intercalado).
 * As tres bandas sao a mesma curva com brilho decrescente, que e onde as
 * cores das waveband.* aparecem no baseline.
 */
export function ondaFixa(): number[][] {
  const base = [0.1, 0.4, 0.2, 0.8, 0.5, 0.3, 0.6, 0.2];
  // 2048 buckets: mais que as ~700 barras de 1512px (BAR_WIDTH=2), para o
  // resample (maximo por segmento) ser o mesmo caminho do backend real --
  // com menos buckets o clamp do fim repete o ultimo bucket e a metade
  // direita do canvas nasce achatada.
  return Array.from({ length: 2048 }, (_, i) => {
    const v = base[i % 8];
    return [v, v * 0.7, v * 0.45];
  });
}

/**
 * Onda com UMA banda dominante por terco (grave, medio, agudo): e o que faz
 * cada cor de waveband.* aparecer pura no canvas. Na ondaFixa as tres bandas
 * sao a mesma curva e a mistura vira laranja/marrom -- util para o baseline,
 * inutil para provar que as tres bandas foram pintadas. Fixture propria
 * deste arquivo (nao e copia do screenshot.spec).
 */
export function ondaPorBanda(): number[][] {
  const n = 2048;
  return Array.from({ length: n }, (_, i) => {
    const terco = Math.floor((i * 3) / n);
    return [0, 1, 2].map((banda) => (banda === terco ? 0.9 : 0.05));
  });
}
