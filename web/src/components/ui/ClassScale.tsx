interface ClassScaleProps {
  label: string | null;
}

// Mesma ordem de LABEL_ORDER que o OrdinalScale da Revisao: -1, neutra, +1.
const SEGMENTOS = [
  { valor: "-1", classe: "class-scale-down", rotulo: "-1" },
  { valor: "neutra", classe: "class-scale-neutral", rotulo: "neutra" },
  { valor: "+1", classe: "class-scale-up", rotulo: "+1" },
] as const;

/**
 * Escala de classe da linha da Biblioteca: tres segmentos, so o ativo
 * aceso na cor da classe. Diferente do OrdinalScale (que marca o palpite
 * do modelo), aqui o segmento aceso e o label decidido pelo usuario.
 */
export function ClassScale({ label }: ClassScaleProps) {
  return (
    <span
      className="class-scale"
      role="img"
      aria-label={`Classe: ${label ?? "sem classe"}`}
    >
      {SEGMENTOS.map((seg) => (
        <span
          key={seg.valor}
          className={`class-scale-seg ${label === seg.valor ? seg.classe : ""}`}
        />
      ))}
    </span>
  );
}
