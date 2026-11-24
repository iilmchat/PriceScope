"""Иерархия доменных ошибок PriceScope."""

from __future__ import annotations


class DomainError(Exception):
    """Базовая ошибка домена. Имеет стабильный код для API."""

    code = "DOMAIN_ERROR"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ParserError(DomainError):
    """Ошибка уровня парсера (сеть, схема, таймаут)."""

    code = "PARSER_ERROR"


class UnknownStoreError(DomainError):
    """Запрошен неизвестный магазин."""

    code = "UNKNOWN_STORE"


class StoreUnavailableError(ParserError):
    """Магазин временно недоступен."""

    code = "STORE_UNAVAILABLE"


class CaptchaDetectedError(ParserError):
    """Обнаружена CAPTCHA — автоматический обход запрещён (ADR-006)."""

    code = "CAPTCHA_DETECTED"

    def __init__(self, message: str, diagnostics: dict | None = None) -> None:
        super().__init__(message, diagnostics)
        self.diagnostics = diagnostics or {}


class NotFoundError(DomainError):
    """Сущность не найдена."""

    code = "NOT_FOUND"


class ConflictError(DomainError):
    """Конфликт идемпотентности/состояния."""

    code = "CONFLICT"
