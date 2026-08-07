import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, TrackAnalysis

_COLUNAS_META = [
    "sha1",
    "filename",
    "extractor",
    "energy_curve",
    "peak_offset_s",
    "meta_bpm",
    "meta_duration_s",
]
_CHUNK = 1024 * 1024


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _nome_livre(base: Path) -> Path:
    """base, ou base-2/base-3/... se ja houver arquivo la.

    Nunca sobrescreve: cada quarentena guarda um parquet distinto, e o que
    esta ali e justamente o dado que nao se quer perder. Dois updates de
    versao seguidos, cada um deixando um arquivo ilegivel, produzem dois
    arquivos -- nao um substituindo o outro.
    """
    contador = 1
    candidato = base
    while candidato.exists():
        contador += 1
        candidato = base.with_name(f"{base.name}-{contador}")
    return candidato


class AnalysisCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._linhas: dict[str, dict] = {}
        #: Mensagem pronta para exibicao quando o parquet existia mas nao
        #: pode ser lido. None no caminho normal. Quem constroi o cache
        #: (TrackService) reporta -- ver o porque em _isola().
        self.load_error: str | None = None
        #: A copia de seguranca de save() e uma vez por processo, nao por
        #: chamada. Ver _guarda_geracao_de_abertura().
        self._geracao_guardada = False
        if self.path.is_file():
            try:
                frame = pd.read_parquet(self.path)
            except Exception as erro:
                # Parquet corrompido ou com schema incompativel (escrita
                # interrompida, drift de versao): trata como se o arquivo
                # nao existisse em vez de derrubar todo comando da CLI.
                frame = None
                self.load_error = self._isola(erro)
            if frame is not None:
                for registro in frame.to_dict(orient="records"):
                    self._linhas[registro["sha1"]] = registro

    def _isola(self, erro: Exception) -> str:
        """Tira o parquet ilegivel do caminho e devolve o que dizer sobre ele.

        Sem isto o arquivo continuaria onde esta com o cache aberto vazio, e o
        primeiro save() do scan escreveria POR CIMA dele via os.replace --
        horas de extracao substituidas por um punhado de linhas novas, sem
        mensagem nenhuma. A causa tipica nao e disco ruim: e bump de
        pyarrow/pandas ou schema novo num update de versao, ou seja, um
        arquivo perfeitamente integro que so esta versao nao sabe ler. Uma
        versao futura (ou um downgrade) pode ler de volta o que fica aqui.

        Renomear em vez de copiar: o objetivo e justamente que self.path
        deixe de existir, para que o save() seguinte crie um arquivo novo
        sem destruir nada.
        """
        destino = _nome_livre(self.path.with_suffix(self.path.suffix + ".corrupt"))
        try:
            os.replace(self.path, destino)
        except OSError as falha:
            # Sem permissao de escrita no data_dir, ou o arquivo sumiu entre
            # a leitura e agora. Nao ha o que isolar, mas quem chama ainda
            # precisa saber que o cache abriu vazio.
            return (
                f"Cache de analises ilegivel ({erro}) e nao deu para isolar "
                f"({falha}). As tracks serao reanalisadas."
            )
        return (
            f"Cache de analises ilegivel ({erro}). O arquivo original foi "
            f"preservado em {destino.name} -- as tracks serao reanalisadas, "
            "mas nada foi apagado."
        )

    def _guarda_geracao_de_abertura(self) -> None:
        """Copia o parquet como estava na ABERTURA para .prev, uma unica vez.

        Uma vez por processo, e nao a cada save: save() roda a cada 10
        extracoes, entao rotacionar sempre deixaria o .prev dez tracks atras
        do arquivo atual -- inutil contra a escrita ruim que ele existe para
        desfazer. Fixo na abertura, .prev e "como estava antes desta versao
        do app mexer", que e a pergunta que se faz depois de um update.

        Copia, nao renomeia: um to_parquet que falhasse depois do rename
        deixaria o data_dir sem cache nenhum.
        """
        if self._geracao_guardada:
            return
        # Marca antes de tentar: se a copia falhar por disco cheio, nao vale
        # repetir a tentativa (e o custo dela) a cada save do scan.
        self._geracao_guardada = True
        if not self.path.is_file():
            return
        anterior = self.path.with_suffix(self.path.suffix + ".prev")
        tmp = anterior.with_suffix(anterior.suffix + ".tmp")
        try:
            shutil.copyfile(self.path, tmp)
            os.replace(tmp, anterior)
        except OSError:
            # Rede de seguranca nao pode impedir o save de verdade: disco
            # cheio ou permissao aqui so significa ficar sem a copia.
            tmp.unlink(missing_ok=True)

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, sha1: str, extractor: str | None = None) -> TrackAnalysis | None:
        registro = self._linhas.get(sha1)
        if registro is None:
            return None
        if extractor is not None and registro["extractor"] != extractor:
            return None
        return TrackAnalysis(
            vector=np.asarray([registro[nome] for nome in FEATURE_NAMES], dtype=np.float64),
            energy_curve=json.loads(registro["energy_curve"]),
            peak_offset_s=float(registro["peak_offset_s"]),
            bpm=float(registro["meta_bpm"]),
            duration_s=float(registro["meta_duration_s"]),
        )

    def put(self, sha1: str, filename: str, extractor: str, analysis: TrackAnalysis) -> None:
        registro = {
            "sha1": sha1,
            "filename": filename,
            "extractor": extractor,
            "energy_curve": json.dumps(analysis.energy_curve),
            "peak_offset_s": float(analysis.peak_offset_s),
            "meta_bpm": float(analysis.bpm),
            "meta_duration_s": float(analysis.duration_s),
        }
        registro.update(
            {nome: float(valor) for nome, valor in zip(FEATURE_NAMES, analysis.vector, strict=True)}
        )
        self._linhas[sha1] = registro

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._guarda_geracao_de_abertura()
        frame = pd.DataFrame(list(self._linhas.values()), columns=_COLUNAS_META + FEATURE_NAMES)
        # Escrita atomica: grava num arquivo temporario no mesmo diretorio e
        # so entao substitui o arquivo real via os.replace (atomico no
        # nivel do SO). Uma interrupcao (Ctrl+C, crash) durante a escrita do
        # temporario nunca corrompe o cache que ja estava no disco.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, self.path)
