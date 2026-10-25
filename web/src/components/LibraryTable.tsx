import { useEffect, useRef } from "react";
import type { TrackRow } from "../api/types";
import { formatDuration, type LibrarySortKey, type SortDirection } from "../library";
import { ClassChip } from "./ui/ClassChip";
import { CoverArt } from "./ui/CoverArt";
import { KeyChip } from "./ui/KeyChip";
import { RowWaveform } from "./ui/RowWaveform";

interface LibraryTableProps {
  rows: TrackRow[];
  selectedSha1: string | null;
  /** Conjunto de SHA1 selecionados para multi-selecao. */
  selected?: Set<string>;
  /** Callback quando uma linha e clicada (selecao simples). */
  onSelect: (sha1: string) => void;
  /** Callback para alternar selecao de uma linha (multi-selecao). */
  onToggleSelect?: (sha1: string) => void;
  /** Callback para selecionar/desselecionar todas as linhas visiveis. */
  onSelectAll?: (selected: boolean) => void;
  sort: LibrarySortKey;
  direction: SortDirection;
  onSort: (key: LibrarySortKey) => void;
}

function CabecalhoOrdenavel({
  rotulo,
  chave,
  sort,
  direction,
  onSort,
  style,
}: {
  rotulo: string;
  chave: LibrarySortKey;
  sort: LibrarySortKey;
  direction: SortDirection;
  onSort: (key: LibrarySortKey) => void;
  style?: React.CSSProperties;
}) {
  const ativo = sort === chave;
  return (
    <th className={ativo ? "library-th-active" : ""} style={style}>
      <button type="button" className="library-th-sort" onClick={() => onSort(chave)}>
        {rotulo}
        {ativo && <span aria-hidden="true"> {direction === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}

function CheckboxCell({
  checked,
  indeterminate,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);

  // `indeterminate` nao e atributo do HTML: e propriedade do elemento, entao
  // precisa ser setada no DOM (o React nao sabereflectionar isso via prop).
  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = Boolean(indeterminate);
    }
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      className="library-checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      disabled={disabled}
      aria-label={indeterminate ? "Selecao parcial" : checked ? "Desselecionar" : "Selecionar"}
    />
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
  selected = new Set(),
  onSelect,
  onToggleSelect,
  onSelectAll,
  sort,
  direction,
  onSort,
}: LibraryTableProps) {
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.sha1));
  const someSelected = rows.some((r) => selected.has(r.sha1));

  const handleHeaderCheckboxChange = (checked: boolean) => {
    if (onSelectAll) {
      onSelectAll(checked);
    }
  };

  return (
    <div className="library-table-wrapper">
      <table className="library-table" data-testid="library-table">
        <thead>
          <tr>
            <th className="library-col-checkbox" style={{ width: "36px" }}>
              {onToggleSelect && (
                <CheckboxCell
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onChange={handleHeaderCheckboxChange}
                />
              )}
            </th>
            <th className="library-col-num" style={{ width: "36px" }}>#</th>
            <th className="library-col-capa" style={{ width: "52px" }}>CAPA</th>
            <CabecalhoOrdenavel
              rotulo="TÍTULO"
              chave="title"
              sort={sort}
              direction={direction}
              onSort={onSort}
              style={{ width: "225px" }}
            />
            <th className="library-col-artista" style={{ width: "165px" }}>ARTISTA</th>
            <th className="library-col-onda" style={{ width: "270px" }}>ONDA</th>
            <th className="library-col-genero" style={{ width: "95px" }}>GÊNERO</th>
            <CabecalhoOrdenavel
              rotulo="BPM"
              chave="bpm"
              sort={sort}
              direction={direction}
              onSort={onSort}
              style={{ width: "65px" }}
            />
            <th className="library-col-key" style={{ width: "55px" }}>KEY</th>
            <th className="library-col-classe" style={{ width: "70px" }}>CLASSE</th>
            <CabecalhoOrdenavel
              rotulo="DURAÇÃO"
              chave="duration"
              sort={sort}
              direction={direction}
              onSort={onSort}
              style={{ width: "80px" }}
            />
            <th className="library-col-arquivo" style={{ width: "72px" }}>ARQUIVO</th>
            <th className="library-col-acoes" style={{ width: "72px" }}>⋮</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const isSelected = selected.has(row.sha1);
            const isHighlighted = row.sha1 === selectedSha1;

            return (
              <tr
                key={row.sha1}
                data-testid="library-row"
                data-sha1={row.sha1}
                data-label={row.label ?? ""}
                className={[
                  isHighlighted ? "library-row-highlighted" : "",
                  isSelected ? "library-row-selected" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect(row.sha1)}
              >
                <td className="library-col-checkbox">
                  {onToggleSelect && (
                    <CheckboxCell
                      checked={isSelected}
                      onChange={() => onToggleSelect?.(row.sha1)}
                    />
                  )}
                </td>
                <td className="library-col-num muted">{i + 1}</td>
                <td className="library-col-capa">
                  <div className="library-cover">
                    {row.cover_path ? (
                      <CoverArt sha1={row.sha1} size={36} radius={4} loading="lazy" />
                    ) : (
                      <div className="library-cover-empty" aria-hidden="true" />
                    )}
                  </div>
                </td>
                <td className="library-col-titulo">
                  <div className="library-title">{row.display_title}</div>
                  {row.artist && <div className="library-artist muted">{row.artist}</div>}
                </td>
                <td className="library-col-artista muted">{row.artist ?? "—"}</td>
                <td className="library-col-onda">
                  <RowWaveform
                    trackSha1={row.sha1}
                    width={240}
                    height={38}
                    peakOffset={row.peak_offset_s}
                    duration={row.duration_s}
                  />
                </td>
                <td>{row.genre ?? "—"}</td>
                <td className="library-num">{Math.round(row.bpm)}</td>
                <td className="library-col-key">
                  <KeyChip keyData={row.key} />
                </td>
                <td className="library-col-classe">
                  <ClassChip label={row.label} />
                </td>
                <td className="library-num">{formatDuration(row.duration_s)}</td>
                <td className="library-col-arquivo">
                  {/* Indicador de formato por linha (mockup): extensao em
                      caps, mutada. O ponto de destaque da linha se mantem. */}
                  <span className="library-format">
                    {row.filename?.split(".").pop()?.toUpperCase() ?? "—"}
                  </span>
                  {isHighlighted && (
                    <span className="library-arquivo-dot" aria-hidden="true" />
                  )}
                </td>
                <td className="library-col-acoes">
                  <div className="library-acoes-menu" aria-hidden="true">⋮</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}