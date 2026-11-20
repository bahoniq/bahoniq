# -*- coding: utf-8 -*-
"""Единый AI-сервис BahonIQ Work Center v2.0.0.

Основной движок: Google Gemini Flash (быстрый надежный облачный API).
Используется только облачный искусственный интеллект.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable, Iterator

LOGGER = logging.getLogger("bahoniq.ai_service")

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    project_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(project_dir, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)
except Exception:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

_gemini_client = None
_client_lock = threading.Lock()


def get_gemini_client():
    """Ленивая инициализация клиента Google GenAI."""
    global _gemini_client
    if _gemini_client is None:
        with _client_lock:
            if _gemini_client is None:
                api_key = os.getenv("GEMINI_API_KEY", "").strip()
                if api_key:
                    try:
                        from google import genai
                        _gemini_client = genai.Client(api_key=api_key)
                    except Exception as exc:
                        LOGGER.warning("Не удалось инициализировать google-genai: %s", exc)
                        _gemini_client = None
    return _gemini_client


def check_ai_status() -> dict[str, Any]:
    """Проверяет доступность облачного ИИ."""
    status = {
        "gemini": False,
        "cloud_ai": False,
        "active_provider": "none",
        "gemini_model": GEMINI_MODEL,
    }
    client = get_gemini_client()
    if client:
        candidates = [GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
        for cand in candidates:
            try:
                res = client.models.generate_content(
                    model=cand,
                    contents="ping",
                )
                if res and res.text:
                    status["gemini"] = True
                    status["cloud_ai"] = True
                    status["active_provider"] = "gemini"
                    status["gemini_model"] = cand
                    break
            except Exception:
                status["gemini"] = False

    return status


def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    timeout: int = 45,
    system_prompt: str = "",
    return_provider: bool = False,
    **kwargs: Any,
) -> str | tuple[str, str]:
    """Генерация текста через облачный Google Gemini."""
    sys_inst = system_instruction or system_prompt

    client = get_gemini_client()
    if not client:
        raise RuntimeError("Облачный ИИ не настроен: отсутствует или недействителен GEMINI_API_KEY.")

    config = {}
    if sys_inst:
        config["system_instruction"] = sys_inst
    if temperature is not None:
        config["temperature"] = temperature

    from google.genai import types
    gen_config = types.GenerateContentConfig(**config) if config else None

    models_to_try = [GEMINI_MODEL]
    for candidate in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"):
        if candidate not in models_to_try:
            models_to_try.append(candidate)

    last_error = None
    for current_model in models_to_try:
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=gen_config,
            )
            if response and response.text:
                text = response.text.strip()
                return (text, "gemini") if return_provider else text
        except Exception as exc:
            LOGGER.warning("Облачный ИИ Gemini (%s) ошибка: %s", current_model, exc)
            last_error = exc

    raise RuntimeError(f"Облачный ИИ временно недоступен: {last_error}")


def generate_text_stream(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    timeout: int = 45,
    system_prompt: str = "",
    **kwargs: Any,
) -> Iterator[str]:
    """Потоковая генерация текста (Streaming / SSE) через облачный Gemini."""
    sys_inst = system_instruction or system_prompt
    client = get_gemini_client()

    if not client:
        raise RuntimeError("Облачный ИИ не настроен: отсутствует GEMINI_API_KEY.")

    config = {}
    if sys_inst:
        config["system_instruction"] = sys_inst
    if temperature is not None:
        config["temperature"] = temperature

    from google.genai import types
    gen_config = types.GenerateContentConfig(**config) if config else None

    models_to_try = [GEMINI_MODEL]
    for candidate in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"):
        if candidate not in models_to_try:
            models_to_try.append(candidate)

    last_error = None
    for current_model in models_to_try:
        try:
            stream_iter = client.models.generate_content_stream(
                model=current_model,
                contents=prompt,
                config=gen_config,
            )
            yielded_any = False
            for chunk in stream_iter:
                if chunk and chunk.text:
                    yielded_any = True
                    yield chunk.text
            if yielded_any:
                return
        except Exception as exc:
            LOGGER.warning("Облачный ИИ stream (%s) ошибка: %s", current_model, exc)
            last_error = exc

    raise RuntimeError(f"Облачный ИИ (stream) недоступен: {last_error}")


def generate_text_async(
    prompt: str,
    callback: Callable[[str, Exception | None], None],
    system_instruction: str = "",
    temperature: float = 0.2,
    timeout: int = 45,
) -> threading.Thread:
    """Асинхронная генерация текста в отдельном фоновом потоке для Tkinter."""
    def worker():
        try:
            res = generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                timeout=timeout,
            )
            callback(res, None)
        except Exception as exc:
            callback("", exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
