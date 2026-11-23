"""
Модуль извлечения, валидации и кэширования обложек аудиофайлов BahonIQ Music.

Поддерживает:
- MP3: ID3v2.2 (PIC), ID3v2.3 (APIC), ID3v2.4 (APIC, включая synchsafe и unsynchronisation)
- MP4 / M4A / AAC: атомы moov -> udta -> meta -> ilst -> covr -> data
- FLAC: блок метаданных METADATA_BLOCK_PICTURE (тип 6)
- OGG / Vorbis / Opus: тег METADATA_BLOCK_PICTURE (base64)
- Форматы изображений: JPEG, PNG, WebP (с проверкой сигнатуры и целостности через PIL)
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import re
import struct
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_COVER_BYTES = 10 * 1024 * 1024
MIN_COVER_BYTES = 64


def compute_cover_hash(img_bytes: bytes) -> str:
    """Возвращает стабильный 12-символьный SHA-1 хэш содержимого изображения."""
    return hashlib.sha1(img_bytes).hexdigest()[:12]


def validate_image_bytes(raw: bytes) -> Optional[Tuple[bytes, str]]:
    """
    Проверяет сигнатуру изображения (JPEG, PNG, WebP) и валидирует его структуру.
    Не доверяет слепо MIME из тега и не обрезает JPEG на встроенном EXIF-thumbnail.
    """
    if not raw or len(raw) < MIN_COVER_BYTES:
        return None

    data = bytes(raw).lstrip(b"\x00")
    if len(data) < MIN_COVER_BYTES or len(data) > MAX_COVER_BYTES:
        return None

    mime: Optional[str] = None
    candidate: Optional[bytes] = None

    # 1. JPEG (\xff\xd8\xff ... последний \xff\xd9)
    if data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
        end_idx = data.rfind(b"\xff\xd9")
        candidate = data[: end_idx + 2] if end_idx != -1 and end_idx + 2 >= MIN_COVER_BYTES else data
    # 2. PNG (\x89PNG\r\n\x1a\n ... IEND\xaeB`\x82)
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
        iend = data.find(b"IEND\xaeB`\x82")
        candidate = data[: iend + 8] if iend != -1 else data
    # 3. WebP (RIFF....WEBP)
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
        riff_size = struct.unpack("<I", data[4:8])[0] + 8
        candidate = data[:riff_size] if MIN_COVER_BYTES <= riff_size <= len(data) else data
    else:
        # Иногда внутри тега перед сигнатурой попадаются 1-4 лишних байта
        for sig, sig_mime in (
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
        ):
            pos = data.find(sig, 0, 64)
            if pos != -1:
                return validate_image_bytes(data[pos:])
        return None

    if not candidate or len(candidate) < MIN_COVER_BYTES or len(candidate) > MAX_COVER_BYTES:
        return None

    # Проверяем реальную читаемость изображения через Pillow (защита от случайных байтов аудиопотока)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(candidate)) as img:
            img.verify()
        with Image.open(io.BytesIO(candidate)) as img2:
            w, h = img2.size
            if w <= 0 or h <= 0 or w > 12000 or h > 12000:
                return None
    except ImportError:
        pass
    except Exception:
        return None

    return candidate, mime


def _decode_synchsafe(raw4: bytes) -> int:
    if len(raw4) != 4:
        return 0
    return ((raw4[0] & 0x7F) << 21) | ((raw4[1] & 0x7F) << 14) | ((raw4[2] & 0x7F) << 7) | (raw4[3] & 0x7F)


def _remove_unsync(data: bytes) -> bytes:
    return data.replace(b"\xff\x00", b"\xff")


def _skip_terminated_string(buf: bytes, pos: int, encoding: int) -> int:
    """Пропускает null-terminated строку в ID3 кадре с учётом кодировки (0/3: 1-byte, 1/2: 2-byte UTF-16)."""
    n = len(buf)
    if pos >= n:
        return n
    if encoding in (1, 2):
        # UTF-16: ищем двухбайтовый \x00\x00 на чётном смещении
        i = pos
        while i + 1 < n:
            if buf[i] == 0 and buf[i + 1] == 0:
                return i + 2
            i += 2
        return n
    else:
        idx = buf.find(b"\x00", pos)
        return (idx + 1) if idx != -1 else n


def _parse_apic_payload(payload: bytes, is_v22: bool = False) -> Optional[Tuple[int, bytes, str]]:
    """Разбирает содержимое кадра APIC (ID3v2.3/2.4) или PIC (ID3v2.2).
    Возвращает (pic_type, img_bytes, mime)."""
    if len(payload) < MIN_COVER_BYTES:
        return None
    encoding = payload[0]
    pos = 1
    if is_v22:
        if pos + 3 > len(payload):
            return None
        pos += 3  # 3-символьный формат ('JPG', 'PNG')
    else:
        end_mime = payload.find(b"\x00", pos)
        if end_mime == -1:
            return None
        pos = end_mime + 1

    if pos >= len(payload):
        return None
    pic_type = payload[pos]
    pos += 1

    pos = _skip_terminated_string(payload, pos, encoding)
    if pos >= len(payload):
        return None

    raw_img = payload[pos:]
    validated = validate_image_bytes(raw_img)
    if not validated:
        return None
    return pic_type, validated[0], validated[1]


def _extract_id3_covers(data: bytes) -> List[Tuple[int, bytes, str]]:
    """Извлекает все валидные картинки из тега ID3v2.2 / ID3v2.3 / ID3v2.4 строго в границах тега."""
    results: List[Tuple[int, bytes, str]] = []
    # Ищем заголовок ID3 в первых 4 КБ (на случай мусорного префикса от бота)
    id3_pos = data.find(b"ID3", 0, 4096)
    if id3_pos == -1 or len(data) < id3_pos + 10:
        return results

    header = data[id3_pos : id3_pos + 10]
    ver_major = header[3]
    flags = header[5]
    tag_size = _decode_synchsafe(header[6:10])
    if ver_major not in (2, 3, 4) or tag_size <= 0:
        return results

    tag_data = data[id3_pos + 10 : id3_pos + 10 + tag_size]
    if flags & 0x80:
        tag_data = _remove_unsync(tag_data)

    pos = 0
    # Extended header в v2.3 / v2.4
    if (flags & 0x40) and ver_major in (3, 4) and len(tag_data) >= 4:
        ext_size = _decode_synchsafe(tag_data[:4]) if ver_major == 4 else struct.unpack(">I", tag_data[:4])[0]
        pos += 4 + ext_size if ver_major == 3 else ext_size

    limit = len(tag_data)
    while pos < limit:
        if ver_major == 2:
            if pos + 6 > limit:
                break
            frame_id = tag_data[pos : pos + 3]
            if frame_id == b"\x00\x00\x00" or not all(32 <= b <= 90 for b in frame_id):
                break
            frame_size = (tag_data[pos + 3] << 16) | (tag_data[pos + 4] << 8) | tag_data[pos + 5]
            pos += 6
            if frame_size <= 0 or pos + frame_size > limit:
                break
            frame_payload = tag_data[pos : pos + frame_size]
            pos += frame_size
            if frame_id == b"PIC":
                parsed = _parse_apic_payload(frame_payload, is_v22=True)
                if parsed:
                    results.append(parsed)
        else:
            if pos + 10 > limit:
                break
            frame_id = tag_data[pos : pos + 4]
            if frame_id == b"\x00\x00\x00\x00" or not all(48 <= b <= 90 for b in frame_id):
                break
            raw_size = tag_data[pos + 4 : pos + 8]
            frame_flags = struct.unpack(">H", tag_data[pos + 8 : pos + 10])[0]
            if ver_major == 4:
                frame_size = _decode_synchsafe(raw_size)
                # Fallback для нестандартных кодировщиков, записавших обычный uint32 в v2.4
                if (
                    frame_size <= 0
                    or pos + 10 + frame_size > limit
                    or (
                        pos + 14 + frame_size <= limit
                        and tag_data[pos + 10 + frame_size : pos + 14 + frame_size] != b"\x00\x00\x00\x00"
                        and not all(48 <= b <= 90 for b in tag_data[pos + 10 + frame_size : pos + 14 + frame_size])
                    )
                ):
                    alt_size = struct.unpack(">I", raw_size)[0]
                    if 0 < alt_size <= limit - (pos + 10):
                        frame_size = alt_size
            else:
                frame_size = struct.unpack(">I", raw_size)[0]

            pos += 10
            if frame_size <= 0 or pos + frame_size > limit:
                break
            frame_payload = tag_data[pos : pos + frame_size]
            pos += frame_size

            if frame_id == b"APIC":
                if ver_major == 4:
                    if frame_flags & 0x0001:  # Data length indicator
                        frame_payload = frame_payload[4:]
                    if frame_flags & 0x0002:  # Frame unsynchronisation
                        frame_payload = _remove_unsync(frame_payload)
                elif ver_major == 3 and (frame_flags & 0x0080):
                    continue
                parsed = _parse_apic_payload(frame_payload, is_v22=False)
                if parsed:
                    results.append(parsed)

    return results


def _extract_mp4_covr(data: bytes) -> List[Tuple[int, bytes, str]]:
    """Извлекает изображения из атомов MP4/M4A covr -> data."""
    results: List[Tuple[int, bytes, str]] = []
    search_pos = 0
    n = len(data)
    while search_pos < n:
        idx = data.find(b"covr", search_pos)
        if idx == -1 or idx < 4:
            break
        covr_start = idx - 4
        covr_size = struct.unpack(">I", data[covr_start:idx])[0]
        if covr_size < 16 or covr_start + covr_size > n + 64:
            search_pos = idx + 4
            continue
        covr_end = min(n, covr_start + covr_size)
        pos = idx + 4
        while pos + 16 <= covr_end:
            atom_size = struct.unpack(">I", data[pos : pos + 4])[0]
            atom_type = data[pos + 4 : pos + 8]
            if atom_size < 16 or pos + atom_size > covr_end:
                break
            if atom_type == b"data":
                raw_img = data[pos + 16 : pos + atom_size]
                validated = validate_image_bytes(raw_img)
                if validated:
                    results.append((3, validated[0], validated[1]))
            pos += atom_size
        search_pos = covr_end
    return results


def _parse_flac_picture_block(block: bytes) -> Optional[Tuple[int, bytes, str]]:
    """Разбирает структуру METADATA_BLOCK_PICTURE (используется во FLAC и OGG/Vorbis)."""
    if len(block) < 32:
        return None
    try:
        pic_type, mime_len = struct.unpack(">II", block[:8])
        pos = 8
        if pos + mime_len + 4 > len(block):
            return None
        pos += mime_len
        desc_len = struct.unpack(">I", block[pos : pos + 4])[0]
        pos += 4 + desc_len
        if pos + 20 > len(block):
            return None
        data_len = struct.unpack(">I", block[pos + 16 : pos + 20])[0]
        pos += 20
        if data_len <= 0 or pos + data_len > len(block):
            return None
        raw_img = block[pos : pos + data_len]
        validated = validate_image_bytes(raw_img)
        if not validated:
            return None
        return pic_type, validated[0], validated[1]
    except Exception:
        return None


def _extract_flac_covers(data: bytes) -> List[Tuple[int, bytes, str]]:
    results: List[Tuple[int, bytes, str]] = []
    if len(data) < 8 or data[:4] != b"fLaC":
        return results
    pos = 4
    n = len(data)
    while pos + 4 <= n:
        header_byte = data[pos]
        is_last = bool(header_byte & 0x80)
        block_type = header_byte & 0x7F
        block_len = (data[pos + 1] << 16) | (data[pos + 2] << 8) | data[pos + 3]
        pos += 4
        if pos + block_len > n:
            break
        if block_type == 6:
            parsed = _parse_flac_picture_block(data[pos : pos + block_len])
            if parsed:
                results.append(parsed)
        pos += block_len
        if is_last:
            break
    return results


def _extract_ogg_covers(data: bytes) -> List[Tuple[int, bytes, str]]:
    results: List[Tuple[int, bytes, str]] = []
    if len(data) < 32 or data[:4] != b"OggS":
        return results
    # В Ogg поток разбит на страницы ~4 КБ. Собираем полезную нагрузку страниц для поиска METADATA_BLOCK_PICTURE=
    payload = bytearray()
    pos = 0
    n = len(data)
    while pos + 27 <= n:
        if data[pos : pos + 4] != b"OggS":
            next_ogg = data.find(b"OggS", pos + 1)
            if next_ogg == -1:
                break
            pos = next_ogg
            continue
        num_segments = data[pos + 26]
        seg_table_end = pos + 27 + num_segments
        if seg_table_end > n:
            break
        page_body_size = sum(data[pos + 27 : seg_table_end])
        body_end = min(n, seg_table_end + page_body_size)
        payload.extend(data[seg_table_end:body_end])
        pos = body_end

    buf = bytes(payload) if payload else data
    marker_upper = b"METADATA_BLOCK_PICTURE="
    idx = buf.upper().find(marker_upper)
    while idx != -1:
        start = idx + len(marker_upper)
        # Длина строки комментария Vorbis записана как 32-bit LE за 4 байта до 'METADATA_BLOCK_PICTURE='
        comment_len = struct.unpack("<I", buf[idx - 4 : idx])[0] if idx >= 4 else 0
        if len(marker_upper) + 16 <= comment_len <= len(buf) - idx:
            b64_end = idx + comment_len
        else:
            b64_end = start
            while b64_end < len(buf) and buf[b64_end] in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=":
                b64_end += 1
        b64_raw = buf[start:b64_end]
        try:
            decoded = base64.b64decode(b64_raw)
            parsed = _parse_flac_picture_block(decoded)
            if parsed:
                results.append(parsed)
        except Exception:
            pass
        idx = buf.upper().find(marker_upper, start + 1)
    return results


def extract_embedded_cover_from_bytes(data: bytes) -> Optional[Tuple[bytes, str]]:
    """
    Универсальное извлечение встроенной обложки из байтов аудиофайла (или первых чанков).
    Поддерживает ID3v2.2/2.3/2.4 (APIC/PIC), MP4/M4A (covr), FLAC (PICTURE), OGG (METADATA_BLOCK_PICTURE).
    При наличии нескольких изображений выбирает Front Cover (pic_type == 3), затем первое валидное.
    """
    if not data or len(data) < MIN_COVER_BYTES:
        return None

    candidates: List[Tuple[int, bytes, str]] = []
    candidates.extend(_extract_id3_covers(data))
    if not candidates:
        candidates.extend(_extract_mp4_covr(data))
    if not candidates:
        candidates.extend(_extract_flac_covers(data))
    if not candidates:
        candidates.extend(_extract_ogg_covers(data))

    if not candidates:
        return None

    # Приоритет 1: Front Cover (pic_type == 3)
    for pic_type, img_bytes, mime in candidates:
        if pic_type == 3:
            return img_bytes, mime

    # Приоритет 2: Первая валидная картинка
    return candidates[0][1], candidates[0][2]


def _norm_lookup_tokens(text: str) -> List[str]:
    cleaned = re.sub(r"[^a-zа-яёәіңғүұқөһ0-9]+", " ", (text or "").lower()).strip()
    return [t for t in cleaned.split() if len(t) >= 2]


def clean_music_query(artist: str, title: str) -> Tuple[str, str]:
    """Очищает artist и title от мусора сайтов/тегов (kzmp3.kz, amp;, скобок) для точного поиска обложки."""
    a = html.unescape(artist or "").replace("amp;", "&").strip()
    t = html.unescape(title or "").replace("amp;", "&").strip()

    noise_re = re.compile(
        r"\[[^\]]*\]|\([^\)]*\)|"
        r"\b(?:kzmp3\.kz|muzik\.kz|agugai\.kz|kazamuza\.net|kissvk\.com|muzzona\.kz|official\s*video|mv|hd|hq|lyrics|remix|mashup|cover|ai\s*cover|tiktok)\b",
        re.IGNORECASE,
    )
    a = re.sub(noise_re, " ", a)
    t = re.sub(noise_re, " ", t)
    a = re.sub(r"\s+", " ", a).strip(" -_|·")
    t = re.sub(r"\s+", " ", t).strip(" -_|·")

    generic_artists = {"неизвестный исполнитель", "музыка дит", "musical.ly", "unknown", "unknown artist", ""}
    if a.lower() in generic_artists and " - " in t:
        left, right = t.split(" - ", 1)
        a, t = left.strip(), right.strip()

    # Убираем дублирование «Исполнитель - Название» внутри title
    if a and t.lower().startswith(a.lower() + " - "):
        t = t[len(a) + 3 :].strip()
    elif a and t.lower().startswith(a.lower() + " – "):
        t = t[len(a) + 3 :].strip()

    # Убираем feat. / ft. для более широкого совпадения
    a = re.split(r"\s+(?:feat\.?|ft\.?|x|&|и)\s+", a, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    t = re.split(r"\s+(?:feat\.?|ft\.?)\s+", t, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return a, t


def _itunes_result_matches(clean_artist: str, clean_title: str, item: Dict[str, Any]) -> bool:
    res_title = str(item.get("trackName") or "").lower()
    res_artist = str(item.get("artistName") or "").lower()
    if not res_title or not item.get("artworkUrl100"):
        return False

    t_tokens = _norm_lookup_tokens(clean_title)
    res_t_tokens = set(_norm_lookup_tokens(res_title))
    if not t_tokens:
        return False

    title_hits = sum(1 for tok in t_tokens if tok in res_t_tokens)
    if title_hits < max(1, len(t_tokens) // 2 + (1 if len(t_tokens) == 1 else 0)):
        if clean_title.lower() not in res_title and res_title not in clean_title.lower():
            return False

    a_tokens = _norm_lookup_tokens(clean_artist)
    if a_tokens:
        res_a_tokens = set(_norm_lookup_tokens(res_artist))
        if not any(tok in res_a_tokens for tok in a_tokens) and clean_artist.lower() not in res_artist:
            return False

    return True


def fetch_itunes_cover_bytes(
    artist: str,
    title: str,
    timeout: float = 4.0,
) -> Optional[Tuple[bytes, str]]:
    """
    Ищет официальную обложку трека в открытом iTunes Search API (без ключей и токенов),
    как это делает официальный клиент Telegram, и возвращает (bytes, mime) размером 300x300.
    """
    clean_artist, clean_title = clean_music_query(artist, title)
    if not clean_title or len(clean_title) < 2:
        return None

    term = f"{clean_artist} {clean_title}".strip() if clean_artist else clean_title
    search_url = (
        "https://itunes.apple.com/search?"
        + urllib.parse.urlencode({"term": term, "media": "music", "entity": "song", "limit": "5"})
    )
    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": "BahonIQMusic/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None

    results = payload.get("results") or []
    chosen_url = ""
    for item in results:
        if isinstance(item, dict) and _itunes_result_matches(clean_artist, clean_title, item):
            art_url = str(item.get("artworkUrl100") or "").strip()
            if art_url:
                chosen_url = art_url.replace("100x100bb", "300x300bb")
                break

    if not chosen_url:
        return None

    try:
        img_req = urllib.request.Request(chosen_url, headers={"User-Agent": "BahonIQMusic/1.0"})
        with urllib.request.urlopen(img_req, timeout=timeout) as img_resp:
            if img_resp.status != 200:
                return None
            raw_img = img_resp.read(MAX_COVER_BYTES + 1)
        return validate_image_bytes(raw_img)
    except Exception:
        return None
