"""Der ganze Antwortweg durch das Gatter -- und die Umschaltung auf Stufe 1."""

from __future__ import annotations

import json

from jarvis.core.audit import AuditLog
from jarvis.core.config import Config, Paths, StopSwitch
from jarvis.core.gate import Gate
from jarvis.core.ratelimit import RateLimiter
from jarvis.skills.mail.allowlist import Allowlist
from jarvis.skills.mail.gmail import DRAFTING, SENDING
from jarvis.skills.mail.reply import MailDraftSkill, MailSendSkill, ReplyOptions, SendOptions
from jarvis.skills.mail.store import STATE_ANALYSED, MailStore, ReplyStore
from jarvis.skills.mail.style import extract_profile
from jarvis.skills.runner import run_skill
from tests.fixtures_gmail import FakeGmailClient, entwurf_hinterlegen, message
from tests.test_mail_reply import ANTWORT, router_mit


def konfig(home, *, dry_run=True, reply_level=0, send_level=0, send_limits=None):
    raw = {
        "dry_run": dry_run,
        "capabilities": {
            "mail_reply": {
                "autonomy_level": reply_level,
                "requires_outbound": False,
                "rate_limits": {"hour": 20},
            },
            "mail_send": {
                "autonomy_level": send_level,
                "requires_outbound": True,
                "rate_limits": send_limits or {"hour": 10},
            },
        },
        "llm": {
            "providers": {
                "trocken": {"kind": "static", "model": "static", "local": True, "reply": "{}"}
            },
            "tasks": {"draft": {"providers": ["trocken"]}},
        },
    }
    return Config.from_mapping(raw, paths=Paths(home=home))


def entwurfs_lauf(conn, home, nachrichten, *, dry_run=True, level=0, capabilities=DRAFTING):
    config = konfig(home, dry_run=dry_run, reply_level=level)
    client = FakeGmailClient(nachrichten, capabilities=capabilities)
    mail_store = MailStore(conn)
    for roh in nachrichten:
        mail_store.remember(
            message_id=roh["id"],
            thread_id=roh["threadId"],
            category="anfrage",
            needs_reply=True,
            state=STATE_ANALYSED,
        )
    skill = MailDraftSkill(
        options=ReplyOptions({}, known_tasks={"draft"}),
        client=client,
        router=router_mit(ANTWORT),
        mail_store=mail_store,
        reply_store=ReplyStore(conn),
        style=extract_profile([]),
    )
    audit = AuditLog(conn)
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
    return skill, client, gate, audit, config


def sende_lauf(conn, home, *, send_level=0, manual=(), limits=None, dry_run=False):
    config = konfig(home, dry_run=dry_run, send_level=send_level, send_limits=limits)
    # Genau die Ableitung, die auch die Kommandozeile macht.
    capabilities = SENDING if config.permits("mail_send", 1) else DRAFTING
    client = FakeGmailClient(capabilities=capabilities)
    skill = MailSendSkill(
        options=SendOptions({}),
        client=client,
        reply_store=ReplyStore(conn),
        allowlist=Allowlist(conn, manual=manual, threshold=3),
    )
    audit = AuditLog(conn)
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
    return skill, client, gate, audit, config


def entwurf_ablegen(conn, message_id="a", empfaenger="anna@example.com", *, client=None):
    """Legt Vorgang und passenden Entwurf an -- beides muss zusammenpassen."""
    draft_id = f"Draft_{message_id}"
    abdruck = "f"
    if client is not None:
        abdruck = entwurf_hinterlegen(client, draft_id=draft_id, to=empfaenger)
    ReplyStore(conn).plan(
        message_id=message_id,
        thread_id="t",
        recipient=empfaenger,
        subject="Re: x",
        fingerprint=abdruck,
        disposition="drafted",
        draft_id=draft_id,
        draft_fingerprint=abdruck,
    )


# --- Entwuerfe -------------------------------------------------------------- #


def test_trockenlauf_legt_keinen_entwurf_an(conn, home):
    skill, client, gate, audit, _ = entwurfs_lauf(conn, home, [message(mid="a")])
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.dry_run == 1
    assert bericht.acted == 0
    assert client.drafts == {}
    # Trotzdem festgehalten, was entstanden waere.
    eintrag = ReplyStore(conn).get("a")
    assert eintrag.disposition == "planned"
    assert eintrag.fingerprint


def test_ohne_trockenlauf_entsteht_ein_entwurf(conn, home):
    skill, client, gate, audit, _ = entwurfs_lauf(conn, home, [message(mid="a")], dry_run=False)
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.acted == 1
    assert list(client.drafts) == ["Draft_1"]
    assert client.sent_drafts == []  # entworfen ist nicht gesendet
    assert ReplyStore(conn).get("a").disposition == "drafted"


def test_entwerfen_kommt_mit_stufe_null_aus(conn, home):
    """Ein Entwurf erreicht niemanden -- die Stufenleiter gilt fuer das Senden."""
    skill, _client, gate, audit, _ = entwurfs_lauf(
        conn, home, [message(mid="a")], dry_run=False, level=0
    )
    assert run_skill(skill, gate=gate, audit=audit).acted == 1


# --- Senden ----------------------------------------------------------------- #


def test_auf_stufe_null_wird_nicht_gesendet(conn, home):
    skill, client, gate, audit, _config = sende_lauf(
        conn, home, send_level=0, manual=["anna@example.com"]
    )
    entwurf_ablegen(conn, client=client)
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.dry_run == 1
    assert bericht.acted == 0
    assert client.sent_drafts == []
    # Und der Client haette es auch gar nicht gekonnt.
    assert client.can("send") is False


def test_stufe_eins_sendet(conn, home):
    """Die Umschaltung aus Abschnitt 6: ein Wert, sonst nichts."""
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"]
    )
    entwurf_ablegen(conn, client=client)
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.acted == 1
    assert client.sent_drafts == ["Draft_a"]
    assert ReplyStore(conn).get("a").disposition == "sent"


def test_stufe_eins_ohne_allowlist_sendet_nicht(conn, home):
    skill, client, gate, audit, _ = sende_lauf(conn, home, send_level=1)
    entwurf_ablegen(conn, empfaenger="fremd@example.com", client=client)
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.skipped == 1
    assert client.sent_drafts == []
    assert ReplyStore(conn).get("a").disposition == "held"


def test_zurueckgehaltenes_verbraucht_kein_kontingent(conn, home):
    skill, client, gate, audit, config = sende_lauf(conn, home, send_level=1)
    entwurf_ablegen(conn, empfaenger="fremd@example.com", client=client)
    run_skill(skill, gate=gate, audit=audit)
    limiter = RateLimiter(conn, config.capabilities)
    assert limiter.usage("mail_send")[0].used == 0


def test_stoppschalter_haelt_das_senden_an(conn, home):
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"]
    )
    entwurf_ablegen(conn, client=client)
    StopSwitch(home / "STOP").engage("Vorfall")
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.blocked == 1
    assert client.sent_drafts == []


def test_obergrenze_bremst_das_senden(conn, home):
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"], limits={"hour": 2}
    )
    for i in range(4):
        entwurf_ablegen(conn, message_id=f"m{i}", client=client)
    bericht = run_skill(skill, gate=gate, audit=audit)

    assert bericht.acted == 2
    assert bericht.blocked == 2
    assert len(client.sent_drafts) == 2


def test_globaler_trockenlauf_schlaegt_auch_stufe_eins(conn, home):
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"], dry_run=True
    )
    entwurf_ablegen(conn, client=client)
    bericht = run_skill(skill, gate=gate, audit=audit)
    assert bericht.dry_run == 1
    assert client.sent_drafts == []


def test_protokoll_erzaehlt_das_senden_nach(conn, home):
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"]
    )
    entwurf_ablegen(conn, client=client)
    run_skill(skill, gate=gate, audit=audit)

    eintraege = list(reversed(audit.recent(10)))
    assert [e.kind for e in eintraege] == ["decision", "action", "action"]
    assert [e.outcome for e in eintraege] == ["send", "act", "performed"]
    assert eintraege[0].detail["decided_by"] == "allowlist"
    assert audit.verify().ok


def test_das_protokoll_nennt_den_empfaenger(conn, home):
    """Nachvollziehbar muss sein, an wen etwas ging."""
    skill, client, gate, audit, _ = sende_lauf(
        conn, home, send_level=1, manual=["anna@example.com"]
    )
    entwurf_ablegen(conn, client=client)
    run_skill(skill, gate=gate, audit=audit)
    assert "anna@example.com" in json.dumps([e.detail for e in audit.recent(10)])


# --- Der Freigabeweg war eine Sackgasse ------------------------------------ #


def _freigabelauf(conn, home):
    """Der echte Ablauf: im Trockenlauf sammeln, dann freigeben.

    Die Warteschlange fuellt sich nur, solange das Gatter nicht handeln laesst
    -- und eine Freigabe hebt den Trockenlauf ausdruecklich *nicht* auf. Beides
    zusammen heisst: gesammelt wird mit `dry_run = true`, ausgefuehrt wird
    danach mit einem Gatter, dem der Trockenlauf abgeschaltet wurde. Genau so
    laeuft es auch beim Nutzer, nur mit einer Aenderung in der Konfiguration
    dazwischen.
    """
    from jarvis.core.approvals import ApprovalStore

    skill, client, gate, audit, _ = entwurfs_lauf(conn, home, [message(mid="a")])
    store = ApprovalStore(conn)
    run_skill(skill, gate=gate, audit=audit, approvals=store, collect_approvals=True)

    scharf = konfig(home, dry_run=False)
    freigabe_gate = Gate(scharf, audit, RateLimiter(conn, scharf.capabilities))
    return skill, client, freigabe_gate, audit, store


def test_eine_freigabe_traegt_den_entwurf_im_speicher_nach(conn, home):
    """Der Befund aus dem End-to-End-Review von Phase 1-7.

    `run_skill` ruft `skill.after()`, `execute_approval` rief nichts. Der
    Entwurf entstand also im Postfach, aber der Antwortspeicher stand weiter
    auf "geplant, kein Entwurf" -- und `pending_for_send` verlangt genau das
    Gegenteil. Ein im Dashboard freigegebener Entwurf konnte deshalb nie
    versendet werden.
    """
    from jarvis.skills.runner import execute_approval

    skill, client, gate, audit, store = _freigabelauf(conn, home)
    vorgang = store.pending(limit=1)[0]

    ergebnis = execute_approval(vorgang, skill=skill, gate=gate, audit=audit, approvals=store)

    assert ergebnis is not None and ergebnis.performed
    assert list(client.drafts), "im Postfach ist ein Entwurf entstanden"

    eintrag = ReplyStore(conn).get("a")
    assert eintrag.disposition == "drafted", "der Entwurf ist im Speicher nicht angekommen"
    assert eintrag.draft_id, "ohne Entwurfskennung findet ihn der Versand nie"

    # Die eigentliche Folge: er steht jetzt ueberhaupt zum Versand bereit.
    assert [e.message_id for e in ReplyStore(conn).pending_for_send()] == ["a"]


def test_eine_kaputte_nachbereitung_macht_die_freigabe_nicht_ungueltig(conn, home):
    """Die Aktion ist gelaufen -- das Nachtragen darf sie nicht zurueckdrehen."""
    from jarvis.skills.runner import execute_approval

    skill, _client, gate, audit, store = _freigabelauf(conn, home)
    vorgang = store.pending(limit=1)[0]

    def kaputt(decision, result):
        raise RuntimeError("Speicher weg")

    skill.after_approval = kaputt
    ergebnis = execute_approval(vorgang, skill=skill, gate=gate, audit=audit, approvals=store)

    assert ergebnis is not None and ergebnis.performed
    assert store.get(vorgang.id).state == "executed"
    gescheitert = [e for e in audit.recent(20) if e.outcome == "failed"]
    assert any("after_approval" in str(e.detail) for e in gescheitert)
