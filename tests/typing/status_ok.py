from betwatch import Event, EventStatus, EventStatuses


def mark(status: EventStatus) -> EventStatus:
    return status


def check(event: Event) -> bool:
    mark("open")
    mark(EventStatuses.FINAL)
    return event.has_status("open") or event.has_status(EventStatuses.FINAL)
