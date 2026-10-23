import type { LibraryState } from "../api/types";
import {
  BPM_RANGES,
  CLASS_CHIPS,
  type LibrarySortKey,
  type LibraryView,
  type SortDirection,
} from "../library";

interface LibraryToolbarProps {
  state: LibraryState;
  view: LibraryView;
  onChange: (patch: Partial<LibraryView>) => void;
}

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
 * absoluta, combos rotulados de genero/key/bpm/sort, botao de filtro.
 * Nao filtra nada localmente -- devolve patches de LibraryView e quem
 * aplica e o LibraryTab via applyLibraryView.
 */
export function LibraryToolbar({
  state,
  view,
  onChange,
}: LibraryToolbarProps) {
  const chipClassMap: Record<string, string> = {
    "-1": "library-chip-down",
    neutra: "library-chip-neutral",
    "+1": "library-chip-up",
  };

  return (
    <div className="library-toolbar">
      <div className="library-search-wrapper">
        <input
          type="search"
          className="library-search"
          data-testid="library-search"
          placeholder="Buscar por título, artista, álbum ou arquivo"
          value={view.query}
          onChange={(e) => onChange({ query: e.target.value })}
        />
        <svg
          className="library-search-icon"
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
        >
          <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M14 14l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      <div className="library-chips" role="group" aria-label="Filtrar por classe">
        {CLASS_CHIPS.map((chip, i) => {
          const contagem = chip.indice === null ? state.total : state.class_counts[chip.indice];
          const extraClass = chip.valor ? chipClassMap[chip.valor] : "";
          return (
            <button
              key={chip.rotulo}
              type="button"
              data-testid={CHIP_TESTIDS[i]}
              className={`library-chip ${extraClass} ${view.label === chip.valor ? "library-chip-active" : ""}`}
              disabled={state.total === 0}
              onClick={() => onChange({ label: chip.valor })}
            >
              <span className="library-chip-label">{chip.rotulo}</span>
              <span className="library-chip-count">{contagem}</span>
            </button>
          );
        })}
      </div>

      <div className="library-field">
        <label htmlFor="library-genre" className="library-field-label">
          Gênero
        </label>
        <select
          id="library-genre"
          className="library-select"
          data-testid="library-genre"
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
      </div>

      <div className="library-field">
        <label htmlFor="library-key" className="library-field-label">
          Key
        </label>
        <select
          id="library-key"
          className="library-select"
          data-testid="library-key"
          value={view.key ?? ""}
          onChange={(e) => onChange({ key: e.target.value || null })}
        >
          <option value="">Todas</option>
          {state.keys.map((tom) => (
            <option key={tom} value={tom}>
              {tom}
            </option>
          ))}
        </select>
      </div>

      <div className="library-field">
        <label htmlFor="library-bpm" className="library-field-label">
          BPM
        </label>
        <select
          id="library-bpm"
          className="library-select"
          data-testid="library-bpm"
          value={view.bpm ?? "all"}
          onChange={(e) => onChange({ bpm: e.target.value || null })}
        >
          {BPM_RANGES.map((opcao) => (
            <option key={opcao.valor} value={opcao.valor}>
              {opcao.rotulo}
            </option>
          ))}
        </select>
      </div>

      <div className="library-field">
        <label htmlFor="library-sort" className="library-field-label">
          Ordenar por
        </label>
        <select
          id="library-sort"
          className="library-select"
          data-testid="library-sort"
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
      </div>

      <button
        type="button"
        className="library-filter-btn"
        data-testid="library-filter"
        title="Filtros avançados"
        disabled
      >
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <line x1="2" y1="4" x2="14" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="2" y1="9" x2="14" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="2" y1="14" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}