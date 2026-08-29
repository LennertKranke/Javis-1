"""Schreibstil ableiten -- und was dabei nicht gespeichert wird."""

from __future__ import annotations

import json

import pytest

from jarvis.skills.mail.style import StyleProfile, StyleStore, eigener_text, extract_profile

FOERMLICH = [
    "Sehr geehrte Frau Meier,\n\nvielen Dank fuer Ihre Nachricht. Ich melde mich bis "
    "Freitag bei Ihnen.\n\nMit freundlichen Gruessen\nLennert",
    "Sehr geehrter Herr Schmitt,\n\nanbei die Unterlagen. Bitte pruefen Sie diese in "
    "Ruhe.\n\nMit freundlichen Gruessen\nLennert",
    "Sehr geehrte Damen und Herren,\n\nich bitte um eine kurze Rueckmeldung zu Ihrem "
    "Angebot.\n\nMit freundlichen Gruessen\nLennert",
]

LOCKER = [
    "Hallo Anna,\n\npasst bei mir. Bis Montag.\n\nViele Gruesse\nL",
    "Hallo Tom,\n\nklar, mach ich dir bis morgen fertig.\n\nViele Gruesse\nL",
    "Hallo Jan,\n\ndanke dir. Schick mir deine Nummer.\n\nViele Gruesse\nL",
]


def test_foermlicher_stil():
    p = extract_profile(FOERMLICH)
    assert p.sample_count == 3
    assert p.language == "Deutsch"
    assert p.form_of_address == "Sie"
    assert p.greeting == "sehr_geehrte"
    assert p.signoff == "mit_freundlichen_gruessen"


def test_lockerer_stil():
    p = extract_profile(LOCKER)
    assert p.form_of_address == "du"
    assert p.greeting == "hallo"
    assert p.signoff == "viele_gruesse"


def test_englischer_stil():
    p = extract_profile(
        [
            "Hello Anna,\n\nthanks for the update. I will have a look on Monday and get "
            "back to you.\n\nBest regards\nL"
        ]
    )
    assert p.language == "Englisch"
    assert p.greeting == "hello"
    assert p.signoff == "best_regards"


def test_zitat_wird_abgeschnitten():
    """Sonst misst der Stil die Schreibweise der Gegenseite mit."""
    text = "Hallo,\n\nja, passt.\n\nViele Gruesse\nL\n\n> Am 3.1. schrieb Anna:\n> " + (
        "Sehr geehrter Herr, " * 50
    )
    assert "Sehr geehrter" not in eigener_text(text)
    assert extract_profile([text]).form_of_address != "Sie"


@pytest.mark.parametrize(
    "trenner",
    ["> zitat", "Am 3.1.2026 schrieb Anna:", "On Jan 3 Anna wrote:", "-----Urspruengliche"],
)
def test_uebliche_zitattrenner(trenner):
    assert eigener_text(f"Meine Antwort.\n{trenner}\nfremder Text") == "Meine Antwort."


def test_kennzahlen():
    p = extract_profile(["Hallo. Kurz. Passt.", "Hallo. Auch kurz."])
    assert p.avg_sentence_words > 0
    assert p.avg_reply_words > 0


def test_ohne_material_kein_profil():
    p = extract_profile([])
    assert not p.usable
    assert "Kein Stilprofil" in p.describe()


def test_nur_zitate_ergeben_kein_profil():
    assert not extract_profile(["> alles zitiert", "> auch das"]).usable


# --- Der Punkt der ganzen Datei --------------------------------------------- #


def test_kein_nachrichtentext_wird_gespeichert(conn):
    """Die getroffene Wahl war: abgeleitete Merkmale, keine Originaltexte."""
    geheim = [
        "Sehr geehrte Frau Meier,\n\ndie Ueberweisung ueber 14000 Euro an die "
        "Kontonummer DE12 ist raus. Das Grundstueck in Bonn gehoert uns.\n\n"
        "Mit freundlichen Gruessen\nLennert"
    ]
    profil = extract_profile(geheim)
    StyleStore(conn).save(profil)

    gespeichert = conn.execute("SELECT profile FROM style_profile WHERE id = 1").fetchone()[0]
    for verraeterisch in ("Ueberweisung", "14000", "DE12", "Grundstueck", "Bonn", "Meier"):
        assert verraeterisch not in gespeichert
        assert verraeterisch not in profil.describe()


def test_beschreibung_nennt_nur_bezeichner_aus_dem_katalog():
    """Die Begruessung ist ein Bezeichner, kein uebernommener Text."""
    p = extract_profile(["Hallo Frau Doktor Sonderbar-Meier,\n\nja.\n\nViele Gruesse\nL"])
    assert p.greeting == "hallo"
    assert "Sonderbar" not in json.dumps(p.greeting_counts)
    assert "Sonderbar" not in p.describe()


def test_speichern_und_laden(conn):
    original = extract_profile(FOERMLICH)
    store = StyleStore(conn)
    store.save(original)
    assert store.load() == original
    assert store.updated_at() is not None


def test_zweimal_speichern_ersetzt(conn):
    store = StyleStore(conn)
    store.save(extract_profile(FOERMLICH))
    store.save(extract_profile(LOCKER))
    assert store.load().signoff == "viele_gruesse"
    assert conn.execute("SELECT COUNT(*) FROM style_profile").fetchone()[0] == 1


def test_leeres_profil_ohne_datenbankzeile(conn):
    assert StyleStore(conn).load() == StyleProfile()
