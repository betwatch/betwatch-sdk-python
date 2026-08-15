from betwatch import Event, EventStatuses


def check(event: Event) -> bool:
    return event.status == "open" or event.status == EventStatuses.FINAL
