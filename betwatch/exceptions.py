class BetwatchError(Exception):
    """Base class for exceptions in this module."""

    pass


class APIKeyNotSetError(BetwatchError):
    message = "The api_key client option must be set either by passing api_key to the client or by setting the BETWATCH_API_KEY environment variable"

    def __init__(self, message=message):
        self.message = message
        super().__init__(self.message)
