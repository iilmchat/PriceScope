"""Middleware: trace_id, тайминг, единая обработка ошибок."""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pricescope_api.errors import ApiError, api_error_handler
from pricescope_api.logging import current_trace_id, new_trace_id


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Устанавливает trace_id и добавляет заголовок времени ответа."""

    async def dispatch(self, request: Request, call_next):
        """Обработать запрос и измерить длительность."""
        trace = request.headers.get("x-trace-id") or new_trace_id()
        request.state.trace_id = trace
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration = time.perf_counter() - start
            request.state.duration_ms = round(duration * 1000, 1)
        response.headers["X-Trace-Id"] = trace
        response.headers["X-Response-Time-Ms"] = str(request.state.duration_ms)
        return response


def register_error_handlers(app: FastAPI) -> None:
    """Зарегистрировать обработчики ошибок приложения."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return await api_error_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Ошибки валидации — в том же envelope, что и доменные ошибки."""
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Некорректные параметры запроса",
                    "details": {"errors": details},
                },
                "trace_id": current_trace_id(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Внутренняя ошибка сервера",
                    "details": {},
                },
                "trace_id": current_trace_id(),
            },
        )
