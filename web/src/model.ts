/**
 * Logica pura da aba Modelo: severidade da matriz de confusao, recomendacao
 * de balanco, agrupamento de falhas e resumo tecnico.
 *
 * Morada fora dos componentes porque os testes deterministicos exercitam
 * estas funcoes sem abrir pagina -- o mesmo papel do viewmodel.py no Qt e
 * do library.ts na aba Biblioteca.
 */

// Ordem de LABEL_ORDER (service.class_counts e a matriz de confusao):
// -1 (lento), neutra, +1 (animada). Os indices desta tupla sao os mesmos
// das linhas/colunas da matriz.
export const LABELS_IN_ORDER = ["-1", "neutra", "+1"] as const;

export type ClassName = "animada" | "neutro" | "lento";

export const CLASS_BY_LABEL: Record<string, ClassName> = {
  "+1": "animada",
  "neutra": "neutro",
  "-1": "lento",
};

// Menor classe abaixo desta fracao da maior dispara a recomendacao de
// rotular mais -- mesmo limiar do class_balance.py do Qt.
export const IMBALANCE_THRESHOLD = 0.70;

// Teto de arquivos listados por grupo de falha; o restante vira "+N" para
// a lista nao engolir a tela quando uma categoria explode.
export const VISIBLE_FILES = 5;

export type Severity = "severity-0" | "severity-1" | "severity-2";

// Distancia ordinal |i-j| da matriz: acerto, erro de 1 classe, erro de 2
// classes. O valor da celula nao entra: a cor marca a gravidade do erro,
// nao o volume.
export function severityClass(i: number, j: number): Severity {
  const dist = Math.abs(i - j);
  if (dist === 0) return "severity-0";
  if (dist === 1) return "severity-1";
  return "severity-2";
}

// null quando nao ha o que recomendar: biblioteca vazia (maior === 0) ou
// balanco dentro do limiar. A fracao usa a MAIOR contagem como denominador,
// nao o total -- normalizar pelo total puniria classes pequenas mesmo num
// balanco perfeito de 3 classes iguais.
export function balanceRecommendation(
  classCounts: readonly number[]
): string | null {
  const maior = Math.max(...classCounts);
  if (maior === 0) return null;
  const indice = classCounts.indexOf(Math.min(...classCounts));
  const proporcao = classCounts[indice] / maior;
  if (proporcao >= IMBALANCE_THRESHOLD) return null;
  const rotulo = LABELS_IN_ORDER[indice];
  const maiorRotulo = LABELS_IN_ORDER[classCounts.indexOf(maior)];
  return `${rotulo} tem ${Math.round(proporcao * 100)}% dos exemplos de ${maiorRotulo}. Rotular mais ${rotulo} é o que mais reduz o erro agora.`;
}

// Agrupa por categoria (3o elemento da tupla) e ordena do maior grupo para
// o menor: o motivo que mais custa em volume de erro vem primeiro.
export function groupFailures(
  failures: readonly [string, string, string][]
): [string, string[]][] {
  const porCategoria: Record<string, string[]> = {};
  for (const [filename, _reason, category] of failures) {
    if (!porCategoria[category]) porCategoria[category] = [];
    porCategoria[category].push(filename);
  }
  return Object.entries(porCategoria).sort((a, b) => b[1].length - a[1].length);
}

// Sem treino (alpha null) so resta o nome do extrator -- os cortes so
// existem depois do primeiro fit.
export function techSummary(
  alpha: number | null,
  thresholds: [number, number] | null,
  extractorName: string
): string {
  if (alpha === null || thresholds === null) {
    return extractorName;
  }
  const [t1, t2] = thresholds;
  return `alpha ${alpha.toFixed(2)} · cortes ${t1.toFixed(3)} / ${t2.toFixed(3)} · ${extractorName}`;
}
