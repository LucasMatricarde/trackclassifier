import { useState } from "react";
import { useProfilesControl } from "../hooks/useProfiles";
import { Popover } from "./ui/Popover";
import { IconeCheck, IconeChevron, IconeMais } from "./ui/ModelIcons";

/**
 * Seletor de perfil do header da Configuracao: rotulo "Perfil", dropdown com
 * o nome do ativo e o botao outline "+ Novo perfil". Sem perfis (servidor
 * antigo, primeiro uso) nao desenha nada.
 */
export function ProfileSwitcher() {
  const perfis = useProfilesControl();
  const [aberto, setAberto] = useState(false);

  if (!perfis?.state || !perfis.ativo) return null;
  const { profiles, active } = perfis.state;

  return (
    <div className="app-perfil" data-testid="profile-switcher">
      <span className="app-perfil-rotulo">Perfil</span>
      <Popover
        open={aberto}
        onClose={() => setAberto(false)}
        trigger={
          <button
            type="button"
            className="app-perfil-botao"
            data-testid="profile-dropdown"
            data-popover-trigger
            aria-haspopup="listbox"
            aria-expanded={aberto}
            onClick={() => setAberto((v) => !v)}
          >
            <span className="app-perfil-nome">{perfis.ativo.name}</span>
            <IconeChevron />
          </button>
        }
      >
        <ul
          className="perfil-lista"
          role="listbox"
          aria-label="Perfis"
          data-testid="profile-list"
        >
          {profiles.map((p) => (
            <li key={p.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={p.id === active}
                className={`perfil-item${p.id === active ? " perfil-item-ativo" : ""}`}
                data-testid="profile-option"
                onClick={() => {
                  setAberto(false);
                  perfis.pedeTroca(p.id);
                }}
              >
                <span className="perfil-item-nome">{p.name}</span>
                {p.id === active && (
                  <span className="perfil-item-check">
                    <IconeCheck />
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </Popover>
      <button
        type="button"
        className="btn-scan btn-scan--perfil"
        data-testid="profile-new"
        onClick={() => perfis.abre("criar")}
      >
        <IconeMais />
        Novo perfil
      </button>
    </div>
  );
}
