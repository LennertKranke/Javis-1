"""Ratenbegrenzung -- Prinzip 2.4."""

from __future__ import annotations

import pytest

from jarvis.core.config import ConfigError
from jarvis.core.ratelimit import RateLimiter
from tests.conftest import build_config


class Uhr:
    """Steuerbare Zeit. Rollende Fenster sind sonst nicht pruefbar."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.jetzt = start

    def __call__(self) -> float:
        return self.jetzt

    def weiter(self, sekunden: float) -> None:
        self.jetzt += sekunden


def limiter(conn, home, **kwargs):
    uhr = Uhr()
    config = build_config(home, **kwargs)
    return RateLimiter(conn, config.capabilities, clock=uhr), uhr


def test_bis_zur_grenze_erlaubt_danach_nicht(conn, home):
    lim, _ = limiter(conn, home, limits={"hour": 3})
    for _ in range(3):
        assert lim.acquire("mail").allowed
    verdict = lim.acquire("mail")
    assert not verdict.allowed
    assert "3/3" in (verdict.reason or "")


def test_fenster_rollt_und_gibt_wieder_frei(conn, home):
    lim, uhr = limiter(conn, home, limits={"hour": 2})
    assert lim.acquire("mail").allowed
    assert lim.acquire("mail").allowed
    assert not lim.acquire("mail").allowed

    uhr.weiter(3601)
    assert lim.acquire("mail").allowed


def test_fenster_ist_rollend_nicht_kalendarisch(conn, home):
    lim, uhr = limiter(conn, home, limits={"hour": 2})
    lim.acquire("mail")
    uhr.weiter(1800)  # halbe Stunde
    lim.acquire("mail")
    assert not lim.acquire("mail").allowed

    uhr.weiter(1801)  # der erste Eintrag faellt heraus, der zweite nicht
    assert lim.acquire("mail").allowed
    assert not lim.acquire("mail").allowed


def test_engstes_fenster_entscheidet(conn, home):
    lim, uhr = limiter(conn, home, limits={"minute": 2, "day": 10})
    assert lim.acquire("mail").allowed
    assert lim.acquire("mail").allowed
    verdict = lim.acquire("mail")
    assert not verdict.allowed
    assert verdict.blocking is not None
    assert verdict.blocking.window == "minute"

    uhr.weiter(61)
    assert lim.acquire("mail").allowed


def test_trockenlauf_verbraucht_nichts(conn, home):
    lim, _ = limiter(conn, home, limits={"hour": 2})
    for _ in range(5):
        verdict = lim.acquire("mail", dry_run=True)
        assert verdict.allowed
        assert not verdict.consumed
    assert lim.usage("mail")[0].used == 0


def test_trockenlauf_meldet_trotzdem_wenn_die_grenze_greifen_wuerde(conn, home):
    lim, _ = limiter(conn, home, limits={"hour": 1})
    lim.acquire("mail")
    verdict = lim.acquire("mail", dry_run=True)
    assert not verdict.allowed  # der Schattenbetrieb soll das sehen


def test_grenze_null_blockiert_alles(conn, home):
    lim, _ = limiter(conn, home, limits={"hour": 0})
    assert not lim.acquire("mail").allowed


def test_check_veraendert_nichts(conn, home):
    lim, _ = limiter(conn, home, limits={"hour": 2})
    for _ in range(10):
        assert lim.check("mail").allowed
    assert lim.usage("mail")[0].used == 0


def test_faehigkeit_ohne_ausgang_ist_unbegrenzt(conn, home):
    lim, _ = limiter(conn, home, outbound=False)
    for _ in range(50):
        verdict = lim.acquire("mail")
        assert verdict.allowed
        assert verdict.windows == ()


def test_unbekannte_faehigkeit_ist_ein_fehler(conn, home):
    lim, _ = limiter(conn, home)
    with pytest.raises(ConfigError):
        lim.acquire("gibtesnicht")


def test_zaehler_ueberlebt_einen_neustart(conn, home):
    """Ein Absturz darf kein Weg sein, die Begrenzung zurueckzusetzen."""
    uhr = Uhr()
    config = build_config(home, limits={"hour": 2})
    erst = RateLimiter(conn, config.capabilities, clock=uhr)
    erst.acquire("mail")
    erst.acquire("mail")

    # Neuer Limiter auf derselben Datenbank -- so als waere der Daemon neu.
    zweit = RateLimiter(conn, config.capabilities, clock=uhr)
    assert not zweit.acquire("mail").allowed


def test_prune_raeumt_nur_abgelaufene_eintraege(conn, home):
    lim, uhr = limiter(conn, home, limits={"hour": 5})
    lim.acquire("mail")
    uhr.weiter(4000)
    lim.acquire("mail")
    entfernt = lim.prune()
    assert entfernt == 1
    assert lim.usage("mail")[0].used == 1
