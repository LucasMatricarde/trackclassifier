import { useState } from "react";
import { scan } from "../api/client";
import { useLibraryState } from "../hooks/useLibraryState";
import {
  applyLibraryView,
  DEFAULT_LIBRARY_VIEW,
  type LibrarySortKey,
  type LibraryView,
} from "../library";
import { EmptyState } from "./EmptyState";
import { LibraryTable } from "./LibraryTable";
import { LibraryToolbar } from "./LibraryToolbar";
import { ErrorBanner } from "./ui/ErrorBanner";

/**
 * Aba Biblioteca: listagem das tracks classificadas.
 *
 * O estado da view (busca, filtros, ordenacao) fica aqui e e aplicado pela
 * logica pura de library.ts; toolbar e tabela so devolvem patches e
 * intencoes. Os tres estados de vazio sao distintos de proposito: total 0
 * chama para o scan, filtro zerado oferece limpar a busca.
 */
export function LibraryTab() {
  const { state, error } = useLibraryState();
  const [view, setView] = useState<LibraryView>(DEFAULT_LIBRARY_VIEW);
  const [selectedSha1, setSelectedSha1] = useState<string | null>(null);

  if (state === null && !error) {
    return (
      <div className="library-tab" data-testid="library-tab">
        <div className="config-loading">Carregando…</div>
      </div>
    );
  }

  const rows = state ? applyLibraryView(state.rows, view) : [];

  const onSort = (chave: LibrarySortKey) => {
    // Clicar na coluna ativa inverte a direcao; trocar de coluna volta
    // para asc, como no Qt.
    setView((v) =>
      v.sort === chave
        ? { ...v, direction: v.direction === "asc" ? "desc" : "asc" }
        : { ...v, sort: chave, direction: "asc" }
    );
  };

  return (
    <div className="library-tab" data-testid="library-tab">
      {error && <ErrorBanner message={error} testId="library-error" />}
      <header className="library-header">
        <h1>Biblioteca</h1>
        <p>Gerencie, visualize e classifique suas musicas.</p>
      </header>
      <div className="library-count" data-testid="library-count">
        {state?.total ?? 0} tracks classificadas
      </div>
      {state && (
        <>
          <LibraryToolbar
            state={state}
            view={view}
            onChange={(patch) => setView((v) => ({ ...v, ...patch }))}
            resultado={rows.length}
          />
          {state.total === 0 ? (
            <EmptyState
              title="Biblioteca vazia"
              subtitle="Nenhuma track classificada ainda."
              actionLabel="Escanear"
              onAction={() => void scan().catch(() => {})}
              testId="library-empty"
            />
          ) : rows.length === 0 ? (
            <div className="library-sem-resultado" data-testid="library-sem-resultado">
              <p>Nenhuma track encontrada.</p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setView(DEFAULT_LIBRARY_VIEW)}
              >
                Limpar busca
              </button>
            </div>
          ) : (
            <LibraryTable
              rows={rows}
              selectedSha1={selectedSha1}
              onSelect={setSelectedSha1}
              sort={view.sort}
              direction={view.direction}
              onSort={onSort}
            />
          )}
        </>
      )}
    </div>
  );
}
