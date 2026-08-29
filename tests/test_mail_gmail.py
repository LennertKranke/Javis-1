"""Gmail-Client: die Allowlist und die Fehlerzuordnung."""

from __future__ import annotations

import json
import urllib.error

import pytest

from jarvis.skills.mail.gmail import (
    DRAFTING,
    LABELLING,
    SENDING,
    GmailAuthError,
    GmailClient,
    GmailError,
)


class FakeAuth:
    def token(self) -> str:
        return "tok-123"


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def client_mit(monkeypatch, antwort=None, fehler=None, capabilities=LABELLING):
    client = GmailClient(FakeAuth(), capabilities=capabilities)
    aufzeichnung = {}

    def fake_open(request, timeout=None):
        aufzeichnung["url"] = request.full_url
        aufzeichnung["method"] = request.get_method()
        aufzeichnung["auth"] = request.get_header("Authorization")
        aufzeichnung["body"] = json.loads(request.data) if request.data else None
        if fehler:
            raise fehler
        return FakeResponse(antwort if antwort is not None else {})

    monkeypatch.setattr(client._opener, "open", fake_open)
    return client, aufzeichnung


# --- Allowlist -------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/messages/send"),
        ("POST", "/messages/abc/send"),
        ("POST", "/drafts"),
        ("POST", "/drafts/send"),
        ("DELETE", "/messages/abc"),
        ("DELETE", "/labels/Label_1"),
        ("GET", "/settings/forwardingAddresses"),
        ("POST", "/settings/filters"),
        ("POST", "/messages/abc/trash"),
    ],
)
def test_nicht_erlaubte_endpunkte_werden_abgewiesen(method, path):
    """Der Token darf laut Zustimmung senden. Der Client darf es nicht."""
    client = GmailClient(FakeAuth(), capabilities=LABELLING)
    with pytest.raises(GmailError, match="erlaubten Endpunkte"):
        client._check_endpoint(method, path)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/profile"),
        ("GET", "/messages"),
        ("GET", "/messages/17f2a1b"),
        ("POST", "/messages/17f2a1b/modify"),
        ("GET", "/labels"),
        ("POST", "/labels"),
    ],
)
def test_erlaubte_endpunkte(method, path):
    GmailClient(FakeAuth(), capabilities=LABELLING)._check_endpoint(method, path)


# --- Faehigkeiten haengen an der Autonomiestufe ----------------------------- #


@pytest.mark.parametrize(
    ("capabilities", "erlaubt_entwurf", "erlaubt_senden"),
    [(LABELLING, False, False), (DRAFTING, True, False), (SENDING, True, True)],
)
def test_stufe_entscheidet_was_der_client_kann(capabilities, erlaubt_entwurf, erlaubt_senden):
    """Auf Stufe 0 kann der Client nicht senden -- nicht weil er es unterlaesst."""
    client = GmailClient(FakeAuth(), capabilities=capabilities)

    def geht(method, path):
        try:
            client._check_endpoint(method, path)
        except GmailError:
            return False
        return True

    assert geht("POST", "/drafts") is erlaubt_entwurf
    assert geht("POST", "/drafts/send") is erlaubt_senden
    # Nie, auf keiner Stufe: eine frisch gebaute zweite Nachricht.
    assert geht("POST", "/messages/send") is False


def test_senden_geht_ausschliesslich_ueber_den_entwurf():
    """So geht genau das hinaus, was vorher dastand und pruefbar war."""
    client = GmailClient(FakeAuth(), capabilities=SENDING)
    with pytest.raises(GmailError):
        client._check_endpoint("POST", "/messages/send")
    client._check_endpoint("POST", "/drafts/send")


def test_unbekannte_faehigkeit_wird_abgelehnt():
    with pytest.raises(ValueError, match="Unbekannte Faehigkeiten"):
        GmailClient(FakeAuth(), capabilities={"alles"})


def test_entwurf_anlegen_und_senden(monkeypatch):
    client, auf = client_mit(monkeypatch, {"id": "d1"}, capabilities=SENDING)
    client.create_draft("cm9o", thread_id="t1")
    assert auf["body"] == {"message": {"raw": "cm9o", "threadId": "t1"}}

    client.send_draft("d1")
    assert auf["url"].endswith("/drafts/send")
    assert auf["body"] == {"id": "d1"}


def test_entwurf_senden_scheitert_auf_stufe_null(monkeypatch):
    client, _ = client_mit(monkeypatch, {"id": "d1"}, capabilities=DRAFTING)
    with pytest.raises(GmailError, match="erlaubten Endpunkte"):
        client.send_draft("d1")


def test_sparsames_format_fuer_viele_nachrichten(monkeypatch):
    client, auf = client_mit(monkeypatch, {"id": "a"})
    client.get_message("a", fmt="metadata", headers=["To", "Cc"])
    assert "format=metadata" in auf["url"]
    assert "metadataHeaders=To%2CCc" in auf["url"]


def test_die_oeffentliche_flaeche_bleibt_uebersichtlich():
    """Kommt eine Methode dazu, faellt es hier auf."""
    client = GmailClient(FakeAuth(), capabilities=SENDING)
    oeffentlich = [n for n in dir(client) if not n.startswith("_")]
    assert not any("trash" in n or "forward" in n or "filter" in n for n in oeffentlich)
    assert sorted(oeffentlich) == [
        "address",
        "can",
        "capabilities",
        "create_draft",
        "create_label",
        "get_draft",
        "get_message",
        "list_labels",
        "list_message_ids",
        "modify_labels",
        "send_draft",
    ]


# --- Aufrufe ---------------------------------------------------------------- #


def test_nachrichtenliste(monkeypatch):
    client, auf = client_mit(monkeypatch, {"messages": [{"id": "a"}, {"id": "b"}]})
    assert client.list_message_ids("is:unread", 10) == ["a", "b"]
    assert "q=is%3Aunread" in auf["url"]
    assert "maxResults=10" in auf["url"]
    assert auf["auth"] == "Bearer tok-123"


def test_obergrenze_wird_gedeckelt(monkeypatch):
    client, auf = client_mit(monkeypatch, {"messages": []})
    client.list_message_ids("x", 100000)
    assert "maxResults=500" in auf["url"]


def test_nachricht_holen_verlangt_format_full(monkeypatch):
    client, auf = client_mit(monkeypatch, {"id": "a"})
    client.get_message("a")
    assert auf["url"].endswith("/messages/a?format=full")


def test_label_setzen(monkeypatch):
    client, auf = client_mit(monkeypatch, {"id": "a"})
    client.modify_labels("a", add=["Label_3"])
    assert auf["method"] == "POST"
    assert auf["body"] == {"addLabelIds": ["Label_3"], "removeLabelIds": []}


def test_label_anlegen_ist_sichtbar(monkeypatch):
    client, auf = client_mit(monkeypatch, {"id": "Label_9"})
    client.create_label("JARVIS/Rechnung")
    assert auf["body"]["name"] == "JARVIS/Rechnung"
    assert auf["body"]["labelListVisibility"] == "labelShow"


# --- Fehler ----------------------------------------------------------------- #


@pytest.mark.parametrize("code", [401, 403])
def test_abgelehnter_zugriff_ist_ein_anmeldefehler(monkeypatch, code):
    fehler = urllib.error.HTTPError("u", code, "nope", {}, None)
    client, _ = client_mit(monkeypatch, fehler=fehler)
    with pytest.raises(GmailAuthError):
        client.list_labels()


def test_drosselung(monkeypatch):
    fehler = urllib.error.HTTPError("u", 429, "slow down", {}, None)
    client, _ = client_mit(monkeypatch, fehler=fehler)
    with pytest.raises(GmailError, match="drosselt"):
        client.list_labels()


def test_serverfehler(monkeypatch):
    fehler = urllib.error.HTTPError("u", 500, "boom", {}, None)
    client, _ = client_mit(monkeypatch, fehler=fehler)
    with pytest.raises(GmailError, match="HTTP 500"):
        client.list_labels()


def test_nicht_erreichbar(monkeypatch):
    client, _ = client_mit(monkeypatch, fehler=urllib.error.URLError("kein Netz"))
    with pytest.raises(GmailError, match="nicht erreichbar"):
        client.list_labels()
