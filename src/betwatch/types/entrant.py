from __future__ import annotations

from datetime import datetime

import msgspec

from .common import Model, NamedPerson, Parent
from .enums import EntryState
from .page import Page


class EntrantRacing(Model):
    number: int = 0
    barrier: int | None = None
    weight_kg: float | None = None
    rider: NamedPerson | None = None
    trainer: NamedPerson | None = None
    form: str | None = None
    silk_url: str | None = None
    sex: str | None = None
    colour: str | None = None
    sire: Parent | None = None
    dam: Parent | None = None


class Entrant(Model):
    id: str
    event_id: str
    competitor_id: str
    name: str
    entry_state: EntryState
    scratched: bool = False
    vacant: bool = False
    racing: EntrantRacing = msgspec.field(default_factory=EntrantRacing)
    updated_at: datetime | None = None

    @property
    def number(self) -> int:
        return self.racing.number


class EntrantPage(Page[Entrant]):
    items: list[Entrant] = []
