import { expect, test } from "@playwright/test";
import {
  IMBALANCE_THRESHOLD,
  LABELS_IN_ORDER,
  VISIBLE_FILES,
  balanceRecommendation,
  groupFailures,
  severityClass,
  techSummary,
} from "../src/model";
import { chipDelta } from "../src/model-logic";

/**
 * Testes puros da logica da aba Modelo (web/src/model.ts) -- nao abrem
 * pagina, rodam direto no worker do Playwright, como library-unit.spec.ts.
 */

test.describe("severityClass", () => {
  test("distancia ordinal define a severidade", () => {
    expect(severityClass(0, 0)).toBe("severity-0");
    expect(severityClass(1, 1)).toBe("severity-0");
    expect(severityClass(2, 2)).toBe("severity-0");
    expect(severityClass(0, 1)).toBe("severity-1");
    expect(severityClass(2, 1)).toBe("severity-1");
    expect(severityClass(0, 2)).toBe("severity-2");
    // simetrica: erro grave vale nos dois sentidos
    expect(severityClass(2, 0)).toBe("severity-2");
  });
});

test.describe("balanceRecommendation", () => {
  test("balanco perfeito nao recomenda nada", () => {
    expect(balanceRecommendation([10, 10, 10])).toBeNull();
  });

  test("biblioteca vazia nao recomenda nada", () => {
    expect(balanceRecommendation([0, 0, 0])).toBeNull();
  });

  test("exatamente no limiar nao recomenda (comparacao e <)", () => {
    // 7/10 == IMBALANCE_THRESHOLD: so abaixo do limiar dispara
    expect(IMBALANCE_THRESHOLD).toBe(0.7);
    expect(balanceRecommendation([10, 7, 10])).toBeNull();
  });

  test("classe menor que 70% da maior gera recomendacao nomeada", () => {
    // ordem de LABELS_IN_ORDER: -1, neutra, +1
    expect(LABELS_IN_ORDER).toEqual(["-1", "neutra", "+1"]);
    const rec = balanceRecommendation([10, 6, 10]);
    expect(rec).toBe(
      "neutra tem 60% dos exemplos de -1. Rotular mais neutra é o que mais reduz o erro agora."
    );
  });

  test("normaliza pela maior contagem, nao pelo total", () => {
    // [4, 3, 3]: menor/maior = 0.75 -> sem recomendacao; pelo total seria
    // 0.3 e dispararia uma recomendacao espuria
    expect(balanceRecommendation([4, 3, 3])).toBeNull();
  });
});

test.describe("groupFailures", () => {
  test("vazio devolve vazio", () => {
    expect(groupFailures([])).toEqual([]);
  });

  test("agrupa por categoria e ordena do maior para o menor", () => {
    const falhas: [string, string, string][] = [
      ["a.mp3", "motivo x", "decode"],
      ["b.mp3", "motivo y", "ffmpeg-ausente"],
      ["c.mp3", "motivo x", "decode"],
      ["d.mp3", "motivo x", "decode"],
      ["e.mp3", "motivo z", "curto"],
    ];
    expect(groupFailures(falhas)).toEqual([
      ["decode", ["a.mp3", "c.mp3", "d.mp3"]],
      ["ffmpeg-ausente", ["b.mp3"]],
      ["curto", ["e.mp3"]],
    ]);
  });

  test("mantem a ordem de chegada dentro do grupo", () => {
    const falhas: [string, string, string][] = [
      ["z.mp3", "m", "decode"],
      ["a.mp3", "m", "decode"],
    ];
    expect(groupFailures(falhas)).toEqual([["decode", ["z.mp3", "a.mp3"]]]);
  });

  test("teto de arquivos visiveis e o mesmo do componente", () => {
    expect(VISIBLE_FILES).toBe(5);
  });
});

test.describe("techSummary", () => {
  test("sem treino sobra so o nome do extrator", () => {
    expect(techSummary(null, null, "handcrafted-v1")).toBe("handcrafted-v1");
    // alpha sem cortes tambem cai no resumo minimo: parcial nao informa
    expect(techSummary(1.5, null, "handcrafted-v1")).toBe("handcrafted-v1");
  });

  test("com treino formata alpha e cortes", () => {
    expect(techSummary(1.234, [0.4567, 0.7891], "handcrafted-v1")).toBe(
      "alpha 1.23 · cortes 0.457 / 0.789 · handcrafted-v1"
    );
  });
});

test.describe("chipDelta", () => {
  test("acuracia em percentual: subir e bom", () => {
    expect(chipDelta(0.023, { formato: "percentual", casas: 1 })).toEqual({
      texto: "+2,3%",
      direcao: "up",
      bom: true,
    });
  });

  test("erro ordinal: menor e melhor, entao descer pinta de verde", () => {
    expect(chipDelta(-0.031, { formato: "decimal", casas: 3, menorMelhor: true })).toEqual({
      texto: "-0,031",
      direcao: "down",
      bom: true,
    });
    expect(chipDelta(0.01, { formato: "decimal", casas: 3, menorMelhor: true })?.bom).toBe(false);
  });

  test("F1 em decimal com duas casas: subir continua bom", () => {
    // Regressao: o formato decimal nao pode implicar "menor e melhor".
    expect(chipDelta(0.05, { formato: "decimal", casas: 2 })).toEqual({
      texto: "+0,05",
      direcao: "up",
      bom: true,
    });
  });

  test("sem delta nao ha chip", () => {
    expect(chipDelta(undefined, { formato: "decimal", casas: 2 })).toBeNull();
  });
});
