"""Структурированное логирование и сквозной trace_id."""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid

import structlog

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)


def new_trace_id() -> str:
    """Создать и установить новый trace_id."""
    value = uuid.uuid4().hex[:16]
    _trace_id.set(value)
    return value


def current_trace_id() -> str:
    """Текущий trace_id (или пустая строка вне запроса)."""
    return _trace_id.get()


def configure_logging(level: str = "INFO") -> None:
    """Настроить structlog + стандартный logging."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str):
    """Получить логгер с именем модуля."""
    return structlog.get_logger(name)
