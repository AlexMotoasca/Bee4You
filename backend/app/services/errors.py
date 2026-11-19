class OpRejected(Exception):
    """A device write that can never succeed (invalid data, not allowed, not found)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
