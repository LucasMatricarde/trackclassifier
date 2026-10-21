import { useMemo } from "react";
import type { ModelState } from "../api/types";
import { VISIBLE_FILES, groupFailures } from "../model";

/**
 * Falhas de análise agrupadas por categoria.
 *
 * Port de failure_list.py: agrupa por categoria (3º elemento da tupla),
 * mostra badge com contagem, motivo em destaque, arquivos truncados.
 */

interface FailureListProps {
  failures: ModelState["failures"];
}

export function FailureList({ failures }: FailureListProps) {
  // Hook antes do early-return: regra dos hooks exige a mesma ordem de
  // chamada em todo render, mesmo quando a lista sai de cena.
  const grupos = useMemo(() => groupFailures(failures ?? []), [failures]);

  if (!failures || failures.length === 0) {
    return null;
  }

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
              {arquivos.slice(0, VISIBLE_FILES).join(" · ")}
              {arquivos.length > VISIBLE_FILES && (
                <>
                  {" · "}
                  <span>+{arquivos.length - VISIBLE_FILES}</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
