import { useCallback, useEffect, useState } from "react";
import { applyConfig, getConfig, validateConfig } from "../api/client";
import type { ConfigState } from "../api/types";
import {
  draftFromRaw,
  mudou,
  rawFromDraft,
  type ConfigDraftValues,
} from "../configDraft";

const DEBOUNCE_MS = 300;
/** Auto-save espera um pouco mais que a validacao: edicao de caminho tem
 * pausas maiores entre toques do que um stepper. */
const AUTO_SAVE_MS = 800;
/** Campos que o servidor normaliza ao gravar (expanduser, data_dir relativo)
 * e que o auto-save reconcilia com o raw recarregado. */
const CAMPOS_DE_CAMINHO = [
  "inbox",
  "up",
  "neutral",
  "down",
  "data_dir",
] as const;

function mensagem(erro: unknown): string {
  return erro instanceof Error ? erro.message : String(erro);
}

/**
 * Estado do formulario de configuracao.
 *
 * Valida a cada mudanca (com debounce, como o settings_form do Qt). Com
 * `autoSave` (tela Configuracao do dashboard), o apply sai sozinho quando o
 * rascunho valida sem erro e difere do salvo -- o mockup nao desenha botao
 * de Salvar ("Todas as configuracoes sao salvas automaticamente"). Sem
 * `autoSave` (primeiro uso), so o botao explicito aplica: nao existe
 * auto-save do que ainda nao existe.
 */
export function useConfig(opts: { autoSave?: boolean } = {}) {
  const autoSave = opts.autoSave ?? false;
  const [state, setState] = useState<ConfigState | null>(null);
  const [draft, setDraft] = useState<ConfigDraftValues | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [autoSaveFalhou, setAutoSaveFalhou] = useState(false);
  const [falha, setFalha] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const carrega = useCallback(async () => {
    setCarregando(true);
    try {
      const resposta = await getConfig();
      setState(resposta);
      setDraft(draftFromRaw(resposta.raw, resposta.active_profile));
      setErrors({});
      setFalha(null);
    } catch (erro) {
      setFalha(mensagem(erro));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    carrega();
  }, [carrega]);

  const atualiza = (
    campo: keyof ConfigDraftValues,
    valor: string | number | boolean
  ) => {
    setDraft((atual) => (atual ? { ...atual, [campo]: valor } : atual));
    setSaved(false);
    setAutoSaveFalhou(false);
  };

  useEffect(() => {
    if (!state || !draft) return;
    const timer = setTimeout(async () => {
      try {
        const resultado = await validateConfig(
          rawFromDraft(state.raw, state.active_profile, draft)
        );
        setErrors(resultado.errors);
      } catch (erro) {
        setFalha(mensagem(erro));
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [state, draft]);

  const original =
    state && draft ? draftFromRaw(state.raw, state.active_profile) : null;
  const sujo = !!(original && draft && mudou(original, draft));
  const valido = Object.keys(errors).length === 0;

  /**
   * Auto-save: aplica quando o rascunho valida e difere do salvo. O draft
   * NAO e recarregado do servidor depois do apply -- se a pessoa digitou
   * mais alguma coisa durante a ida e volta do POST, o refetch sobrescreveria
   * o que ela esta vendo (o mesmo truque do painel de settings do Modelo).
   * Falha trava novas tentativas para este rascunho ate a proxima edicao:
   * sem isso o efeito re-dispara a cada render e martela o servidor.
   *
   * Excecao: os CAMPOS_DE_CAMINHO sao reconciliados com o raw recarregado.
   * O servidor normaliza o que chega (expanduser, data_dir relativo), entao
   * o valor gravado difere do digitado -- sem sincronizar, o rascunho ficaria
   * 'sujo' para sempre e o auto-save reaplicaria a cada 800ms. So toca
   * campos que a pessoa nao editou desde o envio (iguais ao do apply).
   */
  useEffect(() => {
    if (!autoSave || !state || !draft || !sujo || !valido || saving) return;
    if (autoSaveFalhou) return;
    const enviado = draft;
    const raw = rawFromDraft(state.raw, state.active_profile, draft);
    const timer = setTimeout(async () => {
      setSaving(true);
      setFalha(null);
      try {
        await applyConfig(raw);
        const resposta = await getConfig();
        setState(resposta);
        const normalizado = draftFromRaw(resposta.raw, resposta.active_profile);
        setDraft((atual) => {
          if (!atual) return atual;
          const mesclado = { ...atual };
          let mudou = false;
          for (const campo of CAMPOS_DE_CAMINHO) {
            if (
              mesclado[campo] === enviado[campo] &&
              mesclado[campo] !== normalizado[campo]
            ) {
              mesclado[campo] = normalizado[campo];
              mudou = true;
            }
          }
          return mudou ? mesclado : atual;
        });
        setErrors({});
        setSaved(true);
      } catch (erro) {
        setFalha(mensagem(erro));
        setAutoSaveFalhou(true);
      } finally {
        setSaving(false);
      }
    }, AUTO_SAVE_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSave, state, draft, sujo, valido, saving, autoSaveFalhou]);

  const salvar = async (): Promise<boolean> => {
    if (!state || !draft) return false;
    setSaving(true);
    setFalha(null);
    try {
      await applyConfig(rawFromDraft(state.raw, state.active_profile, draft));
      const resposta = await getConfig();
      setState(resposta);
      setDraft(draftFromRaw(resposta.raw, resposta.active_profile));
      setErrors({});
      setSaved(true);
      return true;
    } catch (erro) {
      setFalha(mensagem(erro));
      return false;
    } finally {
      setSaving(false);
    }
  };

  return {
    state,
    draft,
    errors,
    saving,
    saved,
    falha,
    carregando,
    sujo,
    podeSalvar: sujo && valido && !saving,
    atualiza,
    salvar,
    recarrega: carrega,
  };
}
