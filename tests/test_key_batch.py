"""Lote de deteccao de tonalidade (`TrackService.detect_keys_batch`).

Dois estilos de teste, de proposito:

* detector FALSO (atributo `_detector_de_key`) com `max_workers=1`: caminho
  sequencial, sem spawn, para afirmar as regras de negocio (tag, "none",
  cancelamento, saves) de forma rapida e deterministica;
* POOL DE VERDADE (`max_workers=2`) com triades sinteticas e com um detector
  de nivel de modulo que mata o proprio processo, para provar que o desenho
  em blocos contem a morte de um worker.

Nada aqui toca o acervo real: tudo roda em `tmp_path`.
"""

import hashlib
import os

import numpy as np
import pytest
import soundfile as sf

import trackclassifier.service as modulo
from tests.test_service import ExtratorFalso, _config, _povoa
from trackclassifier.keys import Key, Mode
from trackclassifier.labels import Label
from trackclassifier.presentation import PresentationCache
from trackclassifier.service import TrackService

SR = 22050
LA_MENOR = Key(9, Mode.MINOR)
DO_MAIOR = Key(0, Mode.MAJOR)


def _triade(caminho, frequencias, duracao=4.0):
    t = np.linspace(0, duracao, int(SR * duracao), endpoint=False)
    sinal = sum(np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) for f in frequencias)
    sf.write(caminho, (0.3 * sinal / np.abs(sinal).max()).astype(np.float32), SR)
    return caminho


def _triade_la_menor(caminho):
    return _triade(caminho, (220.0, 261.63, 329.63))


def _triade_do_maior(caminho):
    return _triade(caminho, (261.63, 329.63, 392.0))


def _servico(config, max_workers=1) -> TrackService:
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=max_workers)
    servico.analyze_all()
    return servico


def _hash(caminho) -> str:
    return hashlib.sha1(caminho.read_bytes()).hexdigest()


def _detector_fixo(chave):
    """Detector falso que devolve sempre a mesma key e anota quem foi decodificado."""
    chamadas: list[str] = []

    def _detecta(path):
        chamadas.append(path.name)
        return chave, None

    _detecta.chamadas = chamadas
    return _detecta


def _detector_que_nao_pode_rodar(path):
    raise AssertionError(f"o lote decodificou {path.name} que nao era alvo")


def _do_disco(config, sha1):
    return PresentationCache(
        config.data_dir / "presentation.parquet", config.data_dir / "covers"
    ).get(sha1)


# Nivel de modulo: o ProcessPoolExecutor serializa a funcao por referencia.
def _detector_que_morre_em_morto(path):
    """Mata o processo worker (como um segfault) para a track de nome 'morto'."""
    if "morto" in path.name:
        os._exit(1)
    return LA_MENOR, None


# --- regras de negocio (caminho sequencial, detector falso) -------------------


def test_lote_detecta_as_sem_key_e_grava_como_audio(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=2)  # 6 mp3 com bytes que nao sao audio
    servico = _servico(config)
    servico._detector_de_key = _detector_fixo(LA_MENOR)

    relatorio = servico.detect_keys_batch()

    assert (relatorio.total, relatorio.detected, relatorio.none) == (6, 6, 0)
    assert relatorio.cancelled is False
    for ref in servico._labeled:
        assert servico.key_for(ref.sha1) == LA_MENOR
        assert servico.key_source_for(ref.sha1) == "audio"
        # Persistiu: a janela reaberta nao paga o lote de novo.
        assert _do_disco(config, ref.sha1).key == LA_MENOR


def test_lote_nao_sobrescreve_a_key_de_tag(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    com_tag, *sem_tag = servico._labeled
    servico.presentation.set_key(com_tag.sha1, DO_MAIOR, "tag")
    detector = _detector_fixo(LA_MENOR)
    servico._detector_de_key = detector

    relatorio = servico.detect_keys_batch()

    assert servico.key_for(com_tag.sha1) == DO_MAIOR
    assert servico.key_source_for(com_tag.sha1) == "tag"
    assert com_tag.path.name not in detector.chamadas
    assert (relatorio.total, relatorio.skipped) == (len(sem_tag), 1)
    for ref in sem_tag:
        assert servico.key_source_for(ref.sha1) == "audio"


def test_lote_nao_retenta_o_que_ja_deu_none(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    for ref in servico._labeled:
        servico.presentation.set_key(ref.sha1, None, "none")
    servico._detector_de_key = _detector_que_nao_pode_rodar

    relatorio = servico.detect_keys_batch()

    assert (relatorio.total, relatorio.skipped) == (0, 3)
    assert all(servico.key_source_for(r.sha1) == "none" for r in servico._labeled)


def test_lote_nao_cria_registro_para_track_sem_apresentacao(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    orfa, *resto = servico._labeled
    del servico.presentation._linhas[orfa.sha1]
    servico._detector_de_key = _detector_fixo(LA_MENOR)

    relatorio = servico.detect_keys_batch()

    assert relatorio.total == len(resto)
    # set_key nao fabrica linha: o _preenche_apresentacao ainda leria as tags.
    assert servico.presentation.get(orfa.sha1) is None


def test_lote_com_falha_por_track_degrada_para_none_fora_de_failures(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)

    def _detector_quebrado(path):
        if path.name.startswith("t0_0.5"):
            return None, "AudioDecodeError: ffmpeg falhou"
        if path.name.startswith("t0_1."):
            raise RuntimeError("explodiu fora do worker")
        return LA_MENOR, None

    servico._detector_de_key = _detector_quebrado

    relatorio = servico.detect_keys_batch()

    assert (relatorio.total, relatorio.detected, relatorio.none) == (3, 1, 2)
    por_nome = {r.path.name: r for r in servico._labeled}
    for nome, ref in por_nome.items():
        esperado = "audio" if nome.startswith("t0_0.0") else "none"
        assert servico.key_source_for(ref.sha1) == esperado
    assert servico.failures() == []


def test_lote_com_arquivo_ilegivel_de_verdade_vira_none(tmp_path):
    # Sem detector falso: o detect_key real falha no ffmpeg (bytes nao sao audio).
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    alvo = _triade_la_menor(config.folders[Label.UP] / "triade_0.500.wav")
    servico.analyze_all()

    relatorio = servico.detect_keys_batch()

    assert (relatorio.detected, relatorio.none) == (1, 3)
    assert servico.key_for(next(r.sha1 for r in servico._labeled if r.path == alvo)) == LA_MENOR
    assert servico.failures() == []


def test_lote_cancelado_salva_o_parcial_e_deixa_o_resto_pendente(tmp_path, monkeypatch):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=3)  # 9 alvos
    servico = _servico(config)
    servico._detector_de_key = _detector_fixo(LA_MENOR)
    # Limiar alto: so o save do fim (que o cancelamento tambem tem que fazer)
    # pode ter gravado o parcial.
    monkeypatch.setattr(modulo, "_KEY_BATCH_SAVE_EVERY", 1000)
    feitas = []

    relatorio = servico.detect_keys_batch(
        on_progress=lambda f, t, n: feitas.append(n),
        should_cancel=lambda: len(feitas) >= 4,
    )

    assert relatorio.cancelled is True
    assert (relatorio.total, relatorio.detected) == (9, 4)
    gravadas = [r for r in servico._labeled if _do_disco(config, r.sha1).key == LA_MENOR]
    assert len(gravadas) == 4
    # O resto continua "nunca tentada": o proximo lote o pega.
    pendentes = [r for r in servico._labeled if _do_disco(config, r.sha1).key_source is None]
    assert len(pendentes) == 5
    assert servico.failures() == []


def test_lote_salva_a_cada_n_e_no_fim(tmp_path, monkeypatch):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=3)  # 9 alvos
    servico = _servico(config)
    servico._detector_de_key = _detector_fixo(LA_MENOR)
    monkeypatch.setattr(modulo, "_KEY_BATCH_SAVE_EVERY", 4)
    salvou = []
    original = servico.presentation.save
    monkeypatch.setattr(servico.presentation, "save", lambda: (salvou.append(1), original()))

    servico.detect_keys_batch()

    # Em 4 e em 8 (periodicos) e uma vez no fim, pela nona.
    assert len(salvou) == 3


def test_lote_sem_alvos_nao_salva_nada(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    for ref in servico._labeled:
        servico.presentation.set_key(ref.sha1, LA_MENOR, "tag")
    servico.presentation.save()
    antes = _hash(config.data_dir / "presentation.parquet")
    servico._detector_de_key = _detector_que_nao_pode_rodar

    relatorio = servico.detect_keys_batch()

    assert (relatorio.total, relatorio.detected, relatorio.none) == (0, 0, 0)
    assert _hash(config.data_dir / "presentation.parquet") == antes


def test_lote_reporta_progresso_ate_o_total(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    servico._detector_de_key = _detector_fixo(LA_MENOR)
    eventos = []

    servico.detect_keys_batch(on_progress=lambda f, t, n: eventos.append((f, t)))

    assert eventos == [(1, 3), (2, 3), (3, 3)]


def test_lote_nao_decodifica_o_mesmo_sha1_duas_vezes(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    # Mesmo conteudo em outra pasta: mesmo sha1, uma decodificacao so.
    original = next(config.folders[Label.UP].glob("*.mp3"))
    (config.folders[Label.DOWN] / "copia_0.001.mp3").write_bytes(original.read_bytes())
    servico = _servico(config)
    detector = _detector_fixo(LA_MENOR)
    servico._detector_de_key = detector

    relatorio = servico.detect_keys_batch()

    assert relatorio.total == len({r.sha1 for r in servico._labeled})
    assert len(detector.chamadas) == relatorio.total


# --- calibracao ---------------------------------------------------------------


def test_calibrar_mede_contra_a_tag_e_nao_grava_nada(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=2)  # 6 tracks
    servico = _servico(config)
    refs = sorted(servico._labeled, key=lambda r: r.path.name)
    # tag -> o que o detector "estima": exato, relativa, vizinha na roda, errada, none
    tags = [
        (refs[0], LA_MENOR, LA_MENOR),  # exato
        (refs[1], LA_MENOR, DO_MAIOR),  # relativa (8A vs 8B): vizinho
        (refs[2], Key(4, Mode.MINOR), Key(11, Mode.MINOR)),  # 9A vs 10A: vizinho
        (refs[3], LA_MENOR, Key(6, Mode.MAJOR)),  # 8A vs 2B: errado
        (refs[4], LA_MENOR, None),  # detector nao achou
    ]
    estimativas = {}
    for ref, tag, estimada in tags:
        servico.presentation.set_key(ref.sha1, tag, "tag")
        estimativas[ref.path.name] = estimada
    servico.presentation.save()  # refs[5] segue sem tag
    servico._detector_de_key = lambda path: (estimativas[path.name], None)
    parquet = config.data_dir / "presentation.parquet"
    antes = _hash(parquet)

    relatorio = servico.detect_keys_batch(calibrar=True)

    assert relatorio.calibrar is True
    assert (relatorio.com_tag, relatorio.total) == (5, 5)
    assert (relatorio.detected, relatorio.none) == (4, 1)
    assert relatorio.acerto_exato == 1
    assert relatorio.acerto_vizinho == 3  # exato + relativa + vizinha na roda
    assert relatorio.taxa_none == pytest.approx(0.2)
    # Nada gravado: nem em memoria nem em disco.
    assert _hash(parquet) == antes
    assert servico.key_source_for(refs[5].sha1) is None
    for ref, tag, _ in tags:
        assert servico.key_for(ref.sha1) == tag
        assert servico.key_source_for(ref.sha1) == "tag"


def test_calibrar_nao_salva_mesmo_cancelado(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=2)
    servico = _servico(config)
    for ref in servico._labeled:
        servico.presentation.set_key(ref.sha1, LA_MENOR, "tag")
    servico.presentation.save()
    parquet = config.data_dir / "presentation.parquet"
    antes = _hash(parquet)
    servico._detector_de_key = _detector_fixo(DO_MAIOR)
    feitas = []

    relatorio = servico.detect_keys_batch(
        on_progress=lambda f, t, n: feitas.append(n),
        should_cancel=lambda: len(feitas) >= 2,
        calibrar=True,
    )

    assert relatorio.cancelled is True
    assert _hash(parquet) == antes


# --- pool de verdade ----------------------------------------------------------


def test_pool_de_verdade_detecta_triades_e_devolve_a_key_do_worker(tmp_path):
    config = _config(tmp_path)
    _triade_la_menor(config.folders[Label.UP] / "am_0.500.wav")
    _triade_do_maior(config.folders[Label.DOWN] / "c_0.100.wav")
    # Duracao diferente: conteudo identico teria o mesmo sha1 e sairia do lote.
    _triade(config.folders[Label.NEUTRAL] / "am2_0.300.wav", (220.0, 261.63, 329.63), duracao=5.0)
    servico = _servico(config, max_workers=2)

    relatorio = servico.detect_keys_batch()

    assert (relatorio.total, relatorio.detected, relatorio.none) == (3, 3, 0)
    por_nome = {r.path.name: servico.key_for(r.sha1) for r in servico._labeled}
    assert por_nome == {
        "am_0.500.wav": LA_MENOR,
        "c_0.100.wav": DO_MAIOR,
        "am2_0.300.wav": LA_MENOR,
    }
    assert servico.failures() == []


def test_worker_morto_no_pool_degrada_so_a_track_dele_e_o_lote_segue(tmp_path):
    config = _config(tmp_path)
    for i, rotulo in enumerate((Label.UP, Label.DOWN, Label.NEUTRAL, Label.UP)):
        nome = "morto_0.100.mp3" if i == 0 else f"vivo{i}_0.{i}00.mp3"
        (config.folders[rotulo] / nome).write_bytes(nome.encode())
    servico = _servico(config, max_workers=2)
    servico._detector_de_key = _detector_que_morre_em_morto

    relatorio = servico.detect_keys_batch()

    # A morte quebra o executor do bloco inteiro; os vivos sao retentados em
    # pool de 1 e a que matou o processo de novo vira "none" -- so ela.
    assert (relatorio.total, relatorio.detected, relatorio.none) == (4, 3, 1)
    for ref in servico._labeled:
        if ref.path.name.startswith("morto"):
            assert servico.key_source_for(ref.sha1) == "none"
        else:
            assert servico.key_for(ref.sha1) == LA_MENOR
    assert servico.failures() == []


def test_empacotado_forca_pool_mesmo_com_um_unico_alvo(tmp_path, monkeypatch):
    # Empacotado, decodificar + chroma_cqt nunca roda no processo principal
    # (mesma contencao do scan; ver `_empacotado`). O executor falso conta
    # os pools criados: com 1 alvo e max_workers=4 o gate antigo era sequencial.
    config = _config(tmp_path)
    (config.folders[Label.UP] / "so_0.500.mp3").write_bytes(b"x")
    servico = _servico(config, max_workers=4)
    monkeypatch.setattr(modulo, "_empacotado", lambda: True)
    criados = []

    class _Futuro:
        def __init__(self, valor):
            self._valor = valor

        def result(self):
            return self._valor

    class _ExecutorFalso:
        def __init__(self, max_workers=None):
            criados.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, fn, path):
            return _Futuro(fn(path))

    monkeypatch.setattr(modulo, "ProcessPoolExecutor", _ExecutorFalso)
    monkeypatch.setattr(modulo, "as_completed", list)
    monkeypatch.setattr(modulo, "_aquece_cache_numba", lambda: None)
    monkeypatch.setattr(modulo, "_aquece_cache_do_chroma", lambda: None)
    servico._detector_de_key = _detector_fixo(LA_MENOR)

    relatorio = servico.detect_keys_batch()

    assert criados == [4]
    assert relatorio.detected == 1
