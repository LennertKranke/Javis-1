"""Der Faehigkeiten-Vertrag und die Sperre in `Decision`."""

from __future__ import annotations

import pytest

from jarvis.skills.base import Decision, Event, Result, available_skills, register_skill


def entscheidung(**kwargs) -> Decision:
    grund = {
        "skill": "mail",
        "event_key": "m1",
        "action": "label",
        "reason": "weil",
        "decided_by": "model",
    }
    grund.update(kwargs)
    return Decision(**grund)


def test_gewoehnliche_felder_gehen_durch():
    d = entscheidung(fields={"kategorie": "rechnung", "dringlichkeit": 2})
    assert d.fields["kategorie"] == "rechnung"


@pytest.mark.parametrize(
    "feld", ["to", "recipient", "forward_to", "url", "file_path", "iban", "webhook_url"]
)
def test_ziel_in_der_modellhaelfte_wird_abgewiesen(feld):
    """Prinzip 2.1 als Sperre im Datentyp, nicht als Verabredung."""
    with pytest.raises(ValueError, match=r"2\.1"):
        entscheidung(fields={feld: "irgendwas"})


def test_ziele_in_der_richtigen_haelfte_sind_erlaubt():
    d = entscheidung(targets={"message_id": "m1", "label_id": "Label_3"})
    assert d.targets["message_id"] == "m1"


def test_audit_detail_enthaelt_keinen_fremdtext():
    d = entscheidung(
        fields={"kategorie": "rechnung"}, targets={"message_id": "m1"}, model="static-1"
    )
    detail = d.audit_detail
    assert detail["action"] == "label"
    assert detail["decided_by"] == "model"
    assert detail["feld_kategorie"] == "rechnung"
    assert detail["model"] == "static-1"


def test_registrierung_traegt_sich_selbst_ein():
    from jarvis.skills.base import Skill

    @register_skill
    class Probe(Skill):
        name = "probe_faehigkeit"

        def poll(self):
            return []

        def decide(self, event):
            raise NotImplementedError

        def act(self, decision):
            raise NotImplementedError

    assert available_skills()["probe_faehigkeit"] is Probe


def test_faehigkeit_ohne_namen_wird_abgelehnt():
    from jarvis.skills.base import Skill

    class Namenlos(Skill):
        def poll(self):
            return []

        def decide(self, event):
            raise NotImplementedError

        def act(self, decision):
            raise NotImplementedError

    with pytest.raises(ValueError, match="name fehlt"):
        register_skill(Namenlos)


def test_after_ist_freiwillig():
    from jarvis.skills.base import Skill

    class Minimal(Skill):
        name = "minimal"

        def poll(self):
            return []

        def decide(self, event):
            raise NotImplementedError

        def act(self, decision):
            raise NotImplementedError

    ereignis = Event(skill="minimal", key="k", summary="s")
    ergebnis = Result(skill="minimal", event_key="k", performed=False)
    assert Minimal().after(ereignis, entscheidung(), "dry_run", ergebnis) is None
