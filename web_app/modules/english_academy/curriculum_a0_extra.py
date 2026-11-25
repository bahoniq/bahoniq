# -*- coding: utf-8 -*-
"""Дополнительные учебные уроки уровня A0 (с нуля, 5+ упражнений в каждом)."""

from __future__ import annotations


def _ex_bundle(prefix: str, topic_hint: str, items: list[dict]) -> list[dict]:
    """Гарантирует уникальные ID и единый формат упражнений."""
    out = []
    for idx, item in enumerate(items, start=1):
        row = dict(item)
        row.setdefault("id", f"{prefix}-ex{idx}")
        row.setdefault("hint", f"Опора: {topic_hint}")
        out.append(row)
    return out


A0_EXTRA_LESSONS: list[dict] = [
    {
        "id": "a0-l6",
        "kind": "lesson",
        "title": "Приветствия, знакомство и вежливые фразы",
        "skill_focus": ["speaking", "listening", "vocabulary"],
        "estimated_minutes": 12,
        "showcase": [
            {"en": "Hello! Nice to meet you. — Nice to meet you too!", "ru": "Привет! Приятно познакомиться. — Мне тоже!", "speak": "Hello! Nice to meet you."},
            {"en": "Good morning / Good afternoon / Good evening", "ru": "Вежливые приветствия по времени суток: утро, день, вечер.", "speak": "Good morning. Good afternoon. Good evening."},
        ],
        "simple_explanation": "Первые слова в любой стране — приветствие и знакомство. Запомните связку: Good morning (доброе утро), Good afternoon (добрый день), Good evening (добрый вечер), Please (пожалуйста) и Thank you (спасибо). Чтобы представить себя, скажите: My name is ... (Меня зовут ...).",
        "rule_name": "Базовый этикет приветствия и знакомства",
        "examples": [
            {"en": "Good morning! My name is Aidar.", "ipa": "/ɡʊd ˈmɔːnɪŋ maɪ neɪm ɪz ˈaɪdɑː/", "ru_hint": "гуд монин май нэйм из айдар", "ru": "Доброе утро! Меня зовут Айдар."},
            {"en": "How are you? — I am fine, thank you.", "ipa": "/haʊ ɑː juː — aɪ æm faɪn θæŋk juː/", "ru_hint": "хау ар ю — ай эм файн сэнк ю", "ru": "Как дела? — У меня всё хорошо, спасибо."},
        ],
        "vocab": [
            {"word": "hello", "ipa": "/həˈləʊ/", "ru_hint": "хэлоу", "ru": "привет, здравствуйте", "example": "Hello, friend!", "topic": "Общение"},
            {"word": "morning", "ipa": "/ˈmɔːnɪŋ/", "ru_hint": "монин", "ru": "утро", "example": "Good morning!", "topic": "Время"},
            {"word": "please", "ipa": "/pliːz/", "ru_hint": "плиз", "ru": "пожалуйста", "example": "Help me, please.", "topic": "Общение"},
            {"word": "fine", "ipa": "/faɪn/", "ru_hint": "файн", "ru": "хорошо, в порядке", "example": "I am fine.", "topic": "Общение"},
        ],
        "exercises": _ex_bundle("a0-l6", "My name is..., Good morning, Thank you", [
            {"type": "choice", "skill": "vocabulary", "prompt": "Как сказать «Доброе утро» по-английски?", "options": ["Good morning", "Good night", "Good bye"], "answer": "Good morning", "explanation": "Morning — утро, Good morning — доброе утро."},
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте фразы с переводом:", "pairs": [{"left": "Hello", "right": "Привет"}, {"left": "Thank you", "right": "Спасибо"}, {"left": "Please", "right": "Пожалуйста"}, {"left": "Goodbye", "right": "До свидания"}], "explanation": "Базовые вежливые слова пригодятся в любом диалоге."},
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите фразу знакомства «Приятно познакомиться»:", "words": ["you.", "to", "Nice", "meet"], "answer": "Nice to meet you.", "accepted": ["Nice to meet you.", "Nice to meet you"], "explanation": "Устойчивая фраза: Nice to meet you."},
            {"type": "fill_blank", "skill": "writing", "prompt": "Заполните пропуск: My ___ is Dana. (Меня зовут Дана)", "answer": "name", "accepted": ["name"], "explanation": "Имя — name: My name is Dana."},
            {"type": "mini_dialogue", "skill": "speaking", "context": "Вы встретили коллегу утром.", "speaker_line": "Good morning! How are you?", "speaker_ru": "Доброе утро! Как дела?", "prompt": "Выберите вежливый ответ:", "options": ["I am fine, thank you!", "My name is morning.", "Yes, I have."], "answer": "I am fine, thank you!", "explanation": "Естественный ответ на How are you? — I am fine, thank you!"},
        ]),
    },
    {
        "id": "a0-l7",
        "kind": "lesson",
        "title": "Числа от 0 до 100 и возраст",
        "skill_focus": ["vocabulary", "listening", "writing"],
        "estimated_minutes": 12,
        "showcase": [
            {"en": "one (1), two (2), three (3), four (4), five (5)", "ru": "Первые пять цифр, которые нужно знать наизусть.", "speak": "one, two, three, four, five"},
            {"en": "ten (10), twenty (20), thirty (30), fifty (50), one hundred (100)", "ru": "Десятки заканчиваются на -ty: twenty, thirty, forty, fifty.", "speak": "ten, twenty, thirty, fifty, one hundred"},
        ],
        "simple_explanation": "Числа от 13 до 19 заканчиваются на -teen (thirteen, fifteen), а десятки 20–90 — на -ty (twenty, thirty, fifty). Чтобы сказать свой возраст, по-английски используют глагол быть: I am twenty-five (Мне 25 лет), а не «у меня есть».",
        "rule_name": "Количественные числительные 0–100 и возраст с am/is/are",
        "examples": [
            {"en": "I am twenty years old.", "ipa": "/aɪ æm ˈtwenti jɪəz əʊld/", "ru_hint": "ай эм туэнти иэз оулд", "ru": "Мне двадцать лет."},
            {"en": "Room number ten.", "ipa": "/ruːm ˈnʌmbə ten/", "ru_hint": "рум намбэ тэн", "ru": "Комната номер десять."},
        ],
        "vocab": [
            {"word": "number", "ipa": "/ˈnʌmbə/", "ru_hint": "намбэ", "ru": "число, номер", "example": "Phone number.", "topic": "Числа и время"},
            {"word": "ten", "ipa": "/ten/", "ru_hint": "тэн", "ru": "десять", "example": "Ten minutes.", "topic": "Числа и время"},
            {"word": "twenty", "ipa": "/ˈtwenti/", "ru_hint": "туэнти", "ru": "двадцать", "example": "Twenty dollars.", "topic": "Числа и время"},
            {"word": "hundred", "ipa": "/ˈhʌndrəd/", "ru_hint": "хандрэд", "ru": "сто, сотня", "example": "One hundred.", "topic": "Числа и время"},
        ],
        "exercises": _ex_bundle("a0-l7", "суффиксы -teen (13-19) и -ty (20-90)", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте цифры и английские слова:", "pairs": [{"left": "3", "right": "three"}, {"left": "7", "right": "seven"}, {"left": "12", "right": "twelve"}, {"left": "50", "right": "fifty"}], "explanation": "Эти числа встречаются в ценах, номерах и времени."},
            {"type": "choice", "skill": "vocabulary", "prompt": "Какое число означает слово «thirty»?", "options": ["30", "13", "3"], "answer": "30", "explanation": "Суффикс -ty всегда обозначает десятки: thirty = 30 (а 13 — thirteen)."},
            {"type": "fill_blank", "skill": "grammar", "prompt": "Как сказать «Мне 20 лет» (вставьте связку): I ___ twenty.", "answer": "am", "accepted": ["am"], "explanation": "Возраст в английском выражается через am / is / are: I am twenty."},
            {"type": "listening_qa", "skill": "listening", "audio_text": "My office is room number fifteen.", "prompt": "Прослушайте фразу. Какой номер кабинета назван?", "options": ["15 (fifteen)", "50 (fifty)", "5 (five)"], "answer": "15 (fifteen)", "explanation": "Прозвучало fifteen — 15."},
            {"type": "translate_ru_en", "skill": "writing", "prompt": "Переведите: «Десять книг» (используйте ten и books)", "answer": "ten books", "accepted": ["ten books", "Ten books", "Ten books."], "explanation": "После числительного больше 1 существительное получает -s: ten books."},
        ]),
    },
    {
        "id": "a0-l8",
        "kind": "lesson",
        "title": "Время, часы и части дня",
        "skill_focus": ["vocabulary", "listening", "speaking"],
        "estimated_minutes": 12,
        "showcase": [
            {"en": "What time is it? — It is nine o'clock.", "ru": "Который час? — Девять часов ровно.", "speak": "What time is it? It is nine o'clock."},
            {"en": "in the morning | in the afternoon | at night", "ru": "Утром, днём — с предлогом in the, а ночью — at night.", "speak": "in the morning, in the afternoon, at night"},
        ],
        "simple_explanation": "Чтобы спросить «Который час?», скажите What time is it?. Если время ровное, добавьте o'clock: It is five o'clock (5 часов). Для минут можно просто назвать два числа подряд: 9:30 -> nine thirty (очень удобно в разговорной речи!).",
        "rule_name": "Время на часах и предлоги времени суток",
        "examples": [
            {"en": "It is eight thirty.", "ipa": "/ɪt ɪz eɪt ˈθɜːti/", "ru_hint": "ит из эйт сёти", "ru": "Сейчас восемь тридцать."},
            {"en": "I drink tea in the morning.", "ipa": "/aɪ drɪŋk tiː ɪn ðə ˈmɔːnɪŋ/", "ru_hint": "ай дринк ти ин зэ монин", "ru": "Я пью чай утром."},
        ],
        "vocab": [
            {"word": "clock", "ipa": "/klɒk/", "ru_hint": "клок", "ru": "часы (настенные/настольные)", "example": "Nine o'clock.", "topic": "Числа и время"},
            {"word": "minute", "ipa": "/ˈmɪnɪt/", "ru_hint": "минит", "ru": "минута", "example": "Five minutes.", "topic": "Числа и время"},
            {"word": "evening", "ipa": "/ˈiːvnɪŋ/", "ru_hint": "ивнин", "ru": "вечер", "example": "In the evening.", "topic": "Числа и время"},
            {"word": "night", "ipa": "/naɪt/", "ru_hint": "найт", "ru": "ночь", "example": "At night.", "topic": "Числа и время"},
        ],
        "exercises": _ex_bundle("a0-l8", "What time is it? / It is ... o'clock", [
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите вопрос «Который час?»:", "words": ["is", "time", "it?", "What"], "answer": "What time is it?", "accepted": ["What time is it?", "What time is it"], "explanation": "Стандартный вопрос о времени: What time is it?"},
            {"type": "choice", "skill": "grammar", "prompt": "Какой предлог используется со словом night («ночью»)?", "options": ["at night", "in night", "on night"], "answer": "at night", "explanation": "Устойчивое сочетание: at night (ночью)."},
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте время и фразы:", "pairs": [{"left": "08:00", "right": "eight o'clock"}, {"left": "09:30", "right": "nine thirty"}, {"left": "утром", "right": "in the morning"}, {"left": "вечером", "right": "in the evening"}], "explanation": "Цифровой формат «час + минуты» (nine thirty) — самый простой и понятный."},
            {"type": "fill_blank", "skill": "writing", "prompt": "Заполните пропуск: It is seven ___. (7 часов ровно)", "answer": "o'clock", "accepted": ["o'clock", "oclock"], "explanation": "Для ровного часа используется o'clock."},
            {"type": "listening_qa", "skill": "listening", "audio_text": "The bus arrives at ten fifteen in the morning.", "prompt": "Во сколько прибывает автобус?", "options": ["В 10:15 утра", "В 10:50 вечера", "В 12:15 дня"], "answer": "В 10:15 утра", "explanation": "Прозвучало: ten fifteen in the morning (10:15 утра)."},
        ]),
    },
    {
        "id": "a0-l9",
        "kind": "lesson",
        "title": "Семья и близкие люди",
        "skill_focus": ["vocabulary", "reading", "writing"],
        "estimated_minutes": 12,
        "showcase": [
            {"en": "mother (mom), father (dad), sister, brother", "ru": "Мама, папа, сестра, брат — основные слова о семье.", "speak": "mother, father, sister, brother"},
            {"en": "This is my family. My sister is a student.", "ru": "Это моя семья. Моя сестра — студентка.", "speak": "This is my family. My sister is a student."},
        ],
        "simple_explanation": "Чтобы рассказать о своей семье, запомните базовые слова: mother (мама, коротко mom), father (папа, коротко dad), brother (брат), sister (сестра), son (сын), daughter (дочь), friend (друг). Перед родственником ставим my (мой/моя) или his/her (его/её).",
        "rule_name": "Лексика семьи и связка is/are с родственниками",
        "examples": [
            {"en": "My mother is a teacher.", "ipa": "/maɪ ˈmʌðər ɪz ə ˈtiːtʃə/", "ru_hint": "май мазэр из э тичэ", "ru": "Моя мама — учитель."},
            {"en": "My parents are at home.", "ipa": "/maɪ ˈpeərənts ɑːr æt həʊm/", "ru_hint": "май пэрэнтс ар эт хоум", "ru": "Мои родители дома."},
        ],
        "vocab": [
            {"word": "family", "ipa": "/ˈfæməli/", "ru_hint": "фэмили", "ru": "семья", "example": "A big family.", "topic": "Жизнь и семья"},
            {"word": "mother", "ipa": "/ˈmʌðə/", "ru_hint": "мазэ", "ru": "мать, мама", "example": "My mother.", "topic": "Жизнь и семья"},
            {"word": "father", "ipa": "/ˈfɑːðə/", "ru_hint": "фазэ", "ru": "отец, папа", "example": "My father.", "topic": "Жизнь и семья"},
            {"word": "friend", "ipa": "/frend/", "ru_hint": "фрэнд", "ru": "друг, подруга", "example": "My best friend.", "topic": "Жизнь и семья"},
        ],
        "exercises": _ex_bundle("a0-l9", "mother, father, brother, sister, parents", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте слова о семье:", "pairs": [{"left": "mother", "right": "мама"}, {"left": "father", "right": "папа"}, {"left": "brother", "right": "брат"}, {"left": "sister", "right": "сестра"}], "explanation": "Базовые слова семьи."},
            {"type": "choice", "skill": "grammar", "prompt": "Выберите верную связку: «My parents ___ at home.» (Мои родители дома)", "options": ["are", "is", "am"], "answer": "are", "explanation": "Parents (родители) — множественное число, поэтому нужна связка are."},
            {"type": "fill_blank", "skill": "writing", "prompt": "Вставьте слово «друг»: He is my best ___.", "answer": "friend", "accepted": ["friend"], "explanation": "Друг — friend."},
            {"type": "reading_qa", "skill": "reading", "passage": "Hi! My name is Arman. My family is small. My mother is a doctor, and my father is an engineer. My sister Aigerim is a student.", "prompt": "Кем работает мама Армана?", "options": ["Врачом (a doctor)", "Учителем (a teacher)", "Инженером (an engineer)"], "answer": "Врачом (a doctor)", "explanation": "В тексте: «My mother is a doctor»."},
            {"type": "translate_ru_en", "skill": "writing", "prompt": "Переведите: «Это моя семья.»", "answer": "This is my family.", "accepted": ["This is my family.", "This is my family"], "explanation": "This is my family."},
        ]),
    },
    {
        "id": "a0-l10",
        "kind": "lesson",
        "title": "Предметы вокруг нас: стол, книга, сумка, ключи",
        "skill_focus": ["vocabulary", "grammar", "reading"],
        "estimated_minutes": 11,
        "showcase": [
            {"en": "this pen (эта ручка рядом) | that bag (та сумка дальше)", "ru": "this — предмет рядом с вами; that — предмет подальше.", "speak": "this pen, that bag"},
            {"en": "a table, a chair, a key, a bag, a cup", "ru": "Бытовые предметы, которые окружают нас каждый день.", "speak": "a table, a chair, a key, a bag, a cup"},
        ],
        "simple_explanation": "Чтобы указать на предмет рядом с вами, говорите This is... («Это вот...»): This is a key (Это ключ). Если предмет лежит в другом конце комнаты, говорите That is... («Вон то...»): That is a table (Вон то — стол). Когда предметов несколько, вместо a ставим окончание -s: keys, pens, bags.",
        "rule_name": "Указательные слова this / that и бытовые существительные",
        "examples": [
            {"en": "This is my bag.", "ipa": "/ðɪs ɪz maɪ bæɡ/", "ru_hint": "зис из май бэг", "ru": "Это моя сумка."},
            {"en": "Where are my keys?", "ipa": "/weər ɑː maɪ kiːz/", "ru_hint": "уэар ар май киз", "ru": "Где мои ключи?"},
        ],
        "vocab": [
            {"word": "table", "ipa": "/ˈteɪbl/", "ru_hint": "тэйбл", "ru": "стол", "example": "On the table.", "topic": "Дом"},
            {"word": "chair", "ipa": "/tʃeə/", "ru_hint": "чэа", "ru": "стул", "example": "Sit on a chair.", "topic": "Дом"},
            {"word": "bag", "ipa": "/bæɡ/", "ru_hint": "бэг", "ru": "сумка, рюкзак", "example": "My black bag.", "topic": "Повседневное"},
            {"word": "key", "ipa": "/kiː/", "ru_hint": "ки", "ru": "ключ", "example": "House key.", "topic": "Повседневное"},
        ],
        "exercises": _ex_bundle("a0-l10", "this (рядом) / that (далеко) / -s (много)", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте предметы с переводом:", "pairs": [{"left": "table", "right": "стол"}, {"left": "chair", "right": "стул"}, {"left": "bag", "right": "сумка"}, {"left": "key", "right": "ключ"}], "explanation": "Эти предметы встречаются дома и в офисе каждый день."},
            {"type": "choice", "skill": "grammar", "prompt": "Вы держите ручку прямо в руке. Как сказать «Это ручка»?", "options": ["This is a pen.", "That are a pen.", "These is a pen."], "answer": "This is a pen.", "explanation": "Для одного предмета рядом используется This is..."},
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите вопрос «Где мои ключи?»:", "words": ["my", "keys?", "Where", "are"], "answer": "Where are my keys?", "accepted": ["Where are my keys?", "Where are my keys"], "explanation": "Ключей несколько (keys), поэтому используем are: Where are my keys?"},
            {"type": "fill_blank", "skill": "writing", "prompt": "Поставьте во множественное число (много сумок): two ___", "answer": "bags", "accepted": ["bags"], "explanation": "К слову bag добавляем окончание -s: bags."},
            {"type": "translate_ru_en", "skill": "writing", "prompt": "Переведите: «Это моя сумка.»", "answer": "This is my bag.", "accepted": ["This is my bag.", "This is my bag"], "explanation": "This is my bag."},
        ]),
    },
    {
        "id": "a0-l11",
        "kind": "lesson",
        "title": "Цвета и простые описания (big, small, new, old)",
        "skill_focus": ["vocabulary", "grammar", "writing"],
        "estimated_minutes": 11,
        "showcase": [
            {"en": "a red car | a big house | a new phone", "ru": "В английском прилагательное ВСЕГДА ставится ПЕРЕД существительным!", "speak": "a red car, a big house, a new phone"},
            {"en": "black, white, red, blue, green, yellow", "ru": "Основные цвета, которые сразу оживляют речь.", "speak": "black, white, red, blue, green, yellow"},
        ],
        "simple_explanation": "В английском описание (прилагательное) никогда не меняется по родам и числам: new одинаково значит «новый», «новая», «новое» и «новые». И оно всегда стоит ПЕРЕД предметом: a green bag (зелёная сумка), big houses (большие дома).",
        "rule_name": "Прилагательные цвета и размера (позиция перед существительным)",
        "examples": [
            {"en": "I have a black phone.", "ipa": "/aɪ hæv ə blæk fəʊn/", "ru_hint": "ай хэв э блэк фоун", "ru": "У меня чёрный телефон."},
            {"en": "This room is very light.", "ipa": "/ðɪs ruːm ɪz ˈveri laɪt/", "ru_hint": "зис рум из вэри лайт", "ru": "Эта комната очень светлая."},
        ],
        "vocab": [
            {"word": "red", "ipa": "/red/", "ru_hint": "рэд", "ru": "красный", "example": "A red apple.", "topic": "Цвета и описание"},
            {"word": "blue", "ipa": "/bluː/", "ru_hint": "блу", "ru": "синий, голубой", "example": "Blue sky.", "topic": "Цвета и описание"},
            {"word": "green", "ipa": "/ɡriːn/", "ru_hint": "грин", "ru": "зелёный", "example": "Green tea.", "topic": "Цвета и описание"},
            {"word": "new", "ipa": "/njuː/", "ru_hint": "нью", "ru": "новый", "example": "A new laptop.", "topic": "Цвета и описание"},
        ],
        "exercises": _ex_bundle("a0-l11", "прилагательное перед предметом: a red bag", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте цвета:", "pairs": [{"left": "red", "right": "красный"}, {"left": "blue", "right": "синий"}, {"left": "green", "right": "зелёный"}, {"left": "black", "right": "чёрный"}], "explanation": "Основные цвета уровня A0."},
            {"type": "choice", "skill": "grammar", "prompt": "Как правильно сказать «новая книга»?", "options": ["a new book", "a book new", "new a book"], "answer": "a new book", "explanation": "Артикль a + прилагательное (new) + предмет (book)."},
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите предложение «Это большая комната»:", "words": ["big", "is", "room.", "This", "a"], "answer": "This is a big room.", "accepted": ["This is a big room.", "This is a big room"], "explanation": "This is + a + big + room."},
            {"type": "fill_blank", "skill": "vocabulary", "prompt": "Вставьте слово «зелёный» (зелёный чай): ___ tea", "answer": "green", "accepted": ["green", "Green"], "explanation": "Зелёный чай — green tea."},
            {"type": "translate_ru_en", "skill": "writing", "prompt": "Переведите: «Мой телефон новый.»", "answer": "My phone is new.", "accepted": ["My phone is new.", "My phone is new"], "explanation": "My phone is new."},
        ]),
    },
    {
        "id": "a0-l12",
        "kind": "lesson",
        "title": "Базовые вопросы: Who? What? Where? How?",
        "skill_focus": ["grammar", "speaking", "reading"],
        "estimated_minutes": 12,
        "showcase": [
            {"en": "Who is this? | What is this? | Where is it? | How are you?", "ru": "Четыре главных вопросительных слова для старта общения.", "speak": "Who is this? What is this? Where is it? How are you?"},
        ],
        "simple_explanation": "С четырьмя словами вы уже можете спросить почти о чём угодно на базовом уровне: Who (Кто?), What (Что / Какой?), Where (Где / Куда?), How (Как?). Они всегда ставятся в самое начало вопроса перед связкой is / are.",
        "rule_name": "Базовые специальные вопросы с глаголом be",
        "examples": [
            {"en": "Where is the bus stop?", "ipa": "/weər ɪz ðə bʌs stɒp/", "ru_hint": "уэар из зэ бас стоп", "ru": "Где автобусная остановка?"},
            {"en": "Who is your teacher?", "ipa": "/huː ɪz jɔː ˈtiːtʃə/", "ru_hint": "ху из ё тичэ", "ru": "Кто твой преподаватель?"},
        ],
        "vocab": [
            {"word": "who", "ipa": "/huː/", "ru_hint": "ху", "ru": "кто", "example": "Who is he?", "topic": "Вопросы"},
            {"word": "what", "ipa": "/wɒt/", "ru_hint": "уот", "ru": "что, какой", "example": "What is your name?", "topic": "Вопросы"},
            {"word": "how", "ipa": "/haʊ/", "ru_hint": "хау", "ru": "как", "example": "How are you?", "topic": "Вопросы"},
        ],
        "exercises": _ex_bundle("a0-l12", "Who / What / Where / How + is/are", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте вопросительные слова:", "pairs": [{"left": "Who?", "right": "Кто?"}, {"left": "What?", "right": "Что?"}, {"left": "Where?", "right": "Где?"}, {"left": "How?", "right": "Как?"}], "explanation": "Четыре главных вопросительных слова."},
            {"type": "fill_blank", "skill": "grammar", "prompt": "Вставьте вопросительное слово («Где книга?»): ___ is the book?", "answer": "Where", "accepted": ["Where", "where"], "explanation": "«Где?» — Where."},
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите вопрос «Как тебя зовут?»:", "words": ["name?", "your", "is", "What"], "answer": "What is your name?", "accepted": ["What is your name?", "What is your name"], "explanation": "What + is + your name?"},
            {"type": "choice", "skill": "grammar", "prompt": "Выберите правильный вопрос о человеке («Кто это?»):", "options": ["Who is this?", "What is this?", "Where is this?"], "answer": "Who is this?", "explanation": "О людях спрашиваем Who (Кто?)."},
            {"type": "mini_dialogue", "skill": "speaking", "context": "Вы ищете кафе в незнакомом здании.", "speaker_line": "Can I help you?", "speaker_ru": "Могу я вам помочь?", "prompt": "Как спросить «Где кафе?»:", "options": ["Where is the cafe?", "Who is the cafe?", "How is the cafe?"], "answer": "Where is the cafe?", "explanation": "Местоположение спрашиваем через Where is ...?"},
        ]),
    },
    {
        "id": "a0-l13",
        "kind": "lesson",
        "title": "Простые глаголы действий и повелительное наклонение",
        "skill_focus": ["vocabulary", "grammar", "listening"],
        "estimated_minutes": 11,
        "showcase": [
            {"en": "Open the door! | Close the window. | Don't worry!", "ru": "Просьба или команда — просто глагол в начальной форме. Запрет — Don't + глагол.", "speak": "Open the door. Close the window. Don't worry."},
            {"en": "read, write, listen, speak, open, close, go, come", "ru": "Первые 8 глаголов, которые встречаются в каждом задании.", "speak": "read, write, listen, speak"},
        ],
        "simple_explanation": "Чтобы попросить кого-то что-то сделать, в английском достаточно назвать сам глагол без всяких частиц: Read! (Читай!), Listen! (Слушай!), Open the book, please (Открой книгу, пожалуйста). А чтобы сказать «Не делай этого», просто поставьте в начало Don't: Don't open! (Не открывай!).",
        "rule_name": "Повелительное наклонение (Imperative) и базовые глаголы",
        "examples": [
            {"en": "Please listen carefully.", "ipa": "/pliːz ˈlɪsn ˈkeəfəli/", "ru_hint": "плиз лисн кэафули", "ru": "Пожалуйста, слушай внимательно."},
            {"en": "Don't forget your key.", "ipa": "/dəʊnt fəˈɡet jɔː kiː/", "ru_hint": "донт фогэт ё ки", "ru": "Не забудь свой ключ."},
        ],
        "vocab": [
            {"word": "open", "ipa": "/ˈəʊpən/", "ru_hint": "оупэн", "ru": "открывать", "example": "Open the door.", "topic": "Базовые глаголы"},
            {"word": "close", "ipa": "/kləʊz/", "ru_hint": "клоуз", "ru": "закрывать", "example": "Close the file.", "topic": "Базовые глаголы"},
            {"word": "listen", "ipa": "/ˈlɪsn/", "ru_hint": "лисн", "ru": "слушать", "example": "Listen to me.", "topic": "Базовые глаголы"},
            {"word": "write", "ipa": "/raɪt/", "ru_hint": "райт", "ru": "писать", "example": "Write your name.", "topic": "Базовые глаголы"},
        ],
        "exercises": _ex_bundle("a0-l13", "глагол для просьбы / Don't для запрета", [
            {"type": "match", "skill": "vocabulary", "prompt": "Сопоставьте глаголы с переводом:", "pairs": [{"left": "open", "right": "открывать"}, {"left": "close", "right": "закрывать"}, {"left": "listen", "right": "слушать"}, {"left": "write", "right": "писать"}], "explanation": "Основные команды на уроке и в быту."},
            {"type": "choice", "skill": "grammar", "prompt": "Как вежливо попросить «Откройте дверь, пожалуйста»?", "options": ["Open the door, please.", "To open the door, please.", "Opening the door, please."], "answer": "Open the door, please.", "explanation": "Просьба начинается с обычной формы глагола без to: Open..."},
            {"type": "fill_blank", "skill": "grammar", "prompt": "Скажите «Не волнуйся!»: ___ worry!", "answer": "Don't", "accepted": ["Don't", "Do not", "don't"], "explanation": "Отрицательная просьба/запрет начинается с Don't."},
            {"type": "word_order", "skill": "grammar", "prompt": "Соберите фразу «Напишите своё имя»:", "words": ["name.", "your", "Write"], "answer": "Write your name.", "accepted": ["Write your name.", "Write your name"], "explanation": "Write + your name."},
            {"type": "listening_qa", "skill": "listening", "audio_text": "Please close the window and open your book.", "prompt": "Что просит сделать диктор?", "options": ["Закрыть окно и открыть книгу", "Открыть окно и закрыть дверь", "Написать имя в тетради"], "answer": "Закрыть окно и открыть книгу", "explanation": "Прозвучало: close the window and open your book."},
        ]),
    },
]
