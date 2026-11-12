# -*- coding: utf-8 -*-
"""Единый AI-сервис BahonIQ Work Center v2.0.0.

Основной движок: Google Gemini Flash (быстрый бесплатный облачный API).
Тихий Fallback: Локальная Ollama (qwen:7b / qwen:3b) при отсутствии сети,
таймауте или исчерпании лимитов.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Callable

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
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()

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
    """Проверяет доступность провайдеров ИИ."""
    status = {
        "gemini": False,
        "ollama": False,
        "active_provider": "none",
        "gemini_model": GEMINI_MODEL,
        "ollama_model": OLLAMA_MODEL,
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
                    status["active_provider"] = "gemini"
                    status["gemini_model"] = cand
                    break
            except Exception:
                status["gemini"] = False

    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                status["ollama"] = True
                if status["active_provider"] == "none":
                    status["active_provider"] = "ollama"
    except Exception:
        status["ollama"] = False

    return status


def _call_ollama(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    timeout: int = 120,
    model: str = "",
) -> str:
    """Вызов локальной Ollama (fallback)."""
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_instruction,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 1000,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
        return str(body.get("response", "")).strip()


def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    timeout: int = 45,
    system_prompt: str = "",
    return_provider: bool = False,
    ollama_model: str = "",
) -> str | tuple[str, str]:
    """Генерация текста с тихим автоматическим Fallback."""
    sys_inst = system_instruction or system_prompt

    # 1. Попытка через Google Gemini Flash
    client = get_gemini_client()
    if client:
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
                LOGGER.warning("Gemini (%s) ошибка: %s", current_model, exc)

        LOGGER.warning("Все облачные модели Gemini временно недоступны. Активируем тихий fallback на Ollama...")

    # 2. Тихий Fallback на локальную Ollama
    try:
        LOGGER.info("Запуск вызова локальной Ollama (%s)...", OLLAMA_MODEL)
        text = _call_ollama(
            prompt=prompt,
            system_instruction=sys_inst,
            temperature=temperature,
            timeout=timeout,
            model=ollama_model,
        )
        if not text:
            raise RuntimeError("Ollama вернула пустой ответ")
        return (text, "ollama") if return_provider else text
    except Exception as exc:
        LOGGER.error("Ошибка при обращении к Ollama fallback: %s", exc)
        raise RuntimeError(
            "Не удалось получить ответ от ИИ: облачный Gemini недоступен, "
            f"а локальная Ollama вернула ошибку: {exc}"
        ) from exc


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
