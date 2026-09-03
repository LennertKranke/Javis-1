"""Die fuenf Haertungen: Zustandsmodell, Entwurfsintegritaet, Ziele, lokal, Rechte.

Jeder Abschnitt haelt eine Eigenschaft fest, deren Fehlen einmal ein echtes
Problem war. Sie stehen zusammen, weil sie zusammen den Kern absichern.
"""

from __future__ import annotations

import json
import tomllib

import pytest

from jarvis.core.audit import AuditLog
from jarvis.core.config import DEFAULT_CONFIG_TOML, Config, ConfigError, Paths
from jarvis.core.gate import Gate
from jarvis.core.ratelimit import RateLimiter
from jarvis.skills.base import Decision, Skill, TargetMismatch
from jarvis.skills.mail.allowlist import Allowlist
from jarvis.skills.mail.gmail import DRAFTING, SENDING
from jarvis.skills.mail.reply import MailSendSkill, SendOptions
from jarvis.skills.mail.store import (
    STATE_ACTED,
    STATE_ANALYSED,
    MailStore,
    ReplyStore,
)
from jarvis.skills.runner import execute_approval, run_skill
from tests.conftest import build_config
from tests.fixtures_gmail import FakeGmailClient, b64, message
from tests.test_mail_reply import draft_skill
from tests.test_mail_skill import skill_mit


def vollstaendige_konfig(home, **kwargs):
    roh = tomllib.loads(DEFAULT_CONFIG_TOML)
    roh.update(kwargs)
    return Config.from_mapping(roh, paths=Paths(home=home))


# --------------------------------------------------------------------------- #
# 1. Ein Trockenlauf verbrennt keine Nachricht
# --------------------------------------------------------------------------- #


def lauf(conn, home, nachrichten, *, dry_run, level=0):
    config = build_config(home, dry_run=dry_run, level=level, outbound=False)
    skill, client = skill_mit(conn, nachrichten)
    audit = AuditLog(conn)
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
    return run_skill(skill, gate=gate, audit=audit), client, audit


def test_trockenlauf_dann_echter_lauf_handelt_wirklich(conn, home):
    """Der Kern der Korrektur.

    Frueher galt die Nachricht nach dem Trockenlauf als verarbeitet und wurde
    beim echten Lauf uebersprungen -- die Beobachtungswoche hat den
    Posteingang still verbrannt.
    """
    nachrichten = [message(mid="a"), message(mid="b")]

    trocken, client1, _ = lauf(conn, home, nachrichten, dry_run=True)
    assert trocken.dry_run == 2
    assert client1.modified == []
    assert MailStore(conn).counts_by_state() == {STATE_ANALYSED: 2}

    echt, client2, _ = lauf(conn, home, nachrichten, dry_run=False)
    assert echt.polled == 2, "die Nachrichten muessen wieder aufgegriffen werden"
    assert echt.acted == 2
    assert [m[0] for m in client2.modified] == ["a", "b"]
    assert MailStore(conn).counts_by_state() == {STATE_ACTED: 2}


def test_echter_lauf_bleibt_wiederholbar(conn, home):
    nachrichten = [message(mid="a")]
    erst, _client1, _ = lauf(conn, home, nachrichten, dry_run=False)
    zweit, client2, _ = lauf(conn, home, nachrichten, dry_run=False)

    assert erst.acted == 1
    assert zweit.polled == 0
    assert client2.modified == []


def test_ein_spaeterer_trockenlauf_nimmt_nichts_zurueck(conn, home):
    nachrichten = [message(mid="a")]
    lauf(conn, home, nachrichten, dry_run=False)
    MailStore(conn).remember(message_id="a", category="rechnung", state=STATE_ANALYSED)
    assert MailStore(conn).get("a").state == STATE_ACTED


def test_zweiter_trockenlauf_fragt_das_modell_nicht_erneut(conn, home):
    """Sonst kostet jede Beobachtungsstunde erneut Modellaufrufe."""
    nachrichten = [message(mid="a")]
    lauf(conn, home, nachrichten, dry_run=True)
    _, _, audit = lauf(conn, home, nachrichten, dry_run=True)

    quellen = [e.detail.get("decided_by") for e in audit.recent(20) if e.kind == "decision"]
    assert "model" in quellen
    assert "cached" in quellen


def test_das_protokoll_bleibt_vollstaendig(conn, home):
    nachrichten = [message(mid="a")]
    lauf(conn, home, nachrichten, dry_run=True)
    _, _, audit = lauf(conn, home, nachrichten, dry_run=False)
    assert audit.verify().ok
    assert audit.count() >= 4  # zwei Durchlaeufe, je Entscheidung und Gatter


def test_die_vier_zustaende_bleiben_unterscheidbar(conn, home):
    eigene = message(mid="eigen", headers={"From": "ich@example.com"})
    lauf(conn, home, [message(mid="a"), eigene], dry_run=True)
    zustaende = MailStore(conn).counts_by_state()
    assert zustaende["analysed"] == 1
    assert zustaende["skipped"] == 1


# --------------------------------------------------------------------------- #
# 2. Ein veraenderter Entwurf geht nicht hinaus
# --------------------------------------------------------------------------- #


def sendeaufbau(conn, *, capabilities=SENDING, manual=("anna@example.com",)):
    client = FakeGmailClient(capabilities=capabilities)
    skill = MailSendSkill(
        options=SendOptions({}),
        client=client,
        reply_store=ReplyStore(conn),
        allowlist=Allowlist(conn, manual=list(manual), threshold=3),
    )
    return skill, client


def echten_entwurf_anlegen(conn, *, empfaenger="anna@example.com"):
    """Legt ueber die Entwurfsfaehigkeit einen echten Entwurf an."""
    roh = message(mid="a", headers={"From": empfaenger})
    entwurfsskill, entwurfsclient = draft_skill(conn, [roh])
    MailStore(conn).remember(
        message_id="a", category="anfrage", needs_reply=True, state=STATE_ANALYSED
    )
    ereignis = entwurfsskill.poll()[0]
    entscheidung = entwurfsskill.decide(ereignis)
    ergebnis = entwurfsskill.act(entscheidung)
    entwurfsskill.after(ereignis, entscheidung, "act", ergebnis)
    return entwurfsclient


def test_unveraenderter_entwurf_geht_hinaus(conn):
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts

    entscheidung = skill.decide(skill.poll()[0])
    assert entscheidung.action == "send"
    assert skill.act(entscheidung).performed is True
    assert client.sent_drafts == ["Draft_1"]


def test_veraenderter_entwurf_wird_zurueckgehalten(conn):
    """Empfaenger, Betreff, Thread oder Text geaendert: kein Versand."""
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts
    # Jemand aendert den Text im Postfach.
    client.drafts["Draft_1"]["message"]["payload"]["body"]["data"] = b64("Ganz anders")

    entscheidung = skill.decide(skill.poll()[0])
    assert entscheidung.action == "hold"
    assert entscheidung.decided_by == "integritaet"
    assert "weicht" in entscheidung.reason
    assert client.sent_drafts == []


@pytest.mark.parametrize(
    ("kopf", "wert"),
    [("To", "angreifer@boese.tld"), ("Subject", "Etwas ganz anderes")],
)
def test_veraenderter_kopf_wird_zurueckgehalten(conn, kopf, wert):
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts
    kopfzeilen = client.drafts["Draft_1"]["message"]["payload"]["headers"]
    for eintrag in kopfzeilen:
        if eintrag["name"].lower() == kopf.lower():
            eintrag["value"] = wert
    assert skill.decide(skill.poll()[0]).action == "hold"


def test_veraenderter_thread_wird_zurueckgehalten(conn):
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts
    client.drafts["Draft_1"]["message"]["threadId"] = "anderer-thread"
    assert skill.decide(skill.poll()[0]).action == "hold"


def test_act_prueft_noch_einmal_unmittelbar_vor_dem_senden(conn):
    """Zwischen Beurteilung und Versand kann Zeit vergehen -- auch Tage."""
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts

    entscheidung = skill.decide(skill.poll()[0])
    assert entscheidung.action == "send"

    # Erst jetzt wird der Entwurf veraendert.
    client.drafts["Draft_1"]["message"]["payload"]["body"]["data"] = b64("Untergeschoben")

    ergebnis = skill.act(entscheidung)
    assert ergebnis.performed is False
    assert ergebnis.detail["integritaet"] == "abweichung"
    assert client.sent_drafts == []


def test_vertauschte_entwurfskennung_wird_erkannt(conn):
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts

    entscheidung = skill.decide(skill.poll()[0])
    gefaelscht = Decision(
        skill=entscheidung.skill,
        event_key=entscheidung.event_key,
        action="send",
        reason="x",
        decided_by="allowlist",
        targets={**dict(entscheidung.targets), "draft_id": "Draft_999"},
    )
    ergebnis = skill.act(gefaelscht)
    assert ergebnis.performed is False
    assert ergebnis.detail["integritaet"] == "entwurf_vertauscht"
    assert client.sent_drafts == []


def test_die_verweigerung_steht_im_protokoll(conn, home):
    quelle = echten_entwurf_anlegen(conn)
    skill, client = sendeaufbau(conn)
    client.drafts = quelle.drafts
    client.drafts["Draft_1"]["message"]["payload"]["body"]["data"] = b64("Anders")

    config = build_config(home, dry_run=False, level=1, outbound=True, limits={"hour": 5})
    audit = AuditLog(conn)
    # Die Faehigkeit heisst mail_send; die Testkonfiguration kennt nur mail.
    config.capabilities["mail_send"] = config.capabilities["mail"]
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))

    bericht = run_skill(skill, gate=gate, audit=audit)
    assert bericht.acted == 0
    assert bericht.skipped == 1
    protokoll = json.dumps([e.detail for e in audit.recent(10)])
    assert "weicht" in protokoll
    assert client.sent_drafts == []


# --------------------------------------------------------------------------- #
# 3. Aufbewahrte Ziele werden neu berechnet, nicht geglaubt
# --------------------------------------------------------------------------- #


class OhnePruefung(Skill):
    name = "mail"
    autonomy_level = 0
    requires_outbound = False

    def poll(self):
        return []

    def decide(self, event):
        raise NotImplementedError

    def act(self, decision):
        raise AssertionError("darf nicht aufgerufen werden")


def test_faehigkeit_ohne_zielpruefung_wird_verweigert():
    """Vergessen faellt auf, statt stillschweigend durchzugehen."""
    entscheidung = Decision(
        skill="mail",
        event_key="a",
        action="label",
        reason="x",
        decided_by="model",
        targets={"message_id": "a"},
    )
    with pytest.raises(NotImplementedError, match="verify_targets"):
        OhnePruefung().verify_targets(entscheidung)


def test_ohne_ziele_braucht_es_keine_pruefung():
    entscheidung = Decision(
        skill="mail", event_key="a", action="skip", reason="x", decided_by="rule"
    )
    assert OhnePruefung().verify_targets(entscheidung) is entscheidung


def durchlauf_ohne_handeln(skill):
    """Beurteilt einmal und vermerkt den Zustand -- wie ein Trockenlauf."""
    ereignis = skill.poll()[0]
    entscheidung = skill.decide(ereignis)
    skill.after(ereignis, entscheidung, "dry_run", None)
    return entscheidung


def test_label_wird_aus_der_kategorie_neu_gerechnet(conn):
    skill, _ = skill_mit(conn, [message(mid="a")], labels=[{"id": "L1", "name": "JARVIS/Rechnung"}])
    durchlauf_ohne_handeln(skill)
    entscheidung = Decision(
        skill="mail",
        event_key="a",
        action="label",
        reason="x",
        decided_by="model",
        targets={
            "message_id": "a",
            "category": "rechnung",
            "label_id": "GEFAELSCHT",
            "label_name": "Woanders/Hin",
        },
    )
    geprueft = skill.verify_targets(entscheidung)
    assert geprueft.targets["label_id"] == "L1"
    assert geprueft.targets["label_name"] == "JARVIS/Rechnung"


def test_erfundene_kategorie_wird_abgewiesen(conn):
    skill, _ = skill_mit(conn, [message(mid="a")])
    durchlauf_ohne_handeln(skill)
    entscheidung = Decision(
        skill="mail",
        event_key="a",
        action="label",
        reason="x",
        decided_by="model",
        targets={"message_id": "a", "category": "alles_loeschen"},
    )
    with pytest.raises(TargetMismatch, match="Kategorie"):
        skill.verify_targets(entscheidung)


def test_unbekannte_nachrichtenkennung_wird_abgewiesen(conn):
    skill, _ = skill_mit(conn, [message(mid="a")])
    entscheidung = Decision(
        skill="mail",
        event_key="fremd",
        action="label",
        reason="x",
        decided_by="model",
        targets={"message_id": "fremd", "category": "rechnung"},
    )
    with pytest.raises(TargetMismatch, match="nicht bekannt"):
        skill.verify_targets(entscheidung)


def test_empfaenger_wird_aus_den_kopffeldern_neu_gerechnet(conn):
    """Die gespeicherte Zeile bestimmt den Empfaenger nicht."""
    skill, _ = draft_skill(conn, [message(mid="a", headers={"From": "echt@example.com"})])
    MailStore(conn).remember(
        message_id="a", category="anfrage", needs_reply=True, state=STATE_ANALYSED
    )
    ereignis = skill.poll()[0]
    echt = skill.decide(ereignis)

    manipuliert = Decision(
        skill=echt.skill,
        event_key=echt.event_key,
        action="draft",
        reason="x",
        decided_by="model",
        fields=dict(echt.fields),
        targets={**dict(echt.targets), "to": "angreifer@boese.tld"},
    )
    with pytest.raises(TargetMismatch, match="to hat sich geaendert"):
        skill.verify_targets(manipuliert)


def test_geprueft_kommt_der_echte_empfaenger_heraus(conn):
    skill, _ = draft_skill(conn, [message(mid="a", headers={"From": "echt@example.com"})])
    MailStore(conn).remember(
        message_id="a", category="anfrage", needs_reply=True, state=STATE_ANALYSED
    )
    echt = skill.decide(skill.poll()[0])
    geprueft = skill.verify_targets(echt)
    assert geprueft.targets["to"] == "echt@example.com"
    assert geprueft.targets["fingerprint"] == echt.targets["fingerprint"]


def test_freigabe_mit_manipulierten_zielen_wird_verweigert(conn, home):
    """Der ganze Weg: Warteschlange, Manipulation, Freigabe, Verweigerung."""
    from jarvis.core.approvals import ApprovalStore

    skill, client = skill_mit(conn, [message(mid="a")])
    durchlauf_ohne_handeln(skill)
    store = ApprovalStore(conn)
    vorgang = store.enqueue(
        skill="mail",
        event_key="a",
        action="label",
        reason="Stufe zu niedrig",
        decided_by="model",
        fields={"kategorie": "rechnung"},
        targets={"message_id": "a", "category": "erfunden"},
    )

    config = build_config(home, dry_run=False, level=0, outbound=False)
    audit = AuditLog(conn)
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))

    ergebnis = execute_approval(vorgang, skill=skill, gate=gate, audit=audit, approvals=store)
    assert ergebnis is None
    assert store.get(vorgang.id).state == "failed"
    assert client.modified == []
    assert audit.recent(1)[0].outcome == "refused"


# --------------------------------------------------------------------------- #
# 4. "Lokal" ist technisch pruefbar
# --------------------------------------------------------------------------- #


def lade_anbieter(home, **kw):
    body = {"kind": "ollama", "model": "m", "local": True}
    body.update(kw)
    return Config.from_mapping(
        {"capabilities": {}, "llm": {"providers": {"x": body}, "tasks": {}}},
        paths=Paths(home=home),
    )


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"],
)
def test_lokal_mit_loopback_ist_in_ordnung(home, url):
    assert lade_anbieter(home, base_url=url).llm.providers["x"].local is True


@pytest.mark.parametrize(
    "url",
    [
        "http://gpu.example.com:11434",
        "http://192.168.1.50:11434",
        "https://api.fremd.tld/v1",
    ],
)
def test_lokal_mit_fremdem_wirt_wird_abgewiesen(home, url):
    with pytest.raises(ConfigError, match="local = true"):
        lade_anbieter(home, base_url=url)


def test_anthropic_kann_nicht_lokal_sein(home):
    with pytest.raises(ConfigError, match="nicht haltbar"):
        lade_anbieter(home, kind="anthropic")


def test_der_anbieter_prueft_sich_beim_bauen_selbst():
    """Zweite Linie: auch ein im Betrieb zusammengesetzter Anbieter prueft."""
    from jarvis.core.config import ProviderConfig
    from jarvis.llm.provider import ProviderUnavailable
    from jarvis.llm.providers.ollama import OllamaProvider

    fremd = ProviderConfig(
        name="o", kind="ollama", model="m", local=True, base_url="http://gpu.example.com"
    )
    with pytest.raises(ProviderUnavailable, match="als lokal gefuehrt"):
        OllamaProvider(fremd)


def test_vertrauliche_aufgabe_bleibt_damit_wirklich_lokal(home):
    """Die Sperre im Router stuetzt sich jetzt auf eine gepruefte Zusage."""
    with pytest.raises(ConfigError):
        Config.from_mapping(
            {
                "capabilities": {},
                "llm": {
                    "providers": {
                        "getarnt": {
                            "kind": "ollama",
                            "model": "m",
                            "local": True,
                            "base_url": "http://gpu.example.com:11434",
                        }
                    },
                    "tasks": {"personal": {"providers": ["getarnt"], "confidential": True}},
                },
            },
            paths=Paths(home=home),
        )


# --------------------------------------------------------------------------- #
# 5. Gatter und Client rechnen gleich
# --------------------------------------------------------------------------- #


def test_ohne_freigabe_kein_senderecht(home):
    from jarvis.skills.factory import send_capabilities

    config = vollstaendige_konfig(home)
    assert config.permits("mail_send", 1) is False
    assert send_capabilities(config) == DRAFTING


def test_mit_freigabe_beides(home):
    """Frueher liess das Gatter durch, was der Client danach nicht durfte."""
    from jarvis.skills.factory import send_capabilities

    config = vollstaendige_konfig(home)
    assert config.permits("mail_send", 1, approved=True) is True
    assert send_capabilities(config, approved=True) == SENDING


def test_mit_stufe_eins_beides(home):
    from jarvis.skills.factory import send_capabilities

    roh = tomllib.loads(DEFAULT_CONFIG_TOML)
    roh["capabilities"]["mail_send"]["autonomy_level"] = 1
    config = Config.from_mapping(roh, paths=Paths(home=home))
    assert config.permits("mail_send", 1) is True
    assert send_capabilities(config) == SENDING


def test_abgeschaltete_faehigkeit_schlaegt_die_freigabe(home):
    """Eine Freigabe ersetzt die Stufe, nicht den Ein-Aus-Schalter."""
    from jarvis.skills.factory import send_capabilities

    roh = tomllib.loads(DEFAULT_CONFIG_TOML)
    roh["capabilities"]["mail_send"]["enabled"] = False
    config = Config.from_mapping(roh, paths=Paths(home=home))
    assert config.permits("mail_send", 1, approved=True) is False
    assert send_capabilities(config, approved=True) == DRAFTING


def test_gatter_und_fabrik_benutzen_dieselbe_stelle():
    """Strukturell: keine zweite Rechnung, die auseinanderlaufen koennte."""
    import inspect

    from jarvis.core.gate import Gate
    from jarvis.skills.factory import send_capabilities

    assert "permits(" in inspect.getsource(Gate.evaluate)
    assert "permits(" in inspect.getsource(send_capabilities)


def test_pfad_bleibt_unveraendert():
    """Die Kette aus Abschnitt 7 der Vorgabe steht noch."""
    import inspect

    from jarvis.skills.runner import run_skill

    quelle = inspect.getsource(run_skill)
    for schritt in ("skill.poll", "skill.decide", "gate.evaluate", "skill.act", "audit.record"):
        assert schritt in quelle
    # Gehandelt wird nur nach dem Gatter.
    assert quelle.index("gate.evaluate") < quelle.index("skill.act(decision)")


# --------------------------------------------------------------------------- #
# 6. Der Modellteil bleibt vom handelnden Teil getrennt
#
# Der Router beantwortet genau eine Frage: welcher Anbieter bedient diese
# Aufgabe. Nicht: darf gehandelt werden. Diese Grenze war bisher wahr, aber
# nirgends festgehalten -- ein einziger Import haette daraus eine zweite
# Autorisierungsschicht gemacht, ohne dass ein Test es gemerkt haette.
# --------------------------------------------------------------------------- #


#: Woraus `jarvis/llm/` importieren darf. Alles andere aus `jarvis` waere ein
#: Griff in den handelnden Teil.
LLM_DARF_IMPORTIEREN = frozenset({"jarvis.core.config", "jarvis.core.secrets"})


def llm_importe() -> dict[str, set[str]]:
    """Jede Datei unter `jarvis/llm/` und die `jarvis`-Module, die sie holt.

    Statisch ueber den Syntaxbaum, nicht ueber die geladenen Module: so faellt
    auch ein Import auf, der tief in einer Funktion steht und nur in einem
    seltenen Zweig ausgefuehrt wuerde.
    """
    import ast
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[1] / "jarvis" / "llm"
    gefunden: dict[str, set[str]] = {}
    for datei in sorted(wurzel.rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        module: set[str] = set()
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Import):
                module.update(a.name for a in knoten.names)
            elif isinstance(knoten, ast.ImportFrom) and knoten.module and knoten.level == 0:
                module.add(knoten.module)
        gefunden[str(datei.relative_to(wurzel.parent.parent))] = {
            m for m in module if m == "jarvis" or m.startswith("jarvis.")
        }
    return gefunden


def test_der_llm_teil_greift_nicht_in_den_handelnden_teil():
    verstoesse = []
    for datei, module in llm_importe().items():
        for modul in sorted(module):
            if modul.startswith("jarvis.llm"):
                continue
            if modul in LLM_DARF_IMPORTIEREN:
                continue
            verstoesse.append(f"{datei} importiert {modul}")
    assert not verstoesse, (
        "Der Router entscheidet ueber Anbieter und Modell, nicht darueber, ob "
        "gehandelt werden darf. Erlaubt sind nur "
        f"{', '.join(sorted(LLM_DARF_IMPORTIEREN))}: " + "; ".join(verstoesse)
    )


@pytest.mark.parametrize(
    "verboten",
    [
        "jarvis.core.gate",
        "jarvis.core.approvals",
        "jarvis.core.db",
        "jarvis.core.ratelimit",
        "jarvis.core.audit",
        "jarvis.skills",
    ],
)
def test_die_verbotenen_module_stehen_wirklich_nirgends(verboten):
    """Dasselbe von der anderen Seite: die Liste beim Namen genannt.

    Die Zulassungsliste allein wuerde stillschweigend nachgeben, wenn jemand
    sie erweitert. Diese Pruefung nennt die sechs Stellen, um die es geht.
    """
    for datei, module in llm_importe().items():
        treffer = [m for m in module if m == verboten or m.startswith(f"{verboten}.")]
        assert not treffer, f"{datei} importiert {treffer}"


def test_der_router_faellt_geschlossen_aus():
    """Eine Ausfallpause ueberspringt einen Anbieter, sie erlaubt keinen.

    Strukturell: die Kette entsteht in `chain()` samt Vertraulichkeitssperre,
    bevor in `complete()` irgendetwas uebersprungen wird.
    """
    import inspect

    from jarvis.llm.router import Router

    quelle = inspect.getsource(Router.complete)
    assert "self.chain(task)" in quelle
    assert quelle.index("self.chain(task)") < quelle.index("nutzbar")
    # Und die Sperre selbst liegt in chain(), nicht in einem Zweig daneben.
    assert "ConfidentialityError" in inspect.getsource(Router.chain)
