"""Router: Rueckfallkette, Vertraulichkeitssperre und Ausfallpause."""

from __future__ import annotations

import pytest

from jarvis.core.config import LLMConfig, ProviderConfig, TaskRoute
from jarvis.llm.provider import (
    Provider,
    ProviderError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
    Response,
)
from jarvis.llm.providers.static import StaticProvider
from jarvis.llm.router import (
    BEREIT,
    PAUSIERT,
    UNBEKANNT,
    ConfidentialityError,
    Router,
    RouterError,
)


class Uhr:
    """Eine Uhr, die nur vorwaerts geht, wenn der Test sie stellt.

    KI-8 hat gezeigt, wohin echte Zeit in Tests fuehrt. Eine Pause von 60
    Sekunden laesst sich nicht abwarten, und `sleep` machte den Lauf langsam
    und die Aussage schwach.
    """

    def __init__(self) -> None:
        self.jetzt = 1000.0

    def __call__(self) -> float:
        return self.jetzt

    def weiter(self, sekunden: float) -> None:
        self.jetzt += sekunden


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


def router_bauen(tasks, providers, *, cooldown_seconds=60, uhr=None):
    llm = LLMConfig(
        providers={p.name: p.config for p in providers.values()},
        tasks=tasks,
        cooldown_seconds=cooldown_seconds,
    )
    return Router(llm, providers, uhr=uhr)


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


# --------------------------------------------------------------------------- #
# Ausfallpause
#
# Ohne sie wartet jede einzelne Anfrage einer Kette erst das Zeitlimit des
# ausgefallenen Anbieters ab. Mit ihr wird er uebersprungen -- aber nur
# uebersprungen: eine Pause macht keinen Anbieter zulaessig, den die
# Vertraulichkeitssperre ausschliesst.
# --------------------------------------------------------------------------- #


def test_ausgefallener_anbieter_wird_beim_zweiten_mal_uebersprungen():
    a = Attrappe("a", fehler=ProviderUnavailable("nicht erreichbar"))
    b = Attrappe("b", antwort="von b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        uhr=uhr,
    )
    router.complete("classify", Request.single("eins"))
    assert a.aufrufe == 1

    ergebnis = router.complete("classify", Request.single("zwei"))
    assert a.aufrufe == 1  # nicht noch einmal gefragt
    assert ergebnis.response.text == "von b"
    assert b.aufrufe == 2


def test_uebersprungener_versuch_bleibt_vom_gescheiterten_unterscheidbar():
    a = Attrappe("a", fehler=ProviderTimeout("zu langsam"))
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        uhr=uhr,
    )
    erster = router.complete("classify", Request.single("eins"))
    zweiter = router.complete("classify", Request.single("zwei"))

    versuch_gescheitert = erster.attempts[0]
    versuch_uebersprungen = zweiter.attempts[0]
    assert versuch_gescheitert.uebersprungen is False
    assert versuch_uebersprungen.uebersprungen is True
    # Beide sind kein Erfolg -- eine Antwort kam in keinem Fall.
    assert versuch_gescheitert.ok is False
    assert versuch_uebersprungen.ok is False
    assert "pausiert nach ProviderTimeout" in versuch_uebersprungen.error


def test_nach_ablauf_der_pause_wird_wieder_versucht():
    a = Attrappe("a", fehler=ProviderUnavailable("nicht erreichbar"))
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        cooldown_seconds=60,
        uhr=uhr,
    )
    router.complete("classify", Request.single("eins"))
    uhr.weiter(59)
    router.complete("classify", Request.single("zwei"))
    assert a.aufrufe == 1  # Pause laeuft noch

    uhr.weiter(2)
    a.fehler = None  # der Anbieter ist wieder da
    ergebnis = router.complete("classify", Request.single("drei"))
    assert a.aufrufe == 2
    assert ergebnis.response.provider == "a"


def test_ein_erfolg_loescht_die_pause():
    a = Attrappe("a", fehler=ProviderUnavailable("weg"))
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        uhr=uhr,
    )
    router.complete("classify", Request.single("eins"))
    assert router.gesundheit.zustand("a").zustand == PAUSIERT

    uhr.weiter(61)
    a.fehler = None
    router.complete("classify", Request.single("zwei"))
    assert router.gesundheit.zustand("a").zustand == BEREIT


@pytest.mark.parametrize(
    "fehler",
    [ProviderRefused("verweigert"), ProviderError("leere Antwort")],
    ids=["verweigert", "unbrauchbar"],
)
def test_aussagen_ueber_die_anfrage_pausieren_den_anbieter_nicht(fehler):
    """Eine Verweigerung sagt etwas ueber diese Anfrage, nicht ueber den Anbieter."""
    a = Attrappe("a", fehler=fehler)
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        uhr=uhr,
    )
    router.complete("classify", Request.single("eins"))
    router.complete("classify", Request.single("zwei"))
    assert a.aufrufe == 2
    assert router.gesundheit.zustand("a").zustand == UNBEKANNT


def test_pause_null_verhaelt_sich_wie_ohne_pause():
    a = Attrappe("a", fehler=ProviderUnavailable("weg"))
    b = Attrappe("b")
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        cooldown_seconds=0,
    )
    router.complete("classify", Request.single("eins"))
    router.complete("classify", Request.single("zwei"))
    assert a.aufrufe == 2


def test_alle_anbieter_pausiert_meldet_den_fehler_mit_grund():
    a = Attrappe("a", fehler=ProviderUnavailable("nicht erreichbar"))
    b = Attrappe("b", fehler=ProviderTimeout("zu langsam"))
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a", "b"))},
        {"a": a, "b": b},
        uhr=uhr,
    )
    with pytest.raises(RouterError):
        router.complete("classify", Request.single("eins"))

    with pytest.raises(RouterError) as exc:
        router.complete("classify", Request.single("zwei"))
    assert "pausiert nach ProviderUnavailable" in str(exc.value)
    assert "pausiert nach ProviderTimeout" in str(exc.value)
    assert a.aufrufe == 1 and b.aufrufe == 1  # kein Endlos-Retry


def test_eine_pause_oeffnet_keinen_weg_nach_draussen():
    """Der wichtigste Test des Inkrements.

    Pausiert der einzige lokale Anbieter, scheitert die vertrauliche Aufgabe.
    Sie faellt nicht auf den externen zurueck, der in derselben Konfiguration
    steht -- die Kette entsteht vor jeder Pause, und Abschnitt 5.2 laesst ihn
    gar nicht erst hinein.
    """
    lokal = Attrappe("lokal", local=True, fehler=ProviderUnavailable("Ollama laeuft nicht"))
    wolke = Attrappe("wolke", local=False)
    uhr = Uhr()
    router = router_bauen(
        {
            "personal": TaskRoute(name="personal", providers=("lokal",), confidential=True),
            "classify": TaskRoute(name="classify", providers=("lokal", "wolke")),
        },
        {"lokal": lokal, "wolke": wolke},
        uhr=uhr,
    )
    with pytest.raises(RouterError):
        router.complete("personal", Request.single("privat"))
    with pytest.raises(RouterError) as exc:
        router.complete("personal", Request.single("privat"))

    assert "pausiert" in str(exc.value)
    assert wolke.aufrufe == 0  # nichts Vertrauliches hat den Rechner verlassen


def test_die_pause_gilt_ueber_aufgaben_hinweg():
    """Der Anbieter ist ausgefallen, nicht die Aufgabe."""
    a = Attrappe("a", fehler=ProviderUnavailable("weg"))
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {
            "classify": TaskRoute(name="classify", providers=("a", "b")),
            "briefing": TaskRoute(name="briefing", providers=("a", "b")),
        },
        {"a": a, "b": b},
        uhr=uhr,
    )
    router.complete("classify", Request.single("eins"))
    router.complete("briefing", Request.single("zwei"))
    assert a.aufrufe == 1


# --------------------------------------------------------------------------- #
# Gesundheitsstand
# --------------------------------------------------------------------------- #


def test_die_drei_zustaende_sind_unterscheidbar():
    a = Attrappe("a")
    b = Attrappe("b", fehler=ProviderUnavailable("weg"))
    uhr = Uhr()
    router = router_bauen(
        {
            "classify": TaskRoute(name="classify", providers=("a",)),
            "briefing": TaskRoute(name="briefing", providers=("b", "a")),
        },
        {"a": a, "b": b},
        uhr=uhr,
    )
    # Vor dem ersten Aufruf weiss der Router nichts, und nichts ist kein Nein.
    assert router.gesundheit.zustand("a").zustand == UNBEKANNT
    assert router.gesundheit.zustand("a").nutzbar is True

    router.complete("classify", Request.single("eins"))
    assert router.gesundheit.zustand("a").zustand == BEREIT
    assert router.gesundheit.zustand("a").nutzbar is True

    router.complete("briefing", Request.single("zwei"))
    zustand = router.gesundheit.zustand("b")
    assert zustand.zustand == PAUSIERT
    assert zustand.nutzbar is False
    assert zustand.grund == "ProviderUnavailable"
    assert zustand.rest_sekunden == 60


def test_nach_ablauf_ist_der_zustand_unbekannt_nicht_bereit():
    """Ein abgelaufener Ausfall ist kein Nachweis, dass es wieder geht."""
    a = Attrappe("a")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a",))}, {"a": a}, uhr=uhr
    )
    router.complete("classify", Request.single("eins"))
    assert router.gesundheit.zustand("a").zustand == BEREIT

    a.fehler = ProviderUnavailable("weg")
    with pytest.raises(RouterError):
        router.complete("classify", Request.single("zwei"))
    uhr.weiter(61)
    assert router.gesundheit.zustand("a").zustand == UNBEKANNT


def test_die_uebersicht_nennt_nur_bekannte_anbieter():
    a = Attrappe("a")
    b = Attrappe("b")
    uhr = Uhr()
    router = router_bauen(
        {"classify": TaskRoute(name="classify", providers=("a",))}, {"a": a, "b": b}, uhr=uhr
    )
    assert router.gesundheit.uebersicht() == {}
    router.complete("classify", Request.single("eins"))
    assert set(router.gesundheit.uebersicht()) == {"a"}


def test_der_statische_anbieter_bleibt_der_trockenlaufpfad():
    """Abschnitt 8.3: der Weg ohne Netz und ohne Schluessel bleibt unberuehrt."""
    config = ProviderConfig(name="trocken", kind="static", model="static", local=True, reply="{}")
    trocken = StaticProvider(config)
    llm = LLMConfig(
        providers={"trocken": config},
        tasks={"classify": TaskRoute(name="classify", providers=("trocken",))},
    )
    router = Router(llm, {"trocken": trocken}, uhr=Uhr())
    for _ in range(3):
        assert router.complete("classify", Request.single("hallo")).response.text == "{}"
    assert router.gesundheit.zustand("trocken").zustand == BEREIT
