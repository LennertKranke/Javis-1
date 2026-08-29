"""Router: Rueckfallkette und Vertraulichkeitssperre."""

from __future__ import annotations

import pytest

from jarvis.core.config import LLMConfig, ProviderConfig, TaskRoute
from jarvis.llm.provider import Provider, ProviderError, ProviderUnavailable, Request, Response
from jarvis.llm.router import ConfidentialityError, Router, RouterError


class Attrappe(Provider):
    """Anbieter, der antwortet oder ausfaellt, wie der Test es verlangt."""

    def __init__(self, name, *, local=True, fehler=None, antwort="ok"):
        super().__init__(
            ProviderConfig(name=name, kind="static", model=f"{name}-modell", local=local)
        )
        self.fehler = fehler
        self.antwort = antwort
        self.aufrufe = 0
        self.letzte_anfrage: Request | None = None

    def available(self) -> bool:
        return self.fehler is None

    def complete(self, request: Request) -> Response:
        self.aufrufe += 1
        self.letzte_anfrage = request
        if self.fehler:
            raise self.fehler
        return Response(text=self.antwort, provider=self.name, model=self.model)


def router_bauen(tasks, providers):
    llm = LLMConfig(
        providers={p.name: p.config for p in providers.values()},
        tasks=tasks,
    )
    return Router(llm, providers)


def test_erster_anbieter_antwortet():
    a, b = Attrappe("a"), Attrappe("b")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))}, {"a": a, "b": b}
    )
    ergebnis = router.complete("classify", Request.single("hallo"))
    assert ergebnis.response.provider == "a"
    assert b.aufrufe == 0


def test_rueckfall_auf_den_naechsten():
    a = Attrappe("a", fehler=ProviderUnavailable("aus"))
    b = Attrappe("b", antwort="von b")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))}, {"a": a, "b": b}
    )
    ergebnis = router.complete("classify", Request.single("hallo"))
    assert ergebnis.response.text == "von b"
    assert [(v.provider, v.ok) for v in ergebnis.attempts] == [("a", False), ("b", True)]


def test_ausfall_aller_anbieter_nennt_jeden_versuch():
    a = Attrappe("a", fehler=ProviderUnavailable("nicht erreichbar"))
    b = Attrappe("b", fehler=ProviderError("HTTP 500"))
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))}, {"a": a, "b": b}
    )
    with pytest.raises(RouterError) as exc:
        router.complete("classify", Request.single("hallo"))
    assert "nicht erreichbar" in str(exc.value)
    assert "HTTP 500" in str(exc.value)


def test_programmfehler_werden_nicht_verschluckt():
    """Ein Fehler im eigenen Code darf nicht als Anbieterausfall durchgehen."""
    a = Attrappe("a", fehler=ZeroDivisionError("Bug"))
    b = Attrappe("b")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))}, {"a": a, "b": b}
    )
    with pytest.raises(ZeroDivisionError):
        router.complete("classify", Request.single("hallo"))
    assert b.aufrufe == 0


def test_vertrauliche_aufgabe_mit_externem_anbieter_wird_verweigert():
    lokal, wolke = Attrappe("lokal", local=True), Attrappe("wolke", local=False)
    router = router_bauen(
        {"personal": TaskRoute(name="personal", providers=("lokal", "wolke"), confidential=True)},
        {"lokal": lokal, "wolke": wolke},
    )
    with pytest.raises(ConfidentialityError, match=r"5\.2"):
        router.complete("personal", Request.single("privat"))
    assert lokal.aufrufe == 0  # nicht einmal der lokale wird gefragt


def test_vertrauliche_aufgabe_rein_lokal_ist_in_ordnung():
    lokal = Attrappe("lokal", local=True)
    router = router_bauen(
        {"personal": TaskRoute(name="personal", providers=("lokal",), confidential=True)},
        {"lokal": lokal},
    )
    assert router.complete("personal", Request.single("privat")).response.provider == "lokal"


def test_unbekannte_aufgabe():
    router = router_bauen({}, {})
    with pytest.raises(RouterError, match="Unbekannte Aufgabe"):
        router.chain("gibtesnicht")


def test_aufgabenvorgaben_landen_in_der_anfrage():
    a = Attrappe("a")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a",), effort="low", max_tokens=512)},
        {"a": a},
    )
    router.complete("classify", Request.single("hallo"))
    assert a.letzte_anfrage.effort == "low"
    assert a.letzte_anfrage.max_tokens == 512


def test_anfrage_schlaegt_die_aufgabenvorgabe():
    a = Attrappe("a")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a",), effort="low")}, {"a": a}
    )
    router.complete("classify", Request.single("hallo", effort="max"))
    assert a.letzte_anfrage.effort == "max"


def test_die_schnittstelle_kennt_keine_werkzeuge():
    """Prinzip 2.2 als Bauform: was es nicht gibt, kann nicht benutzt werden."""
    felder = Request.__dataclass_fields__
    assert not {"tools", "functions", "tool_choice"} & set(felder)
