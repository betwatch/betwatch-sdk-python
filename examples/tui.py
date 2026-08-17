"""Racing odds TUI: TTJ-ordered event list + bookmaker grid.

Not part of the installed package. Same pattern as the other examples:

    fnox exec -- uv run examples/tui.py
    fnox exec -- uv run examples/tui.py --sport harness --country au
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import cast

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import DescendantBlur
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from _tui_card import GridRow, RaceGrid, apply_event_list, apply_frame, build_grid
from _tui_format import (
    COUNTRIES,
    SPORT_MARK,
    SPORTS,
    date_bucket,
    event_title,
    format_clock,
    format_ttj,
    is_stale_finished,
    next_open,
    race_number,
    sort_events,
    status_label,
    status_style,
    track_name,
    utcnow,
)
from betwatch import APIKeyNotSetError, AsyncBetwatch, BetwatchError, ResyncRequired, Sport
from betwatch.types.event import Event
from betwatch.types.snapshot import EventSnapshot
from betwatch.types.stream import EventFrame, OddsFrame, StreamEvent, StreamFrame
from betwatch.types.venue import Venue

_PAGE = 50


def _list_window() -> tuple[str, str]:
    now = utcnow()
    start = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    end = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    return start, end


_HELP = """\
[b]Betwatch[/b]  —  racing odds, in the terminal.

[b]Races[/b]
  ↑ ↓ j k     move in the event list
  enter       open the highlighted race
  n           jump to the next race to jump
  /           filter tracks
  esc         clear filter / close help

[b]Card[/b]
  tab         switch between list and grid
  w / p       win / place
  r           reload the event list
  a           show or hide finished races

[b]Scope[/b]
  1 2 3 0     thoroughbred / harness / greyhound / all
  c           cycle country (AU / NZ / all)

  q           quit
"""


class EventsBatch(Message):
    def __init__(
        self,
        events: list[Event],
        *,
        cursor: str | None,
        replace: bool,
        generation: int,
    ) -> None:
        super().__init__()
        self.events = events
        self.cursor = cursor
        self.replace = replace
        self.generation = generation


class VenuesReady(Message):
    def __init__(self, venues: dict[str, Venue], generation: int) -> None:
        super().__init__()
        self.venues = venues
        self.generation = generation


class CardReady(Message):
    def __init__(self, card: EventSnapshot) -> None:
        super().__init__()
        self.card = card


class LiveFrame(Message):
    def __init__(self, frame: StreamFrame) -> None:
        super().__init__()
        self.frame = frame


class WatchFailed(Message):
    def __init__(self, detail: str) -> None:
        super().__init__()
        self.detail = detail


class NeedResync(Message):
    def __init__(self, event_id: str) -> None:
        super().__init__()
        self.event_id = event_id


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,question_mark", "dismiss", "Close", show=False)]

    def compose(self) -> ComposeResult:
        yield Static(_HELP, id="help-card")


class EventList(OptionList):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(id="events", compact=True)
        self.events: list[Event] = []
        self.venues: dict[str, Venue] = {}
        self.filter = ""
        self.hide_finished = True
        self.active_id: str | None = None

    def visible_events(self, now: datetime) -> list[Event]:
        needle = self.filter.casefold()
        out: list[Event] = []
        for event in sort_events(self.events):
            if self.hide_finished and is_stale_finished(event, now):
                continue
            title = event_title(event, self.venues)
            if needle and needle not in title.casefold() and needle not in event.name.casefold():
                continue
            out.append(event)
        return out

    def rebuild(
        self,
        now: datetime,
        *,
        preferred: str | None = None,
        keep_scroll: bool = False,
    ) -> None:
        keep = preferred or self.active_id
        if self.highlighted_option and self.highlighted_option.id:
            keep = keep or self.highlighted_option.id
        scroll = self.scroll_y
        visible = self.visible_events(now)
        options: list[Option | None] = []
        last_bucket = ""
        for event in visible:
            bucket = date_bucket(event.start_at, now)
            if bucket != last_bucket:
                if options:
                    options.append(None)
                options.append(Option(Text(bucket.upper(), style="bold #8b93a7"), disabled=True))
                last_bucket = bucket
            options.append(Option(self._prompt(event, now), id=event.id))
        self.set_options(options)
        if not visible:
            return
        target = keep if keep and any(event.id == keep for event in visible) else None
        if target is None and not keep_scroll:
            nxt = next_open(visible, now)
            target = nxt.id if nxt else visible[0].id
        if target:
            try:
                self.highlighted = self.get_option_index(target)
            except Exception:
                self.highlighted = 0
        if keep_scroll:
            self.scroll_y = scroll
        else:
            self.scroll_to_highlight()

    def tick(self, now: datetime) -> None:
        by_id = {event.id: event for event in self.events}
        for index, option in enumerate(self.options):
            if option.id and option.id in by_id:
                self.replace_option_prompt_at_index(index, self._prompt(by_id[option.id], now))

    def _prompt(self, event: Event, now: datetime) -> Text:
        mark = SPORT_MARK.get(event.sport, "?")
        number = race_number(event)
        race = f"R{number}" if number else "R-"
        track = track_name(event, self.venues)
        clock = format_clock(event.start_at)
        label = status_label(event, now)
        style = status_style(event, now)
        selected = event.id == self.active_id
        line = Text(no_wrap=True)
        line.append(f"{mark} ", style="#6b7385")
        line.append(f"{race:<3} ", style="bold #f4e8c1" if selected else "bold")
        line.append(f"{track:<14.14} ", style="#f4e8c1" if selected else "")
        line.append(f"{clock} ", style="#8b93a7")
        line.append(f"{label:>6}", style=style)
        return line


class RaceTable(DataTable[Text]):
    def __init__(self) -> None:
        super().__init__(id="grid", cursor_type="row", zebra_stripes=True, fixed_columns=2)

    def show_grid(self, grid: RaceGrid) -> None:
        highlighted = self.cursor_row
        self.clear(columns=True)
        for column in grid.columns:
            width = 4 if column.key == "num" else 20 if column.key == "runner" else 6
            self.add_column(column.label, key=column.key, width=width)
        for row in grid.rows:
            self.add_row(*self._cells(row), key=row.entrant_id)
        if grid.rows and 0 <= highlighted < len(grid.rows):
            self.move_cursor(row=highlighted)

    def _cells(self, row: GridRow) -> list[Text]:
        name_style = "strike dim" if row.scratched or row.vacant else "bold"
        cells = [
            Text(row.number, style="dim" if row.scratched else "bold #c9b27c", justify="right"),
            Text(row.name, style=name_style),
        ]
        for cell in row.cells:
            if cell.price is None:
                cells.append(Text("·", style="dim", justify="right"))
            elif cell.best:
                cells.append(Text(cell.text, style="bold #3dd68c", justify="right"))
            else:
                cells.append(Text(cell.text, style="#d7dde8", justify="right"))
        return cells


class BetwatchApp(App[None]):
    """TTJ-ordered event list + bookmaker grid, fed by public /v1."""

    TITLE = "Betwatch"
    AUTO_FOCUS = "#events"
    CSS = """
    Screen {
        background: #0b0e14;
        color: #d7dde8;
    }

    #chrome-row {
        height: auto;
        background: #10141c;
        border-bottom: tall #1e2633;
    }

    #chrome {
        height: auto;
        width: 1fr;
        padding: 0 1;
        color: #f4e8c1;
        text-style: bold;
        content-align: left middle;
    }

    #mkt-win, #mkt-place {
        min-width: 9;
        margin: 0 1 0 0;
        border: none;
    }

    #meta {
        height: auto;
        background: #0f141d;
        border-bottom: tall #1e2633;
        padding: 0 1;
        color: #c9b27c;
    }

    #body {
        height: 1fr;
    }

    #sidebar {
        width: 42;
        min-width: 36;
        background: #10141c;
        border-right: tall #1e2633;
    }

    #sidebar-head {
        height: auto;
        padding: 0 1;
        color: #8b93a7;
        text-style: bold;
    }

    #filter {
        display: none;
        height: 3;
        margin: 0 1 1 1;
        border: tall #2a3344;
        background: #0b0e14;
    }

    #filter.visible {
        display: block;
    }

    EventList {
        height: 1fr;
        padding: 0 0;
        background: #10141c;
        border: none;
    }

    EventList > .option-list--option {
        padding: 0 1;
        color: #d7dde8;
    }

    EventList > .option-list--option-highlighted {
        background: #243044;
        color: #f4e8c1;
        text-style: bold;
    }

    EventList > .option-list--option-disabled {
        color: #6b7385;
        text-style: bold;
        padding: 0 1;
        background: #0b0e14;
    }

    #main {
        width: 1fr;
        background: #0b0e14;
    }

    RaceTable {
        height: 1fr;
        background: #0b0e14;
    }

    RaceTable > .datatable--header {
        background: #141922;
        color: #c9b27c;
        text-style: bold;
    }

    RaceTable > .datatable--cursor {
        background: #1c2838;
    }

    RaceTable > .datatable--fixed {
        background: #10141c;
        color: #f4e8c1;
    }

    RaceTable > .datatable--odd-row {
        background: #0d1118;
    }

    #empty {
        height: 1fr;
        content-align: center middle;
        color: #8b93a7;
    }

    HelpScreen {
        align: center middle;
        background: #0b0e14 70%;
    }

    #help-card {
        width: 72;
        height: auto;
        padding: 1 2;
        background: #141922;
        border: tall #c9b27c;
        color: #d7dde8;
    }

    Footer {
        background: #10141c;
        color: #8b93a7;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", priority=True),
        Binding("n", "next_open", "Next", priority=True),
        Binding("r", "reload", "Reload", priority=True),
        Binding("w", "market_win", "Win", priority=True),
        Binding("p", "market_place", "Place", priority=True),
        Binding("slash", "filter", "Filter", priority=True),
        Binding("escape", "clear_filter", "Clear", show=False, priority=True),
        Binding("a", "toggle_finished", "Finished", priority=True),
        Binding("c", "cycle_country", "Country", priority=True),
        Binding("1", "sport_thoroughbred", "T", show=False, priority=True),
        Binding("2", "sport_harness", "H", show=False, priority=True),
        Binding("3", "sport_greyhound", "G", show=False, priority=True),
        Binding("0", "sport_all", "All", show=False, priority=True),
        Binding("tab", "focus_next", "Pane", show=False),
    ]

    sport: reactive[str | None] = reactive("thoroughbred")
    country: reactive[str | None] = reactive("au")
    market: reactive[str] = reactive("win")
    live: reactive[bool] = reactive(False)
    status_note: reactive[str] = reactive("loading")

    def __init__(
        self,
        *,
        client: AsyncBetwatch | None = None,
        sport: str | None = "thoroughbred",
        country: str | None = "au",
        event_id: str | None = None,
        market: str = "win",
        stream: bool = True,
    ) -> None:
        super().__init__()
        self._injected = client
        self._owns_client = client is None
        self.client: AsyncBetwatch | None = client
        self.sport = None if sport in {None, "all"} else sport
        self.country = None if country in {None, "all"} else country
        self.market = market
        self.stream_enabled = stream
        self.boot_event_id = event_id
        self.events: list[Event] = []
        self.venues: dict[str, Venue] = {}
        self.card: EventSnapshot | None = None
        self.active_id: str | None = None
        self._select_seq = 0
        self._list_gen = 0
        self._events_cursor: str | None = None
        self._events_done = False
        self._start_from, self._start_to = _list_window()

    def compose(self) -> ComposeResult:
        with Horizontal(id="chrome-row"):
            yield Static(self._chrome(), id="chrome")
            yield Button("WIN", id="mkt-win", compact=True)
            yield Button("PLACE", id="mkt-place", compact=True)
        yield Static(self._meta(), id="meta")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static(self._sidebar_head(), id="sidebar-head")
                yield Input(placeholder="filter tracks…", id="filter")
                yield EventList()
            with Vertical(id="main"):
                yield RaceTable()
                yield Static("Select a race.", id="empty")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)
        self.query_one("#empty").display = True
        self.query_one(RaceTable).display = False
        self.query_one("#filter", Input).can_focus = False
        self.call_after_refresh(self._boot)

    async def on_unmount(self) -> None:
        if self._owns_client and self.client is not None:
            await self.client.close()
            self.client = None

    def _boot(self) -> None:
        try:
            if self.client is None:
                self.client = AsyncBetwatch()
        except APIKeyNotSetError:
            self.status_note = "set BETWATCH_API_KEY (or fnox exec --)"
            self._paint()
            return
        self._refresh_events()

    def _refresh_events(self) -> None:
        self._begin_list()
        self.load_events()
        self.load_venues()

    def _chrome(self) -> Text:
        line = Text()
        line.append("BETWATCH", style="bold #f4e8c1")
        line.append("  ")
        line.append(self.sport or "all sports", style="#7ae0b8")
        line.append(" · ")
        line.append((self.country or "all").upper(), style="#7ae0b8")
        line.append("   ")
        if self.live:
            line.append("● LIVE", style="bold #3dd68c")
        else:
            line.append("○ idle", style="dim")
        line.append("   ", style="")
        line.append(self.status_note, style="dim")
        return line

    def _meta(self) -> Text:
        card = self.card
        if card is None:
            return Text("No race selected", style="dim")
        event = card.event
        now = utcnow()
        bits = [event_title(event, self.venues)]
        if event.racing.distance_meters:
            bits.append(f"{event.racing.distance_meters}m")
        if event.racing.track_condition:
            bits.append(event.racing.track_condition)
        if event.racing.race_class:
            bits.append(event.racing.race_class)
        bits.append(event.status)
        bits.append(format_clock(event.start_at))
        if event.is_open:
            bits.append(format_ttj(event.start_at, now))
        runners = sum(1 for row in card.entrants if not row.scratched and not row.vacant)
        bits.append(f"{runners} runners")
        return Text("  ·  ".join(bits), style="#c9b27c")

    def _sidebar_head(self) -> str:
        now = utcnow()
        try:
            events = self.query_one(EventList).visible_events(now)
        except NoMatches:
            events = sort_events(self.events)
        nxt = next_open(events, now)
        extra = f"  next {event_title(nxt, self.venues)}" if nxt else ""
        suffix = "+" if not self._events_done else ""
        return f"RACES  {len(events)}{suffix}{extra}"

    def _paint(self) -> None:
        self.query_one("#chrome", Static).update(self._chrome())
        self.query_one("#meta", Static).update(self._meta())
        self.query_one("#sidebar-head", Static).update(self._sidebar_head())
        self._sync_market_buttons()

    def _sync_market_buttons(self) -> None:
        try:
            win = self.query_one("#mkt-win", Button)
            place = self.query_one("#mkt-place", Button)
        except NoMatches:
            return
        win.variant = "primary" if self.market == "win" else "default"
        place.variant = "primary" if self.market == "place" else "default"

    def _tick(self) -> None:
        listing = self.query_one(EventList)
        if listing.events:
            listing.tick(utcnow())
        self._paint()

    def _render_card(self) -> None:
        empty = self.query_one("#empty", Static)
        table = self.query_one(RaceTable)
        if self.card is None:
            table.display = False
            empty.display = True
            empty.update("Select a race.")
            self._paint()
            return
        grid = build_grid(self.card, self.market)
        table.display = True
        empty.display = False
        table.show_grid(grid)
        if not grid.rows:
            table.display = False
            empty.display = True
            empty.update("No runners on this card yet.")
        elif grid.priced == 0:
            empty.display = False
        self._paint()

    def _begin_list(self) -> None:
        self._list_gen += 1
        self._events_cursor = None
        self._events_done = False
        self._start_from, self._start_to = _list_window()
        self.events = []
        self.venues = {}
        try:
            listing = self.query_one(EventList)
        except NoMatches:
            return
        listing.events = []
        listing.venues = {}
        listing.rebuild(utcnow())
        self.status_note = "loading races…"
        self._paint()

    def _list_status(self, listing: EventList) -> str:
        count = len(listing.visible_events(utcnow()))
        if not self._events_done:
            return f"{count} races · loading…"
        return f"{count} races"

    @work(exclusive=True, group="events", exit_on_error=False)
    async def load_events(self) -> None:
        client = self.client
        if client is None:
            return
        generation = self._list_gen
        after: str | None = None
        replace = True
        while True:
            try:
                page = await client.events.list(
                    sport=cast(Sport | None, self.sport),
                    country=self.country,
                    start_from=self._start_from,
                    start_to=self._start_to,
                    after=after,
                    limit=_PAGE,
                    include="racing",
                )
            except BetwatchError as exc:
                if generation == self._list_gen:
                    self.status_note = f"list failed: {exc}"
                    self._paint()
                return
            if generation != self._list_gen or get_current_worker().is_cancelled:
                return
            self.post_message(
                EventsBatch(
                    list(page.items),
                    cursor=page.next,
                    replace=replace,
                    generation=generation,
                )
            )
            if not page.next:
                return
            after = page.next
            replace = False

    @work(exclusive=True, group="venues", exit_on_error=False)
    async def load_venues(self) -> None:
        client = self.client
        if client is None:
            return
        generation = self._list_gen
        venues: dict[str, Venue] = {}
        after: str | None = None
        while True:
            try:
                page = await client.venues.list(
                    sport=cast(Sport | None, self.sport),
                    country=self.country,
                    after=after,
                    limit=200,
                )
            except BetwatchError:
                return
            if generation != self._list_gen or get_current_worker().is_cancelled:
                return
            for venue in page.items:
                venues[venue.id] = venue
            self.post_message(VenuesReady(dict(venues), generation))
            if not page.next:
                return
            after = page.next

    def on_events_batch(self, message: EventsBatch) -> None:
        if message.generation != self._list_gen:
            return
        if message.replace:
            self.events = list(message.events)
        else:
            seen = {event.id for event in self.events}
            self.events.extend(event for event in message.events if event.id not in seen)
        self._events_cursor = message.cursor
        self._events_done = message.cursor is None
        listing = self.query_one(EventList)
        listing.events = self.events
        preferred = self.boot_event_id or self.active_id
        listing.rebuild(
            utcnow(),
            preferred=preferred,
            keep_scroll=not message.replace,
        )
        self.status_note = self._list_status(listing)
        self._paint()
        boot = self.boot_event_id
        if boot and any(event.id == boot for event in self.events):
            self.boot_event_id = None
            self.select_event(boot)
        elif self.active_id is None:
            option = listing.highlighted_option
            if option and option.id:
                self.select_event(option.id)
        elif boot and self._events_done:
            self.boot_event_id = None
            option = listing.highlighted_option
            if option and option.id:
                self.select_event(option.id)

    def on_venues_ready(self, message: VenuesReady) -> None:
        if message.generation != self._list_gen:
            return
        self.venues = message.venues
        listing = self.query_one(EventList)
        listing.venues = message.venues
        if listing.events:
            listing.tick(utcnow())
        self._paint()

    def on_option_list_option_highlighted(self, message: OptionList.OptionHighlighted) -> None:
        if message.option_list.id != "events":
            return
        if message.option_id:
            self.select_event(message.option_id)

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        if message.option_id:
            self.select_event(message.option_id, force=True)

    def select_event(self, event_id: str, *, force: bool = False) -> None:
        if not force and event_id == self.active_id and self.card is not None:
            return
        self.active_id = event_id
        self.query_one(EventList).active_id = event_id
        self._select_seq += 1
        self.open_event(event_id, token=self._select_seq)

    @work(exclusive=True, group="watch", exit_on_error=False)
    async def open_event(self, event_id: str, token: int) -> None:
        client = self.client
        if client is None:
            return
        self.live = False
        self.status_note = "loading card…"
        self._paint()
        try:
            if self.stream_enabled:
                async with client.watch(event_id) as live:
                    if token != self._select_seq or get_current_worker().is_cancelled:
                        return
                    if live.snapshot is not None:
                        self.post_message(CardReady(live.snapshot))
                    self.live = True
                    self.status_note = "live"
                    async for frame in live:
                        if token != self._select_seq or get_current_worker().is_cancelled:
                            return
                        self.post_message(LiveFrame(frame))
            else:
                card = await client.events.snapshot(event_id)
                if token == self._select_seq:
                    self.post_message(CardReady(card))
                    self.status_note = "snapshot"
        except ResyncRequired:
            if token == self._select_seq:
                self.post_message(NeedResync(event_id))
        except BetwatchError as exc:
            if token == self._select_seq:
                self.post_message(WatchFailed(str(exc)))
        finally:
            if token == self._select_seq:
                self.live = False

    def on_card_ready(self, message: CardReady) -> None:
        self.card = message.card
        event = message.card.event
        self.events = apply_event_list(
            self.events,
            StreamEvent(
                id=event.id,
                status=event.status,
                start_at=event.start_at,
                updated_at=event.updated_at,
            ),
        )
        self.query_one(EventList).events = self.events
        self._render_card()

    def on_live_frame(self, message: LiveFrame) -> None:
        frame = message.frame
        if isinstance(frame, EventFrame):
            self.events = apply_event_list(self.events, frame.data)
            self.query_one(EventList).events = self.events
        if self.card is None:
            return
        if apply_frame(self.card, frame):
            if isinstance(frame, (OddsFrame, EventFrame)):
                self._render_card()
            else:
                self._paint()

    def on_watch_failed(self, message: WatchFailed) -> None:
        self.status_note = message.detail
        self.live = False
        self._paint()

    def on_need_resync(self, message: NeedResync) -> None:
        self.status_note = "resync"
        if self.active_id == message.event_id:
            self.select_event(message.event_id, force=True)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_reload(self) -> None:
        self._refresh_events()

    def action_next_open(self) -> None:
        listing = self.query_one(EventList)
        nxt = next_open(listing.visible_events(utcnow()), utcnow())
        if nxt is None:
            return
        try:
            listing.highlighted = listing.get_option_index(nxt.id)
        except Exception:
            return
        listing.scroll_to_highlight()
        self.select_event(nxt.id, force=True)

    def action_market_win(self) -> None:
        self.market = "win"
        self._render_card()

    def action_market_place(self) -> None:
        self.market = "place"
        self._render_card()

    @on(Button.Pressed, "#mkt-win")
    def _press_win(self) -> None:
        self.action_market_win()

    @on(Button.Pressed, "#mkt-place")
    def _press_place(self) -> None:
        self.action_market_place()

    def action_toggle_finished(self) -> None:
        listing = self.query_one(EventList)
        listing.hide_finished = not listing.hide_finished
        listing.rebuild(utcnow(), preferred=self.active_id)
        self.status_note = self._list_status(listing)
        self._paint()

    def action_filter(self) -> None:
        field = self.query_one("#filter", Input)
        field.can_focus = True
        field.add_class("visible")
        field.focus()

    def action_clear_filter(self) -> None:
        field = self.query_one("#filter", Input)
        if field.has_class("visible"):
            field.value = ""
            field.can_focus = False
            field.remove_class("visible")
            listing = self.query_one(EventList)
            listing.filter = ""
            listing.rebuild(utcnow(), preferred=self.active_id)
            listing.focus()
            self.status_note = self._list_status(listing)
            self._paint()

    @on(Input.Changed, "#filter")
    def _filter_changed(self, message: Input.Changed) -> None:
        listing = self.query_one(EventList)
        listing.filter = message.value.strip()
        listing.rebuild(utcnow(), preferred=self.active_id)
        self.status_note = self._list_status(listing)
        self._paint()

    @on(Input.Submitted, "#filter")
    def _filter_submitted(self) -> None:
        self.query_one(EventList).focus()

    @on(DescendantBlur, "#filter")
    def _filter_blur(self) -> None:
        field = self.query_one("#filter", Input)
        if not field.value.strip():
            field.can_focus = False
            field.remove_class("visible")

    def action_cycle_country(self) -> None:
        order: list[str | None] = [*COUNTRIES, None]
        try:
            index = order.index(self.country)
        except ValueError:
            index = 0
        self.country = order[(index + 1) % len(order)]
        self._refresh_events()

    def action_sport_thoroughbred(self) -> None:
        self._set_sport("thoroughbred")

    def action_sport_harness(self) -> None:
        self._set_sport("harness")

    def action_sport_greyhound(self) -> None:
        self._set_sport("greyhound")

    def action_sport_all(self) -> None:
        self._set_sport(None)

    def _set_sport(self, sport: str | None) -> None:
        if self.sport == sport:
            return
        self.sport = sport
        self._refresh_events()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="examples/tui.py",
        description="Betwatch racing odds TUI — event list by time-to-jump, then the bookmaker grid.",
    )
    parser.add_argument(
        "--sport",
        default="thoroughbred",
        choices=[*SPORTS, "all"],
        help="Race code (default: thoroughbred).",
    )
    parser.add_argument(
        "--country",
        default="au",
        help="ISO country filter (default: au). Use all for every country.",
    )
    parser.add_argument("--event", dest="event_id", help="Open this event id on launch.")
    parser.add_argument("--market", default="win", choices=["win", "place"])
    parser.add_argument("--no-stream", action="store_true", help="Snapshot only, no live SSE.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    app = BetwatchApp(
        sport=args.sport,
        country=args.country,
        event_id=args.event_id,
        market=args.market,
        stream=not args.no_stream,
    )
    app.run()


if __name__ == "__main__":
    main()
