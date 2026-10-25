/**
 * Midia sintetica das rotas de capa/thumb e audio que os specs stubam para o
 * <img>/<audio> nao baterem no backend. Fonte unica: screenshot.spec.ts e
 * review-fixtures.ts tinham cada um a sua copia.
 */

/**
 * PNG 1x1 transparente: capa/thumb stubadas nunca mudam de pixel e o
 * placeholder do app pode resmungar com a rota ausente.
 */
export const PNG_1PX = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64"
);

/**
 * WAV PCM mono/silencioso de 8 kHz: o player abre e fica em pause. Com 0
 * segundo sobra so o cabecalho de 44 bytes (sem nenhuma amostra).
 */
export function wavSilencioso(segundos: number): Buffer {
  const sr = 8000;
  const n = segundos * sr;
  const buf = Buffer.alloc(44 + n * 2);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + n * 2, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sr, 24);
  buf.writeUInt32LE(sr * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(n * 2, 40);
  return buf; // amostras zeradas: silencio
}
