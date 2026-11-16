"""Educational AI mentor: Gemini first, local Ollama as fallback (no code execution or file mutation)."""
import logging

from .mentor_core import build_messages

LOGGER = logging.getLogger("bahoniq.ai_tutor")
PROVIDER_LABELS = {"gemini": "BahonIQ AI", "ollama": "BahonIQ AI (резерв)"}


def ask_tutor_detailed(question, filename='', code='', model='', timeout=180,
                       mode='hint', context=None, history=()):
    """Return (answer, provider). provider is 'gemini' or 'ollama'."""
    if not 10 <= int(timeout) <= 900:
        raise ValueError('Ожидание должно быть от 10 до 900 секунд')
    if len(question) > 4000:
        raise ValueError('Вопрос слишком длинный')
    context = dict(context or {})
    context.setdefault('file', filename)
    context.setdefault('code', code)
    messages = build_messages(question, mode, context, history)

    from ai_service import generate_text
    system_inst = messages[0]['content'] if messages and messages[0].get('role') == 'system' else ''
    parts = []
    for m in messages[1:]:
        prefix = 'Ученик: ' if m.get('role') == 'user' else 'Наставник: '
        parts.append(prefix + str(m.get('content')))
    prompt = '\n\n'.join(parts) if parts else question
    try:
        answer, provider = generate_text(prompt=prompt, system_instruction=system_inst,
                                         temperature=0.3, timeout=int(timeout),
                                         return_provider=True, ollama_model=(model or '').strip())
    except Exception as exc:
        LOGGER.error('AI mentor failed: %s', exc)
        raise RuntimeError('ИИ недоступен: Gemini не ответил, а локальная Ollama вернула ошибку. '
                           'Проверьте GEMINI_API_KEY, интернет и запуск Ollama. Детали: %s' % exc) from exc
    answer = str(answer or '').strip()
    if not answer:
        raise RuntimeError('ИИ вернул пустой ответ.')
    return answer, provider


def ask_tutor(*args, **kwargs):
    """Backward-compatible wrapper returning only the answer text."""
    return ask_tutor_detailed(*args, **kwargs)[0]


def ask_tutor_stream(question, filename='', code='', model='', timeout=180,
                     mode='hint', context=None, history=()):
    """Потоковая генерация ответа наставника (SSE)."""
    import json
    if not 10 <= int(timeout) <= 900:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Ожидание должно быть от 10 до 900 секунд'}, ensure_ascii=False)}\n\n"
        return
    if len(question) > 4000:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Вопрос слишком длинный'}, ensure_ascii=False)}\n\n"
        return
    context = dict(context or {})
    context.setdefault('file', filename)
    context.setdefault('code', code)
    messages = build_messages(question, mode, context, history)

    from ai_service import generate_text_stream
    system_inst = messages[0]['content'] if messages and messages[0].get('role') == 'system' else ''
    parts = []
    for m in messages[1:]:
        prefix = 'Ученик: ' if m.get('role') == 'user' else 'Наставник: '
        parts.append(prefix + str(m.get('content')))
    prompt = '\n\n'.join(parts) if parts else question

    chunks = []
    try:
        stream = generate_text_stream(
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.3,
            timeout=int(timeout),
            ollama_model=(model or '').strip(),
        )
        for chunk in stream:
            if chunk:
                chunks.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"

        full_answer = "".join(chunks).strip()
        yield f"data: {json.dumps({'type': 'done', 'answer': full_answer, 'provider': 'gemini', 'provider_label': 'BahonIQ AI'}, ensure_ascii=False)}\n\n"
    except Exception as exc:
        LOGGER.error('AI mentor stream failed: %s', exc)
        yield f"data: {json.dumps({'type': 'error', 'error': f'ИИ временно недоступен: {exc}'}, ensure_ascii=False)}\n\n"
