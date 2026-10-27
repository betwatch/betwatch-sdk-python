from __future__ import annotations

from datetime import datetime

import msgspec

from .common import Model, NamedPerson, Parent
from .enums import DeductionKind, EntryState
from .page import Page


class Deduction(Model):
    """Late-scratching deduction, in cents.

    `official` is the home tote's figure and `unanimous` means every book
    agrees; both carry `win_cents`/`place_cents`. `range` means the books
    disagree and carries `win_min`/`win_max`/`place_min`/`place_max` instead.
    A component the source did not state is None, not zero.
    """

    kind: DeductionKind
    win_cents: int | None = None
    place_cents: int | None = None
    win_min: int | None = None
    win_max: int | None = None
    place_min: int | None = None
    place_max: int | None = None


class EntrantRacing(Model):
    number: int = 0
    barrier: int | None = None
    weight_kg: float | None = None
    rider: NamedPerson | None = None
    rider_claim_kg: float | None = None
    trainer: NamedPerson | None = None
    form: str | None = None
    emergency: bool | None = None
    blinkers: bool | None = None
    gear: str | None = None
    scratched_at: datetime | None = None
    deduction: Deduction | None = None
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
