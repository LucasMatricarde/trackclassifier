import os
import shutil
from pathlib import Path


class FileVanishedError(Exception):
    pass


def _destino_livre(dest_dir: Path, nome: str) -> Path:
    """Reivindica atomicamente um nome de arquivo livre dentro de dest_dir.

    Usa os.open(..., O_CREAT | O_EXCL) para criar um placeholder vazio: essa
    chamada e atomica no nivel do sistema operacional e falha com
    FileExistsError se o caminho ja existir. Isso fecha a janela de
    "verificar se o nome esta livre, depois mover para la" (TOCTOU) que um
    `if not candidato.exists(): return candidato` teria. A atomicidade e o
    que garante seguranca quando move_to_folder e chamado concorrentemente
    por threads do mesmo processo -- caso real deste projeto, ja que as
    rotas do servico web (/api/decide, /api/bulk-approve) sao sincronas e o
    Starlette/FastAPI as executa em um thread pool: duas requisicoes podem
    cair em threads diferentes ao mesmo tempo e disputar o mesmo nome de
    destino.
    """
    base = Path(nome).stem
    sufixo = Path(nome).suffix
    contador = 0
    while True:
        candidato_nome = nome if contador == 0 else f"{base} ({contador}){sufixo}"
        candidato = dest_dir / candidato_nome
        try:
            fd = os.open(str(candidato), os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            contador += 1
            continue
        os.close(fd)
        return candidato


def move_to_folder(src: Path, dest_dir: Path) -> Path:
    """Move src para dentro de dest_dir preservando bytes e sem sobrescrever.

    A reserva do nome de destino (_destino_livre) e atomica, o que torna
    seguro chamar esta funcao concorrentemente a partir de threads do mesmo
    processo (por exemplo, as rotas sincronas do servico web executadas no
    thread pool do Starlette/FastAPI) sem risco de duas chamadas resolverem
    o mesmo nome livre e uma delas sobrescrever silenciosamente a outra.
    """
    src = Path(src)
    if not src.is_file():
        raise FileVanishedError(f"Arquivo nao existe mais: {src}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    destino = _destino_livre(dest_dir, src.name)
    try:
        shutil.move(str(src), str(destino))
    except BaseException:
        # Qualquer falha durante o move (disco cheio, permissao, drive
        # desmontado) nao pode deixar o placeholder vazio reservado por
        # _destino_livre para tras dentro de uma pasta rotulada real do
        # usuario -- ele seria rescaneado e falharia na analise para sempre.
        destino.unlink(missing_ok=True)
        raise
    return destino
