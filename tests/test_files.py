"""Dateirechte unter `~/.jarvis`.

Der Befund, der diese Datei ausgeloest hat: Basisverzeichnis und Datenbank
entstanden mit den Standardrechten des Systems -- 0755 und 0644 bei der
ueblichen umask 022. In `state.db` stehen Entwurfstexte samt Empfaenger,
Betreffzeilen und das Gedaechtnis; auf einem Mac mit mehreren Konten konnte das
jeder mitlesen.

Die Tests hier pruefen deshalb nicht, dass `chmod` aufgerufen *wird*, sondern
was am Ende auf der Platte steht. Und sie setzen die Rechte vorher absichtlich
auf offen, damit auch die Reparatur einer aelteren Ablage abgedeckt ist -- ein
Test, der nur den Neuanlagefall prueft, uebersieht genau die Installationen,
die schon Daten enthalten.
"""

from __future__ import annotations

import os
import stat

import pytest

from jarvis.core.config import Config, Paths
from jarvis.core.db import connect, migrate
from jarvis.core.files import (
    DIR_MODE,
    FILE_MODE,
    ist_geschuetzt,
    secure_db,
    secure_dir,
    secure_file,
)
from jarvis.core.log import configure

# Unix-Rechte gibt es nur dort, wo das Dateisystem sie kennt.
pytestmark = pytest.mark.skipif(os.name != "posix", reason="braucht Unix-Rechte")


def modus(pfad) -> int:
    return stat.S_IMODE(pfad.stat().st_mode)


def offen_fuer_andere(pfad) -> bool:
    return bool(modus(pfad) & (stat.S_IRWXG | stat.S_IRWXO))


# --- die Bausteine ---------------------------------------------------------- #


def test_neues_verzeichnis_entsteht_geschlossen(tmp_path):
    ziel = secure_dir(tmp_path / "neu")
    assert modus(ziel) == DIR_MODE


def test_vorhandenes_offenes_verzeichnis_wird_nachgezogen(tmp_path):
    """Der Fall, auf den es ankommt: eine Ablage von vor dem Fix."""
    ziel = tmp_path / "alt"
    ziel.mkdir(mode=0o755)
    os.chmod(ziel, 0o755)
    assert offen_fuer_andere(ziel)

    secure_dir(ziel)
    assert modus(ziel) == DIR_MODE


def test_neue_datei_wird_geschlossen(tmp_path):
    datei = tmp_path / "x.txt"
    datei.write_text("inhalt", encoding="utf-8")
    os.chmod(datei, 0o644)

    secure_file(datei)
    assert modus(datei) == FILE_MODE


def test_fehlende_datei_ist_kein_fehler(tmp_path):
    secure_file(tmp_path / "gibtsnicht")  # darf nicht werfen


def test_umask_kann_die_rechte_nicht_aufweichen(tmp_path):
    """`mkdir(mode=...)` wird von der umask beschnitten, `chmod` nicht."""
    vorher = os.umask(0o077)
    try:
        os.umask(0o000)  # denkbar schlechteste Einstellung
        ziel = secure_dir(tmp_path / "trotzdem")
        datei = ziel / "d"
        datei.write_text("x", encoding="utf-8")
        secure_file(datei)
        assert modus(ziel) == DIR_MODE
        assert modus(datei) == FILE_MODE
    finally:
        os.umask(vorher)


def test_ist_geschuetzt_erkennt_offene_rechte(tmp_path):
    ziel = tmp_path / "p"
    ziel.mkdir()
    os.chmod(ziel, 0o755)
    assert not ist_geschuetzt(ziel)
    os.chmod(ziel, 0o700)
    assert ist_geschuetzt(ziel)


def test_ist_geschuetzt_akzeptiert_engere_rechte(tmp_path):
    """0500 ist enger als verlangt und keine Abweichung."""
    ziel = tmp_path / "eng"
    ziel.mkdir()
    os.chmod(ziel, 0o500)
    assert ist_geschuetzt(ziel)


# --- die Stellen, die es benutzen ------------------------------------------- #


def test_basis_und_logverzeichnis_sind_geschlossen(tmp_path):
    paths = Paths(home=tmp_path / "jarvis")
    paths.ensure()
    assert modus(paths.home) == DIR_MODE
    assert modus(paths.log_dir) == DIR_MODE


def test_ensure_repariert_eine_offene_ablage(tmp_path):
    heim = tmp_path / "jarvis"
    (heim / "logs").mkdir(parents=True)
    os.chmod(heim, 0o755)
    os.chmod(heim / "logs", 0o755)

    Paths(home=heim).ensure()
    assert not offen_fuer_andere(heim)
    assert not offen_fuer_andere(heim / "logs")


def test_die_datenbank_ist_nicht_weltlesbar(tmp_path):
    """Hier stehen Entwurfstexte, Empfaenger und Betreffzeilen."""
    ziel = tmp_path / "jarvis" / "state.db"
    conn = connect(ziel)
    migrate(conn)
    conn.close()
    assert modus(ziel) == FILE_MODE
    assert not offen_fuer_andere(ziel.parent)


def test_auch_die_wal_dateien_sind_geschlossen(tmp_path):
    """Die WAL-Begleitdateien enthalten dieselben Daten wie die Datenbank."""
    ziel = tmp_path / "state.db"
    conn = connect(ziel)
    migrate(conn)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
    conn.execute("COMMIT")

    begleiter = [p for p in tmp_path.iterdir() if p.name.startswith("state.db-")]
    assert begleiter, "WAL-Modus hat keine Begleitdateien angelegt"
    secure_db(ziel)
    for pfad in begleiter:
        assert not offen_fuer_andere(pfad), f"{pfad.name} ist offen"
    conn.close()


def test_ein_erneuter_verbindungsaufbau_repariert_die_rechte(tmp_path):
    """Eine Datenbank von vor dem Fix wird beim naechsten Start geschlossen."""
    ziel = tmp_path / "state.db"
    connect(ziel).close()
    os.chmod(ziel, 0o644)
    assert offen_fuer_andere(ziel)

    connect(ziel).close()
    assert not offen_fuer_andere(ziel)


def test_die_logdatei_ist_nicht_weltlesbar(tmp_path):
    log_dir = tmp_path / "logs"
    logger = configure(log_dir, level="INFO")
    logger.info("Probe", extra={"skill": "test"})
    for handler in logger.handlers:
        handler.flush()

    datei = log_dir / "jarvis.jsonl"
    assert datei.exists()
    assert modus(datei) == FILE_MODE
    assert modus(log_dir) == DIR_MODE


def test_auch_eine_rotierte_logdatei_bleibt_geschlossen(tmp_path):
    """Ein einmaliges chmod haette nur die erste Datei getroffen."""
    log_dir = tmp_path / "logs"
    logger = configure(log_dir, level="INFO")
    logger.info("vorher")
    handler = next(h for h in logger.handlers if hasattr(h, "baseFilename"))

    handler.doRollover()
    logger.info("nachher")
    handler.flush()

    for pfad in log_dir.iterdir():
        assert not offen_fuer_andere(pfad), f"{pfad.name} ist nach der Rotation offen"


def test_der_stoppschalter_verraet_den_grund_nicht_weiter(tmp_path):
    """Der Grund kann nennen, woran gerade gearbeitet wird."""
    paths = Paths(home=tmp_path / "jarvis")
    paths.ensure()
    config = Config.load(home=paths.home)
    config.stop_switch.engage("Vertragsverhandlung laeuft", actor="test")

    assert config.stop_switch.engaged()
    assert modus(paths.stop_file) == FILE_MODE


def test_die_konfiguration_wird_bei_jedem_laden_nachgezogen(tmp_path):
    """`init` laeuft nur einmal -- die Reparatur muss woanders haengen.

    Beim Verdrahten des Statusberichts fiel auf, dass `config.toml` nur beim
    Anlegen abgesichert wurde. Eine Ablage von vor dieser Aenderung waere damit
    dauerhaft offen geblieben.
    """
    paths = Paths(home=tmp_path / "jarvis")
    paths.ensure()
    paths.config_file.write_text("dry_run = true\n", encoding="utf-8")
    os.chmod(paths.config_file, 0o644)
    assert offen_fuer_andere(paths.config_file)

    Config.load(home=paths.home)
    assert not offen_fuer_andere(paths.config_file)


def test_status_meldet_offene_rechte(tmp_path, capsys):
    """Was sich nicht reparieren laesst, soll wenigstens auffallen.

    Ein `chmod` kann scheitern -- fremder Eigentuemer, Netzlaufwerk. Dann darf
    die Abweichung nicht stillschweigend gelten.
    """
    from jarvis.interfaces.cli import main

    paths = Paths(home=tmp_path / "jarvis")
    paths.ensure()
    paths.config_file.write_text("dry_run = true\n", encoding="utf-8")
    os.chmod(paths.home, 0o755)  # nach dem Anlegen aufgeweicht

    code = main(["--home", str(paths.home), "status", "--ohne-anbieter"])
    ausgabe = capsys.readouterr().out

    assert "OFFEN" in ausgabe
    assert code == 1


def test_eine_leere_ablage_ist_keine_luecke(tmp_path, capsys):
    """Vor `jarvis init` gibt es nichts, was auslaufen koennte.

    Der erste Entwurf der Pruefung meldete hier "OFFEN" und gab 1 zurueck --
    ein Fehlalarm auf einem leeren Verzeichnis, und er brach einen
    bestehenden Test. Aufgefallen ist das nur durch dessen Fehlschlag.
    """
    from jarvis.interfaces.cli import main

    heim = tmp_path / "leer"
    heim.mkdir(mode=0o755)
    os.chmod(heim, 0o755)

    code = main(["--home", str(heim), "status", "--ohne-anbieter"])
    ausgabe = capsys.readouterr().out

    assert "OFFEN" not in ausgabe
    assert code == 0


# --- N-1 bis N-3: die Wege, die die Regel umgingen ------------------------- #


def test_der_web_token_legt_das_verzeichnis_geschlossen_an(tmp_path):
    """N-1: die Tokendatei war 0600, das Verzeichnis darum nicht.

    Wer den Token nicht lesen kann, soll auch nicht sehen, was sonst dort
    liegt. Ueber die Kommandozeile war der Weg nicht erreichbar -- `jarvis web`
    bricht ohne Datenbank ab --, auf Bibliotheksebene schon.
    """
    from jarvis.interfaces.web.security import TOKEN_FILE, load_or_create_token

    heim = tmp_path / "jarvis"
    load_or_create_token(heim)

    assert modus(heim) == DIR_MODE
    assert modus(heim / TOKEN_FILE) == FILE_MODE


def test_die_sperrdatei_des_daemons_ist_geschlossen(tmp_path):
    """N-2: entstand mit 0644, weil `open("a+")` die Standardrechte nimmt.

    Der Inhalt ist harmlos -- eine PID und ein Zeitstempel. Die Regel gilt
    trotzdem: die naechste Datei an dieser Stelle ist vielleicht nicht harmlos.
    """
    from jarvis.daemon import DaemonLock

    heim = tmp_path / "jarvis"
    sperre = DaemonLock(heim / "daemon.lock")
    sperre.acquire()
    try:
        assert modus(heim) == DIR_MODE
        assert modus(heim / "daemon.lock") == FILE_MODE
    finally:
        sperre.release()


def test_offene_pfade_findet_was_eine_liste_uebersieht(tmp_path):
    """N-3: der Durchlauf ersetzt die von Hand gepflegte Liste.

    Genau die zwei Dateien, die in der alten Aufzaehlung fehlten, waren die
    offenen. Hier steht der Fall nachgestellt: etwas Unbekanntes, tief im
    Baum, das keine Liste kennen wuerde.
    """
    from jarvis.core.files import offene_pfade

    heim = secure_dir(tmp_path / "jarvis")
    tief = secure_dir(heim / "spaeter" / "noch-tiefer")
    fremd = tief / "unbekannt.dat"
    fremd.write_text("x", encoding="utf-8")
    os.chmod(fremd, 0o644)

    gefunden = offene_pfade(heim)
    assert fremd in gefunden
    assert len(gefunden) == 1, f"unerwartet auch: {gefunden}"


def test_offene_pfade_meldet_eine_geschlossene_ablage_als_leer(tmp_path):
    heim = secure_dir(tmp_path / "jarvis")
    secure_dir(heim / "logs")
    (heim / "state.db").write_text("x", encoding="utf-8")
    secure_file(heim / "state.db")

    from jarvis.core.files import offene_pfade

    assert offene_pfade(heim) == []


def test_offene_pfade_meldet_auch_die_wurzel(tmp_path):
    from jarvis.core.files import offene_pfade

    heim = tmp_path / "jarvis"
    heim.mkdir(mode=0o755)
    os.chmod(heim, 0o755)
    assert offene_pfade(heim) == [heim]


def test_offene_pfade_folgt_keiner_verknuepfung(tmp_path):
    """Sonst haengt das Ergebnis daran, wohin jemand die Verknuepfung legt.

    Und ein Ring liesse den Durchlauf nie enden.
    """
    from jarvis.core.files import offene_pfade

    aussen = tmp_path / "aussen"
    aussen.mkdir(mode=0o755)
    os.chmod(aussen, 0o755)

    heim = secure_dir(tmp_path / "jarvis")
    (heim / "zeigt-nach-aussen").symlink_to(aussen, target_is_directory=True)

    assert offene_pfade(heim) == []


def test_offene_pfade_bei_fehlendem_verzeichnis(tmp_path):
    from jarvis.core.files import offene_pfade

    assert offene_pfade(tmp_path / "gibtsnicht") == []


def test_zwischenverzeichnisse_entstehen_ebenfalls_geschlossen(tmp_path):
    """`mkdir(parents=True, mode=...)` setzt den Modus nur auf die letzte Stufe.

    Gefunden beim Nachziehen von N-3: ein mehrstufiger Pfad hinterliess offene
    Zwischenstufen. Bei `JARVIS_HOME=/a/b/c` waeren das `/a` und `/a/b`.
    """
    ziel = secure_dir(tmp_path / "eins" / "zwei" / "drei")

    for stufe in (ziel, ziel.parent, ziel.parent.parent):
        assert modus(stufe) == DIR_MODE, f"{stufe} ist offen"


def test_ein_vorhandenes_fremdes_verzeichnis_wird_nicht_angetastet(tmp_path):
    """Die Gegenprobe. `~` oder `/tmp` umzustellen waere ein Uebergriff.

    Nachgezogen wird nur, was `secure_dir` selbst angelegt hat.
    """
    fremd = tmp_path / "gehoert-jemand-anderem"
    fremd.mkdir(mode=0o755)
    os.chmod(fremd, 0o755)

    secure_dir(fremd / "unseres")

    assert modus(fremd) == 0o755, "fremdes Verzeichnis wurde veraendert"
    assert modus(fremd / "unseres") == DIR_MODE
