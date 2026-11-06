class ServiceError(Exception):
    """A safe, public problem; upstream payloads and credentials never leave the service."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)
