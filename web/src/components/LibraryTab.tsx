import { useCallback, useMemo, useState } from "react";
import { decide, remove, scan } from "../api/client";
import { useAudioPlayer } from "../hooks/useAudioPlayer";
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
import { LibraryTransport } from "./LibraryTransport";
import { ErrorBanner } from "./ui/ErrorBanner";
import { Segmented } from "./ui/Segmented";
import { Tooltip } from "./ui/Tooltip";

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
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [inspectorError, setInspectorError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "cards">("table");

  // Player elevado ao tab: o play do inspetor e o da barra sao o mesmo player
  // (mockup mostra os dois acesos e o mesmo estado isPlaying). useAudioPlayer
  // ja memoiza os callbacks internos, entao chamar diretamente preserva a ordem
  // dos hooks — NAO colocar dentro de useMemo (os hooks internos só
  // executariam no mount e quebrariam a sequencia na re-render).
  const player = useAudioPlayer();

  // Nenhum retorno condicional antes deste ponto: o loading renderiza la em
  // baixo, depois dos hooks. Retornar cedo aqui muda o numero de hooks entre
  // renders (state comeca null e o fetch resolve depois) e o React derruba o
  // componente com erro #310 — foi o que quebrou o teclado na Task 5.
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

  const handleToggleSelect = useCallback((sha1: string) => {
    setSelectedRows((prev) => {
      const next = new Set(prev);
      if (next.has(sha1)) {
        next.delete(sha1);
      } else {
        next.add(sha1);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback((select: boolean) => {
    if (select) {
      setSelectedRows(new Set(rows.map((r) => r.sha1)));
    } else {
      setSelectedRows(new Set());
    }
  }, [rows]);

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
        <div className="library-header-left">
          <h1>Biblioteca</h1>
          <p>Gerencie, visualize e classifique suas musicas.</p>
        </div>
        <div className="library-header-right">
          <Tooltip text="Em desenvolvimento">
            <Segmented
              className="library-view-toggle"
              options={[
                { value: "table", label: "Tabela", icon: (
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                    <rect x="1" y="1" width="5" height="5" rx="1" fill="currentColor"/>
                    <rect x="8" y="1" width="5" height="5" rx="1" fill="currentColor"/>
                    <rect x="1" y="8" width="5" height="5" rx="1" fill="currentColor"/>
                    <rect x="8" y="8" width="5" height="5" rx="1" fill="currentColor"/>
                  </svg>
                ) },
                { value: "cards", label: "Cards", disabled: true, icon: (
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                    <rect x="1" y="1" width="5" height="5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.2"/>
                    <rect x="8" y="1" width="5" height="5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.2"/>
                    <rect x="1" y="8" width="5" height="5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.2"/>
                    <rect x="8" y="8" width="5" height="5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.2"/>
                  </svg>
                ) },
              ]}
              selected={viewMode}
              onChange={(v) => setViewMode(v as "table" | "cards")}
            />
          </Tooltip>
          <button
            type="button"
            className="library-columns-btn"
            data-testid="library-columns"
            title="Colunas"
            disabled
          >
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <path
                d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
                stroke="currentColor"
                strokeWidth="1.8"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>Colunas</span>
          </button>
        </div>
      </header>
      {state && (
        <>
          <div className="library-content">
            <div className="library-table-panel">
              <LibraryToolbar
                state={state}
                view={view}
                onChange={(patch) => setView((v) => ({ ...v, ...patch }))}
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
                  /* A tabela recebe a selecao EFETIVA (com o fallback para
                     rows[0]), nao o selectedSha1 cru: sem isto a primeira
                     linha abre no inspetor sem o highlight roxo ateh o
                     primeiro clique. */
                  selectedSha1={selectedTrack?.sha1 ?? null}
                  selected={selectedRows}
                  onSelect={setSelectedSha1}
                  onToggleSelect={handleToggleSelect}
                  onSelectAll={handleSelectAll}
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
              onToggle={player.toggle}
              isPlaying={player.isPlaying}
              progress={player.durationMs > 0 ? player.positionMs / player.durationMs : 0}
            />
          </div>
          <LibraryTransport
            track={selectedTrack ? {
              sha1: selectedTrack.sha1,
              display_title: selectedTrack.display_title,
              artist: selectedTrack.artist,
              duration_s: selectedTrack.duration_s,
            } : null}
            player={player}
          />
        </>
      )}
    </div>
  );
}