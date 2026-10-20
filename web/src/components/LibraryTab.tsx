import { useLibraryState } from "../hooks/useLibraryState";
import { ErrorBanner } from "./ui/ErrorBanner";

/**
 * Aba Biblioteca: listagem das tracks classificadas.
 *
 * Por enquanto so o header e a contagem; a grade entra nas proximas tasks.
 */
export function LibraryTab() {
  const { state, error } = useLibraryState();

  if (state === null && !error) {
    return (
      <div className="library-tab" data-testid="library-tab">
        <div className="config-loading">Carregando…</div>
      </div>
    );
  }

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
    </div>
  );
}
