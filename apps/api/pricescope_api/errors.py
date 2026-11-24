"""Единый формат ошибок API."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from pricescope_api.logging import current_trace_id


class ApiError(Exception):
    """Ошибка API со стабильным кодом и HTTP-статусом."""

    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Преобразовать ApiError в единый JSON-ответ."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "trace_id": current_trace_id(),
        },
    )
