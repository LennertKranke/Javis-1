"""Die Mail-Faehigkeit: liest den Posteingang und ordnet ihn ein.

Sie sendet nichts. In dieser Phase gibt es keinen Sendepfad im Code, und der
Gmail-Client laesst den Endpunkt gar nicht erst zu.

Die feine Stelle steckt in `decide`. Das Modell nennt eine Kategorie aus einer
geschlossenen Aufzaehlung -- mehr kann es nicht, das Schema laesst nichts
anderes zu. Welches Label daraus wird, rechnet danach `LabelMap` aus. Das
Modell waehlt also eine Eigenschaft, nie ein Ziel; das Ziel entsteht in
deterministischem Code aus dieser Eigenschaft und der Gmail-Kennung der
Nachricht. Genau so ist Prinzip 2.1 gemeint.
"""

from __future__ import annotations

from typing import Any

from jarvis.core.config import Config, ConfigError
from jarvis.core.sanitize import sanitize
from jarvis.llm.router import Router
from jarvis.skills.base import Decision, Event, Result, Skill, register_skill
from jarvis.skills.mail.classify import build_schema, classify
from jarvis.skills.mail.gmail import GmailClient, GmailError
from jarvis.skills.mail.labels import LabelMap
from jarvis.skills.mail.message import MailMessage, parse_message
from jarvis.skills.mail.prefilter import prefilter
from jarvis.skills.mail.store import MailStore

__all__ = ["MailOptions", "MailSkill"]

DEFAULTS: dict[str, Any] = {
    "query": "is:unread in:inbox",
    "max_per_run": 25,
    "label_prefix": "JARVIS",
    "task": "classify",
    "client_secret": "gmail_client_secret",
    "token_secret": "gmail_token",
}

DEFAULT_CATEGORIES = [
    "rechnung",
    "termin",
    "anfrage",
    "newsletter",
    "werbung",
    "benachrichtigung",
    "persoenlich",
    "sonstiges",
]


class MailOptions:
    """Prueft den Abschnitt [skills.mail] selbst -- der Kern kennt ihn nicht."""

    def __init__(self, roh: dict[str, Any], *, known_tasks: set[str] | None = None) -> None:
        erlaubt = set(DEFAULTS) | {"categories"}
        unbekannt = sorted(set(roh) - erlaubt)
        if unbekannt:
            raise ConfigError(f"skills.mail: unbekannte Schluessel {', '.join(unbekannt)}")

        self.query = str(roh.get("query", DEFAULTS["query"]))
        if not self.query.strip():
            raise ConfigError("skills.mail.query: darf nicht leer sein")

        max_per_run = roh.get("max_per_run", DEFAULTS["max_per_run"])
        if isinstance(max_per_run, bool) or not isinstance(max_per_run, int):
            raise ConfigError("skills.mail.max_per_run: erwartet eine ganze Zahl")
        if not 1 <= max_per_run <= 500:
            raise ConfigError("skills.mail.max_per_run: muss zwischen 1 und 500 liegen")
        self.max_per_run = max_per_run

        self.label_prefix = str(roh.get("label_prefix", DEFAULTS["label_prefix"])).strip("/")
        if not self.label_prefix:
            raise ConfigError("skills.mail.label_prefix: darf nicht leer sein")

        self.task = str(roh.get("task", DEFAULTS["task"]))
        if known_tasks is not None and self.task not in known_tasks:
            bekannt = ", ".join(sorted(known_tasks)) or "keine"
            raise ConfigError(
                f"skills.mail.task: {self.task!r} steht nicht in [llm.tasks] (bekannt: {bekannt})"
            )

        categories = roh.get("categories", DEFAULT_CATEGORIES)
        if not isinstance(categories, list) or not categories:
            raise ConfigError("skills.mail.categories: erwartet eine nicht leere Liste")
        if not all(isinstance(c, str) and c.strip() for c in categories):
            raise ConfigError("skills.mail.categories: erwartet nicht leere Zeichenketten")
        if len(set(categories)) != len(categories):
            raise ConfigError("skills.mail.categories: enthaelt Doppelungen")
        self.categories = [c.strip() for c in categories]

        self.client_secret = str(roh.get("client_secret", DEFAULTS["client_secret"]))
        self.token_secret = str(roh.get("token_secret", DEFAULTS["token_secret"]))


@register_skill
class MailSkill(Skill):
    name = "mail"
    autonomy_level = 0  # Einordnen erreicht niemanden, Stufe 0 genuegt
    requires_outbound = False

    def __init__(
        self,
        *,
        options: MailOptions,
        client: GmailClient,
        router: Router,
        store: MailStore,
        sanitize_max_chars: int = 20000,
    ) -> None:
        self._options = options
        self._client = client
        self._router = router
        self._store = store
        self._max_chars = sanitize_max_chars
        self._labels = LabelMap(client, options.label_prefix)
        self._schema = build_schema(options.categories)
        self._own_address: str | None = None

    @classmethod
    def from_config(
        cls, config: Config, *, client: GmailClient, router: Router, store: MailStore
    ) -> MailSkill:
        options = MailOptions(config.skill_options("mail"), known_tasks=set(config.llm.tasks))
        return cls(
            options=options,
            client=client,
            router=router,
            store=store,
            sanitize_max_chars=config.sanitize_max_chars,
        )

    @property
    def client(self) -> GmailClient:
        return self._client

    @property
    def options(self) -> MailOptions:
        return self._options

    @property
    def labels(self) -> LabelMap:
        return self._labels

    # ------------------------------------------------------------------ #

    def poll(self) -> list[Event]:
        ids = self._client.list_message_ids(self._options.query, self._options.max_per_run)
        bekannt = self._store.seen(ids)
        offen = [mid for mid in ids if mid not in bekannt]

        events: list[Event] = []
        for message_id in offen:
            message = parse_message(self._client.get_message(message_id))
            # Betreff und Text zusammen -- beides bestimmt der Absender.
            content = sanitize(message.untrusted_text, max_chars=self._max_chars)
            events.append(
                Event(
                    skill=self.name,
                    key=message.message_id,
                    summary=self._summary(message, content.text),
                    payload=message,
                    content=content,
                )
            )
        return events

    @staticmethod
    def _summary(message: MailMessage, sauberer_text: str) -> str:
        absender = message.sender.address if message.sender else "unbekannt"
        betreff = sauberer_text.removeprefix("Betreff:").strip().splitlines()
        kopf = betreff[0][:70] if betreff else "(ohne Betreff)"
        return f"{absender} -- {kopf}"

    def decide(self, event: Event) -> Decision:
        message: MailMessage = event.payload

        treffer = prefilter(
            message,
            categories=self._options.categories,
            own_addresses=[self._address()] if self._address() else [],
            own_label_ids=self._labels.own_label_ids(),
        )

        if treffer is not None and treffer.action == "skip":
            return Decision(
                skill=self.name,
                event_key=event.key,
                action="skip",
                reason=treffer.reason,
                decided_by="prefilter",
                targets={"message_id": message.message_id},
            )

        if treffer is not None and treffer.category:
            fields: dict[str, Any] = {"kategorie": treffer.category}
            decided_by, reason, model = "prefilter", treffer.reason, None
        else:
            if event.content is None:
                raise ValueError("Ereignis ohne normalisierten Inhalt")
            fields, model = classify(
                event.content,
                router=self._router,
                task=self._options.task,
                schema=self._schema,
            )
            decided_by = "model"
            reason = str(fields.get("begruendung", ""))[:200]

        kategorie = str(fields["kategorie"])
        return Decision(
            skill=self.name,
            event_key=event.key,
            action="label",
            reason=reason,
            decided_by=decided_by,
            fields=fields,
            # Das Ziel entsteht hier, aus der Gmail-Kennung und der Zuordnung
            # Kategorie -> Label. Nicht aus der Modellantwort.
            targets={
                "message_id": message.message_id,
                "label_name": self._labels.label_name(kategorie),
                "label_id": self._labels.lookup(kategorie),
                "category": kategorie,
            },
            model=model,
        )

    def act(self, decision: Decision) -> Result:
        if decision.action == "skip":
            return Result(
                skill=self.name,
                event_key=decision.event_key,
                performed=False,
                detail={"reason": decision.reason},
            )

        message_id = str(decision.targets["message_id"])
        kategorie = str(decision.targets["category"])
        try:
            label_id = decision.targets.get("label_id") or self._labels.ensure_one(kategorie)
            self._client.modify_labels(message_id, add=[str(label_id)])
        except GmailError as exc:
            return Result(
                skill=self.name,
                event_key=decision.event_key,
                performed=False,
                detail={"label": decision.targets.get("label_name")},
                error=str(exc),
            )
        return Result(
            skill=self.name,
            event_key=decision.event_key,
            performed=True,
            detail={"label": decision.targets.get("label_name")},
        )

    def after(
        self, event: Event, decision: Decision, disposition: str, result: Result | None
    ) -> None:
        message: MailMessage = event.payload
        self._store.remember(
            message_id=decision.event_key,
            thread_id=getattr(message, "thread_id", ""),
            category=decision.targets.get("category"),
            decided_by=decision.decided_by,
            labelled=bool(result and result.performed),
            # Phase 3 liest das: nur was hier vermerkt ist, bekommt spaeter
            # ueberhaupt einen Antwortentwurf.
            needs_reply=bool(decision.fields.get("antwort_noetig")),
        )

    # ------------------------------------------------------------------ #

    def _address(self) -> str | None:
        if self._own_address is None:
            try:
                self._own_address = self._client.address()
            except GmailError:
                self._own_address = ""
        return self._own_address or None
