import type { TrackRow } from "./api/types";

/**
 * Logica pura da aba Biblioteca: filtro, ordenacao e formatacao.
 *
 * Morada fora dos componentes porque os testes deterministicos exercitam
 * estas funcoes sem abrir pagina -- o mesmo papel do viewmodel.py no backend.
 */

export type LibrarySortKey = "title" | "artist" | "bpm" | "duration";
export type SortDirection = "asc" | "desc";

export interface LibraryView {
  query: string;
  label: string | null; // null = todos; senao "-1" | "neutra" | "+1"
  genre: string | null;
  key: string | null; // string Camelot, como vem em state.keys
  bpm: string | null; // "all" | "<100" | "100-120" | "120-130" | "130-140" | ">140"
  sort: LibrarySortKey;
  direction: SortDirection;
}

export const DEFAULT_LIBRARY_VIEW: LibraryView = {
  query: "",
  label: null,
  genre: null,
  key: null,
  bpm: "all",
  sort: "title",
  direction: "asc",
};

// Ordem de LABEL_ORDER (service.class_counts): -1, neutra, +1. Os chips
// mostram a contagem absoluta de class_counts[indice], que nao encolhe
// com a busca -- senao o usuario perde a nocao do tamanho da classe.
export const CLASS_CHIPS: readonly {
  rotulo: string;
  valor: string | null;
  indice: number | null;
}[] = [
  { rotulo: "Todos", valor: null, indice: null },
  { rotulo: "-1", valor: "-1", indice: 0 },
  { rotulo: "neutra", valor: "neutra", indice: 1 },
  { rotulo: "+1", valor: "+1", indice: 2 },
];

function comparaTexto(a: string, b: string): number {
  // Sem localeCompare com sensitivity "base" o byte-order separa "beta" de
  // "Alpha" (maiusculas antes de minusculas) e a ordenacao de titulo fica
  // ininteligivel para quem procura a track pela primeira letra.
  return a.localeCompare(b, "pt-BR", { sensitivity: "base" });
}

function compara(a: TrackRow, b: TrackRow, sort: LibrarySortKey): number {
  switch (sort) {
    case "title":
      return comparaTexto(a.display_title, b.display_title);
    case "artist":
      // Sem artista afunda para o fim em asc junto com a string vazia --
      // ausente (None no backend) conta como "".
      return comparaTexto(a.artist ?? "", b.artist ?? "");
    case "bpm":
      return a.bpm - b.bpm;
    case "duration":
      return a.duration_s - b.duration_s;
  }
}

/**
 * Faixas de BPM do filtro. Os limites sao intervalos meio-abertos para as
 * tres faixas centrais (o limite superior e exclusivo) e fechadas nas
 * pontas, de modo que todo BPM cai em exatamente uma faixa -- sem faixa
 * "furada" que o usuario nao consegue achar.
 */
export const BPM_RANGES: readonly { valor: string; rotulo: string }[] = [
  { valor: "all", rotulo: "Todos" },
  { valor: "lt100", rotulo: "< 100" },
  { valor: "100-120", rotulo: "100 - 120" },
  { valor: "120-130", rotulo: "120 - 130" },
  { valor: "130-140", rotulo: "130 - 140" },
  { valor: "gt140", rotulo: "> 140" },
];

function bpmNoIntervalo(bpm: number, faixa: string | null): boolean {
  switch (faixa) {
    case null:
    case "all":
      return true;
    case "lt100":
      return bpm < 100;
    case "100-120":
      return bpm >= 100 && bpm < 120;
    case "120-130":
      return bpm >= 120 && bpm < 130;
    case "130-140":
      return bpm >= 130 && bpm < 140;
    case "gt140":
      return bpm >= 140;
    default:
      // Faixa desconhecida nao esconde a track: o filtro desconhecido e
      // tratado como "sem filtro" em vez de zerar a tabela sem explicacao.
      return true;
  }
}

export function applyLibraryView(
  rows: readonly TrackRow[],
  view: LibraryView
): TrackRow[] {
  const consulta = view.query.trim().toLocaleLowerCase("pt-BR");

  const filtradas = rows.filter((row) => {
    if (consulta) {
      const campos = [row.display_title, row.artist, row.album, row.filename];
      const achou = campos.some((campo) =>
        campo?.toLocaleLowerCase("pt-BR").includes(consulta)
      );
      if (!achou) return false;
    }
    if (view.label !== null && row.label !== view.label) return false;
    if (view.genre !== null && row.genre !== view.genre) return false;
    // A lista state.keys e Camelot mesmo quando a tela mostra notacao
    // classica, entao o filtro compara camelot, nao classic.
    if (view.key !== null && row.key?.camelot !== view.key) return false;
    if (!bpmNoIntervalo(row.bpm, view.bpm)) return false;
    return true;
  });

  const sinal = view.direction === "desc" ? -1 : 1;
  // Copia antes de ordenar: sort muta in-place e a entrada e do hook de
  // estado -- mutar state.rows quebraria qualquer comparacao de referencia
  // a montante.
  return [...filtradas].sort((a, b) => {
    const principal = compara(a, b, view.sort);
    if (principal !== 0) return principal * sinal;
    // Desempate deterministico: sem ele a ordem de tracks com titulo
    // igual dependeria da ordem de chegada e mudaria a cada scan.
    const desempate = comparaTexto(
      a.filename.toLocaleLowerCase("pt-BR"),
      b.filename.toLocaleLowerCase("pt-BR")
    );
    return desempate * sinal;
  });
}

/**
 * Mesmo formato do viewmodel.py: floor, clamp em zero, "m:ss".
 * As copias locais de PlayerBar/ReviewHeader/WaveformCanvas ficam como
 * estao -- unificar e fora de escopo desta task.
 */
export function formatDuration(seconds: number): string {
  const total = Math.floor(Math.max(0, seconds));
  const minutos = Math.floor(total / 60);
  const resto = total % 60;
  return `${minutos}:${String(resto).padStart(2, "0")}`;
}
