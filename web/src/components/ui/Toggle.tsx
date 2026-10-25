/**
 * Toggle da secao "Organizacao automatica" da Configuracao, geometricamente
 * o do mockup (trilho 52x28 pill, knob 22px). Cores por tokens
 * color.settings.toggle-*, nunca hex local.
 *
 * `somenteVisual` e o padrao dos elementos que o mockup desenha mas o
 * backend ainda nao tem (ex.: "Manter uma copia na entrada"): aria-disabled
 * sem handler, como o menu de linha e "Ver recomendacoes" do Modelo.
 */

interface ToggleProps {
  ligado: boolean;
  onChange?: (ligado: boolean) => void;
  somenteVisual?: boolean;
  rotulo: string;
  descricao: string;
  testid?: string;
}

export function Toggle({
  ligado,
  onChange,
  somenteVisual = false,
  rotulo,
  descricao,
  testid,
}: ToggleProps) {
  return (
    <div className="config-toggle-item">
      <button
        type="button"
        role="switch"
        aria-checked={ligado}
        aria-disabled={somenteVisual || undefined}
        data-testid={testid}
        className="config-toggle"
        onClick={somenteVisual ? undefined : () => onChange?.(!ligado)}
      >
        <span className="config-toggle-knob" aria-hidden="true" />
      </button>
      <div className="config-toggle-texto">
        <span className="config-toggle-label">{rotulo}</span>
        <p className="config-toggle-desc">{descricao}</p>
      </div>
    </div>
  );
}
