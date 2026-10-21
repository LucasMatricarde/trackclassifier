import type { ModelState, TrainingHistoryEntry } from "./api/types";

/**
 * Logica pura do dashboard do Modelo — espelho dos derivados do desktop
 * (viewmodel/model_tab) e das decisoes do spec
 * docs/superpowers/specs/2026-10-21-aba-modelo-dashboard-web.md.
 *
 * Nada de React aqui: o que e derivado de ModelState mora num modulo
 * testavel, igual ao library.ts da Biblioteca.
 *
 * A recomendacao de desbalanco NAO mora aqui: virou balanceRecommendation
 * em model.ts (modulo da main), que alimenta tambem os testes de unidade.
 */

//# Serie dos sparklines ------------------------------------------------------
//# O card usa a historia do dado proprio (acuracia, mae, f1, exemplos).

export function serieDaHistoria(
  state: ModelState | null,
  campo: CampoHistorico
): number[] {
  if (!state) return [];
  // O backend entrega recente primeiro (o ativo e history[0]); a linha da
  // sparkline e cronologica: mais antigo a esquerda, novo a direita.
  return [...state.history].reverse().map((entrada) => entrada[campo]);
}

export type CampoHistorico =
  | keyof Pick<TrainingHistoryEntry, "n_examples" | "accuracy" | "ordinal_mae" | "weighted_f1">;

//# Formatacao                                                                 -
//# pt-BR: decimal por virgula, percentual com uma casa. O backend entrega
//# fracoes; a formatacao e da tela.

export function percentual(valor: number | null, casas = 0): string {
  if (valor === null) return "--";
  return `${(valor * 100).toFixed(casas).replace(".", ",")}%`;
}

export function decimal(valor: number | null, casas = 3): string {
  if (valor === null || Number.isNaN(valor)) return "--";
  return valor.toFixed(casas).replace(".", ",");
}

export function dataCurta(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--";
  const dois = (n: number) => String(n).padStart(2, "0");
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()} ${dois(d.getHours())}:${dois(d.getMinutes())}`;
}

//# Chips de delta ------------------------------------------------------------
//# "bom" quando o sinal aponta para o progresso: acuracia/F1 sobem,
//# erro ordinal desce. O chip so existe com comparacao da MESMA era --
//# o backend ja filtra (deltas ausente = sem chip).

export type Direcao = "up" | "down";

export interface ChipDelta {
  texto: string;
  direcao: Direcao;
  bom: boolean;
}

export function chipDelta(delta: number | undefined, campo: "percentual" | "decimal"): ChipDelta | null {
  if (delta === undefined || delta === null) {
    return null;
  }
  const sentido: Direcao = delta > 0 ? "up" : "down";
  const texto =
    campo === "percentual"
      ? `${sentido === "up" ? "+" : "-"}${Math.abs(delta * 100).toFixed(1).replace(".", ",")}%`
      : `${sentido === "up" ? "+" : "-"}${Math.abs(delta).toFixed(3).replace(".", ",")}`;
  // Acuracia/F1: subir e bom. Erro ordinal: descer e bom (menor, melhor).
  const campo_bom = campo === "decimal" ? sentido === "down" : sentido === "up";
  return { texto, direcao: sentido, bom: campo_bom };
}

export const statusDeHistorico = (index: number, total: number): string =>
  index === 0 && total > 0 ? "Ativo" : "-";
