"""Conversao entre notacao Camelot e classica. Funcoes puras, sem Qt."""

import pytest

from trackclassifier.keys import (
    ALL_KEYS,
    Key,
    KeyNotation,
    Mode,
    format_key,
    parse_key,
)


def test_existem_exatamente_24_tonalidades():
    assert len(ALL_KEYS) == 24
    assert len(set(ALL_KEYS)) == 24


def test_toda_tonalidade_faz_round_trip_nas_duas_notacoes():
    # E o contrato que sustenta guardar a forma canonica em vez da string:
    # se o round-trip quebrasse, trocar de notacao perderia dado.
    for chave in ALL_KEYS:
        assert parse_key(chave.camelot) == chave
        assert parse_key(chave.classic) == chave


def test_camelot_de_referencia():
    # 8A = Am e o exemplo canonico da roda de Camelot; 8B = C e o relativo.
    assert Key(9, Mode.MINOR).camelot == "8A"
    assert Key(9, Mode.MINOR).classic == "Am"
    assert Key(0, Mode.MAJOR).camelot == "8B"
    assert Key(0, Mode.MAJOR).classic == "C"


def test_camelot_number_fica_entre_1_e_12():
    for chave in ALL_KEYS:
        assert 1 <= chave.camelot_number <= 12


def test_pitch_class_fora_da_faixa_levanta():
    with pytest.raises(ValueError):
        Key(12, Mode.MINOR)
    with pytest.raises(ValueError):
        Key(-1, Mode.MAJOR)


def test_format_respeita_a_notacao():
    chave = Key(9, Mode.MINOR)
    assert chave.format(KeyNotation.CAMELOT) == "8A"
    assert chave.format(KeyNotation.CLASSIC) == "Am"


def test_parse_aceita_enarmonicos_que_aparecem_em_tag_id3():
    # Tags de ID3 nao seguem padrao nenhum: o mesmo tom aparece como C#m ou
    # Dbm dependendo da ferramenta que gravou.
    assert parse_key("C#m") == parse_key("Dbm")
    assert parse_key("G#") == parse_key("Ab")


def test_parse_tolera_espaco_e_caixa():
    assert parse_key("  8a  ") == Key(9, Mode.MINOR)
    assert parse_key("AM") == parse_key("Am")


def test_parse_de_lixo_devolve_none():
    # A tag pode conter qualquer coisa; quem chama decide o que fazer.
    for lixo in ("", "   ", "banana", "13A", "0A", "8C", "H", "999"):
        assert parse_key(lixo) is None, lixo


def test_format_key_de_none_mostra_travessao():
    assert format_key(None, KeyNotation.CAMELOT) == "—"
    assert format_key(Key(9, Mode.MINOR), KeyNotation.CAMELOT) == "8A"
