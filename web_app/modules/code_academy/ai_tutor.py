"""Local Ollama educational assistant, without code execution or file mutation."""
import json
import urllib.request
import urllib.error
from .mentor_core import build_messages

URL = 'http://127.0.0.1:11434/api/chat'


def ask_tutor(question, filename='', code='', model='qwen2.5:3b', timeout=180,
              mode='hint', context=None, history=()):
    if not 10 <= int(timeout) <= 900:
        raise ValueError('Ожидание должно быть от 10 до 900 секунд')
    if len(question) > 4000:
        raise ValueError('Вопрос слишком длинный')
    context = dict(context or {})
    context.setdefault('file', filename)
    context.setdefault('code', code)

    messages = build_messages(question, mode, context, history)

    # 1. Первичный вызов через Google Gemini с автоматическим тихим Fallback
    try:
        from ai_service import generate_text
        system_inst = messages[0]['content'] if messages and messages[0].get('role') == 'system' else ''
        user_prompt_parts = []
        for m in messages[1:]:
            role_prefix = "Ученик: " if m.get('role') == 'user' else "Наставник: "
            user_prompt_parts.append(f"{role_prefix}{m.get('content')}")
        full_user_prompt = "\n\n".join(user_prompt_parts) if user_prompt_parts else question

        answer = generate_text(
            prompt=full_user_prompt,
            system_instruction=system_inst,
            temperature=0.3,
            timeout=timeout,
        )
        if answer and str(answer).strip():
            return str(answer).strip()
    except Exception:
        pass

    # 2. Тихий резервный вызов локальной Ollama
    payload = {'model': model, 'stream': False,
               'messages': messages,
               'options': {'temperature': 0.3, 'num_predict': 900, 'num_ctx': 8192}}
    req = urllib.request.Request(URL, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=int(timeout)) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError('Нет ответа ИИ-сервера. Проверь подключение к интернету или запуск Ollama.') from exc
    answer = data.get('message', {}).get('content', '').strip()
    if not answer:
        raise RuntimeError('ИИ вернул пустой ответ.')
    return answer
