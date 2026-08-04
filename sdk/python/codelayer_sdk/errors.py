class ForgeError(Exception):
    """Base error that can safely cross the plugin protocol boundary."""

    code = -32000

    def __init__(self, message: str, *, data: object | None = None) -> None:
        super().__init__(message)
        self.data = data


class ValidationError(ForgeError):
    code = -32602


class PermissionDenied(ForgeError):
    code = -32001
