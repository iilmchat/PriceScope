"""Политика CAPTCHA: детект → остановка, обход запрещён (ADR-006)."""

from __future__ import annotations

from dataclasses import dataclass

from pricescope_core import CaptchaDetectedError

MARKERS = (
    "captcha",
    "капча",
    "подтвердите, что вы не робот",
    "подтвердите что вы не робот",
    "я не робот",
    "verify you are human",
    "are you human",
    "unusual traffic",
    "проверка безопасности",
    "доступ ограничен",
)


@dataclass(frozen=True)
class CaptchaDiagnostics:
    """Диагностика страницы для ParseRun.error_details."""

    markers: tuple[str, ...]
    title: str
    url: str
    snippet: str


def detect_captcha(title: str, url: str, body_text: str) -> CaptchaDiagnostics | None:
    """Найти видимые маркеры CAPTCHA; не пытается её решать."""
    visible = f"{title}\n{body_text}".lower()
    found = tuple(marker for marker in MARKERS if marker in visible)
    if not found:
        return None
    return CaptchaDiagnostics(found, title, url, " ".join(body_text.split())[:350])


def ensure_no_captcha(title: str, url: str, body_text: str) -> None:
    """Бросить `CaptchaDetectedError` с диагностикой, если видна проверка."""
    diagnostics = detect_captcha(title, url, body_text)
    if diagnostics is not None:
        message = (
            "Обнаружена CAPTCHA/антибот-проверка 5ka.ru. Автоматический сбор остановлен; "
            "скрипт не пытается решать или обходить проверку. Не запускайте парсер повторно "
            "до восстановления обычного доступа к сайту."
        )
        raise CaptchaDetectedError(message, diagnostics.__dict__)
