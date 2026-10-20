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

function mensagem(erro: unknown): string {
  return erro instanceof Error ? erro.message : String(erro);
}

/**
 * Estado do formulario de configuracao.
 *
 * Valida a cada mudanca (com debounce, como o settings_form do Qt) e so
 * libera o Salvar quando o rascunho difere do salvo e nao ha erro. O apply
 * revalida no servidor -- aqui a validacao e feedback, nao a garantia.
 */
export function useConfig() {
  const [state, setState] = useState<ConfigState | null>(null);
  const [draft, setDraft] = useState<ConfigDraftValues | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
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

  const atualiza = (campo: keyof ConfigDraftValues, valor: string | number) => {
    setDraft((atual) => (atual ? { ...atual, [campo]: valor } : atual));
    setSaved(false);
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

  const salvar = async () => {
    if (!state || !draft) return;
    setSaving(true);
    setFalha(null);
    try {
      await applyConfig(rawFromDraft(state.raw, state.active_profile, draft));
      const resposta = await getConfig();
      setState(resposta);
      setDraft(draftFromRaw(resposta.raw, resposta.active_profile));
      setErrors({});
      setSaved(true);
    } catch (erro) {
      setFalha(mensagem(erro));
    } finally {
      setSaving(false);
    }
  };

  const original =
    state && draft ? draftFromRaw(state.raw, state.active_profile) : null;
  const sujo = !!(original && draft && mudou(original, draft));
  const valido = Object.keys(errors).length === 0;

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
