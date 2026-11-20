"""Базовый HTTP-клиент для адаптеров BahonIQ Sports."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("bahoniq.sports.providers")

DEFAULT_TIMEOUT = 15.0
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.8",
}


class ProviderError(RuntimeError):
    """Ошибка обращения к внешнему спорному/спортивному источнику."""


def _merge_headers(url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(DEFAULT_HEADERS)
    if "wikipedia.org" in url or "wikimedia.org" in url:
        merged["User-Agent"] = "BahonIQWorkCenter/2.0 (sports-hub)"
        merged["Api-User-Agent"] = "BahonIQWorkCenter/2.0 (sports-hub)"
    if headers:
        merged.update(headers)
    return merged


def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> dict[str, Any] | list[Any]:
    """Выполняет GET-запрос с таймаутом и ограниченным retry, возвращает проверенный JSON."""
    merged_headers = _merge_headers(url, headers)

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code} от источника")
            data = resp.json()
            if not isinstance(data, (dict, list)):
                raise ProviderError("Некорректный формат JSON от источника")
            return data
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    logger.warning("Ошибка провайдера (%s): %s", url.split("?")[0], type(last_exc).__name__)
    raise ProviderError(str(last_exc) or "Источник недоступен") from last_exc


def fetch_text_with_headers(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> tuple[str, dict[str, str]]:
    """Выполняет GET-запрос и возвращает (текст, HTTP-заголовки ответа)."""
    merged_headers = _merge_headers(url, headers)

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=merged_headers, timeout=timeout)
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code} от источника")
            resp_headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
            return resp.text, resp_headers
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    logger.warning("Ошибка текста (%s): %s", url.split("?")[0], type(last_exc).__name__)
    raise ProviderError(str(last_exc) or "Источник недоступен") from last_exc


def fetch_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> str:
    """Выполняет GET-запрос для XML/RSS/HTML-страниц."""
    text, _ = fetch_text_with_headers(url, headers=headers, timeout=timeout, retries=retries)
    return text
