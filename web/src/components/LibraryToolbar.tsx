import type { LibraryState } from "../api/types";
import { useKeyNotation } from "../hooks/useKeyNotation";
import {
  CLASS_CHIPS,
  type LibrarySortKey,
  type LibraryView,
  type SortDirection,
} from "../library";

interface LibraryToolbarProps {
  state: LibraryState;
  view: LibraryView;
  onChange: (patch: Partial<LibraryView>) => void;
  resultado: number;
}

// Testid por chip: o valor do label nao e estavel o bastante para seletor
// ("-1" e "neutra" viram texto ambiguo em getByRole), entao cada chip tem
// o seu, na mesma ordem de CLASS_CHIPS.
const CHIP_TESTIDS = [
  "library-chip-todos",
  "library-chip-down",
  "library-chip-neutral",
  "library-chip-up",
] as const;

const OPCOES_SORT: readonly {
  valor: `${LibrarySortKey}:${SortDirection}`;
  rotulo: string;
}[] = [
  { valor: "title:asc", rotulo: "Título (A–Z)" },
  { valor: "title:desc", rotulo: "Título (Z–A)" },
  { valor: "artist:asc", rotulo: "Artista (A–Z)" },
  { valor: "artist:desc", rotulo: "Artista (Z–A)" },
  { valor: "bpm:asc", rotulo: "BPM ↑" },
  { valor: "bpm:desc", rotulo: "BPM ↓" },
  { valor: "duration:asc", rotulo: "Duração ↑" },
  { valor: "duration:desc", rotulo: "Duração ↓" },
];

/**
 * Barra de filtros da Biblioteca: busca, chips de classe com contagem
 * absoluta, combos de genero/key e o toggle de notacao (mesmo padrao do
 * ReviewHeader). Nao filtra nada localmente -- devolve patches de
 * LibraryView e quem aplica e o LibraryTab via applyLibraryView.
 */
export function LibraryToolbar({
  state,
  view,
  onChange,
  resultado,
}: LibraryToolbarProps) {
  const { notation, setNotation } = useKeyNotation();

  return (
    <div className="library-toolbar">
      <input
        type="search"
        className="library-search"
        data-testid="library-search"
        placeholder="Buscar por titulo, artista, album ou arquivo"
        value={view.query}
        onChange={(e) => onChange({ query: e.target.value })}
      />

      <div className="library-chips" role="group" aria-label="Filtrar por classe">
        {CLASS_CHIPS.map((chip, i) => {
          // Contagem absoluta de class_counts: nao encolhe com a busca,
          // senao o usuario perde a nocao do tamanho real da classe.
          const contagem = chip.indice === null ? state.total : state.class_counts[chip.indice];
          return (
            <button
              key={chip.rotulo}
              type="button"
              data-testid={CHIP_TESTIDS[i]}
              className={`library-chip ${view.label === chip.valor ? "library-chip-active" : ""}`}
              disabled={state.total === 0}
              onClick={() => onChange({ label: chip.valor })}
            >
              {chip.rotulo} · {contagem}
            </button>
          );
        })}
      </div>

      <select
        className="library-select"
        data-testid="library-genre"
        aria-label="Filtrar por gênero"
        value={view.genre ?? ""}
        onChange={(e) => onChange({ genre: e.target.value || null })}
      >
        <option value="">Todos</option>
        {state.genres.map((genero) => (
          <option key={genero} value={genero}>
            {genero}
          </option>
        ))}
      </select>

      <select
        className="library-select"
        data-testid="library-key"
        aria-label="Filtrar por tonalidade"
        value={view.key ?? ""}
        onChange={(e) => onChange({ key: e.target.value || null })}
      >
        <option value="">Todas</option>
        {/* state.keys ja vem em ordem de roda do servidor -- consumir como
            esta, reordenar aqui quebraria a navegacao harmonica. */}
        {state.keys.map((tom) => (
          <option key={tom} value={tom}>
            {tom}
          </option>
        ))}
      </select>

      <select
        className="library-select"
        data-testid="library-sort"
        aria-label="Ordenar por"
        value={`${view.sort}:${view.direction}`}
        onChange={(e) => {
          const [sort, direction] = e.target.value.split(":") as [
            LibrarySortKey,
            SortDirection,
          ];
          onChange({ sort, direction });
        }}
      >
        {OPCOES_SORT.map((opcao) => (
          <option key={opcao.valor} value={opcao.valor}>
            {opcao.rotulo}
          </option>
        ))}
      </select>

      <button
        type="button"
        className="key-notation-toggle"
        data-testid="library-notation"
        title="Alternar notação da tonalidade"
        onClick={() => setNotation(notation === "camelot" ? "classic" : "camelot")}
      >
        {notation === "camelot" ? "Camelot" : "Clássica"}
      </button>

      <span className="library-resultado">{resultado} tracks</span>
    </div>
  );
}
