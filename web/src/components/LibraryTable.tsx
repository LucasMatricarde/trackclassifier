import type { TrackRow } from "../api/types";
import { formatDuration, type LibrarySortKey, type SortDirection } from "../library";
import { ClassScale } from "./ui/ClassScale";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { MiniWave } from "./ui/MiniWave";

interface LibraryTableProps {
  rows: TrackRow[];
  selectedSha1: string | null;
  onSelect: (sha1: string) => void;
  sort: LibrarySortKey;
  direction: SortDirection;
  onSort: (key: LibrarySortKey) => void;
}

// So Titulo, BPM e Dur tem coluna propria E chave de ordenacao -- artist
// existe so no select da toolbar. Cabecalho clicavel que promete
// ordenacao que nao existe e porta que nao abre, entao Genero/Key/Classe
// ficam estaticos.
function CabecalhoOrdenavel({
  rotulo,
  chave,
  sort,
  direction,
  onSort,
}: {
  rotulo: string;
  chave: LibrarySortKey;
  sort: LibrarySortKey;
  direction: SortDirection;
  onSort: (key: LibrarySortKey) => void;
}) {
  const ativo = sort === chave;
  return (
    <th className={ativo ? "library-th-active" : ""}>
      <button type="button" className="library-th-sort" onClick={() => onSort(chave)}>
        {rotulo}
        {ativo && <span aria-hidden="true"> {direction === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}

/**
 * Tabela da Biblioteca. Renderiza as rows ja filtradas/ordenadas pelo
 * applyLibraryView -- aqui dentro nao ha logica de filtro, so apresentacao
 * e o repasse de selecao/ordenacao para o LibraryTab.
 */
export function LibraryTable({
  rows,
  selectedSha1,
  onSelect,
  sort,
  direction,
  onSort,
}: LibraryTableProps) {
  return (
    <div className="library-table-wrapper">
      <table className="library-table" data-testid="library-table">
        <thead>
          <tr>
            <th className="library-col-num">#</th>
            <th>Capa</th>
            <CabecalhoOrdenavel
              rotulo="Título · artista"
              chave="title"
              sort={sort}
              direction={direction}
              onSort={onSort}
            />
            <th>Onda</th>
            <th>Gênero</th>
            <CabecalhoOrdenavel
              rotulo="BPM"
              chave="bpm"
              sort={sort}
              direction={direction}
              onSort={onSort}
            />
            <th>Key</th>
            <th>Classe</th>
            <CabecalhoOrdenavel
              rotulo="Dur"
              chave="duration"
              sort={sort}
              direction={direction}
              onSort={onSort}
            />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.sha1}
              data-testid="library-row"
              data-sha1={row.sha1}
              data-label={row.label ?? ""}
              className={row.sha1 === selectedSha1 ? "library-row-selected" : ""}
              onClick={() => onSelect(row.sha1)}
            >
              <td className="library-col-num muted">{i + 1}</td>
              <td>
                <div className="library-cover">
                  {row.cover_path ? (
                    <CoverArt sha1={row.sha1} size={28} radius={3} loading="lazy" />
                  ) : (
                    <div className="library-cover-empty" aria-hidden="true" />
                  )}
                </div>
              </td>
              <td>
                <div className="library-title">{row.display_title}</div>
                {row.artist && <div className="library-artist muted">{row.artist}</div>}
              </td>
              <td>
                <MiniWave energy={row.energy_curve} />
              </td>
              <td>{row.genre ?? "—"}</td>
              <td className="library-num">{Math.round(row.bpm)}</td>
              <td>
                <KeyChip keyData={row.key} />
              </td>
              <td>
                <ClassScale label={row.label} />
              </td>
              <td className="library-num">{formatDuration(row.duration_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
