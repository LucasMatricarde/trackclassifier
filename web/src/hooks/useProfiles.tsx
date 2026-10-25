import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";
import {
  activateProfile,
  createProfile,
  deleteProfile,
  duplicateProfile,
  getProfiles,
  getReviewState,
  onWSMessage,
  renameProfile,
  scan,
} from "../api/client";
import type { Profile, ProfilesState } from "../api/types";

/** Id do perfil que nao pode ser excluido (o que a migracao cria). */
export const PERFIL_PADRAO_ID = "default";

/** Qual dialogo de perfil esta aberto. `pendentes` e a fila de Revisao do
 * perfil ativo no momento em que o dialogo abriu: trocar ou criar (que
 * tambem ativa) deixa essas faixas para tras, entao a pessoa confirma. */
export type DialogoPerfil =
  | { tipo: "criar"; pendentes: number }
  | { tipo: "renomear"; id: string }
  | { tipo: "excluir"; id: string }
  | { tipo: "trocar"; id: string; pendentes: number };

export interface ProfilesControl {
  /** null enquanto carrega ou quando o servidor nao responde (a UI some). */
  state: ProfilesState | null;
  ativo: Profile | null;
  dialogo: DialogoPerfil | null;
  ocupado: boolean;
  erro: string | null;
  /** Registrado pela Configuracao: grava o rascunho pendente ANTES de uma
   * operacao de perfil, senao o debounce do auto-save grava o rascunho do
   * perfil antigo depois da troca. */
  flushRef: MutableRefObject<(() => Promise<void>) | null>;
  abre: (dialogo: "criar" | { renomear: string } | { excluir: string }) => void;
  fecha: () => void;
  /** Troca pelo dropdown: pede confirmacao quando ha fila pendente. */
  pedeTroca: (id: string) => void;
  confirmaTroca: (id: string) => Promise<void>;
  confirmaCriar: (nome: string, copiarPastas: boolean) => Promise<void>;
  confirmaRenomear: (id: string, nome: string) => Promise<void>;
  confirmaExcluir: (id: string) => Promise<void>;
  duplica: (id: string) => Promise<void>;
  recarrega: () => Promise<void>;
}

const ProfilesContext = createContext<ProfilesControl | null>(null);

/** null fora do Provider (primeiro uso, testes de componente isolado). */
export function useProfilesControl(): ProfilesControl | null {
  return useContext(ProfilesContext);
}

function mensagem(erro: unknown): string {
  return erro instanceof Error ? erro.message : String(erro);
}

/** Mesma regra do servidor (validate_profile_name), para o dialogo mostrar o
 * erro antes do POST. O servidor continua sendo a borda que decide. */
export function validaNomePerfil(
  nome: string,
  perfis: Profile[],
  ignorarId?: string
): string | null {
  const limpo = nome.trim();
  if (!limpo) return "Informe um nome para o perfil.";
  const repetido = perfis.some(
    (p) => p.id !== ignorarId && p.name.trim().toLowerCase() === limpo.toLowerCase()
  );
  return repetido ? "Já existe um perfil com esse nome." : null;
}

async function pendentesDaFila(): Promise<number> {
  try {
    return (await getReviewState()).remaining;
  } catch {
    // Sem o numero nao ha o que avisar: segue sem o aviso em vez de travar.
    return 0;
  }
}

export function ProfilesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ProfilesState | null>(null);
  const [dialogo, setDialogo] = useState<DialogoPerfil | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const flushRef = useRef<(() => Promise<void>) | null>(null);

  const recarrega = useCallback(async () => {
    try {
      setState(await getProfiles());
    } catch {
      // Borda: sem perfis a tela segue sem o dropdown, nao cai.
      setState(null);
    }
  }, []);

  useEffect(() => {
    void recarrega();
    return onWSMessage((msg) => {
      if (
        msg.type === "profile_changed" ||
        msg.type === "profiles_changed" ||
        msg.type === "config_reloaded"
      ) {
        void recarrega();
      }
    });
  }, [recarrega]);

  const fecha = useCallback(() => {
    setDialogo(null);
    setErro(null);
  }, []);

  /** Roda uma operacao de perfil: flush do auto-save, trava o dialogo, mostra
   * a falha nele (Confirmar vira "tentar de novo") e fecha no sucesso. */
  const executa = useCallback(
    async (acao: () => Promise<ProfilesState>, novoAtivo = false) => {
      setOcupado(true);
      setErro(null);
      try {
        await flushRef.current?.();
        const novo = await acao();
        setState(novo);
        setDialogo(null);
        // Ativar outro perfil escaneia a pasta dele: sem isso a fila nasce
        // vazia (mesmo caminho da pill da Revisao).
        if (novoAtivo) void scan().catch(() => {});
      } catch (e) {
        setErro(mensagem(e));
      } finally {
        setOcupado(false);
      }
    },
    []
  );

  const abre = useCallback<ProfilesControl["abre"]>((alvo) => {
    setErro(null);
    if (alvo === "criar") {
      // O perfil novo vira o ativo: a fila do atual fica para tras.
      void pendentesDaFila().then((pendentes) =>
        setDialogo({ tipo: "criar", pendentes })
      );
    } else if ("renomear" in alvo) {
      setDialogo({ tipo: "renomear", id: alvo.renomear });
    } else {
      setDialogo({ tipo: "excluir", id: alvo.excluir });
    }
  }, []);

  const pedeTroca = useCallback(
    (id: string) => {
      if (!state || id === state.active) return;
      void pendentesDaFila().then((pendentes) => {
        if (pendentes > 0) {
          setErro(null);
          setDialogo({ tipo: "trocar", id, pendentes });
        } else {
          void executa(() => activateProfile(id), true);
        }
      });
    },
    [state, executa]
  );

  const control = useMemo<ProfilesControl>(
    () => ({
      state,
      ativo: state?.profiles.find((p) => p.id === state.active) ?? null,
      dialogo,
      ocupado,
      erro,
      flushRef,
      abre,
      fecha,
      pedeTroca,
      confirmaTroca: (id) => executa(() => activateProfile(id), true),
      confirmaCriar: (nome, copiar) =>
        executa(() => createProfile(nome.trim(), copiar), true),
      confirmaRenomear: (id, nome) =>
        executa(() => renameProfile(id, nome.trim())),
      // Excluir o ativo troca para o proximo (decisao do servidor): escaneia.
      confirmaExcluir: (id) =>
        executa(() => deleteProfile(id), id === state?.active),
      duplica: (id) => executa(() => duplicateProfile(id)),
      recarrega,
    }),
    [state, dialogo, ocupado, erro, abre, fecha, pedeTroca, executa, recarrega]
  );

  return (
    <ProfilesContext.Provider value={control}>
      {children}
    </ProfilesContext.Provider>
  );
}
