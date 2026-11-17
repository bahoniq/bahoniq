#!/usr/bin/env python3
"""
Скрипт первоначальной локальной авторизации Telegram (Telethon)
для модуля «Музыка в авто» BahonIQ Work Center.

Запускается ОДИН РАЗ на локальном компьютере:
    py scripts/auth_telegram_music.py

Результат:
    Строка TELEGRAM_SESSION (StringSession), которую вы добавляете
    в переменные окружения Render (Environment Variables).
    Секреты НЕ сохраняются в файлы проекта и НЕ попадают в Git.
"""
from __future__ import annotations
import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def main():
    print("=" * 64)
    print("  BahonIQ Work Center — Авторизация Telegram для «Музыка в авто»")
    print("=" * 64)
    print("\nЭтот скрипт генерирует защищённую строковую сессию (StringSession).")
    print("Сервер на Render будет использовать её для доступа к каналу без повторного ввода кода.\n")

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("Ошибка: библиотека telethon не установлена.")
        print("Выполните: pip install telethon")
        sys.exit(1)

    api_id_env = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash_env = os.getenv("TELEGRAM_API_HASH", "").strip()

    if api_id_env and api_hash_env:
        print(f"Используются TELEGRAM_API_ID и TELEGRAM_API_HASH из окружения.")
        api_id = int(api_id_env)
        api_hash = api_hash_env
    else:
        print("Получить API ID и API HASH можно на https://my.telegram.org (раздел API development tools).")
        api_id_input = input("Введите Telegram API ID: ").strip()
        if not api_id_input.isdigit():
            print("Ошибка: API ID должен быть числом.")
            sys.exit(1)
        api_id = int(api_id_input)
        api_hash = input("Введите Telegram API HASH: ").strip()
        if not api_hash:
            print("Ошибка: API HASH не может быть пустым.")
            sys.exit(1)

    channel_name = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip()
    print(f"\nКанал по умолчанию: @{channel_name}")
    custom_ch = input(f"Нажмите Enter для использования '@{channel_name}' или введите другой username/ссылку: ").strip()
    if custom_ch:
        channel_name = custom_ch.replace("https://t.me/", "").replace("@", "").strip()

    print("\nПодключение к серверам Telegram...")
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    me = await client.get_me()
    print(f"\n✓ Успешный вход под аккаунтом: {me.first_name} (@{me.username or me.id})")

    # Получаем информацию о канале
    channel_id = None
    try:
        entity = await client.get_entity(channel_name)
        channel_id = entity.id
        # Для каналов в Telethon внутренний ID обычно представляется с префиксом -100
        full_id = f"-100{channel_id}" if not str(channel_id).startswith("-100") else str(channel_id)
        print(f"✓ Канал найден: «{getattr(entity, 'title', channel_name)}»")
        print(f"  Внутренний ID канала: {full_id}")
    except Exception as exc:
        print(f"⚠ Предупреждение при поиске канала @{channel_name}: {exc}")
        print("  Вы сможете указать ID канала позже в переменных окружения Render.")
        full_id = ""

    session_string = client.session.save()
    await client.disconnect()

    # Сохраняем в локальный файл и копируем в буфер обмена Windows
    try:
        from pathlib import Path
        import subprocess
        session_file = Path(__file__).resolve().parent.parent / "telegram_session.txt"
        session_file.write_text(session_string, encoding="utf-8")
        if sys.platform == "win32":
            subprocess.run(["clip"], input=session_string.encode("utf-16"), check=False)
            copied_notice = " (и автоматически скопирована в буфер обмена Windows!)"
        else:
            copied_notice = ""
    except Exception:
        copied_notice = ""

    print("\n" + "=" * 64)
    print("  ГОТОВО! СКОПИРУЙТЕ ЭТИ ДАННЫЕ В RENDER ENVIRONMENT VARIABLES:")
    print("=" * 64)
    print(f"\nTELEGRAM_API_ID={api_id}")
    print(f"TELEGRAM_API_HASH={api_hash}")
    print(f"TELEGRAM_CHANNEL_USERNAME={channel_name}")
    if full_id:
        print(f"TELEGRAM_CHANNEL_ID={full_id}")
    print(f"\nTELEGRAM_SESSION={session_string}\n")
    print(f"✓ Строка сессии сохранена в файл telegram_session.txt{copied_notice}")
    print("=" * 64)
    print("ВНИМАНИЕ: Строка сессии даёт доступ к аккаунту! Никогда не публикуйте")
    print("её в Git, не передавайте в чаты и храните только в настройках Render Environment.")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
