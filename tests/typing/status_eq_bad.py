from betwatch import Event


def check(event: Event) -> bool:
    return event.status == "resulted"
