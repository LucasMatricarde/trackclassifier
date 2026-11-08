import { expect, test } from "@playwright/test";
import { resampleCurva } from "../src/lib/curva";

/**
 * Testes puros de resampleCurva -- nao abrem pagina.
 *
 * A energy_curve tem uma entrada por JANELA (10s, salto de 5s numa track de
 * 5 min), indexada pelo inicio dela. A entrada k descreve o trecho centrado em
 * janela/2 + k*salto, nao em k/(N-1)*duracao: esticar a curva de ponta a ponta
 * deslocava a onda mono em ate meia janela (5s) em relacao ao playhead.
 */

const DURACAO = 300;
const JANELAS = 59; // floor((300 - 10) / 5) + 1
const BARRAS = 300; // 1s por barra: facil de ler

function impulsoEm(k: number): Float32Array {
  const curva = new Float32Array(JANELAS);
  curva[k] = 1;
  return curva;
}

function indiceDoPico(v: Float32Array): number {
  let melhor = 0;
  for (let i = 1; i < v.length; i++) if (v[i] > v[melhor]) melhor = i;
  return melhor;
}

test("a primeira janela vale ate o centro dela (5s) e decai dali, nao desde 0s", () => {
  const out = resampleCurva(impulsoEm(0), BARRAS, DURACAO);
  // Antes de 5s nao ha dado: segura o valor da borda.
  expect(out[2]).toBeCloseTo(1, 5);
  // t=7.5s fica a meio caminho entre o centro da janela 0 (5s) e o da 1 (10s).
  expect(out[7]).toBeCloseTo(0.5, 1);
  // A partir de 10s a janela 0 nao influencia mais. Esticada de ponta a ponta,
  // ela ja estaria zerada em 7s (a onda sairia ~5s adiantada).
  expect(out[10]).toBeCloseTo(0, 5);
});

test("a ultima janela cai no centro dela (295s), nao na borda direita", () => {
  const pico = indiceDoPico(resampleCurva(impulsoEm(JANELAS - 1), BARRAS, DURACAO));
  expect(pico).toBeGreaterThanOrEqual(294);
  expect(pico).toBeLessThanOrEqual(295);
});

test("a janela do meio continua no meio", () => {
  const pico = indiceDoPico(resampleCurva(impulsoEm(29), BARRAS, DURACAO));
  expect(pico).toBeGreaterThanOrEqual(149);
  expect(pico).toBeLessThanOrEqual(150);
});

test("curva de um ponto preenche tudo e curva vazia nao quebra", () => {
  expect([...resampleCurva(new Float32Array([0.7]), 4, DURACAO)]).toEqual([
    expect.closeTo(0.7, 5), expect.closeTo(0.7, 5), expect.closeTo(0.7, 5), expect.closeTo(0.7, 5),
  ]);
  expect(resampleCurva(new Float32Array(0), 4, DURACAO).length).toBe(4);
});
