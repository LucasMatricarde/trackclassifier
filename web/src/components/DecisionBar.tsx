import type { TrackRow } from "../api/types";
import { ClassActionCard } from "./ClassActionCard";
import { Kbd } from "./ui/Kbd";
import { VDivider } from "./ui/VDivider";

interface DecisionBarProps {
  track: TrackRow | null;
  onDecide: (label: number) => void;
}

const SHORTCUTS: [string, string][] = [
  ["1", "Classificar como -1"],
  ["2", "Classificar como neutra"],
  ["3", "Classificar como +1"],
  ["Space", "Reproduzir / Pausar"],
  ["← →", "Música anterior / próxima"],
];

/**
 * Barra de decisão com 3 cards de classe + coluna de atalhos.
 * Port de decision_bar.py.
 */
export function DecisionBar({ track, onDecide }: DecisionBarProps) {
  const enabled = track !== null;

  return (
    <div className="decision-bar" data-testid="decision-bar">
      <div className="decision-left">
        <div className="decision-heading">
          <h3 className="section-title">Classificar esta música</h3>
          <p className="section-hint muted">
            Escolha a classificação baseada na energia e no seu critério.
          </p>
        </div>
        <div className="decision-cards">
          <ClassActionCard
            label="-1"
            detail="Energia baixa"
            digit="1"
            tone="lento"
            enabled={enabled}
            onClick={() => onDecide(-1)}
          />
          <ClassActionCard
            label="neutra"
            detail="Energia equilibrada"
            digit="2"
            tone="neutro"
            enabled={enabled}
            onClick={() => onDecide(0)}
          />
          <ClassActionCard
            label="+1"
            detail="Energia alta"
            digit="3"
            tone="animada"
            enabled={enabled}
            onClick={() => onDecide(1)}
          />
        </div>
      </div>
      <VDivider />
      <div className="decision-shortcuts">
        <span className="label-sentence">Atalhos do teclado</span>
        {SHORTCUTS.map(([key, desc]) => (
          <div key={key} className="shortcut-row">
            <Kbd>{key}</Kbd>
            <span className="muted">{desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
