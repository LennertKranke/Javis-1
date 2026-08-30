"""Kalender: zerlegen, rechnen, merken, durchlaufen."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from jarvis.core.audit import AuditLog
from jarvis.core.config import Config, ConfigError, Paths
from jarvis.core.gate import Gate
from jarvis.core.ratelimit import RateLimiter
from jarvis.skills.base import TargetMismatch
from jarvis.skills.calendar.conflicts import KEIN_PUFFER, UEBERSCHNEIDUNG, find_conflicts
from jarvis.skills.calendar.event import parse_event
from jarvis.skills.calendar.google import CALENDAR_READ, CalendarClient
from jarvis.skills.calendar.skill import CalendarOptions, CalendarSkill
from jarvis.skills.calendar.store import CalendarStore
from jarvis.skills.mail.gmail import GmailError
from jarvis.skills.mail.store import STATE_ACTED, STATE_ANALYSED
from jarvis.skills.runner import run_skill
from tests.fixtures_calendar import FakeCalendarClient, termin

JETZT = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def kalender_config(
    home, *, dry_run: bool = True, level: int = 0, zone: str = "", **skill_optionen
) -> Config:
    raw = {
        "dry_run": dry_run,
        "timezone": zone,
        "capabilities": {
            "calendar": {
                "autonomy_level": level,
                "requires_outbound": False,
                "rate_limits": {"hour": 60},
            }
        },
        "llm": {
            "providers": {
                "trocken": {"kind": "static", "model": "static", "local": True, "reply": "{}"}
            },
            "tasks": {"classify": {"providers": ["trocken"]}},
        },
        "skills": {"calendar": skill_optionen} if skill_optionen else {},
    }
    return Config.from_mapping(raw, paths=Paths(home=home))


def baue_skill(home, conn, *, events=None, dry_run=True, level=0, zone="", **optionen):
    client = FakeCalendarClient(events)
    config = kalender_config(home, dry_run=dry_run, level=level, zone=zone, **optionen)
    skill = CalendarSkill.from_config(config, client=client, store=CalendarStore(conn))
    skill._now = lambda: JETZT
    return skill, client, config


# --------------------------------------------------------------------------- #
# Zerlegen
# --------------------------------------------------------------------------- #


def test_zeiten_werden_zeitzonenbewusst_gelesen():
    e = parse_event(termin(), calendar_id="primary")
    assert e.starts_at == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    assert e.ends_at == datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    assert e.all_day is False
    assert e.blocks_time is True


def test_zeit_ohne_zone_gilt_als_utc_statt_zu_scheitern():
    e = parse_event(
        termin(start="2026-03-02T09:00:00", ende="2026-03-02T10:00:00"), calendar_id="primary"
    )
    assert e.starts_at is not None
    assert e.starts_at.tzinfo is not None


def test_unlesbare_zeit_ergibt_keinen_zeitpunkt():
    e = parse_event(termin(start="uebermorgen frueh"), calendar_id="primary")
    assert e.starts_at is None
    assert e.blocks_time is False


def test_ganztaegiger_termin_belegt_keine_zeit():
    e = parse_event(termin(ganztags=True), calendar_id="primary")
    assert e.all_day is True
    assert e.blocks_time is False


def test_abgesagter_und_abgelehnter_termin_belegen_keine_zeit():
    abgesagt = parse_event(termin(status="cancelled"), calendar_id="primary")
    assert abgesagt.cancelled is True
    assert abgesagt.blocks_time is False

    abgelehnt = parse_event(
        termin(
            teilnehmer=[{"email": "ich@example.com", "responseStatus": "declined", "self": True}]
        ),
        calendar_id="primary",
    )
    assert abgelehnt.declined_by_me is True
    assert abgelehnt.blocks_time is False


def test_titel_ort_und_beschreibung_gelten_als_fremdtext():
    e = parse_event(termin(titel="Titel", ort="Ort", beschreibung="Text"), calendar_id="primary")
    assert e.untrusted_text == "Titel\nOrt\nText"


# --------------------------------------------------------------------------- #
# Rechnen
# --------------------------------------------------------------------------- #


def ev(eid, beginn, ende, **rest):
    return parse_event(
        termin(
            eid=eid,
            start=f"2026-03-02T{beginn}:00+00:00",
            ende=f"2026-03-02T{ende}:00+00:00",
            **rest,
        ),
        calendar_id="primary",
    )


def test_ueberschneidung_wird_gefunden():
    befunde = find_conflicts([ev("a", "09:00", "10:00"), ev("b", "09:30", "10:30")])
    assert [b.kind for b in befunde] == [UEBERSCHNEIDUNG]
    assert set(befunde[0].event_ids) == {"a", "b"}


def test_zu_knapper_uebergang_wird_gefunden():
    befunde = find_conflicts(
        [ev("a", "09:00", "10:00"), ev("b", "10:05", "11:00")], min_gap_minutes=15
    )
    assert [b.kind for b in befunde] == [KEIN_PUFFER]
    assert befunde[0].minutes == 5


def test_ausreichender_abstand_ist_kein_befund():
    assert find_conflicts([ev("a", "09:00", "10:00"), ev("b", "11:00", "12:00")]) == []


def test_puffer_null_meldet_nur_noch_ueberschneidungen():
    termine = [ev("a", "09:00", "10:00"), ev("b", "10:00", "11:00")]
    assert find_conflicts(termine, min_gap_minutes=0) == []
    assert len(find_conflicts(termine, min_gap_minutes=15)) == 1


def test_ganztaegige_termine_kollidieren_mit_nichts():
    ganztags = parse_event(termin(eid="feiertag", ganztags=True), calendar_id="primary")
    assert find_conflicts([ganztags, ev("a", "09:00", "10:00")]) == []


def test_beschreibung_benutzt_uebergebene_titel():
    befund = find_conflicts([ev("a", "09:00", "10:00"), ev("b", "09:30", "10:30")])[0]
    text = befund.describe({"a": "Zahnarzt", "b": "Standup"})
    assert "Zahnarzt" in text and "Standup" in text


# --------------------------------------------------------------------------- #
# Merken
# --------------------------------------------------------------------------- #


def test_store_haelt_acted_fest(conn):
    store = CalendarStore(conn)
    store.remember(event_id="a", calendar_id="primary", state=STATE_ACTED)
    store.remember(event_id="a", calendar_id="primary", summary="neuer Titel")
    eintrag = store.get("a")
    assert eintrag is not None
    assert eintrag.state == STATE_ACTED
    assert eintrag.summary == "neuer Titel"


def test_store_weist_unbekannten_zustand_ab(conn):
    with pytest.raises(ValueError):
        CalendarStore(conn).remember(event_id="a", calendar_id="primary", state="erfunden")


def test_verschwundener_befund_wird_geloescht_und_acted_faellt_weg(conn):
    store = CalendarStore(conn)
    store.remember(event_id="a", calendar_id="primary", state=STATE_ACTED)
    store.record_finding("a", "kollidiert mit b")

    assert store.clear_stale_findings({}) == 1
    eintrag = store.get("a")
    assert eintrag is not None
    assert eintrag.finding is None
    assert eintrag.state == STATE_ANALYSED


def test_bestehender_befund_bleibt_wenn_er_noch_gilt(conn):
    store = CalendarStore(conn)
    store.remember(event_id="a", calendar_id="primary", state=STATE_ACTED)
    store.record_finding("a", "kollidiert mit b")

    assert store.clear_stale_findings({"a": "kollidiert mit b"}) == 0
    eintrag = store.get("a")
    assert eintrag is not None
    assert eintrag.finding == "kollidiert mit b"
    assert eintrag.state == STATE_ACTED


def test_geaenderter_befund_zaehlt_als_veraltet(conn):
    """Der Termin steckt weiter in einem Konflikt -- aber in einem anderen."""
    store = CalendarStore(conn)
    store.remember(event_id="a", calendar_id="primary", state=STATE_ACTED)
    store.record_finding("a", "kollidiert mit b")

    assert store.clear_stale_findings({"a": "kollidiert mit c"}) == 1
    eintrag = store.get("a")
    assert eintrag is not None
    assert eintrag.finding is None
    assert eintrag.state == STATE_ANALYSED


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


def test_client_laesst_nur_lesende_endpunkte_zu():
    client = CalendarClient(auth=None, capabilities=CALENDAR_READ)  # type: ignore[arg-type]
    client._check_endpoint("GET", "/calendars/primary/events")
    for methode, pfad in (
        ("POST", "/calendars/primary/events"),
        ("DELETE", "/calendars/primary/events/abc"),
        ("PUT", "/calendars/primary/events/abc"),
        ("PATCH", "/calendars/primary/events/abc"),
    ):
        with pytest.raises(GmailError):
            client._check_endpoint(methode, pfad)


def test_client_ohne_faehigkeiten_darf_gar_nichts():
    client = CalendarClient(auth=None, capabilities=frozenset())  # type: ignore[arg-type]
    with pytest.raises(GmailError):
        client._check_endpoint("GET", "/calendars/primary/events")


def test_unbekannte_faehigkeit_ist_ein_fehler():
    with pytest.raises(ValueError):
        CalendarClient(auth=None, capabilities={"write"})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Einstellungen
# --------------------------------------------------------------------------- #


def test_unbekannter_schluessel_faellt_auf():
    with pytest.raises(ConfigError):
        CalendarOptions({"kalender": ["primary"]})


@pytest.mark.parametrize(
    "roh",
    [
        {"calendar_ids": []},
        {"calendar_ids": "primary"},
        {"calendar_ids": [1]},
        {"window_days": 0},
        {"window_days": 61},
        {"window_days": True},
        {"min_gap_minutes": -1},
        {"max_per_run": 0},
    ],
)
def test_unbrauchbare_werte_werden_abgewiesen(roh):
    with pytest.raises(ConfigError):
        CalendarOptions(roh)


# --------------------------------------------------------------------------- #
# Durchlauf
# --------------------------------------------------------------------------- #


def test_poll_liefert_alle_termine_im_fenster(home, conn):
    skill, client, _ = baue_skill(
        home, conn, events=[termin(eid="a"), termin(eid="b", start="2026-03-03T09:00:00+00:00")]
    )
    events = skill.poll()
    assert [e.key for e in events] == ["a", "b"]
    assert client.calls[0][0] == "primary"


def test_titel_wird_normalisiert_bevor_er_irgendwo_landet(home, conn):
    skill, _, _ = baue_skill(home, conn, events=[termin(eid="a", titel="Team​sitzung <b>jetzt</b>")])
    skill.poll()
    eintrag = CalendarStore(conn).get("a")
    assert eintrag is not None
    assert "​" not in eintrag.summary
    assert "<b>" not in eintrag.summary


def test_decide_meldet_ueberschneidung_ohne_modell(home, conn):
    skill, _, _ = baue_skill(
        home,
        conn,
        events=[
            termin(eid="a", titel="Zahnarzt"),
            termin(
                eid="b",
                titel="Standup",
                start="2026-03-02T09:30:00+00:00",
                ende="2026-03-02T10:30:00+00:00",
            ),
        ],
    )
    events = skill.poll()
    entscheidung = skill.decide(events[0])
    assert entscheidung.action == "notice"
    assert entscheidung.decided_by == "rule"
    assert entscheidung.model is None
    assert entscheidung.targets["kind"] == UEBERSCHNEIDUNG
    assert "Standup" in entscheidung.targets["finding"]


def test_decide_ohne_konflikt_ist_ein_nichtstun(home, conn):
    skill, _, _ = baue_skill(home, conn, events=[termin(eid="a")])
    entscheidung = skill.decide(skill.poll()[0])
    assert entscheidung.is_noop is True


def test_trockenlauf_haelt_den_befund_zurueck(home, conn):
    skill, _, config = baue_skill(
        home,
        conn,
        dry_run=True,
        events=[
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T09:30:00+00:00", ende="2026-03-02T10:30:00+00:00"),
        ],
    )
    audit = AuditLog(conn)
    report = run_skill(
        skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
    )
    assert report.dry_run == 2
    assert report.acted == 0
    eintrag = CalendarStore(conn).get("a")
    assert eintrag is not None
    assert eintrag.finding is None
    assert eintrag.state == STATE_ANALYSED


def test_echter_lauf_haelt_den_befund_fest(home, conn):
    skill, _, config = baue_skill(
        home,
        conn,
        dry_run=False,
        events=[
            termin(eid="a", titel="Zahnarzt"),
            termin(
                eid="b",
                titel="Standup",
                start="2026-03-02T09:30:00+00:00",
                ende="2026-03-02T10:30:00+00:00",
            ),
        ],
    )
    audit = AuditLog(conn)
    report = run_skill(
        skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
    )
    assert report.acted == 2
    eintrag = CalendarStore(conn).get("a")
    assert eintrag is not None
    assert eintrag.state == STATE_ACTED
    assert "Standup" in (eintrag.finding or "")


def test_gemeldeter_konflikt_wird_nicht_erneut_gemeldet(home, conn):
    def lauf():
        skill, _, config = baue_skill(
            home,
            conn,
            dry_run=False,
            events=[
                termin(eid="a"),
                termin(
                    eid="b", start="2026-03-02T09:30:00+00:00", ende="2026-03-02T10:30:00+00:00"
                ),
            ],
        )
        audit = AuditLog(conn)
        return run_skill(
            skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
        )

    assert lauf().acted == 2
    assert lauf().polled == 0


def test_konfliktfreier_termin_wird_weiter_angesehen(home, conn):
    """`analysed` ist nicht endgueltig: morgen kann ein Konflikt entstehen."""

    def lauf(events):
        skill, _, config = baue_skill(home, conn, dry_run=False, events=events)
        audit = AuditLog(conn)
        return run_skill(
            skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
        )

    erster = lauf([termin(eid="a")])
    assert erster.polled == 1 and erster.skipped == 1

    zweiter = lauf(
        [
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T09:30:00+00:00", ende="2026-03-02T10:30:00+00:00"),
        ]
    )
    assert zweiter.polled == 2
    assert zweiter.acted == 2


def test_konfliktpartner_wechselt_a_b_wird_zu_a_c(home, conn):
    """Der Fehler aus der Durchsicht: A blieb "im Konflikt", behielt aber B.

    A liegt am Montag mit B ueber Kreuz, am Dienstag mit C. Wer nur fragt, ob A
    noch irgendwie in einem Konflikt steckt, laesst den Satz ueber B stehen --
    und das Briefing warnt vor einem Termin, den es nicht mehr gibt.
    """

    def lauf(events):
        skill, _, config = baue_skill(home, conn, dry_run=False, events=events)
        audit = AuditLog(conn)
        return run_skill(
            skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
        )

    A = termin(eid="A", titel="Zahnarzt")
    B = termin(
        eid="B",
        titel="Standup",
        start="2026-03-02T09:30:00+00:00",
        ende="2026-03-02T10:30:00+00:00",
    )
    C = termin(
        eid="C",
        titel="Kundentermin",
        start="2026-03-02T09:15:00+00:00",
        ende="2026-03-02T11:00:00+00:00",
    )

    lauf([A, B])
    zuerst = CalendarStore(conn).get("A")
    assert zuerst is not None
    assert "Standup" in (zuerst.finding or "")

    # B ist verschoben, C ist neu. A kollidiert weiterhin -- nur mit jemand anderem.
    lauf([A, C])

    danach = CalendarStore(conn).get("A")
    assert danach is not None
    assert "Standup" not in (danach.finding or ""), "veralteter Befund ueber B blieb stehen"
    assert "Kundentermin" in (danach.finding or "")

    verschoben = CalendarStore(conn).get("B")
    assert verschoben is not None
    assert verschoben.finding is None
    assert verschoben.state == STATE_ANALYSED


def test_wechselnder_konflikt_steht_richtig_im_briefing(home, conn):
    """Dieselbe Lage, aber von der Seite, auf der es auffaellt."""
    from jarvis.skills.briefing.skill import build_facts
    from jarvis.skills.mail.store import MailStore, ReplyStore

    def lauf(events):
        skill, _, config = baue_skill(home, conn, dry_run=False, events=events)
        audit = AuditLog(conn)
        return run_skill(
            skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
        )

    A = termin(eid="A", titel="Zahnarzt")
    B = termin(
        eid="B",
        titel="Standup",
        start="2026-03-02T09:30:00+00:00",
        ende="2026-03-02T10:30:00+00:00",
    )
    C = termin(
        eid="C",
        titel="Kundentermin",
        start="2026-03-02T09:15:00+00:00",
        ende="2026-03-02T11:00:00+00:00",
    )
    lauf([A, B])
    lauf([A, C])

    facts = build_facts(
        date(2026, 3, 2),
        calendar=CalendarStore(conn),
        mail=MailStore(conn),
        replies=ReplyStore(conn),
    )
    zusammen = " | ".join(facts["konflikte"])
    assert "Standup" not in zusammen, f"Briefing warnt vor einem alten Konflikt: {zusammen}"
    assert "Kundentermin" in zusammen


def test_verschwundener_konflikt_verschwindet_beim_naechsten_lauf(home, conn):
    def lauf(events):
        skill, _, config = baue_skill(home, conn, dry_run=False, events=events)
        audit = AuditLog(conn)
        return run_skill(
            skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
        )

    lauf(
        [
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T09:30:00+00:00", ende="2026-03-02T10:30:00+00:00"),
        ]
    )
    vorher = CalendarStore(conn).get("a")
    assert vorher is not None and vorher.finding

    # Der zweite Termin ist verschoben worden.
    lauf(
        [
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T14:00:00+00:00", ende="2026-03-02T15:00:00+00:00"),
        ]
    )
    eintrag = CalendarStore(conn).get("a")
    assert eintrag is not None
    assert eintrag.finding is None


# --------------------------------------------------------------------------- #
# Ziele
# --------------------------------------------------------------------------- #


def test_verify_targets_rechnet_den_befund_neu(home, conn):
    skill, _, _ = baue_skill(
        home,
        conn,
        events=[
            termin(eid="a", titel="Zahnarzt"),
            termin(
                eid="b",
                titel="Standup",
                start="2026-03-02T09:30:00+00:00",
                ende="2026-03-02T10:30:00+00:00",
            ),
        ],
    )
    events = skill.poll()
    entscheidung = skill.decide(events[0])
    manipuliert = replace(
        entscheidung,
        targets={"event_id": "a", "finding": "frei erfunden", "kind": "ueberschneidung"},
    )
    geprueft = skill.verify_targets(manipuliert)
    assert geprueft.targets["finding"] != "frei erfunden"
    assert "Standup" in geprueft.targets["finding"]


def test_verify_targets_weist_unbekannten_termin_ab(home, conn):
    skill, _, _ = baue_skill(home, conn, events=[termin(eid="a")])
    events = skill.poll()
    entscheidung = skill.decide(events[0])
    gefaelscht = replace(
        entscheidung,
        action="notice",
        targets={"event_id": "gibtsnicht", "finding": "x", "kind": "ueberschneidung"},
    )
    with pytest.raises(TargetMismatch):
        skill.verify_targets(gefaelscht)


def test_verify_targets_weist_verschwundenen_konflikt_ab(home, conn):
    skill, client, _ = baue_skill(
        home,
        conn,
        events=[
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T09:30:00+00:00", ende="2026-03-02T10:30:00+00:00"),
        ],
    )
    entscheidung = skill.decide(skill.poll()[0])
    assert entscheidung.action == "notice"

    # Der zweite Termin wird verschoben, bevor die Freigabe ausgefuehrt wird.
    client.set_events(
        "primary",
        [
            termin(eid="a"),
            termin(eid="b", start="2026-03-02T14:00:00+00:00", ende="2026-03-02T15:00:00+00:00"),
        ],
    )
    skill.poll()
    with pytest.raises(TargetMismatch):
        skill.verify_targets(entscheidung)


# --------------------------------------------------------------------------- #
# Zeitzonen
# --------------------------------------------------------------------------- #


def test_zeitstempel_werden_als_utc_abgelegt(home, conn):
    """Sonst ist die Textreihenfolge in SQLite nicht die zeitliche."""
    skill, _, _ = baue_skill(
        home,
        conn,
        zone="Europe/Berlin",
        events=[
            termin(
                eid="a",
                start="2026-03-02T09:00:00+02:00",
                ende="2026-03-02T10:00:00+02:00",
            )
        ],
    )
    skill.poll()
    eintrag = CalendarStore(conn).get("a")
    assert eintrag is not None
    assert eintrag.starts_at == "2026-03-02T07:00:00+00:00"
    assert eintrag.ends_at == "2026-03-02T08:00:00+00:00"


def test_abgelegte_zeitstempel_sind_textlich_sortierbar(home, conn):
    """Der eigentliche Grund fuer die Normalisierung."""
    skill, _, _ = baue_skill(
        home,
        conn,
        zone="Europe/Berlin",
        events=[
            # 01:00+02:00 ist 23:00 UTC am Vortag -- also frueher als das zweite.
            termin(
                eid="spaet",
                start="2026-03-02T01:00:00+02:00",
                ende="2026-03-02T02:00:00+02:00",
            ),
            termin(
                eid="frueher",
                start="2026-03-01T23:30:00+00:00",
                ende="2026-03-02T00:30:00+00:00",
            ),
        ],
    )
    skill.poll()
    gespeichert = [
        z["starts_at"]
        for z in conn.execute(
            "SELECT starts_at FROM calendar_events ORDER BY starts_at ASC"
        ).fetchall()
    ]
    assert gespeichert == sorted(gespeichert)
    assert gespeichert[0].startswith("2026-03-01T23:00")


def test_zeitangabe_zeigt_ortszeit(home, conn):
    skill, _, _ = baue_skill(
        home,
        conn,
        zone="Europe/Berlin",
        events=[
            termin(
                eid="a",
                titel="Zahnarzt",
                start="2026-03-02T09:00:00+00:00",
                ende="2026-03-02T10:00:00+00:00",
            )
        ],
    )
    events = skill.poll()
    # 09:00 UTC ist im Maerz 10:00 in Berlin.
    assert events[0].summary.startswith("02.03. 10:00")


@pytest.mark.parametrize("zone", ["Europe/Berlin", "America/New_York", "Pacific/Auckland"])
def test_ganztaegiger_termin_liegt_in_jeder_zone_im_richtigen_tag(home, conn, zone):
    """Ein Feiertag darf nicht aus dem Briefing fallen, nur weil die Zone
    westlich von Greenwich liegt."""
    from datetime import date
    from zoneinfo import ZoneInfo

    from jarvis.skills.briefing.skill import build_facts
    from jarvis.skills.mail.store import MailStore, ReplyStore

    skill, _, _ = baue_skill(
        home,
        conn,
        zone=zone,
        events=[termin(eid="feiertag", titel="Feiertag", start="2026-03-02", ganztags=True)],
    )
    skill.poll()

    z = ZoneInfo(zone)
    facts = build_facts(
        date(2026, 3, 2),
        calendar=CalendarStore(conn),
        mail=MailStore(conn),
        replies=ReplyStore(conn),
        timezone=z,
    )
    assert [t["titel"] for t in facts["termine"]] == ["Feiertag"]
    assert facts["termine"][0]["zeit"] == "ganztags"

    # Am Vortag darf er nicht auftauchen.
    davor = build_facts(
        date(2026, 3, 1),
        calendar=CalendarStore(conn),
        mail=MailStore(conn),
        replies=ReplyStore(conn),
        timezone=z,
    )
    assert davor["termine"] == []


def test_ganztaegiger_termin_behaelt_sein_datum_in_der_uebersicht(home, conn):
    skill, _, _ = baue_skill(
        home,
        conn,
        zone="America/New_York",
        events=[termin(eid="feiertag", titel="Feiertag", start="2026-03-02", ganztags=True)],
    )
    events = skill.poll()
    assert events[0].summary.startswith("2026-03-02 ganztags")
