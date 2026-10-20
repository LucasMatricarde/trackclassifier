import { useCallback, useMemo, useState } from "react";
import { decide, remove, scan } from "../api/client";
import { useKeyboard } from "../hooks/useKeyboard";
import { useLibraryState } from "../hooks/useLibraryState";
import {
  applyLibraryView,
  DEFAULT_LIBRARY_VIEW,
  type LibrarySortKey,
  type LibraryView,
} from "../library";
import { EmptyState } from "./EmptyState";
import { LibraryInspector } from "./LibraryInspector";
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
  const { state, error, reload } = useLibraryState();
  const [view, setView] = useState<LibraryView>(DEFAULT_LIBRARY_VIEW);
  const [selectedSha1, setSelectedSha1] = useState<string | null>(null);
  const [inspectorError, setInspectorError] = useState<string | null>(null);

  if (state === null && !error) {
    return (
      <div className="library-tab" data-testid="library-tab">
        <div className="config-loading">Carregando…</div>
      </div>
    );
  }

  const rows = state ? applyLibraryView(state.rows, view) : [];

  // Seleciona a primeira linha por default; depois, o usuario clica para
  // trocar. Se a selecao anterior sumiu apos filtrar, volta para a primeira.
  const selectedTrack = selectedSha1
    ? rows.find((r) => r.sha1 === selectedSha1) ?? (rows[0] ?? null)
    : rows[0] ?? null;

  const onSort = (chave: LibrarySortKey) => {
    // Clicar na coluna ativa inverte a direcao; trocar de coluna volta
    // para asc, como no Qt.
    setView((v) =>
      v.sort === chave
        ? { ...v, direction: v.direction === "asc" ? "desc" : "asc" }
        : { ...v, sort: chave, direction: "asc" }
    );
  };

  const classify = useCallback(async (label: number) => {
    if (!selectedTrack) return;
    setInspectorError(null);
    try {
      await decide(selectedTrack.sha1, label);
      await reload();
    } catch (e) {
      setInspectorError(String(e));
    }
  }, [selectedTrack, reload]);

  const handleRemove = async () => {
    if (!selectedTrack) return;
    setInspectorError(null);
    try {
      await remove(selectedTrack.sha1);
      setSelectedSha1(null);
      await reload();
    } catch (e) {
      setInspectorError(String(e));
    }
  };

  const handleReveal = () => {
    if (!selectedTrack) return;
    // window.trackclassifier.revealItem e definido no preload do Electron
    if (typeof window.trackclassifier?.revealItem === "function") {
      void window.trackclassifier.revealItem(selectedTrack.path_hint);
    }
  };

  const canReveal = typeof window.trackclassifier?.revealItem === "function";

  const keyboardHandlers = useMemo(
    () => ({ onDecide: classify }),
    [classify]
  );

  // Teclado: 1/2/3 classificam
  useKeyboard(keyboardHandlers, true);

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
          <div className="library-content">
            <div className="library-table-panel">
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
            </div>
            <LibraryInspector
              track={selectedTrack}
              onClassify={classify}
              onRemove={handleRemove}
              onReveal={handleReveal}
              canReveal={canReveal}
              error={inspectorError}
            />
          </div>
        </>
      )}
    </div>
  );
}