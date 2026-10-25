import { useEffect, useState } from "react";
import { useProfilesControl, validaNomePerfil } from "../hooks/useProfiles";
import { ConfirmDialog } from "./ui/ConfirmDialog";

/**
 * Dialogos de perfil (criar, renomear, excluir, trocar com fila pendente),
 * todos sobre o ConfirmDialog. Um unico componente montado no App: quem abre
 * (header, sidebar) so chama `perfis.abre(...)`.
 */
export function ProfileDialogs() {
  const perfis = useProfilesControl();
  const dialogo = perfis?.dialogo ?? null;

  const [nome, setNome] = useState("");
  const [copiar, setCopiar] = useState(true);
  // O erro de validacao so aparece depois da primeira edicao: abrir o dialogo
  // de criar com o campo vazio nao pode abrir ja gritando.
  const [tocou, setTocou] = useState(false);

  // Reinicia o formulario a cada abertura (o componente fica montado).
  useEffect(() => {
    if (!perfis?.state) return;
    setTocou(false);
    setCopiar(true);
    if (dialogo?.tipo === "renomear") {
      setNome(perfis.state.profiles.find((p) => p.id === dialogo.id)?.name ?? "");
    } else {
      setNome("");
    }
    // Depende so do dialogo: o state de perfis muda a cada operacao.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dialogo?.tipo, dialogo && "id" in dialogo ? dialogo.id : null]);

  if (!perfis?.state || !dialogo) return null;
  const { profiles, active } = perfis.state;
  const nomeDe = (id: string) => profiles.find((p) => p.id === id)?.name ?? id;
  const ativo = nomeDe(active);

  const campoNome = (
    <label className="dialog-campo">
      <span className="dialog-campo-rotulo">Nome do perfil</span>
      <input
        type="text"
        className="config-input"
        data-testid="profile-name-input"
        value={nome}
        maxLength={60}
        autoComplete="off"
        spellCheck={false}
        onChange={(e) => {
          setNome(e.target.value);
          setTocou(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !erroNome && !perfis.ocupado) confirmar();
        }}
      />
    </label>
  );

  const ignorar = dialogo.tipo === "renomear" ? dialogo.id : undefined;
  const erroNome =
    dialogo.tipo === "criar" || dialogo.tipo === "renomear"
      ? validaNomePerfil(nome, profiles, ignorar)
      : null;
  const mostraErroNome = tocou && erroNome;

  function confirmar() {
    if (!perfis || !dialogo) return;
    if (dialogo.tipo === "criar") void perfis.confirmaCriar(nome, copiar);
    else if (dialogo.tipo === "renomear") void perfis.confirmaRenomear(dialogo.id, nome);
    else if (dialogo.tipo === "excluir") void perfis.confirmaExcluir(dialogo.id);
    else void perfis.confirmaTroca(dialogo.id);
  }

  const comum = {
    open: true,
    busy: perfis.ocupado,
    error: perfis.erro,
    onConfirm: confirmar,
    onCancel: perfis.fecha,
  };

  if (dialogo.tipo === "criar") {
    return (
      <ConfirmDialog
        {...comum}
        title="Novo perfil"
        message="Dê um nome ao perfil. Ele passa a ser o perfil ativo."
        confirmLabel="Criar perfil"
        busyLabel="Criando…"
        focoInicial="conteudo"
        confirmDisabled={!!erroNome}
      >
        {campoNome}
        {mostraErroNome && (
          <span className="config-error" data-testid="profile-name-error">
            {erroNome}
          </span>
        )}
        <label className="dialog-check">
          <input
            type="checkbox"
            className="library-checkbox"
            data-testid="profile-copy-folders"
            checked={copiar}
            onChange={(e) => setCopiar(e.target.checked)}
          />
          Copiar pastas do perfil ativo
        </label>
        {dialogo.pendentes > 0 && (
          <p className="dialog-aviso" data-testid="profile-pending-warning">
            {dialogo.pendentes}{" "}
            {dialogo.pendentes === 1 ? "faixa pendente" : "faixas pendentes"} em{" "}
            {ativo} continuam na fila desse perfil.
          </p>
        )}
      </ConfirmDialog>
    );
  }

  if (dialogo.tipo === "renomear") {
    return (
      <ConfirmDialog
        {...comum}
        title="Renomear perfil"
        message={`Novo nome para ${nomeDe(dialogo.id)}.`}
        confirmLabel="Renomear"
        busyLabel="Renomeando…"
        focoInicial="conteudo"
        confirmDisabled={!!erroNome}
      >
        {campoNome}
        {mostraErroNome && (
          <span className="config-error" data-testid="profile-name-error">
            {erroNome}
          </span>
        )}
      </ConfirmDialog>
    );
  }

  if (dialogo.tipo === "excluir") {
    const eAtivo = dialogo.id === active;
    const proximo = profiles.find((p) => p.id !== dialogo.id);
    return (
      <ConfirmDialog
        {...comum}
        title="Excluir perfil"
        message={
          `Excluir ${nomeDe(dialogo.id)}? As pastas e as faixas no disco não são apagadas, ` +
          "só as configurações do perfil." +
          (eAtivo && proximo ? ` O perfil ativo passa a ser ${proximo.name}.` : "")
        }
        confirmLabel="Excluir"
        busyLabel="Excluindo…"
      />
    );
  }

  return (
    <ConfirmDialog
      {...comum}
      title="Trocar de perfil"
      message={
        `${dialogo.pendentes} ${dialogo.pendentes === 1 ? "faixa pendente" : "faixas pendentes"} ` +
        `na fila de revisão de ${ativo}. Trocar para ${nomeDe(dialogo.id)} não descarta a fila: ` +
        "ela volta quando você retornar a esse perfil."
      }
      confirmLabel="Trocar"
      busyLabel="Trocando…"
    />
  );
}
