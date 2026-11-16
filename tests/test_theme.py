"""
Test del tema: i badge devono restare compatibili con quelli già salvati nel database.
"""
import theme

# Valori di controllo dei badge prima del tema: non devono cambiare,
# altrimenti chi ha già un badge potrebbe perderlo al ricalcolo.
CHECK_VALUES = {
    1: 100, 2: 50 * 3600, 3: 10 * 3600, 4: 50, 5: 25, 6: 10, 7: None, 8: None, 9: None,
    10: 7, 11: 365, 12: 5 * 3600, 13: 10 * 3600, 14: 50 * 3600, 15: 1000, 16: 50, 17: 30,
}


def test_gli_id_dei_badge_sono_gli_stessi():
    assert [b[0] for b in theme.BADGES] == list(range(1, 18))


def test_i_valori_di_controllo_non_cambiano():
    assert {b[0]: b[4] for b in theme.BADGES} == CHECK_VALUES


def test_nomi_dei_badge_unici():
    # La colonna badges.name è UNIQUE nel database
    names = [b[1] for b in theme.BADGES]
    assert len(names) == len(set(names))


def test_ogni_badge_ha_icona_e_descrizione():
    for _, name, description, icon, _ in theme.BADGES:
        assert name and description and icon


def test_ricerca_badge_per_id():
    assert theme.badge(9)[1] == 'Veni Vidi Vici'
    assert theme.badge(99) is None


def test_messaggi_formattati():
    assert "<@1>" in theme.WELCOME_TEXT.format(mention="<@1>")
    assert "57" in theme.WELCOME_FOOTER.format(count=57)
    for _ in range(20):
        msg = theme.level_up_message("<@1>", 12)
        assert "<@1>" in msg and "**12**" in msg


def test_barra_di_avanzamento():
    assert theme.progress_bar(0.5, 10) == theme.PROGRESS_FULL * 5 + theme.PROGRESS_EMPTY * 5
    assert theme.progress_bar(1.7, 4) == theme.PROGRESS_FULL * 4
    assert theme.progress_bar(-1, 4) == theme.PROGRESS_EMPTY * 4
