import { useMemo } from "react";
import type { ModelState } from "../api/types";

/**
 * Falhas de análise agrupadas por categoria.
 *
 * Port de failure_list.py: agrupa por categoria (3º elemento da tupla),
 * mostra badge com contagem, motivo em destaque, arquivos truncados.
 */

const ARQUIVOS_VISIVEIS = 5;

interface FailureListProps {
  failures: ModelState["failures"];
}

function agrupa(failures: [string, string, string][]): [string, string[]][] {
  const porCategoria: Record<string, string[]> = {};
  for (const [_filename, _reason, category] of failures) {
    if (!porCategoria[category]) porCategoria[category] = [];
    porCategoria[category].push(_filename);
  }
  return Object.entries(porCategoria).sort((a, b) => b[1].length - a[1].length);
}

export function FailureList({ failures }: FailureListProps) {
  if (!failures || failures.length === 0) {
    return null;
  }

  const grupos = useMemo(() => agrupa(failures), [failures]);

  return (
    <div className="failure-list">
      <div className="failure-list-header">
        <span className="failure-list-title">Falhas de analise</span>
        <span className="failure-list-summary">
          {failures.length} arquivos · {grupos.length} motivos
        </span>
      </div>

      <div className="failure-groups">
        {grupos.map(([categoria, arquivos]) => (
          <div key={categoria} className="failure-group">
            <div className="failure-group-header">
              <span className="failure-badge">{arquivos.length}</span>
              <span className="failure-category">{categoria}</span>
            </div>
            <div className="failure-files">
              {arquivos.slice(0, ARQUIVOS_VISIVEIS).join(" · ")}
              {arquivos.length > ARQUIVOS_VISIVEIS && (
                <>
                  {" · "}
                  <span>+{arquivos.length - ARQUIVOS_VISIVEIS}</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
