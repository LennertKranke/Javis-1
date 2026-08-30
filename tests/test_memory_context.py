"""Gedaechtnis und Kontext -- die Trennung von Speicherung und Prompt.

Der Punkt dieser Datei: was JARVIS aufbewahrt, waechst mit der Nutzungsdauer.
Was ans Modell geht, darf das nicht. Die Tests halten diese Grenze fest.
"""

from __future__ import annotations

import pytest

from jarvis.core.audit import AuditLog
from jarvis.core.context import ContextBudget, ContextBuilder, ShortTermContext
from jarvis.core.memory import LongTermMemory, normalise_key

# --- Langzeitgedaechtnis ---------------------------------------------------- #


def test_ablegen_und_lesen(conn):
    m = LongTermMemory(conn)
    fakt = m.remember("Anrede Kunden", "Kunden immer siezen", category="praeferenz")
    assert fakt.key == "anrede_kunden"
    assert m.get("anrede_kunden").value == "Kunden immer siezen"
    assert m.count() == 1


def test_zweimal_ablegen_ersetzt(conn):
    m = LongTermMemory(conn)
    m.remember("ton", "foermlich")
    m.remember("ton", "locker")
    assert m.get("ton").value == "locker"
    assert m.count() == 1


def test_vergessen(conn):
    m = LongTermMemory(conn)
    m.remember("ton", "foermlich")
    assert m.forget("ton") is True
    assert m.forget("ton") is False
    assert m.count() == 0


def test_schluessel_werden_vereinheitlicht():
    assert normalise_key("  Anrede / Kunden!  ") == "anrede_kunden"
    with pytest.raises(ValueError):
        normalise_key("   ")


def test_werte_werden_gedeckelt(conn):
    m = LongTermMemory(conn)
    fakt = m.remember("lang", "x" * 5000)
    assert len(fakt.value) <= 500


def test_unbekannte_kategorie(conn):
    with pytest.raises(ValueError, match="Kategorie"):
        LongTermMemory(conn).remember("x", "y", category="erfunden")


def test_relevanz_waehlt_aus(conn):
    m = LongTermMemory(conn)
    m.remember("anrede_kunden", "Kunden immer siezen", category="praeferenz")
    m.remember("lieblingsfarbe", "blau", category="sonstiges")
    treffer = m.relevant("Wie soll ich Kunden anreden", limit=5)
    assert [f.key for f in treffer] == ["anrede_kunden"]


def test_ohne_suchbegriffe_kommt_alles_nach_gewicht(conn):
    m = LongTermMemory(conn)
    m.remember("wichtig", "sehr", weight=5.0)
    m.remember("unwichtig", "kaum", weight=0.1)
    assert [f.key for f in m.relevant("", limit=2)] == ["wichtig", "unwichtig"]


# --- Kurzzeitkontext -------------------------------------------------------- #


def test_kurzzeitkontext_beschneidet_sich_selbst(conn):
    """Der Verlauf darf nicht mit der Nutzungsdauer wachsen."""
    st = ShortTermContext(conn, scope="thread:1", max_entries=3)
    for i in range(20):
        st.append("notiz", f"Eintrag {i}")
    assert st.count() == 3
    assert [e.text for e in st.recent()] == ["Eintrag 17", "Eintrag 18", "Eintrag 19"]


def test_bereiche_stoeren_sich_nicht(conn):
    a = ShortTermContext(conn, scope="a", max_entries=5)
    b = ShortTermContext(conn, scope="b", max_entries=5)
    a.append("notiz", "aus a")
    b.append("notiz", "aus b")
    assert [e.text for e in a.recent()] == ["aus a"]
    assert [e.text for e in b.recent()] == ["aus b"]


def test_einzelne_eintraege_werden_gedeckelt(conn):
    st = ShortTermContext(conn, scope="a")
    assert len(st.append("notiz", "x" * 5000).text) <= 1000


def test_leerer_eintrag_wird_abgelehnt(conn):
    with pytest.raises(ValueError):
        ShortTermContext(conn, scope="a").append("notiz", "   ")


def test_bereich_leeren(conn):
    st = ShortTermContext(conn, scope="a")
    st.append("notiz", "eins")
    st.append("notiz", "zwei")
    assert st.clear() == 2
    assert st.count() == 0


# --- Kontextbauer ----------------------------------------------------------- #


def test_obergrenze_wird_eingehalten(conn):
    """Die zentrale Zusicherung: der Prompt waechst nicht mit den Daten."""
    m = LongTermMemory(conn)
    for i in range(200):
        m.remember(f"fakt_{i}", f"Ein Wert mit Nummer {i} und etwas Text dazu")
    st = ShortTermContext(conn, scope="a", max_entries=50)
    for i in range(50):
        st.append("notiz", f"Eine Notiz mit Nummer {i} und etwas Text dazu")

    gebaut = ContextBuilder(memory=m, short_term=st, budget=ContextBudget(max_chars=400)).build(
        preamble="Anweisung."
    )

    assert gebaut.chars <= 400
    assert gebaut.truncated


def test_praeambel_hat_vorrang(conn):
    m = LongTermMemory(conn)
    m.remember("etwas", "Wert")
    gebaut = ContextBuilder(memory=m, budget=ContextBudget(max_chars=20)).build(
        preamble="Die Anweisung zaehlt zuerst."
    )
    assert gebaut.text.startswith("Die Anweisung")
    assert gebaut.facts == ()


def test_ohne_quellen_bleibt_es_leer(conn):
    assert ContextBuilder().build().text == ""


def test_nur_passende_tatsachen_gehen_mit(conn):
    m = LongTermMemory(conn)
    m.remember("anrede_kunden", "Kunden immer siezen")
    m.remember("lieblingsfarbe", "blau")
    gebaut = ContextBuilder(memory=m).build(terms="Anrede fuer Kunden")
    assert "siezen" in gebaut.text
    assert "blau" not in gebaut.text


def test_hoechstzahl_an_tatsachen(conn):
    m = LongTermMemory(conn)
    for i in range(30):
        m.remember(f"fakt_{i}", f"Wert {i}")
    gebaut = ContextBuilder(memory=m, budget=ContextBudget(max_facts=5)).build()
    assert len(gebaut.facts) <= 5


# --- Die Grenze, um die es geht --------------------------------------------- #


def test_das_protokoll_geht_niemals_mit(conn):
    """Audit-Logs sind Nachweis, nicht Prompt-Material."""
    audit = AuditLog(conn)
    for i in range(50):
        audit.record(
            capability="mail",
            kind="decision",
            outcome="label",
            subject=f"nachricht-{i}",
            detail={"summary": f"GEHEIMER BETREFF {i}", "reason": "weil"},
        )
    m = LongTermMemory(conn)
    m.remember("harmlos", "ein abgelegter Wert")

    # Selbst wenn genau nach dem Protokollinhalt gesucht wird, kommt nichts
    # davon heraus -- es ist keine Quelle des Kontextbauers.
    gebaut = ContextBuilder(memory=m, short_term=ShortTermContext(conn, scope="a")).build(
        terms="GEHEIMER BETREFF nachricht"
    )
    assert "GEHEIMER" not in gebaut.text
    assert gebaut.facts == ()

    # Das Protokoll bleibt dabei vollstaendig -- getrennt, nicht beschnitten.
    assert audit.count() == 50
    assert audit.verify().ok

    # Und was ausdruecklich abgelegt wurde, geht sehr wohl mit.
    mit_treffer = ContextBuilder(memory=m).build(terms="harmlos abgelegter")
    assert "ein abgelegter Wert" in mit_treffer.text


def test_der_kontextbauer_kennt_keine_protokollquelle():
    """Strukturell: es gibt keinen Weg, das Protokoll einzuspeisen."""
    import inspect

    quelle = inspect.getsource(ContextBuilder)
    for verboten in ("audit", "AuditLog", "audit_log", "logging"):
        assert verboten not in quelle


def test_speicherung_waechst_kontext_nicht(conn):
    """Dreihundertmal so viele Daten -- der Kontext bleibt unter der Grenze.

    Das ist die Eigenschaft, um die es geht. Der Kontext darf die Obergrenze
    ausschoepfen; er darf sie nicht ueberschreiten, egal wie viel gespeichert
    ist. Sonst waechst jede Anfrage mit der Nutzungsdauer.
    """
    m = LongTermMemory(conn)
    st = ShortTermContext(conn, scope="a", max_entries=8)
    bauer = ContextBuilder(memory=m, short_term=st, budget=ContextBudget(max_chars=600))

    m.remember("eins", "erster Wert")
    st.append("notiz", "erste Notiz")
    assert bauer.build().chars <= 600

    for i in range(300):
        m.remember(f"weiterer_{i}", f"Wert Nummer {i}")
        st.append("notiz", f"Notiz Nummer {i}")

    gebaut = bauer.build()
    assert gebaut.chars <= 600
    assert m.count() == 301  # gespeichert ist alles
    assert st.count() == 8  # der Verlauf hat sich selbst beschnitten
    assert len(gebaut.facts) <= bauer.budget.max_facts


# --------------------------------------------------------------------------- #
# Der Speicher waechst nicht unbegrenzt
# --------------------------------------------------------------------------- #


def test_der_bestand_bleibt_unter_der_obergrenze(conn):
    from jarvis.core.memory import MAX_FAKTEN

    gedaechtnis = LongTermMemory(conn)
    for i in range(MAX_FAKTEN + 150):
        gedaechtnis.remember(f"fakt-{i}", f"wert {i}", category="sonstiges")
    assert gedaechtnis.count() == MAX_FAKTEN


def test_verdraengt_wird_das_unwichtigste_nicht_das_aelteste(conn):
    """`weight` ist die Angabe, wie sehr etwas behalten werden soll."""
    from jarvis.core.memory import MAX_FAKTEN

    gedaechtnis = LongTermMemory(conn)
    gedaechtnis.remember("sehr wichtig", "das soll bleiben", category="person", weight=9.0)
    for i in range(MAX_FAKTEN + 50):
        gedaechtnis.remember(f"belanglos-{i}", f"wert {i}", category="sonstiges", weight=1.0)

    assert gedaechtnis.get("sehr wichtig") is not None, "das Wichtige wurde verdraengt"
    assert gedaechtnis.count() == MAX_FAKTEN


def test_unter_der_obergrenze_wird_nichts_verdraengt(conn):
    gedaechtnis = LongTermMemory(conn)
    for i in range(20):
        gedaechtnis.remember(f"fakt-{i}", f"wert {i}", category="sonstiges")
    assert gedaechtnis.count() == 20
    assert gedaechtnis.get("fakt-0") is not None


def test_bei_gleichem_gewicht_entscheidet_das_alter(conn):
    from jarvis.core.memory import MAX_FAKTEN

    gedaechtnis = LongTermMemory(conn)
    gedaechtnis.remember("der aelteste", "zuerst abgelegt", category="sonstiges", weight=1.0)
    for i in range(MAX_FAKTEN + 5):
        gedaechtnis.remember(f"spaeter-{i}", f"wert {i}", category="sonstiges", weight=1.0)
    assert gedaechtnis.get("der aelteste") is None


def test_ein_ersetzter_eintrag_zaehlt_nicht_doppelt(conn):
    gedaechtnis = LongTermMemory(conn)
    for _ in range(50):
        gedaechtnis.remember("derselbe", "immer wieder", category="sonstiges")
    assert gedaechtnis.count() == 1
