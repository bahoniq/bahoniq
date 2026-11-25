# -*- coding: utf-8 -*-
"""Учебный контент уровней A0 (Абсолютный ноль) и A1 (Базовый английский).

Каждый урок следует методике:
Показ -> Простое объяснение на русском -> Название правила -> Примеры с озвучкой ->
Упражнения с постепенным снятием поддержки -> Применение и проверка.
"""

from __future__ import annotations

LEVEL_A0 = {
    "id": "A0",
    "code": "A0",
    "title": "A0 — Абсолютный ноль",
    "subtitle": "Алфавит, звуки, правила чтения с нуля, первые слова и первые простые предложения",
    "cefr_goal": "Научиться уверенно читать простые английские слова, понимать разницу между буквой и звуком, узнавать базовую лексику на слух и строить первые утверждения, отрицания и вопросы с глаголом-связкой am / is / are.",
    "pass_exam_score": 80,
    "sections": [
        {
            "id": "a0-sec-1",
            "title": "Раздел 1. Буквы, звуки и чтение слогов",
            "description": "Снимаем страх перед английскими буквами: учимся видеть и озвучивать слова.",
            "lessons": [
                {
                    "id": "a0-l1",
                    "kind": "lesson",
                    "title": "Алфавит и главное отличие буквы от звука",
                    "skill_focus": ["reading", "listening"],
                    "estimated_minutes": 12,
                    "showcase": [
                        {"en": "A a — name [eɪ], sound [æ] in cat", "ru": "Буква называет себя «эй», но в простом слове cat читается как широкий звук «э».", "speak": "A. cat"},
                        {"en": "B b — [b] book, C c — [k] cup, D d — [d] desk", "ru": "Согласные B, D читаются почти как русские Б, Д (но кончик языка на бугорках над зубами).", "speak": "book, cup, desk"},
                        {"en": "E e — [e] pen, I i — [ɪ] sit, O o — [ɒ] box", "ru": "Краткие гласные в закрытом слоге звучат чётко и коротко.", "speak": "pen, sit, box"},
                    ],
                    "simple_explanation": "В русском языке мы почти всегда читаем букву так же, как она называется. В английском у каждой буквы есть «паспортное имя» в алфавите (например, A — «эй», I — «ай») и «рабочий звук» внутри слова (в слове cat буква A даёт звук [æ], а в слове sit буква I даёт короткий [ɪ]). Всего в английском алфавите 26 букв: 6 гласных букв (A, E, I, O, U, Y) и 20 согласных.",
                    "rule_name": "Английский алфавит (The Alphabet) и пара «Буква ≠ Звук»",
                    "examples": [
                        {"en": "cat", "ipa": "/kæt/", "ru_hint": "кэт", "ru": "кошка"},
                        {"en": "bed", "ipa": "/bed/", "ru_hint": "бэд", "ru": "кровать"},
                        {"en": "big", "ipa": "/bɪɡ/", "ru_hint": "биг", "ru": "большой"},
                        {"en": "dog", "ipa": "/dɒɡ/", "ru_hint": "дог", "ru": "собака"},
                        {"en": "bus", "ipa": "/bʌs/", "ru_hint": "бас", "ru": "автобус"},
                    ],
                    "vocab": [
                        {"word": "cat", "ipa": "/kæt/", "ru_hint": "кэт", "ru": "кошка", "example": "A black cat.", "topic": "Базовые слова"},
                        {"word": "bed", "ipa": "/bed/", "ru_hint": "бэд", "ru": "кровать", "example": "My bed is big.", "topic": "Дом"},
                        {"word": "big", "ipa": "/bɪɡ/", "ru_hint": "биг", "ru": "большой", "example": "A big dog.", "topic": "Описание"},
                        {"word": "dog", "ipa": "/dɒɡ/", "ru_hint": "дог", "ru": "собака", "example": "Good dog.", "topic": "Базовые слова"},
                        {"word": "bus", "ipa": "/bʌs/", "ru_hint": "бас", "ru": "автобус", "example": "A red bus.", "topic": "Транспорт"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l1-ex1",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Сколько всего букв в английском алфавите и почему слово «cat» не читается как «си-эй-ти»?",
                            "hint": "Вспомните разницу между названием буквы в алфавите и её рабочим звуком в слове.",
                            "options": [
                                "26 букв; внутри слова работают звуки букв, а не их алфавитные имена",
                                "33 буквы; каждая буква всегда читается только по алфавиту",
                                "20 букв; гласные в английском не произносятся",
                            ],
                            "answer": "26 букв; внутри слова работают звуки букв, а не их алфавитные имена",
                            "explanation": "В английском 26 букв. Имя буквы нужно, чтобы продиктовать слово по буквам, а внутри слова буквы передают звуки: c [k] + a [æ] + t [t] = cat."
                        },
                        {
                            "id": "a0-l1-ex2",
                            "type": "match",
                            "skill": "vocabulary",
                            "prompt": "Сопоставьте английские слова с переводом:",
                            "hint": "Опирайтесь на первые согласные звуки: b — б, d — д, c — к.",
                            "pairs": [
                                {"left": "cat", "right": "кошка"},
                                {"left": "bed", "right": "кровать"},
                                {"left": "dog", "right": "собака"},
                                {"left": "bus", "right": "автобус"},
                            ],
                            "explanation": "cat — кошка, bed — кровать, dog — собака, bus — автобус."
                        },
                        {
                            "id": "a0-l1-ex3",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Какой звук даёт буква «u» в коротком закрытом слове «bus» (автобус)?",
                            "options": ["Короткий звук [ʌ], близкий к «а» (бас)", "Долгий звук «ю» (бьюс)", "Звук «о» (бос)"],
                            "answer": "Короткий звук [ʌ], близкий к «а» (бас)",
                            "explanation": "В коротких закрытых словах (bus, cup, sun) буква U читается как краткий звук [ʌ], похожий на русский безударный «а»."
                        },
                        {
                            "id": "a0-l1-ex4",
                            "type": "dictation",
                            "skill": "listening",
                            "audio_text": "big dog",
                            "prompt": "Прослушайте фразу и напишите два английских слова («большая собака»):",
                            "answer": "big dog",
                            "accepted": ["big dog"],
                            "explanation": "Фраза звучит /bɪɡ dɒɡ/ и пишется big dog."
                        },
                        {
                            "id": "a0-l1-ex5",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Напишите по-английски одно слово: «автобус»",
                            "answer": "bus",
                            "accepted": ["bus", "a bus"],
                            "explanation": "Автобус по-английски — bus."
                        }
                    ]
                },
                {
                    "id": "a0-l2",
                    "kind": "lesson",
                    "title": "Открытый и закрытый слог. Немая буква «e»",
                    "skill_focus": ["reading", "vocabulary"],
                    "estimated_minutes": 14,
                    "showcase": [
                        {"en": "cap [kæp] → cape [keɪp]", "ru": "Добавили немую «e» в конец: сама она не звучит, но заставляет «a» читаться как в алфавите [eɪ].", "speak": "cap, cape"},
                        {"en": "sit [sɪt] → site [saɪt]", "ru": "Закрытый слог sit [ɪ] превращается в открытый site [aɪ].", "speak": "sit, site"},
                        {"en": "not [nɒt] → note [nəʊt]", "ru": "Короткое [ɒ] в not меняется на двугласный звук [əʊ] в note (заметка).", "speak": "not, note"},
                    ],
                    "simple_explanation": "Представьте, что согласная буква в конце слова (например, в слове name или sit) — это дверь. Если после гласной стоит согласная и больше ничего нет (sit, cap, not) — дверь закрыта, слог называется закрытым, и гласная звучит коротко. Но если на конце слова появляется буква «e» (name, take, home, time), сама буква «e» молчит (не читается!), зато «открывает дверь» предыдущей гласной — и та читается так же, как называется в алфавите!",
                    "rule_name": "Открытый/закрытый слог и немая «e» (Silent E)",
                    "examples": [
                        {"en": "name", "ipa": "/neɪm/", "ru_hint": "нэйм", "ru": "имя"},
                        {"en": "time", "ipa": "/taɪm/", "ru_hint": "тайм", "ru": "время"},
                        {"en": "home", "ipa": "/həʊm/", "ru_hint": "хоум", "ru": "дом (место, где живут)"},
                        {"en": "take", "ipa": "/teɪk/", "ru_hint": "тэйк", "ru": "брать, взять"},
                        {"en": "pen", "ipa": "/pen/", "ru_hint": "пэн", "ru": "ручка"},
                    ],
                    "vocab": [
                        {"word": "name", "ipa": "/neɪm/", "ru_hint": "нэйм", "ru": "имя", "example": "My name is Anna.", "topic": "Знакомство"},
                        {"word": "time", "ipa": "/taɪm/", "ru_hint": "тайм", "ru": "время", "example": "It is time.", "topic": "Время"},
                        {"word": "home", "ipa": "/həʊm/", "ru_hint": "хоум", "ru": "дом", "example": "I am at home.", "topic": "Дом"},
                        {"word": "take", "ipa": "/teɪk/", "ru_hint": "тэйк", "ru": "брать", "example": "Take a pen.", "topic": "Действия"},
                        {"word": "pen", "ipa": "/pen/", "ru_hint": "пэн", "ru": "ручка", "example": "A blue pen.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l2-ex1",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Как правильно читается слово «name» (имя) и почему?",
                            "hint": "Посмотрите на последнюю букву «e».",
                            "options": [
                                "«нэйм» — конечная «e» не читается, а буква «a» звучит как в алфавите [eɪ]",
                                "«наме» — читается каждая буква подряд",
                                "«нэм» — буква «a» читается коротко, как в слове cat",
                            ],
                            "answer": "«нэйм» — конечная «e» не читается, а буква «a» звучит как в алфавите [eɪ]",
                            "explanation": "Немая буква «e» в конце слова не произносится, но делает слог условно открытым: name -> /neɪm/."
                        },
                        {
                            "id": "a0-l2-ex2",
                            "type": "match",
                            "skill": "reading",
                            "prompt": "Соедините слово и его звучание:",
                            "pairs": [
                                {"left": "time", "right": "/taɪm/ (тайм — время)"},
                                {"left": "home", "right": "/həʊm/ (хоум — дом)"},
                                {"left": "pen", "right": "/pen/ (пэн — ручка)"},
                                {"left": "take", "right": "/teɪk/ (тэйк — брать)"},
                            ],
                            "explanation": "В словах time, home, take работает немая «e», а pen — закрытый слог."
                        },
                        {
                            "id": "a0-l2-ex3",
                            "type": "fill_blank",
                            "skill": "writing",
                            "prompt": "Допишите пропущенную немую букву в конце слова «дом» (/həʊm/): hom__",
                            "answer": "e",
                            "accepted": ["e", "home"],
                            "explanation": "Слово «дом» пишется home — с немой буквой e на конце."
                        },
                        {
                            "id": "a0-l2-ex4",
                            "type": "dictation",
                            "skill": "listening",
                            "audio_text": "take a pen",
                            "prompt": "Прослушайте и напишите фразу («возьми ручку»):",
                            "answer": "take a pen",
                            "accepted": ["take a pen", "take a pen."],
                            "explanation": "Take (/teɪk/) a pen (/pen/) — возьми ручку."
                        }
                    ]
                },
                {
                    "id": "a0-l3",
                    "kind": "lesson",
                    "title": "Сочетания согласных: sh, ch, th, ph",
                    "skill_focus": ["reading", "listening"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "sh → [ʃ] shop, fish | ch → [tʃ] chat, check", "ru": "Две буквы вместе дают один привычный звук: sh — мягкое «ш», ch — «ч».", "speak": "shop, fish, chat, check"},
                        {"en": "th → [θ] thank / [ð] this | ph → [f] phone", "ru": "В th кончик языка слегка между зубами! А ph всегда читается как обычный «ф».", "speak": "thank, this, phone"},
                    ],
                    "simple_explanation": "В английском языке звуков больше, чем букв, поэтому две согласные часто объединяются в одну команду и дают один звук: sh (ш — shop), ch (ч — check), ph (ф — phone). А знаменитое сочетание th произносится с кончиком языка между передними зубами: глухо в слове thank («спасибо») и звонко в слове this («это»).",
                    "rule_name": "Диграфы согласных: sh, ch, th, ph",
                    "examples": [
                        {"en": "shop", "ipa": "/ʃɒp/", "ru_hint": "шоп", "ru": "магазин"},
                        {"en": "check", "ipa": "/tʃek/", "ru_hint": "чек", "ru": "проверять, чек"},
                        {"en": "phone", "ipa": "/fəʊn/", "ru_hint": "фоун", "ru": "телефон"},
                        {"en": "this", "ipa": "/ðɪs/", "ru_hint": "з(межзубн.)ис", "ru": "это, этот"},
                    ],
                    "vocab": [
                        {"word": "shop", "ipa": "/ʃɒp/", "ru_hint": "шоп", "ru": "магазин", "example": "Open shop.", "topic": "Город"},
                        {"word": "phone", "ipa": "/fəʊn/", "ru_hint": "фоун", "ru": "телефон", "example": "My phone.", "topic": "Повседневное"},
                        {"word": "this", "ipa": "/ðɪs/", "ru_hint": "зис (межзубный)", "ru": "это, этот", "example": "This is a book.", "topic": "Базовые слова"},
                        {"word": "thank", "ipa": "/θæŋk/", "ru_hint": "сэнк (межзубный)", "ru": "благодарить", "example": "Thank you!", "topic": "Общение"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l3-ex1",
                            "type": "match",
                            "skill": "reading",
                            "prompt": "Сопоставьте буквосочетание согласных со словом и переводом:",
                            "pairs": [
                                {"left": "ph → [f]", "right": "phone (телефон)"},
                                {"left": "sh → [ʃ]", "right": "shop (магазин)"},
                                {"left": "ch → [tʃ]", "right": "check (проверять)"},
                                {"left": "th → [ð]", "right": "this (это)"},
                            ],
                            "explanation": "ph даёт [f], sh даёт [ʃ], ch даёт [tʃ], th даёт межзубный звук."
                        },
                        {
                            "id": "a0-l3-ex2",
                            "type": "fill_blank",
                            "skill": "writing",
                            "prompt": "Вставьте буквосочетание из двух букв в слово «телефон»: ___one",
                            "hint": "Звук [f] в греческих словах передаётся двумя буквами.",
                            "answer": "ph",
                            "accepted": ["ph", "phone"],
                            "explanation": "Телефон пишется phone (ph = [f])."
                        },
                        {
                            "id": "a0-l3-ex3",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Какой звук даёт сочетание «sh» в слове «shop»?",
                            "options": ["[ʃ] — мягкий звук «ш»", "[s] — звук «с»", "[tʃ] — звук «ч»"],
                            "answer": "[ʃ] — мягкий звук «ш»",
                            "explanation": "Буквосочетание sh всегда читается как [ʃ] (shop, fish, she)."
                        }
                    ]
                },
                {
                    "id": "a0-l3b",
                    "kind": "lesson",
                    "title": "Пары гласных: ee, oo, ai/ay, oa, ou",
                    "skill_focus": ["reading", "listening"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "ee → [iː] see, tree | oo → [uː]/[ʊ] book, room", "ru": "Двойное ee даёт долгое «и», а двойное oo — звук «у» (короткий в book, долгий в room).", "speak": "see, tree, book, room"},
                        {"en": "ai / ay → [eɪ] rain, day | oa → [əʊ] road | ou → [aʊ] house", "ru": "Пары гласных читаются устойчиво и помогают сразу узнавать сотни слов.", "speak": "rain, day, road, house"},
                    ],
                    "simple_explanation": "Когда две гласные встают рядом, они обычно образуют предсказуемую пару: ee — долгое «и» (see — видеть), oo — «у» (book — книга, room — комната), ai в середине и ay в конце слова — «эй» (rain — дождь, day — день), oa — «оу» (road — дорога), ou — «ау» (house — здание дома).",
                    "rule_name": "Диграфы гласных: ee, oo, ai/ay, oa, ou",
                    "examples": [
                        {"en": "see", "ipa": "/siː/", "ru_hint": "сии", "ru": "видеть"},
                        {"en": "book", "ipa": "/bʊk/", "ru_hint": "бук", "ru": "книга"},
                        {"en": "day", "ipa": "/deɪ/", "ru_hint": "дэй", "ru": "день"},
                        {"en": "road", "ipa": "/rəʊd/", "ru_hint": "роуд", "ru": "дорога"},
                        {"en": "house", "ipa": "/haʊs/", "ru_hint": "хаус", "ru": "дом (здание)"},
                    ],
                    "vocab": [
                        {"word": "book", "ipa": "/bʊk/", "ru_hint": "бук", "ru": "книга", "example": "Read a book.", "topic": "Работа и учёба"},
                        {"word": "day", "ipa": "/deɪ/", "ru_hint": "дэй", "ru": "день", "example": "Good day!", "topic": "Время"},
                        {"word": "house", "ipa": "/haʊs/", "ru_hint": "хаус", "ru": "дом (здание)", "example": "A big house.", "topic": "Дом"},
                        {"word": "road", "ipa": "/rəʊd/", "ru_hint": "роуд", "ru": "дорога", "example": "Long road.", "topic": "Город"},
                        {"word": "see", "ipa": "/siː/", "ru_hint": "сии", "ru": "видеть", "example": "I see you.", "topic": "Действия"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l3b-ex1",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Как читается слово «see» (видеть)?",
                            "options": ["[siː] — долгий звук «и»", "[se] — короткий звук «э»", "[saɪ] — звук «ай»"],
                            "answer": "[siː] — долгий звук «и»",
                            "explanation": "Двойное ee всегда даёт долгий чистый звук [iː]: see, tree, week."
                        },
                        {
                            "id": "a0-l3b-ex2",
                            "type": "match",
                            "skill": "reading",
                            "prompt": "Сопоставьте пару гласных со словом и его переводом:",
                            "pairs": [
                                {"left": "oo → [ʊ]", "right": "book (книга)"},
                                {"left": "ay → [eɪ]", "right": "day (день)"},
                                {"left": "oa → [əʊ]", "right": "road (дорога)"},
                                {"left": "ou → [aʊ]", "right": "house (дом)"},
                            ],
                            "explanation": "Эти пять сочетаний гласных встречаются в самых частых бытовых словах."
                        },
                        {
                            "id": "a0-l3b-ex3",
                            "type": "translate_en_ru",
                            "skill": "reading",
                            "prompt": "Переведите словосочетание на русский язык: «good day»",
                            "answer": "хороший день",
                            "accepted": ["хороший день", "добрый день"],
                            "explanation": "Good day — добрый день / хороший день."
                        }
                    ]
                },
            ],
        },
        {
            "id": "a0-sec-2",
            "title": "Раздел 2. Местоимения, глагол am / is / are и первые предложения",
            "description": "Учимся собирать настоящие английские предложения без пропусков связки.",
            "lessons": [
                {
                    "id": "a0-l4",
                    "kind": "lesson",
                    "title": "Личные местоимения и связка am / is / are",
                    "skill_focus": ["grammar", "vocabulary", "speaking"],
                    "estimated_minutes": 15,
                    "showcase": [
                        {"en": "I am ready.", "ru": "Дословно: «Я есть готовый». В русском «есть» пропало, а в английском am обязательно!", "speak": "I am ready."},
                        {"en": "He is at work. She is a doctor. It is a phone.", "ru": "Для одного человека или предмета (он, она, оно/предмет) ставим is.", "speak": "He is at work. She is a doctor. It is a phone."},
                        {"en": "You are kind. We are friends. They are at home.", "ru": "Для ты/вы, мы, они всегда используется форма are.", "speak": "You are kind. We are friends. They are at home."},
                    ],
                    "simple_explanation": "В русском мы говорим просто «Я дома», «Он врач», «Это телефон» — без глагола. Английское предложение так жить не может: в нём обязательно должен быть глагол! Когда действия нет (никто не бежит и не пишет), англичане ставят глагол «быть/являться» в трёх простых формах: с I (я — всегда пишется с большой буквы!) дружит только am; с he (он), she (она), it (оно/любой неодушевлённый предмет) дружит is; а с you (ты и вы), we (мы), they (они) дружит are.",
                    "rule_name": "Личные местоимения (Subject Pronouns) + глагол to be (am / is / are)",
                    "examples": [
                        {"en": "I am a student.", "ipa": "/aɪ æm ə ˈstjuːdənt/", "ru_hint": "ай эм э стьюдэнт", "ru": "Я студент."},
                        {"en": "She is happy.", "ipa": "/ʃiː ɪz ˈhæpi/", "ru_hint": "ши из хэпи", "ru": "Она счастлива."},
                        {"en": "It is a good book.", "ipa": "/ɪt ɪz ə ɡʊd bʊk/", "ru_hint": "ит из э гуд бук", "ru": "Это хорошая книга."},
                        {"en": "We are at home.", "ipa": "/wiː ɑːr æt həʊm/", "ru_hint": "уи ар эт хоум", "ru": "Мы дома."},
                    ],
                    "vocab": [
                        {"word": "I", "ipa": "/aɪ/", "ru_hint": "ай", "ru": "я", "example": "I am ready.", "topic": "Местоимения"},
                        {"word": "you", "ipa": "/juː/", "ru_hint": "ю", "ru": "ты, вы", "example": "You are right.", "topic": "Местоимения"},
                        {"word": "he", "ipa": "/hiː/", "ru_hint": "хи", "ru": "он", "example": "He is busy.", "topic": "Местоимения"},
                        {"word": "she", "ipa": "/ʃiː/", "ru_hint": "ши", "ru": "она", "example": "She is here.", "topic": "Местоимения"},
                        {"word": "it", "ipa": "/ɪt/", "ru_hint": "ит", "ru": "оно, это (о предмете)", "example": "It is new.", "topic": "Местоимения"},
                        {"word": "we", "ipa": "/wiː/", "ru_hint": "уи", "ru": "мы", "example": "We are ready.", "topic": "Местоимения"},
                        {"word": "they", "ipa": "/ðeɪ/", "ru_hint": "зэй", "ru": "они", "example": "They are students.", "topic": "Местоимения"},
                        {"word": "ready", "ipa": "/ˈredi/", "ru_hint": "рэди", "ru": "готовый", "example": "I am ready.", "topic": "Состояния"},
                        {"word": "happy", "ipa": "/ˈhæpi/", "ru_hint": "хэпи", "ru": "счастливый, рад", "example": "She is happy.", "topic": "Состояния"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l4-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Какую форму глагола-связки нужно поставить: «She ___ happy» (Она счастлива)?",
                            "hint": "She — это «она» (единственное число).",
                            "options": ["is", "am", "are"],
                            "answer": "is",
                            "explanation": "С местоимениями he, she, it всегда используется форма is: She is happy."
                        },
                        {
                            "id": "a0-l4-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте правильную связку (am / is / are): We ___ at home.",
                            "answer": "are",
                            "accepted": ["are"],
                            "explanation": "С местоимениями we, you, they используется форма are."
                        },
                        {
                            "id": "a0-l4-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите предложение «Я готов» из слов:",
                            "words": ["ready", "I", "am"],
                            "answer": "I am ready",
                            "accepted": ["I am ready", "I am ready."],
                            "explanation": "Прямой порядок слов: кто (I) + связка (am) + какой (ready)."
                        },
                        {
                            "id": "a0-l4-ex4",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте частую ошибку новичков (пропущен глагол-связка): «It a good book.»",
                            "hint": "После It перед артиклем a нужна связка.",
                            "answer": "It is a good book.",
                            "accepted": ["It is a good book.", "It is a good book", "It's a good book.", "It's a good book"],
                            "explanation": "В английском нельзя сказать «It a book» без связки — правильно: It is a good book."
                        },
                        {
                            "id": "a0-l4-ex5",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите на английский: «Они дома.» (используйте at home)",
                            "answer": "They are at home.",
                            "accepted": ["They are at home.", "They are at home", "They're at home.", "They're at home"],
                            "explanation": "Они — They, связка — are, дома — at home: They are at home."
                        }
                    ]
                },
                {
                    "id": "a0-l5",
                    "kind": "lesson",
                    "title": "Порядок слов: утверждения и отрицания с not",
                    "skill_focus": ["grammar", "writing"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "[+] He is busy. / You are ready.", "ru": "Утверждение: сначала КТО (подлежащее), затем ГЛАГОЛ (am / is / are), потом остальное.", "speak": "He is busy. You are ready."},
                        {"en": "[-] He is not busy. / I am not tired.", "ru": "Отрицание: просто ставим частицу not сразу ПОСЛЕ am / is / are.", "speak": "He is not busy. I am not tired."},
                    ],
                    "simple_explanation": "В русском языке слова можно менять местами. В английском порядок слов — как конструктор с чёткими пазами: 1) В утверждении всегда сначала КТО, потом ГЛАГОЛ: You are ready. 2) Чтобы сделать отрицание («не»), ничего не переставляем — просто ставим частицу not сразу после am / is / are: You are not ready, He is not busy.",
                    "rule_name": "Прямой порядок слов и отрицание с not",
                    "examples": [
                        {"en": "I am not tired.", "ipa": "/aɪ æm nɒt ˈtaɪəd/", "ru_hint": "ай эм нот тайэд", "ru": "Я не устал."},
                        {"en": "He is busy today.", "ipa": "/hiː ɪz ˈbɪzi təˈdeɪ/", "ru_hint": "хи из бизи тудэй", "ru": "Он сегодня занят."},
                        {"en": "They are not at work.", "ipa": "/ðeɪ ɑː nɒt æt wɜːk/", "ru_hint": "зэй ар нот эт уёрк", "ru": "Они не на работе."},
                    ],
                    "vocab": [
                        {"word": "not", "ipa": "/nɒt/", "ru_hint": "нот", "ru": "не", "example": "It is not big.", "topic": "Грамматика"},
                        {"word": "busy", "ipa": "/ˈbɪzi/", "ru_hint": "бизи", "ru": "занятой", "example": "He is busy.", "topic": "Работа и учёба"},
                        {"word": "tired", "ipa": "/ˈtaɪəd/", "ru_hint": "тайэд", "ru": "уставший", "example": "I am not tired.", "topic": "Состояния"},
                        {"word": "work", "ipa": "/wɜːk/", "ru_hint": "уёрк", "ru": "работа", "example": "At work.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l5-ex1",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Сделайте предложение отрицательным («Он не занят»): He is ___ busy.",
                            "answer": "not",
                            "accepted": ["not"],
                            "explanation": "Частица not ставится сразу после am / is / are: He is not busy."
                        },
                        {
                            "id": "a0-l5-ex2",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите отрицательное предложение «Я не устал»:",
                            "words": ["not", "am", "tired.", "I"],
                            "answer": "I am not tired.",
                            "accepted": ["I am not tired.", "I am not tired"],
                            "explanation": "Прямой порядок: I + am + not + tired."
                        },
                        {
                            "id": "a0-l5-ex3",
                            "type": "reading_qa",
                            "skill": "reading",
                            "passage": "Hello! My name is Maksat. I am at work today. My friend Timur is not at work — he is at home.",
                            "prompt": "Прочитайте короткий текст. Где сейчас находится Тимур?",
                            "options": ["Тимур дома (at home)", "Тимур на работе (at work)", "Тимур в магазине (at the shop)"],
                            "answer": "Тимур дома (at home)",
                            "explanation": "В тексте сказано: «Timur is not at work — he is at home» (Тимур не на работе — он дома)."
                        }
                    ]
                },
                {
                    "id": "a0-l5b",
                    "kind": "lesson",
                    "title": "Вопросы с am / is / are и краткие ответы",
                    "skill_focus": ["grammar", "speaking", "writing"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "You are ready. → Are you ready?", "ru": "Чтобы задать вопрос, берём am / is / are и выносим ВПЕРЁД перед подлежащим!", "speak": "Are you ready?"},
                        {"en": "Is he busy? — Yes, he is. / No, he is not.", "ru": "В кратком ответе повторяем то же местоимение и связку am / is / are.", "speak": "Is he busy? Yes, he is."},
                    ],
                    "simple_explanation": "По-русски мы задаём вопрос одной интонацией («Ты готов?»). В английском одной интонации недостаточно: нужно переставить связку am, is или are на самое первое место перед человеком. Было «You are ready» -> стало «Are you ready?». Было «It is your phone» -> стало «Is it your phone?».",
                    "rule_name": "Вопросы с am / is / are (инверсия)",
                    "examples": [
                        {"en": "Are you ready?", "ipa": "/ɑːr juː ˈredi/", "ru_hint": "ар ю рэди", "ru": "Ты готов? / Вы готовы?"},
                        {"en": "Is it your phone?", "ipa": "/ɪz ɪt jɔː fəʊn/", "ru_hint": "из ит ё фоун", "ru": "Это твой телефон?"},
                        {"en": "Yes, I am.", "ipa": "/jes aɪ æm/", "ru_hint": "ес ай эм", "ru": "Да (я готов)."},
                    ],
                    "vocab": [
                        {"word": "ready", "ipa": "/ˈredi/", "ru_hint": "рэди", "ru": "готов, готовый", "example": "Are you ready?", "topic": "Общение"},
                        {"word": "your", "ipa": "/jɔː/", "ru_hint": "ё / юр", "ru": "твой, ваш", "example": "Your book.", "topic": "Местоимения"},
                    ],
                    "exercises": [
                        {
                            "id": "a0-l5b-ex1",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопросительное предложение «Ты готов?»:",
                            "words": ["ready?", "you", "Are"],
                            "answer": "Are you ready?",
                            "accepted": ["Are you ready?", "Are you ready"],
                            "explanation": "В вопросе глагол Are выносится перед подлежащим you: Are you ready?"
                        },
                        {
                            "id": "a0-l5b-ex2",
                            "type": "mini_dialogue",
                            "skill": "speaking",
                            "context": "Коллега спрашивает вас перед началом встречи.",
                            "speaker_line": "Hello! Are you ready?",
                            "speaker_ru": "Привет! Ты готов(а)?",
                            "prompt": "Выберите грамотный ответ на английском:",
                            "options": ["Yes, I am ready.", "Yes, I ready.", "Yes, am I ready."],
                            "answer": "Yes, I am ready.",
                            "explanation": "В утвердительном ответе сохраняется прямой порядок и связка am: Yes, I am ready."
                        },
                        {
                            "id": "a0-l5b-ex3",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите вопрос на английский: «Это твой телефон?»",
                            "hint": "Начните с Is it ...",
                            "answer": "Is it your phone?",
                            "accepted": ["Is it your phone?", "Is it your phone", "Is this your phone?", "Is this your phone"],
                            "explanation": "Вопрос начинается с Is: Is it your phone? (или Is this your phone?)."
                        }
                    ]
                },
                {
                    "id": "a0-check-1",
                    "kind": "checkpoint",
                    "title": "Промежуточная проверка A0: Чтение и первые фразы",
                    "skill_focus": ["reading", "grammar", "listening"],
                    "estimated_minutes": 10,
                    "simple_explanation": "Проверим, как усвоены правила чтения слогов, буквосочетаний и первые конструкции с am / is / are перед выходом на итоговый экзамен уровня A0.",
                    "rule_name": "Контроль освоения разделов 1–2 уровня A0",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "a0-ch-1",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "В каком ряду ОБА слова читаются с долгим/алфавитным звуком благодаря открытому слогу или паре гласных?",
                            "options": ["name, road", "cat, bed", "bus, dog"],
                            "answer": "name, road",
                            "explanation": "В name работает немая e (/neɪm/), а в road — диграф oa (/rəʊd/)."
                        },
                        {
                            "id": "a0-ch-2",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку в предложении: «We is ready.»",
                            "answer": "We are ready.",
                            "accepted": ["We are ready.", "We are ready"],
                            "explanation": "С местоимением we употребляется только форма are: We are ready."
                        },
                        {
                            "id": "a0-ch-3",
                            "type": "dictation",
                            "skill": "listening",
                            "audio_text": "This is my home",
                            "prompt": "Прослушайте и запишите предложение («Это мой дом»):",
                            "answer": "This is my home",
                            "accepted": ["This is my home", "This is my home."],
                            "explanation": "This (/ðɪs/) is my home (/həʊm/)."
                        },
                        {
                            "id": "a0-ch-4",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите отрицательное предложение «Я не устал»:",
                            "words": ["tired", "am", "not", "I"],
                            "answer": "I am not tired",
                            "accepted": ["I am not tired", "I am not tired."],
                            "explanation": "Порядок: I + am + not + tired."
                        }
                    ]
                },
                {
                    "id": "a0-exam",
                    "kind": "exam",
                    "title": "Итоговый экзамен A0 (переход на уровень A1)",
                    "skill_focus": ["reading", "listening", "grammar", "writing", "vocabulary"],
                    "estimated_minutes": 15,
                    "simple_explanation": "Финальная проверка уровня A0. Наберите не менее 80%, чтобы подтвердить базу чтения и построения первых предложений и разблокировать уровень A1.",
                    "rule_name": "Экзамен уровня A0 (порог прохождения — 80%)",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "a0-ex-1",
                            "type": "choice",
                            "skill": "reading",
                            "prompt": "Какое буквосочетание даёт звук [f] в слове «phone»?",
                            "options": ["ph", "th", "sh"],
                            "answer": "ph",
                            "explanation": "Буквосочетание ph всегда читается как [f]."
                        },
                        {
                            "id": "a0-ex-2",
                            "type": "match",
                            "skill": "vocabulary",
                            "prompt": "Сопоставьте слова уровня A0 с их переводом:",
                            "pairs": [
                                {"left": "house", "right": "дом (здание)"},
                                {"left": "busy", "right": "занятой"},
                                {"left": "book", "right": "книга"},
                                {"left": "work", "right": "работа"},
                            ],
                            "explanation": "house — дом, busy — занятой, book — книга, work — работа."
                        },
                        {
                            "id": "a0-ex-3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопрос «Она на работе?»:",
                            "words": ["at", "work?", "she", "Is"],
                            "answer": "Is she at work?",
                            "accepted": ["Is she at work?", "Is she at work"],
                            "explanation": "Глагол Is ставится перед подлежащим she: Is she at work?"
                        },
                        {
                            "id": "a0-ex-4",
                            "type": "listening_qa",
                            "skill": "listening",
                            "audio_text": "Good day! My name is Alina. I am not busy now.",
                            "prompt": "Прослушайте аудиофрагмент. Занята ли сейчас Алина?",
                            "options": ["Нет, она сейчас свободна (not busy)", "Да, она очень занята", "Она спит дома"],
                            "answer": "Нет, она сейчас свободна (not busy)",
                            "explanation": "Алина говорит: «I am not busy now» — я сейчас не занята."
                        },
                        {
                            "id": "a0-ex-5",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Напишите по-английски полное предложение: «Мы дома.»",
                            "answer": "We are at home.",
                            "accepted": ["We are at home.", "We are at home", "We're at home.", "We're at home"],
                            "explanation": "Мы дома — We are at home."
                        }
                    ]
                }
            ]
        }
    ]
}


LEVEL_A1 = {
    "id": "A1",
    "code": "A1",
    "title": "A1 — Базовый английский",
    "subtitle": "Повседневные действия (Present Simple), have/has, can, there is/are, вопросы, числа и бытовые темы",
    "cefr_goal": "Рассказывать о себе, семье, доме, работе, распорядке дня, ориентироваться в городе, времени и датах, задавать вопросы и писать короткие связные сообщения.",
    "pass_exam_score": 80,
    "sections": [
        {
            "id": "a1-sec-1",
            "title": "Раздел 1. Регулярные действия, владение и возможности",
            "description": "Present Simple, have / has, модальный глагол can / cannot и вопросы.",
            "lessons": [
                {
                    "id": "a1-l1",
                    "kind": "lesson",
                    "title": "Present Simple: обычные действия и окончание -s",
                    "skill_focus": ["grammar", "vocabulary", "writing"],
                    "estimated_minutes": 16,
                    "showcase": [
                        {"en": "I work every day. We live in Almaty.", "ru": "С I / you / we / they глагол остаётся в базовой форме без изменений.", "speak": "I work every day. We live in Almaty."},
                        {"en": "He works in an office. She reads books.", "ru": "Для he / she / it к глаголу в утверждении добавляется окончание -s!", "speak": "He works in an office. She reads books."},
                        {"en": "Do you work here? — He does not (doesn't) work here.", "ru": "В вопросах и отрицаниях появляются помощники do и does (и перетягивают -s на себя).", "speak": "Do you work here? He does not work here."},
                    ],
                    "simple_explanation": "Когда вы говорите о том, что происходит обычно, регулярно или вообще по жизни («я работаю», «она пьёт кофе утром», «автобус ходит каждый день»), используется настоящее простое время. Главное правило очень простое: если действует один человек или предмет (он — he, она — she, оно — it), к глаголу приклеивается хвостик -s: I work, но He works. А чтобы задать вопрос или сделать отрицание, мы зовём глагол-помощник do (или does для he/she/it). Как только пришёл does, у основного глагола хвостик -s исчезает: Does he work? He does not work.",
                    "rule_name": "Present Simple (Настоящее простое время: утверждения, do / does)",
                    "examples": [
                        {"en": "I live in a big city.", "ipa": "/aɪ lɪv ɪn ə bɪɡ ˈsɪti/", "ru_hint": "ай лив ин э биг сити", "ru": "Я живу в большом городе."},
                        {"en": "She works at a hospital.", "ipa": "/ʃiː wɜːks æt ə ˈhɒspɪtl/", "ru_hint": "ши уёркс эт э хоспитл", "ru": "Она работает в больнице."},
                        {"en": "Do you speak English?", "ipa": "/duː juː spiːk ˈɪŋɡlɪʃ/", "ru_hint": "ду ю спик инглиш", "ru": "Вы говорите по-английски?"},
                        {"en": "He does not drink coffee.", "ipa": "/hiː dʌz nɒt drɪŋk ˈkɒfi/", "ru_hint": "хи даз нот дринк кофи", "ru": "Он не пьёт кофе."},
                    ],
                    "vocab": [
                        {"word": "live", "ipa": "/lɪv/", "ru_hint": "лив", "ru": "жить", "example": "We live here.", "topic": "Жизнь и семья"},
                        {"word": "city", "ipa": "/ˈsɪti/", "ru_hint": "сити", "ru": "город", "example": "A clean city.", "topic": "Город"},
                        {"word": "speak", "ipa": "/spiːk/", "ru_hint": "спик", "ru": "говорить (на языке)", "example": "Speak slowly, please.", "topic": "Общение"},
                        {"word": "drink", "ipa": "/drɪŋk/", "ru_hint": "дринк", "ru": "пить", "example": "I drink tea.", "topic": "Еда и напитки"},
                        {"word": "coffee", "ipa": "/ˈkɒfi/", "ru_hint": "кофи", "ru": "кофе", "example": "Hot coffee.", "topic": "Еда и напитки"},
                        {"word": "every day", "ipa": "/ˈevri deɪ/", "ru_hint": "эври дэй", "ru": "каждый день", "example": "I study every day.", "topic": "Время"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l1-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму: «My brother ___ in Astana.» (Мой брат живёт в Астане)",
                            "hint": "My brother = he (он).",
                            "options": ["lives", "live", "is live"],
                            "answer": "lives",
                            "explanation": "My brother — это 3-е лицо ед. числа (he), поэтому в Present Simple добавляется -s: lives."
                        },
                        {
                            "id": "a1-l1-ex2",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку в отрицании: «She does not works today.»",
                            "hint": "Помощник does уже забрал на себя окончание -s.",
                            "answer": "She does not work today.",
                            "accepted": ["She does not work today.", "She does not work today", "She doesn't work today.", "She doesn't work today"],
                            "explanation": "После does / does not основной глагол всегда стоит без окончания -s: work."
                        },
                        {
                            "id": "a1-l1-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопрос «Ты говоришь по-английски?»:",
                            "words": ["English?", "speak", "you", "Do"],
                            "answer": "Do you speak English?",
                            "accepted": ["Do you speak English?", "Do you speak English"],
                            "explanation": "Вопрос в Present Simple с you начинается с помощника Do: Do you speak English?"
                        },
                        {
                            "id": "a1-l1-ex4",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите на английский: «Я работаю каждый день.»",
                            "answer": "I work every day.",
                            "accepted": ["I work every day.", "I work every day"],
                            "explanation": "I work every day."
                        }
                    ]
                },
                {
                    "id": "a1-l2",
                    "kind": "lesson",
                    "title": "Глагол have / has (у меня есть)",
                    "skill_focus": ["grammar", "vocabulary"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "I / you / we / they have a car.", "ru": "У меня, тебя, нас, них есть -> используем форму have.", "speak": "I have a car. We have time."},
                        {"en": "He / she / it has a new laptop.", "ru": "Для он / она / оно (he, she, it) берём форму has!", "speak": "She has a new laptop."},
                    ],
                    "simple_explanation": "В русском языке мы говорим «У меня есть...». По-английски это дословно «Я имею...»: I have. Правило простое: с местоимениями I, you, we, they используется have, а с he, she, it (он, она, оно) — особая форма has.",
                    "rule_name": "Глагол обладания have / has",
                    "examples": [
                        {"en": "I have a question.", "ipa": "/aɪ hæv ə ˈkwestʃən/", "ru_hint": "ай хэв э куэсчэн", "ru": "У меня есть вопрос."},
                        {"en": "She has two brothers.", "ipa": "/ʃiː hæz tuː ˈbrʌðəz/", "ru_hint": "ши хэз ту бразэз", "ru": "У неё два брата."},
                    ],
                    "vocab": [
                        {"word": "have", "ipa": "/hæv/", "ru_hint": "хэв", "ru": "иметь (у меня есть)", "example": "I have time.", "topic": "Базовые глаголы"},
                        {"word": "brother", "ipa": "/ˈbrʌðə/", "ru_hint": "бразэ", "ru": "брат", "example": "My brother.", "topic": "Жизнь и семья"},
                        {"word": "question", "ipa": "/ˈkwestʃən/", "ru_hint": "куэсчэн", "ru": "вопрос", "example": "I have a question.", "topic": "Общение"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l2-ex1",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте have или has: She ___ a question.",
                            "answer": "has",
                            "accepted": ["has"],
                            "explanation": "С местоимениями he, she, it используется форма has."
                        },
                        {
                            "id": "a1-l2-ex2",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильное предложение «У нас есть время»:",
                            "options": ["We have time.", "We has time.", "We are have time."],
                            "answer": "We have time.",
                            "explanation": "После we (мы) всегда используется форма have."
                        },
                        {
                            "id": "a1-l2-ex3",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите на английский: «У меня есть книга.»",
                            "answer": "I have a book.",
                            "accepted": ["I have a book.", "I have a book"],
                            "explanation": "I have a book."
                        }
                    ]
                },
                {
                    "id": "a1-l2b",
                    "kind": "lesson",
                    "title": "Модальный глагол can / cannot (могу, умею)",
                    "skill_focus": ["grammar", "speaking", "writing"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "I can swim. She can read English.", "ru": "can («могу, умею») НЕ меняется по лицам (даже с he/she) и используется без частицы to!", "speak": "I can swim. She can read English."},
                        {"en": "He cannot (can't) drive. / Can you help me?", "ru": "Отрицание — cannot / can't. В вопросе Can выносится в начало.", "speak": "He cannot drive. Can you help me?"},
                    ],
                    "simple_explanation": "Can — самый дружелюбный глагол в английском языке! Он никогда не меняет форму: I can, she can, they can. Сразу после него ставим обычный глагол без частицы to: I can help (я могу помочь). Отрицание пишется слитно cannot (или кратко can't). Чтобы попросить о помощи, выносим Can вперёд: Can you help me?",
                    "rule_name": "Модальный глагол can / cannot",
                    "examples": [
                        {"en": "Can you help me?", "ipa": "/kæn juː help miː/", "ru_hint": "кэн ю хэлп ми", "ru": "Ты можешь мне помочь?"},
                        {"en": "I cannot drive a car.", "ipa": "/aɪ ˈkænɒt draɪv ə kɑː/", "ru_hint": "ай кэнот драйв э ка", "ru": "Я не умею водить машину."},
                    ],
                    "vocab": [
                        {"word": "help", "ipa": "/help/", "ru_hint": "хэлп", "ru": "помогать, помощь", "example": "Can you help me?", "topic": "Общение"},
                        {"word": "drive", "ipa": "/draɪv/", "ru_hint": "драйв", "ru": "водить машину", "example": "I can drive.", "topic": "Транспорт"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l2b-ex1",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вежливую просьбу «Ты можешь мне помочь?»:",
                            "words": ["help", "me?", "Can", "you"],
                            "answer": "Can you help me?",
                            "accepted": ["Can you help me?", "Can you help me"],
                            "explanation": "В вопросе модальный глагол Can ставится перед подлежащим: Can you help me?"
                        },
                        {
                            "id": "a1-l2b-ex2",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку (после can не нужна частица to): «She can to speak English.»",
                            "answer": "She can speak English.",
                            "accepted": ["She can speak English.", "She can speak English"],
                            "explanation": "После модального глагола can сразу идёт глагол без to: She can speak English."
                        },
                        {
                            "id": "a1-l2b-ex3",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите на английский: «Я не могу водить.» (используйте drive и cannot)",
                            "answer": "I cannot drive.",
                            "accepted": ["I cannot drive.", "I cannot drive", "I can't drive.", "I can't drive"],
                            "explanation": "Я не умею / не могу водить — I cannot drive (или I can't drive)."
                        }
                    ]
                },
                {
                    "id": "a1-l2c",
                    "kind": "lesson",
                    "title": "Оборот there is / there are (где что находится)",
                    "skill_focus": ["grammar", "vocabulary", "reading"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "There is a bank on this street.", "ru": "Когда предмет ОДИН — начинаем с There is...", "speak": "There is a bank on this street."},
                        {"en": "There are two parks near my house.", "ru": "Когда предметов МНОГО — начинаем с There are...", "speak": "There are two parks near my house."},
                    ],
                    "simple_explanation": "Если по-русски мы часто начинаем с места («Рядом с домом есть магазин»), то в английском языке такое предложение начинается со специальной связки There is (если предмет один) или There are (если их несколько), а место ставится в конец: There is a shop near my house.",
                    "rule_name": "Конструкция наличия there is / there are",
                    "examples": [
                        {"en": "There is a cafe near the office.", "ipa": "/ðeər ɪz ə ˈkæfeɪ nɪə ðə ˈɒfɪs/", "ru_hint": "зэар из э кэфэй ниа зи офис", "ru": "Рядом с офисом есть кафе."},
                        {"en": "There are ten rooms on this floor.", "ipa": "/ðeər ɑː ten ruːmz ɒn ðɪs flɔː/", "ru_hint": "зэар ар тэн румз он зис фло", "ru": "На этом этаже десять комнат."},
                    ],
                    "vocab": [
                        {"word": "office", "ipa": "/ˈɒfɪs/", "ru_hint": "офис", "ru": "офис", "example": "Near the office.", "topic": "Работа и учёба"},
                        {"word": "street", "ipa": "/striːt/", "ru_hint": "стрит", "ru": "улица", "example": "A quiet street.", "topic": "Город"},
                        {"word": "near", "ipa": "/nɪə/", "ru_hint": "ниа", "ru": "рядом с, около", "example": "Near my house.", "topic": "Город"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l2c-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Как правильно сказать «Рядом с моим домом есть магазин»?",
                            "options": [
                                "There is a shop near my house.",
                                "There are a shop near my house.",
                                "Near my house have a shop."
                            ],
                            "answer": "There is a shop near my house.",
                            "explanation": "Магазин один (a shop), поэтому выбираем оборот в единственном числе: There is a shop..."
                        },
                        {
                            "id": "a1-l2c-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте is или are: There ___ two parks in our city.",
                            "answer": "are",
                            "accepted": ["are"],
                            "explanation": "Парков два (two parks — множественное число), поэтому нужно There are."
                        },
                        {
                            "id": "a1-l2c-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите предложение «Рядом с офисом есть кафе»:",
                            "words": ["cafe", "There", "is", "near", "a", "the office."],
                            "answer": "There is a cafe near the office.",
                            "accepted": ["There is a cafe near the office.", "There is a cafe near the office"],
                            "explanation": "Сначала There is + предмет (a cafe) + место (near the office)."
                        }
                    ]
                },
                {
                    "id": "a1-l3",
                    "kind": "lesson",
                    "title": "Артикли a / an / the и множественное число",
                    "skill_focus": ["grammar", "vocabulary"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "a book, an apple → the book on my desk", "ru": "a/an — «один какой-то» (an перед гласным звуком!); the — «тот самый, конкретный».", "speak": "a book, an apple, the book on my desk"},
                        {"en": "one book → two books | one city → two cities", "ru": "Множественное число: обычно добавляем -s; после шипящих -es; -y после согласной меняется на -ies.", "speak": "one book, two books, one city, two cities"},
                    ],
                    "simple_explanation": "Перед каждым исчисляемым предметом в единственном числе в английском нужен артикль. Если называем предмет впервые («какая-то чашка») — ставим a (перед согласным звуком: a cup) или an (перед гласным звуком: an apple, an office). Если собеседник уже понимает, о каком именно предмете речь — ставим the. А когда предметов много, артикль a/an убираем и добавляем окончание -s (books) или -es/-ies (buses, cities).",
                    "rule_name": "Артикли (a / an / the) и множественное число (-s / -es)",
                    "examples": [
                        {"en": "I work in an office.", "ipa": "/aɪ wɜːk ɪn ən ˈɒfɪs/", "ru_hint": "ай уёрк ин эн офис", "ru": "Я работаю в офисе."},
                        {"en": "Open the window, please.", "ipa": "/ˈəʊpən ðə ˈwɪndəʊ pliːz/", "ru_hint": "оупэн зэ уиндоу плиз", "ru": "Открой, пожалуйста, окно (то самое, в комнате)."},
                    ],
                    "vocab": [
                        {"word": "apple", "ipa": "/ˈæpl/", "ru_hint": "эпл", "ru": "яблоко", "example": "An apple a day.", "topic": "Еда и напитки"},
                        {"word": "city", "ipa": "/ˈsɪti/", "ru_hint": "сити", "ru": "город", "example": "Two big cities.", "topic": "Город"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l3-ex1",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте правильный неопределённый артикль (a или an) перед словом с гласного звука: ___ apple",
                            "answer": "an",
                            "accepted": ["an"],
                            "explanation": "Перед словами, которые начинаются с гласного звука (apple, office, hour), используется артикль an."
                        },
                        {
                            "id": "a1-l3-ex2",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильное множественное число от слова city (город):",
                            "options": ["cities", "citys", "cityes"],
                            "answer": "cities",
                            "explanation": "Согласная + y на конце во множественном числе меняется на -ies: city -> cities."
                        },
                        {
                            "id": "a1-l3-ex3",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильный артикль: «Open ___ window, please.» (Открой, пожалуйста, окно в этой комнате)",
                            "options": ["the", "a", "an"],
                            "answer": "the",
                            "explanation": "Мы имеем в виду конкретное окно в комнате, о котором знают оба собеседника -> the."
                        }
                    ]
                },
                {
                    "id": "a1-l3b",
                    "kind": "lesson",
                    "title": "Притяжательные формы: my / your / his / her и 's",
                    "skill_focus": ["grammar", "writing"],
                    "estimated_minutes": 9,
                    "showcase": [
                        {"en": "my phone, your bag, his car, her laptop", "ru": "Слова-владельцы (my, your, his, her, our, their) заменяют артикль — вместе с a/the они не ставятся!", "speak": "my phone, your bag, her laptop"},
                        {"en": "my sister's phone / Aidar's office", "ru": "Чтобы сказать «чей-то» по имени или родству, добавляем 's к владельцу.", "speak": "my sister's phone, Aidar's office"},
                    ],
                    "simple_explanation": "Чтобы сказать, кому принадлежит вещь, в английском используют притяжательные местоимения (my — мой, your — твой/ваш, his — его, her — её, our — наш, their — их). А если владелец — конкретный человек, к нему просто добавляют апостроф и s ('s): my sister's phone (телефон моей сестры). После my/'s артикль уже не нужен!",
                    "rule_name": "Притяжательные местоимения и притяжательный падеж ('s)",
                    "examples": [
                        {"en": "This is my sister's phone.", "ipa": "/ðɪs ɪz maɪ ˈsɪstəz fəʊn/", "ru_hint": "зис из май систэз фоун", "ru": "Это телефон моей сестры."},
                        {"en": "Our meeting is today.", "ipa": "/ˈaʊə ˈmiːtɪŋ ɪz təˈdeɪ/", "ru_hint": "ауа митинг из тудэй", "ru": "Наша встреча сегодня."},
                    ],
                    "vocab": [
                        {"word": "sister", "ipa": "/ˈsɪstə/", "ru_hint": "систэ", "ru": "сестра", "example": "My sister.", "topic": "Жизнь и семья"},
                        {"word": "our", "ipa": "/ˈaʊə/", "ru_hint": "ауа", "ru": "наш, наша", "example": "Our team.", "topic": "Местоимения"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l3b-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Как правильно сказать «телефон моей сестры»?",
                            "options": ["my sister's phone", "the phone my sister", "my sister phone"],
                            "answer": "my sister's phone",
                            "explanation": "Владелец + 's + предмет: my sister's phone."
                        },
                        {
                            "id": "a1-l3b-ex2",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите на английский: «Это наша книга.»",
                            "answer": "This is our book.",
                            "accepted": ["This is our book.", "This is our book"],
                            "explanation": "Наш — our: This is our book."
                        },
                        {
                            "id": "a1-l3b-ex3",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку (после my артикль a не нужен): «This is a my phone.»",
                            "answer": "This is my phone.",
                            "accepted": ["This is my phone.", "This is my phone"],
                            "explanation": "Притяжательное местоимение my само определяет предмет — артикль a убираем."
                        }
                    ]
                },
                {
                    "id": "a1-l3c",
                    "kind": "lesson",
                    "title": "Вопросительные слова (Where, When, What) и время",
                    "skill_focus": ["grammar", "reading", "writing"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "What, Where, When, Why, How, What time", "ru": "Вопросительные слова всегда стоят в самом начале вопроса перед do / does / is / are.", "speak": "Where do you work? What time is it?"},
                        {"en": "at 9 o'clock | on Monday | in May", "ru": "Предлоги времени: at — точный час, on — день недели, in — месяц или год.", "speak": "at nine o'clock, on Monday, in May"},
                    ],
                    "simple_explanation": "Чтобы спросить «Где? Когда? Что? Почему?», ставим вопросительное слово в самое начало предложения, а сразу за ним — помощника (do/does или am/is/are): Where do you live? (Где ты живёшь?), What time is the meeting? (Во сколько встреча?). Для времени запомните удобную тройку предлогов: at — часы (at 10 o'clock), on — дни недели (on Monday), in — месяцы (in May).",
                    "rule_name": "Вопросительные слова (Wh-questions) и предлоги времени (at / on / in)",
                    "examples": [
                        {"en": "Where do you live?", "ipa": "/weə duː juː lɪv/", "ru_hint": "уэа ду ю лив", "ru": "Где ты живёшь?"},
                        {"en": "Our meeting is at nine o'clock on Monday.", "ipa": "/ˈaʊə ˈmiːtɪŋ ɪz æt naɪn əˈklɒk ɒn ˈmʌndeɪ/", "ru_hint": "ауа митинг из эт найн оклок он мандэй", "ru": "Наша встреча в 9 часов в понедельник."},
                    ],
                    "vocab": [
                        {"word": "where", "ipa": "/weə/", "ru_hint": "уэа", "ru": "где, куда", "example": "Where is the bus?", "topic": "Вопросы"},
                        {"word": "when", "ipa": "/wen/", "ru_hint": "уэн", "ru": "когда", "example": "When is the train?", "topic": "Вопросы"},
                        {"word": "meeting", "ipa": "/ˈmiːtɪŋ/", "ru_hint": "митинг", "ru": "встреча, совещание", "example": "Morning meeting.", "topic": "Работа и учёба"},
                        {"word": "Monday", "ipa": "/ˈmʌndeɪ/", "ru_hint": "мандэй", "ru": "понедельник", "example": "On Monday.", "topic": "Время"},
                    ],
                    "exercises": [
                        {
                            "id": "a1-l3c-ex1",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопрос «Где ты работаешь?»:",
                            "words": ["work?", "do", "Where", "you"],
                            "answer": "Where do you work?",
                            "accepted": ["Where do you work?", "Where do you work"],
                            "explanation": "Схема вопроса: Вопросительное слово (Where) + помощник (do) + кто (you) + глагол (work)."
                        },
                        {
                            "id": "a1-l3c-ex2",
                            "type": "reading_qa",
                            "skill": "reading",
                            "passage": "Aidar works in an IT company in Almaty. Every Monday he has a team meeting at 10 o'clock. Near his office there is a small cafe. He drinks tea and eats a sandwich there at 1 o'clock.",
                            "prompt": "Во сколько у Айдара командная встреча по понедельникам?",
                            "options": ["В 10 часов (at 10 o'clock)", "В 1 час дня (at 1 o'clock)", "В 9 часов утра"],
                            "answer": "В 10 часов (at 10 o'clock)",
                            "explanation": "В тексте указано: «Every Monday he has a team meeting at 10 o'clock»."
                        },
                        {
                            "id": "a1-l3c-ex3",
                            "type": "guided_writing",
                            "skill": "writing",
                            "prompt": "Напишите по образцу 1 короткое предложение о себе на английском: где вы живёте (например: I live in Almaty.)",
                            "sample": "I live in Almaty.",
                            "required_tokens": ["i", "live", "in"],
                            "min_words": 4,
                            "answer": "I live in Almaty.",
                            "explanation": "Отлично! Конструкция «I live in + город» — базовая модель рассказа о себе."
                        }
                    ]
                },
                {
                    "id": "a1-exam",
                    "kind": "exam",
                    "title": "Итоговый экзамен A1 (переход на уровень A2)",
                    "skill_focus": ["grammar", "reading", "listening", "writing", "vocabulary"],
                    "estimated_minutes": 18,
                    "simple_explanation": "Итоговая проверка уровня A1: Present Simple, have/has, can, there is/are, артикли, вопросы и бытовые тексты. Порог прохождения — 80%.",
                    "rule_name": "Экзамен уровня A1 (порог — 80%)",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "a1-ex-1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите грамматически верное предложение:",
                            "options": [
                                "She does not drink coffee in the evening.",
                                "She do not drinks coffee in the evening.",
                                "She not drink coffee in the evening."
                            ],
                            "answer": "She does not drink coffee in the evening.",
                            "explanation": "Для she используется помощник does not, а глагол drink остаётся в начальной форме без -s."
                        },
                        {
                            "id": "a1-ex-2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте is или are: There ___ two buses on the street.",
                            "answer": "are",
                            "accepted": ["are"],
                            "explanation": "Два автобуса (two buses — множественное число), поэтому There are."
                        },
                        {
                            "id": "a1-ex-3",
                            "type": "listening_qa",
                            "skill": "listening",
                            "audio_text": "Excuse me, can you help me? Where is the train station? It is on Green Street, near the big bank.",
                            "prompt": "Прослушайте диалог. Где находится вокзал (train station)?",
                            "options": ["На Грин-стрит, рядом с большим банком", "Рядом с больницей на Главной улице", "За магазином и школой"],
                            "answer": "На Грин-стрит, рядом с большим банком",
                            "explanation": "В ответе прозвучало: «It is on Green Street, near the big bank»."
                        },
                        {
                            "id": "a1-ex-4",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите предложение «У моей сестры есть новая машина»:",
                            "words": ["car.", "new", "has", "sister", "My", "a"],
                            "answer": "My sister has a new car.",
                            "accepted": ["My sister has a new car.", "My sister has a new car"],
                            "explanation": "My sister (она -> has) + a new car."
                        },
                        {
                            "id": "a1-ex-5",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите вопрос на английский: «Где ты живёшь?»",
                            "answer": "Where do you live?",
                            "accepted": ["Where do you live?", "Where do you live"],
                            "explanation": "Where do you live?"
                        }
                    ]
                }
            ]
        }
    ]
}


def _attach_extra_sections(level_dict: dict, extra_lessons: list[dict], sec_id: str, sec_title: str, sec_desc: str) -> None:
    last_sec = level_dict["sections"][-1]
    exam_item = last_sec["lessons"].pop()
    level_dict["sections"].append(
        {
            "id": sec_id,
            "title": sec_title,
            "description": sec_desc,
            "lessons": [*extra_lessons, exam_item],
        }
    )


from .curriculum_a0_extra import A0_EXTRA_LESSONS as _A0_EXTRA
from .curriculum_a1_extra import A1_EXTRA_LESSONS as _A1_EXTRA

_attach_extra_sections(
    LEVEL_A0,
    _A0_EXTRA,
    "a0-sec-3",
    "Раздел 3. Числа, время, семья, цвета и базовое общение",
    "Уверенная база для повседневных ситуаций и итогового экзамена A0.",
)
_attach_extra_sections(
    LEVEL_A1,
    _A1_EXTRA,
    "a1-sec-2",
    "Раздел 2. Времена A1, модальные глаголы и жизненные ситуации",
    "Покупки, поездки, здоровье, работа и короткие письма.",
)
