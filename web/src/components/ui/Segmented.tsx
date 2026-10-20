interface SegmentedProps {
  options: string[];
  selected: number;
  onChange: (index: number) => void;
}

/**
 * Alternador de N posições visíveis lado a lado.
 * Port de segmented.py.
 */
export function Segmented({ options, selected, onChange }: SegmentedProps) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((opt, i) => (
        <button
          key={opt}
          className={`segment ${i === selected ? "selected" : ""}`}
          role="radio"
          aria-checked={i === selected}
          onClick={() => onChange(i)}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
