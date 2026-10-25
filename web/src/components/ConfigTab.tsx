import { ConfigDashboard } from "./ConfigDashboard";
import { ConfigSetupForm } from "./ConfigSetupForm";

/**
 * Aba Configuracao: duas faces.
 *
 * No app configurado, o dashboard do mockup (Settings): auto-save, sem
 * botao Salvar. No primeiro uso (sem config.toml), o formulario classico
 * com envio explicito -- o mockup nao desenha primeiro uso, e o apply cria
 * o arquivo: nao existe auto-save do que ainda nao existe.
 */
interface ConfigTabProps {
  setup?: boolean;
  onSaved?: () => void;
}

export function ConfigTab({ setup = false, onSaved }: ConfigTabProps) {
  if (setup) {
    return <ConfigSetupForm onSaved={onSaved} />;
  }
  return <ConfigDashboard />;
}
