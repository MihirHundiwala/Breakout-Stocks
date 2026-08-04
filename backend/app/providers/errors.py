class ProviderError(RuntimeError):
    """A safe provider failure that can cross the worker boundary."""

    def __init__(self, *, code: str, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
