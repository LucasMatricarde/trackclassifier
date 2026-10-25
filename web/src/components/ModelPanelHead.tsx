import type { ReactNode } from "react";

/**
 * Cabecalho dos paineis da aba Modelo (mockup): icone ~26px no tom do
 * accent a esquerda, titulo e subtitulo empilhados ao lado. Um componente
 * so porque os cinco paineis repetem a mesma geometria.
 */
interface ModelPanelHeadProps {
  icone: ReactNode;
  titulo: string;
  subtitulo: string;
}

export function ModelPanelHead({ icone, titulo, subtitulo }: ModelPanelHeadProps) {
  return (
    <header className="model-panel-head">
      <span className="model-panel-head-icon">{icone}</span>
      <h2>{titulo}</h2>
      <p>{subtitulo}</p>
    </header>
  );
}
