from typing import Any


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, **details: Any) -> None:
        self.code = code
        self.message = message
        self.status = status
        self.details = details
