"""Labels anlegen und zuordnen.

Alles entsteht unterhalb eines eigenen Oberlabels ("JARVIS/Rechnung"), damit
JARVIS nie ein bestehendes Label des Nutzers anfasst oder umdeutet. Die
Zuordnung Kategorie -> Label ist eine Rechenvorschrift im Code, kein Feld in
der Modellantwort: das Modell nennt eine Kategorie, welches Label daraus wird,
entscheidet diese Datei.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["LabelMap"]


class LabelMap:
    def __init__(self, client: object, prefix: str = "JARVIS") -> None:
        self._client = client
        self._prefix = prefix.strip("/") or "JARVIS"
        self._by_name: dict[str, str] = {}
        self._geladen = False

    def label_name(self, category: str) -> str:
        return f"{self._prefix}/{category.strip().capitalize()}"

    def _load(self) -> None:
        if self._geladen:
            return
        self._by_name = {
            str(label.get("name", "")): str(label.get("id", ""))
            for label in self._client.list_labels()  # type: ignore[attr-defined]
        }
        self._geladen = True

    def own_label_ids(self) -> set[str]:
        """Alle Label-IDs unterhalb des eigenen Oberlabels."""
        self._load()
        return {
            label_id
            for name, label_id in self._by_name.items()
            if name == self._prefix or name.startswith(f"{self._prefix}/")
        }

    def lookup(self, category: str) -> str | None:
        """Sucht die ID, ohne etwas anzulegen.

        Getrennt von `ensure_one`, weil im Trockenlauf kein Label entstehen
        darf: JARVIS soll eine Woche mitlaufen koennen, ohne dass sich im
        Postfach irgendetwas veraendert.
        """
        self._load()
        return self._by_name.get(self.label_name(category))

    def ensure_one(self, category: str) -> str:
        """Sucht die ID und legt das Label an, falls es fehlt."""
        vorhanden = self.lookup(category)
        if vorhanden:
            return vorhanden
        name = self.label_name(category)
        erzeugt = self._client.create_label(name)  # type: ignore[attr-defined]
        label_id = str(erzeugt.get("id", ""))
        self._by_name[name] = label_id
        return label_id

    def ensure(self, categories: Sequence[str]) -> dict[str, str]:
        """Legt alle fehlenden Labels an. Fuer `jarvis mail labels`."""
        return {category: self.ensure_one(category) for category in categories}
