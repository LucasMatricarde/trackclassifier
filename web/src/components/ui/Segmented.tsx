import type { ReactNode } from "react";

export interface SegmentedOption {
  value: string;
  label: string;
  disabled?: boolean;
  /** Ícone opcional antes do rótulo (a Biblioteca usa no toggle de visualização). */
  icon?: ReactNode;
}

interface SegmentedProps {
  options: string[] | SegmentedOption[];
  selected: number | string;
  onChange: (value: string | number) => void;
  className?: string;
}

/**
 * Alternador de N posicoes visiveis lado a lado.
 * Port de segmented.py.
 *
 * Dois modos: array de strings (legado, a Revisao usa para o seletor de
 * perfil) e array de objetos {value, label, disabled?}. No legado o
 * onChange recebe o indice (number); no modo objeto, o value (string).
 * O chamador deve usar Number() ou cast se precisar garantir o tipo.
 *
 * className permite namespacing do estilo: as regras de .segmented/.segment
 * sao globais e a Biblioteca precisa de um visual diferente sem mexer
 * na tela de Revisao.
 */
export function Segmented({
  options,
  selected,
  onChange,
  className = "",
}: SegmentedProps) {
  const legado = options.length === 0 || typeof options[0] === "string";

  const itens: SegmentedOption[] = legado
    ? (options as string[]).map((label, i) => ({ value: String(i), label }))
    : (options as SegmentedOption[]);

  const selecionado = String(selected);

  return (
    <div className={`segmented ${className}`.trim()} role="radiogroup">
      {itens.map((opt) => {
        const isSelected = opt.value === selecionado;
        return (
          <button
            key={opt.value}
            className={`segment ${isSelected ? "selected" : ""}`}
            role="radio"
            aria-checked={isSelected}
            aria-disabled={opt.disabled}
            onClick={() => {
              if (opt.disabled) return;
              // No legado o value e o indice em string: devolve number para
              // nao quebrar o onChange da Revisao, que indexa o array.
              onChange(legado ? Number(opt.value) : opt.value);
            }}
            disabled={opt.disabled}
          >
            {opt.icon && <span className="segment-icon">{opt.icon}</span>}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}