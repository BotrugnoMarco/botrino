"""
Test per le funzioni di calcolo dell'XP in utils/xp_utils.py.
"""
import pytest

from utils.xp_utils import calculate_xp_for_level_up, get_multiplier_for_level

BASE_XP = 250


def test_livello_zero_restituisce_xp_base():
    assert calculate_xp_for_level_up(0, BASE_XP) == BASE_XP


def test_livello_uno_applica_il_primo_moltiplicatore():
    assert calculate_xp_for_level_up(1, BASE_XP) == int(BASE_XP * 1.22)


def test_crescita_monotona_fino_al_livello_100():
    xp_per_livello = [calculate_xp_for_level_up(level, BASE_XP) for level in range(101)]
    assert all(prev < curr for prev, curr in zip(xp_per_livello, xp_per_livello[1:]))


@pytest.mark.parametrize("level, expected", [
    (10, 1.22), (11, 1.16),
    (20, 1.16), (21, 1.11),
    (30, 1.11), (31, 1.03),
])
def test_moltiplicatore_ai_confini_delle_fasce(level, expected):
    assert get_multiplier_for_level(level) == expected
