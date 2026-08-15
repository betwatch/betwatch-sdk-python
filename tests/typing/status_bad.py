from betwatch import Event, EventStatus


def mark(status: EventStatus) -> EventStatus:
    return status


def check(event: Event) -> bool:
    mark("resulted")
    return event.has_status("resulted")
