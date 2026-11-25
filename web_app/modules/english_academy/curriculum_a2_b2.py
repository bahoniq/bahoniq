# -*- coding: utf-8 -*-
"""Учебный контент уровней A2, B1 и B2 для English Academy Studio."""

from __future__ import annotations

LEVEL_A2 = {
    "id": "A2",
    "code": "A2",
    "title": "A2 — Элементарное самостоятельное общение",
    "subtitle": "Прошедшее, длительное и будущее время, сравнения, модальные глаголы, покупки, поездки и здоровье",
    "cefr_goal": "Свободно описывать то, что происходит прямо сейчас, рассказывать о прошлом опыте и планах на будущее, сравнивать предметы, решать бытовые вопросы в поездках, магазинах и у врача.",
    "pass_exam_score": 80,
    "sections": [
        {
            "id": "a2-sec-1",
            "title": "Раздел 1. Действие сейчас, прошлое и планы на будущее",
            "description": "Present Continuous, Past Simple и Future Simple / be going to.",
            "lessons": [
                {
                    "id": "a2-l1",
                    "kind": "lesson",
                    "title": "Present Continuous (прямо сейчас) и отличие от Present Simple",
                    "skill_focus": ["grammar", "listening", "speaking"],
                    "estimated_minutes": 16,
                    "showcase": [
                        {"en": "Usually I drink tea, but right now I am drinking coffee.", "ru": "Обычно -> drink (Present Simple), прямо сейчас в момент речи -> am drinking (Present Continuous).", "speak": "Usually I drink tea, but right now I am drinking coffee."},
                        {"en": "She is talking on the phone now. Are you waiting for the bus?", "ru": "Формула простая: am / is / are + глагол с окончанием -ing.", "speak": "She is talking on the phone now. Are you waiting for the bus?"},
                    ],
                    "simple_explanation": "Если действие происходит прямо на ваших глазах в эту секунду (маркеры now — сейчас, right now — прямо сейчас, at the moment — в данный момент), англичане включают «прямой эфир»: берут уже знакомую связку am / is / are и добавляют к глаголу окончание -ing: I am working now (Я работаю прямо сейчас). Не забывайте связку am/is/are — один только -ing без неё не работает!",
                    "rule_name": "Present Continuous (am / is / are + V-ing)",
                    "examples": [
                        {"en": "I am reading an email right now.", "ipa": "/aɪ æm ˈriːdɪŋ ən ˈiːmeɪl raɪt naʊ/", "ru_hint": "ай эм ридинг эн имейл райт нау", "ru": "Я читаю письмо прямо сейчас."},
                        {"en": "They are waiting outside.", "ipa": "/ðeɪ ɑː ˈweɪtɪŋ ˌaʊtˈsaɪd/", "ru_hint": "зэй ар уэйтинг аутсайд", "ru": "Они ждут на улице."},
                        {"en": "What are you doing?", "ipa": "/wɒt ɑː juː ˈduːɪŋ/", "ru_hint": "уот ар ю дуинг", "ru": "Что ты сейчас делаешь?"},
                    ],
                    "vocab": [
                        {"word": "wait", "ipa": "/weɪt/", "ru_hint": "уэйт", "ru": "ждать", "example": "Wait for me.", "topic": "Действия"},
                        {"word": "right now", "ipa": "/raɪt naʊ/", "ru_hint": "райт нау", "ru": "прямо сейчас", "example": "I am busy right now.", "topic": "Время"},
                        {"word": "outside", "ipa": "/ˌaʊtˈsaɪd/", "ru_hint": "аутсайд", "ru": "снаружи, на улице", "example": "It is cold outside.", "topic": "Город"},
                        {"word": "usually", "ipa": "/ˈjuːʒuəli/", "ru_hint": "южуали", "ru": "обычно", "example": "Usually I walk.", "topic": "Время"},
                    ],
                    "exercises": [
                        {
                            "id": "a2-l1-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму: «Look! It ___ outside.» (Смотри! На улице идёт дождь)",
                            "options": ["is raining", "rains", "raining"],
                            "answer": "is raining",
                            "explanation": "Слово Look! показывает, что действие идёт прямо сейчас: is + raining."
                        },
                        {
                            "id": "a2-l1-ex2",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку: «I working on the report right now.»",
                            "answer": "I am working on the report right now.",
                            "accepted": ["I am working on the report right now.", "I am working on the report right now", "I'm working on the report right now.", "I'm working on the report right now"],
                            "explanation": "В Present Continuous перед V-ing обязательна связка am / is / are."
                        },
                        {
                            "id": "a2-l1-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопрос «Что ты сейчас делаешь?»:",
                            "words": ["doing", "you", "What", "now?", "are"],
                            "answer": "What are you doing now?",
                            "accepted": ["What are you doing now?", "What are you doing now"],
                            "explanation": "What + are + you + doing + now?"
                        },
                        {
                            "id": "a2-l1-ex4",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите: «Они ждут на улице.»",
                            "answer": "They are waiting outside.",
                            "accepted": ["They are waiting outside.", "They are waiting outside", "They're waiting outside.", "They're waiting outside"],
                            "explanation": "They are waiting outside."
                        }
                    ]
                },
                {
                    "id": "a2-l2",
                    "kind": "lesson",
                    "title": "Past Simple: завершённое прошлое и помощник did",
                    "skill_focus": ["grammar", "reading", "writing"],
                    "estimated_minutes": 11,
                    "showcase": [
                        {"en": "Yesterday I worked late and went home at 9 PM.", "ru": "В прошлом: правильные глаголы получают -ed (worked), неправильные — 2-ю форму (go -> went).", "speak": "Yesterday I worked late and went home at nine PM."},
                        {"en": "Did you call him? — I did not (didn't) see the message.", "ru": "В вопросе и отрицании в прошлом работает помощник did, а глагол возвращается в 1-ю форму!", "speak": "Did you call him? I did not see the message."},
                    ],
                    "simple_explanation": "Чтобы рассказать о завершённом событии в прошлом (yesterday — вчера, last week — на прошлой неделе), в утверждении добавляем к правильным глаголам окончание -ed (worked, visited), а у частых неправильных берём вторую форму (go — went, buy — bought, see — saw). В вопросах и отрицаниях приходит помощник did — и забирает прошедшее время на себя, поэтому сам глагол остаётся в 1-й форме: Did you go? I didn't go.",
                    "rule_name": "Past Simple (V-ed / V2, did / didn't)",
                    "examples": [
                        {"en": "Yesterday we bought tickets.", "ipa": "/ˈjestədeɪ wiː bɔːt ˈtɪkɪts/", "ru_hint": "естэдэй уи бот тикетс", "ru": "Вчера мы купили билеты."},
                        {"en": "Did you finish the task?", "ipa": "/dɪd juː ˈfɪnɪʃ ðə tɑːsk/", "ru_hint": "дид ю финиш зэ таск", "ru": "Ты закончил задачу?"},
                    ],
                    "vocab": [
                        {"word": "yesterday", "ipa": "/ˈjestədeɪ/", "ru_hint": "естэдэй", "ru": "вчера", "example": "I called you yesterday.", "topic": "Время"},
                        {"word": "bought", "ipa": "/bɔːt/", "ru_hint": "бот", "ru": "купил (2-я форма от buy)", "example": "She bought a coat.", "topic": "Покупки"},
                        {"word": "ticket", "ipa": "/ˈtɪkɪt/", "ru_hint": "тикет", "ru": "билет, заявка", "example": "Train ticket.", "topic": "Поездки"},
                    ],
                    "exercises": [
                        {
                            "id": "a2-l2-ex1",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте частую ошибку с помощником did: «Did you went to the office yesterday?»",
                            "answer": "Did you go to the office yesterday?",
                            "accepted": ["Did you go to the office yesterday?", "Did you go to the office yesterday"],
                            "explanation": "После помощника Did глагол всегда возвращается в начальную форму (go, а не went)."
                        },
                        {
                            "id": "a2-l2-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Поставьте глагол work в Past Simple: Last Friday I ___ from home.",
                            "answer": "worked",
                            "accepted": ["worked"],
                            "explanation": "Work — правильный глагол, в Past Simple добавляется окончание -ed: worked."
                        },
                        {
                            "id": "a2-l2-ex3",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите: «Вчера мы купили билеты.»",
                            "answer": "Yesterday we bought tickets.",
                            "accepted": ["Yesterday we bought tickets.", "Yesterday we bought tickets", "We bought tickets yesterday.", "We bought tickets yesterday"],
                            "explanation": "Buy во 2-й форме — bought: Yesterday we bought tickets."
                        }
                    ]
                },
                {
                    "id": "a2-l2b",
                    "kind": "lesson",
                    "title": "Будущее время: will vs be going to",
                    "skill_focus": ["grammar", "listening", "speaking"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "I will send the file now. (решение в момент речи)", "ru": "Спонтанное решение прямо сейчас, обещание или прогноз -> will + глагол.", "speak": "I will send the file now."},
                        {"en": "We are going to travel in July. (заранее задуманный план)", "ru": "Когда вы уже решили и запланировали действие заранее -> am/is/are going to.", "speak": "We are going to travel in July."},
                    ],
                    "simple_explanation": "Для будущего времени в английском есть два удобных инструмента: 1) will + глагол — когда вы принимаете решение прямо в секунду разговора, даёте обещание или делаете прогноз («Не переживай, я помогу» — I will help you!). 2) оборот be going to («собираюсь») — когда план уже продуман заранее («Завтра я собираюсь пойти к врачу» — I am going to see a doctor tomorrow).",
                    "rule_name": "Future Simple (will) vs Планы (be going to)",
                    "examples": [
                        {"en": "I am going to see a doctor tomorrow.", "ipa": "/aɪ æm ˈɡəʊɪŋ tuː siː ə ˈdɒktə təˈmɒrəʊ/", "ru_hint": "ай эм гоуинг ту си э доктэ тэмороу", "ru": "Я собираюсь пойти к врачу завтра."},
                        {"en": "Don't worry, I will call you.", "ipa": "/dəʊnt ˈwʌri aɪ wɪl kɔːl juː/", "ru_hint": "донт уори ай уил кол ю", "ru": "Не переживай, я тебе позвоню."},
                    ],
                    "vocab": [
                        {"word": "tomorrow", "ipa": "/təˈmɒrəʊ/", "ru_hint": "тэмороу", "ru": "завтра", "example": "See you tomorrow.", "topic": "Время"},
                        {"word": "doctor", "ipa": "/ˈdɒktə/", "ru_hint": "доктэ", "ru": "врач", "example": "See a doctor.", "topic": "Здоровье"},
                    ],
                    "exercises": [
                        {
                            "id": "a2-l2b-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "У вас уже куплены чемоданы и запланирован отпуск. Как естественнее сказать «Мы собираемся поехать в Рим в мае»?",
                            "options": [
                                "We are going to travel to Rome in May.",
                                "We travel to Rome yesterday.",
                                "We going travel to Rome in May."
                            ],
                            "answer": "We are going to travel to Rome in May.",
                            "explanation": "Для заранее намеченных планов используется конструкция am/is/are going to + глагол."
                        },
                        {
                            "id": "a2-l2b-ex2",
                            "type": "listening_qa",
                            "skill": "listening",
                            "audio_text": "Hi Dana! Yesterday I felt a bit sick, so I stayed at home. Tomorrow I am going to visit the clinic at nine AM.",
                            "prompt": "Прослушайте голосовое сообщение. Что говорящий планирует сделать завтра?",
                            "options": ["Пойти в клинику в 9 утра", "Поехать в аэропорт за билетами", "Работать в офисе допоздна"],
                            "answer": "Пойти в клинику в 9 утра",
                            "explanation": "Прозвучало: «Tomorrow I am going to visit the clinic at nine AM»."
                        },
                        {
                            "id": "a2-l2b-ex3",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите спонтанное обещание: «Не переживай, я тебе позвоню.» (используйте will)",
                            "answer": "Don't worry, I will call you.",
                            "accepted": ["Don't worry, I will call you.", "Don't worry, I will call you", "Do not worry, I will call you.", "I will call you."],
                            "explanation": "Спонтанное обещание в момент разговора передаётся через will: I will call you."
                        }
                    ]
                },
                {
                    "id": "a2-l3",
                    "kind": "lesson",
                    "title": "Степени сравнения прилагательных (faster, better, more comfortable)",
                    "skill_focus": ["grammar", "vocabulary"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "faster → the fastest | more comfortable → the most comfortable", "ru": "Короткие прилагательные: -er / the -est; длинные: more / the most.", "speak": "faster, the fastest, more comfortable"},
                        {"en": "good → better → the best | bad → worse → the worst", "ru": "Два главных исключения: good (лучше — better) и bad (хуже — worse).", "speak": "good, better, the best"},
                    ],
                    "simple_explanation": "Чтобы сравнить два предмета: к коротким словам в 1 слог добавляем -er (cheaper — дешевле, faster — быстрее) и the -est для превосходной степени (the cheapest — самый дешёвый). Перед длинными словами (2+ слога) ставим more / the most (more important — важнее). Обязательно запомните два исключения: good -> better -> the best (лучший) и bad -> worse -> the worst (худший).",
                    "rule_name": "Степени сравнения прилагательных",
                    "examples": [
                        {"en": "This train is faster than the bus.", "ipa": "/ðɪs treɪn ɪz ˈfɑːstə ðæn ðə bʌs/", "ru_hint": "зис трэйн из фастэ зэн зэ бас", "ru": "Этот поезд быстрее, чем автобус."},
                        {"en": "Today I feel better.", "ipa": "/təˈdeɪ aɪ fiːl ˈbetə/", "ru_hint": "тудэй ай фил бэтэ", "ru": "Сегодня я чувствую себя лучше."},
                    ],
                    "vocab": [
                        {"word": "faster", "ipa": "/ˈfɑːstə/", "ru_hint": "фастэ", "ru": "быстрее", "example": "A faster route.", "topic": "Описание"},
                        {"word": "better", "ipa": "/ˈbetə/", "ru_hint": "бэтэ", "ru": "лучше", "example": "I feel better today.", "topic": "Здоровье"},
                    ],
                    "exercises": [
                        {
                            "id": "a2-l3-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму сравнения: «Today my English is ___ than last month.» (лучше, чем в прошлом месяце)",
                            "options": ["better", "gooder", "more good"],
                            "answer": "better",
                            "explanation": "Прилагательное good — исключение: good -> better -> the best."
                        },
                        {
                            "id": "a2-l3-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Образуйте сравнительную степень от fast: This train is ___ than the bus.",
                            "answer": "faster",
                            "accepted": ["faster"],
                            "explanation": "Короткое прилагательное fast получает суффикс -er: faster."
                        },
                        {
                            "id": "a2-l3-ex3",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму для длинного прилагательного comfortable (удобный):",
                            "options": ["more comfortable", "comfortabler", "most comfortable than"],
                            "answer": "more comfortable",
                            "explanation": "Длинные прилагательные образуют сравнительную степень с помощью слова more: more comfortable."
                        }
                    ]
                },
                {
                    "id": "a2-l3b",
                    "kind": "lesson",
                    "title": "Советы (should / have to) и количество (much / many)",
                    "skill_focus": ["grammar", "speaking", "writing"],
                    "estimated_minutes": 11,
                    "showcase": [
                        {"en": "You should rest. / I have to wear a badge at work.", "ru": "should — мягкий совет («стоит, следует»); have to / must — обязанность («нужно, приходится»).", "speak": "You should rest. I have to wear a badge at work."},
                        {"en": "How much time / water? vs How many tickets / messages?", "ru": "Неисчисляемое (вода, время, деньги) -> much; штучное -> many.", "speak": "How much time? How many tickets?"},
                    ],
                    "simple_explanation": "1) Модальные оттенки: should даёт дружеский совет («Тебе стоит отдохнуть» — You should rest), а have to говорит о правилах и необходимости («Мне приходится вставать в 7» — I have to get up at 7). 2) Исчисляемые и неисчисляемые: то, что можно посчитать штуками (apples, emails, tickets) — это many; то, что нельзя посчитать поштучно (water, money, information, time) — это much.",
                    "rule_name": "Модальные (should / have to / must) и much / many",
                    "examples": [
                        {"en": "You should drink more water.", "ipa": "/juː ʃʊd drɪŋk mɔː ˈwɔːtə/", "ru_hint": "ю шуд дринк мо уотэ", "ru": "Тебе стоит пить больше воды."},
                        {"en": "How much does this jacket cost?", "ipa": "/haʊ mʌtʃ dʌz ðɪs ˈdʒækɪt kɒst/", "ru_hint": "хау мач даз зис джэкит кост", "ru": "Сколько стоит эта куртка?"},
                    ],
                    "vocab": [
                        {"word": "should", "ipa": "/ʃʊd/", "ru_hint": "шуд", "ru": "следует, стоит (совет)", "example": "You should sleep.", "topic": "Модальные глаголы"},
                        {"word": "price", "ipa": "/praɪs/", "ru_hint": "прайс", "ru": "цена", "example": "Good price.", "topic": "Покупки"},
                        {"word": "medicine", "ipa": "/ˈmedsn/", "ru_hint": "мэдсн", "ru": "лекарство", "example": "Take this medicine.", "topic": "Здоровье"},
                    ],
                    "exercises": [
                        {
                            "id": "a2-l3b-ex1",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте much или many: How ___ time do we have before the flight?",
                            "answer": "much",
                            "accepted": ["much"],
                            "explanation": "Time (время) — неисчисляемое существительное, поэтому используется much."
                        },
                        {
                            "id": "a2-l3b-ex2",
                            "type": "mini_dialogue",
                            "skill": "speaking",
                            "context": "Вы в аптеке, у вас болит горло.",
                            "speaker_line": "Good afternoon! How can I help you?",
                            "speaker_ru": "Добрый день! Чем могу вам помочь?",
                            "prompt": "Выберите естественный ответ покупателя:",
                            "options": [
                                "I have a sore throat. What medicine should I take?",
                                "I am have throat. Give medicine much.",
                                "Where did you bought medicine yesterday?"
                            ],
                            "answer": "I have a sore throat. What medicine should I take?",
                            "explanation": "Корректная бытовая реплика уровня A2: называем симптом и спрашиваем совет с модальным глаголом should."
                        },
                        {
                            "id": "a2-l3b-ex3",
                            "type": "guided_writing",
                            "skill": "writing",
                            "prompt": "Напишите короткое сообщение коллеге (1–2 предложения) о том, что завтра вы собираетесь работать из дома (используйте tomorrow и going to).",
                            "sample": "Hi! Tomorrow I am going to work from home.",
                            "required_tokens": ["tomorrow", "going", "to"],
                            "min_words": 5,
                            "answer": "Tomorrow I am going to work from home.",
                            "explanation": "Отлично! Конструкция going to + tomorrow чётко передаёт запланированное действие."
                        }
                    ]
                },
                {
                    "id": "a2-exam",
                    "kind": "exam",
                    "title": "Итоговый экзамен A2 (переход на уровень B1)",
                    "skill_focus": ["grammar", "reading", "listening", "writing", "vocabulary"],
                    "estimated_minutes": 18,
                    "simple_explanation": "Проверяем уверенное владение базовыми временами (Present Simple / Continuous, Past Simple, Future), степенями сравнения, модальными конструкциями и бытовым общением.",
                    "rule_name": "Экзамен уровня A2 (порог — 80%)",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "a2-ex-1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите верный вариант: «Please be quiet, the baby ___ right now.»",
                            "options": ["is sleeping", "sleeps", "slept"],
                            "answer": "is sleeping",
                            "explanation": "Действие происходит прямо сейчас (right now) -> Present Continuous: is sleeping."
                        },
                        {
                            "id": "a2-ex-2",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку: «We didn't saw him at the station.»",
                            "answer": "We didn't see him at the station.",
                            "accepted": ["We didn't see him at the station.", "We didn't see him at the station", "We did not see him at the station.", "We did not see him at the station"],
                            "explanation": "После didn't используется начальная форма глагола see (а не saw)."
                        },
                        {
                            "id": "a2-ex-3",
                            "type": "reading_qa",
                            "skill": "reading",
                            "passage": "Last weekend Sanzhar went to Astana by train because train tickets were cheaper and more comfortable than flights. Next month he is going to visit Shymkent with his family.",
                            "prompt": "Почему Санжар выбрал поезд для поездки в Астану?",
                            "options": [
                                "Билеты на поезд были дешевле и удобнее перелёта",
                                "В аэропорту отменили все рейсы из-за снега",
                                "Он боится летать на самолётах"
                            ],
                            "answer": "Билеты на поезд были дешевле и удобнее перелёта",
                            "explanation": "В тексте прямо сказано: «because train tickets were cheaper and more comfortable than flights»."
                        },
                        {
                            "id": "a2-ex-4",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите совет: «Тебе стоит отдохнуть.» (используйте rest)",
                            "answer": "You should rest.",
                            "accepted": ["You should rest.", "You should rest", "You should take a rest.", "You should get some rest."],
                            "explanation": "Совет передаётся через should: You should rest."
                        }
                    ]
                }
            ]
        }
    ]
}


LEVEL_B1 = {
    "id": "B1",
    "code": "B1",
    "title": "B1 — Самостоятельный английский",
    "subtitle": "Present Perfect, условные предложения, пассивный залог, косвенная речь, рабочая переписка и выражение мнения",
    "cefr_goal": "Уверенно общаться в большинстве рабочих и жизненных ситуаций, связывать прошлый опыт с настоящим, писать деловые письма, аргументировать своё мнение и понимать связную речь.",
    "pass_exam_score": 80,
    "sections": [
        {
            "id": "b1-sec-1",
            "title": "Раздел 1. Результат к настоящему, условия, пассив и косвенная речь",
            "description": "Главные конструкции среднего уровня для живой речи и переписки.",
            "lessons": [
                {
                    "id": "b1-l1",
                    "kind": "lesson",
                    "title": "Present Perfect (результат и опыт) против Past Simple",
                    "skill_focus": ["grammar", "reading", "writing"],
                    "estimated_minutes": 18,
                    "showcase": [
                        {"en": "I have already sent the report. (результат есть сейчас!)", "ru": "Когда не важно «когда именно», а важен готовый РЕЗУЛЬТАТ сейчас -> have / has + V3.", "speak": "I have already sent the report."},
                        {"en": "I sent the report two hours ago. (закрытая точка в прошлом)", "ru": "Как только назвали ТОЧНОЕ время в прошлом (yesterday, two hours ago, in 2022) — только Past Simple!", "speak": "I sent the report two hours ago."},
                    ],
                    "simple_explanation": "Новички часто путают Past Simple и Present Perfect, потому что на русский оба переводятся прошедшим временем («отправил»). Секрет прост: Past Simple — это «архив» с датой (вчера, в 2023 году, 5 минут назад — время уже закончилось). А Present Perfect (have/has + 3-я форма глагола) — это «мост в настоящее»: вы показываете свежий результат прямо сейчас («Я уже отправил отчёт — вот он у тебя на почте!») или жизненный опыт без даты («Я бывал в Лондоне» — I have been to London). Его верные спутники: already (уже), just (только что), yet (ещё не / уже в вопросе), ever / never.",
                    "rule_name": "Present Perfect (have / has + V3) vs Past Simple",
                    "examples": [
                        {"en": "We have just finished the deployment.", "ipa": "/wiː hæv dʒʌst ˈfɪnɪʃt ðə dɪˈplɔɪmənt/", "ru_hint": "уи хэв джаст финишт зэ диплоймэнт", "ru": "Мы только что завершили развёртывание."},
                        {"en": "Have you ever worked remotely?", "ipa": "/hæv juː ˈevə wɜːkt rɪˈməʊtli/", "ru_hint": "хэв ю эвэ уёркт римоутли", "ru": "Ты когда-нибудь работал удалённо?"},
                        {"en": "She hasn't replied to my email yet.", "ipa": "/ʃiː ˈhæznt rɪˈplaɪd tuː maɪ ˈiːmeɪl jet/", "ru_hint": "ши хэзнт риплайд ту май имейл ет", "ru": "Она ещё не ответила на моё письмо."},
                    ],
                    "vocab": [
                        {"word": "already", "ipa": "/ɔːlˈredi/", "ru_hint": "олрэди", "ru": "уже", "example": "I have already checked it.", "topic": "Грамматика и время"},
                        {"word": "yet", "ipa": "/jet/", "ru_hint": "ет", "ru": "ещё (в отриц.) / уже (в вопр.)", "example": "Not yet.", "topic": "Грамматика и время"},
                        {"word": "remotely", "ipa": "/rɪˈməʊtli/", "ru_hint": "римоутли", "ru": "удалённо", "example": "Work remotely.", "topic": "Работа и учёба"},
                        {"word": "reply", "ipa": "/rɪˈplaɪ/", "ru_hint": "риплай", "ru": "отвечать, ответ", "example": "Thank you for your quick reply.", "topic": "Деловая переписка"},
                        {"word": "experience", "ipa": "/ɪkˈspɪəriəns/", "ru_hint": "икспиариэнс", "ru": "опыт", "example": "Valuable experience.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "b1-l1-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму: «I ___ the contract yesterday afternoon.»",
                            "hint": "Есть точное указание прошедшего времени: yesterday afternoon.",
                            "options": ["signed", "have signed", "has signed"],
                            "answer": "signed",
                            "explanation": "При точном маркере прошлого (yesterday afternoon) Present Perfect запрещён — используется только Past Simple (signed)."
                        },
                        {
                            "id": "b1-l1-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Вставьте have или has: She ___ already updated the document.",
                            "answer": "has",
                            "accepted": ["has"],
                            "explanation": "Для she в Present Perfect используется вспомогательный глагол has."
                        },
                        {
                            "id": "b1-l1-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите вопрос о жизненном опыте: «Ты когда-нибудь работал удалённо?»",
                            "words": ["remotely?", "ever", "you", "worked", "Have"],
                            "answer": "Have you ever worked remotely?",
                            "accepted": ["Have you ever worked remotely?", "Have you ever worked remotely"],
                            "explanation": "Have + you + ever + V3 (worked) + remotely?"
                        },
                        {
                            "id": "b1-l1-ex4",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите: «Я уже отправил отчёт.» (используйте already и sent)",
                            "answer": "I have already sent the report.",
                            "accepted": [
                                "I have already sent the report.",
                                "I have already sent the report",
                                "I've already sent the report.",
                                "I've already sent the report",
                                "I have already sent a report."
                            ],
                            "explanation": "Результат к настоящему моменту: I have already sent the report."
                        }
                    ]
                },
                {
                    "id": "b1-l2",
                    "kind": "lesson",
                    "title": "Условные предложения: 1st & 2nd Conditionals",
                    "skill_focus": ["grammar", "speaking"],
                    "estimated_minutes": 11,
                    "showcase": [
                        {"en": "1st: If we finish early, we will call you. (реальное будущее, без will после if!)", "ru": "В части с If для реального будущего пишем настоящее время (Present Simple), а will — только в главной части.", "speak": "If we finish early, we will call you."},
                        {"en": "2nd: If I had more time, I would learn Spanish. (воображаемая ситуация сейчас)", "ru": "Воображаемое «если бы»: If + Past Simple, ... would + глагол.", "speak": "If I had more time, I would learn Spanish."},
                    ],
                    "simple_explanation": "В реальном условии (First Conditional: «Если пойдёт дождь, мы останемся дома») после слова if НЕ ставится will — там работает обычный Present Simple: If it rains, we will stay at home. А для мечты или воображаемого условия в настоящем («Если бы я был на твоём месте...») берём Second Conditional: If I were you, I would accept the offer.",
                    "rule_name": "Conditionals (Type 1 & Type 2)",
                    "examples": [
                        {"en": "If you send the draft today, I will review it tomorrow.", "ipa": "/ɪf juː send ðə drɑːft təˈdeɪ aɪ wɪl rɪˈvjuː ɪt təˈmɒrəʊ/", "ru_hint": "иф ю сэнд зэ драфт тудэй ай уил ривью ит тэмороу", "ru": "Если вы пришлёте черновик сегодня, я проверю его завтра."},
                        {"en": "If I were you, I would talk to the manager.", "ipa": "/ɪf aɪ wɜː juː aɪ wʊd tɔːk tuː ðə ˈmænɪdʒə/", "ru_hint": "иф ай уё ю ай вуд ток ту зэ мэнэджэ", "ru": "На твоём месте я бы поговорил с руководителем."},
                    ],
                    "vocab": [
                        {"word": "draft", "ipa": "/drɑːft/", "ru_hint": "драфт", "ru": "черновик, проект документа", "example": "First draft.", "topic": "Деловая переписка"},
                        {"word": "accept", "ipa": "/əkˈsept/", "ru_hint": "эксэпт", "ru": "принимать", "example": "Accept an offer.", "topic": "Деловая переписка"},
                    ],
                    "exercises": [
                        {
                            "id": "b1-l2-ex1",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте классическую ошибку в 1-м типе условных предложений: «If it will rain tomorrow, we will stay inside.»",
                            "answer": "If it rains tomorrow, we will stay inside.",
                            "accepted": ["If it rains tomorrow, we will stay inside.", "If it rains tomorrow, we will stay inside", "If it rains tomorrow we will stay inside."],
                            "explanation": "В придаточном предложении после If для будущего времени используется Present Simple (rains), а не will rain."
                        },
                        {
                            "id": "b1-l2-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Дополните 2-й тип условных предложений: If I had more money, I ___ travel more.",
                            "answer": "would",
                            "accepted": ["would"],
                            "explanation": "В воображаемом «бы» в главной части используется would."
                        },
                        {
                            "id": "b1-l2-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите предложение совета в 2-м условном типе («На твоём месте я бы поговорил с менеджером»):",
                            "words": ["I", "would", "If", "were", "talk", "to the manager.", "you,", "I"],
                            "answer": "If I were you, I would talk to the manager.",
                            "accepted": ["If I were you, I would talk to the manager.", "If I were you, I would talk to the manager"],
                            "explanation": "Устойчивая формула совета: If I were you, I would..."
                        }
                    ]
                },
                {
                    "id": "b1-l2b",
                    "kind": "lesson",
                    "title": "Пассивный залог (Passive Voice: be + V3)",
                    "skill_focus": ["grammar", "reading"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "The system was updated at night. / Tickets are booked online.", "ru": "Когда важнее сам предмет и результат, а не кто сделал действие -> be (am/is/are/was/were) + 3-я форма глагола (V3).", "speak": "The system was updated at night."},
                    ],
                    "simple_explanation": "В деловых текстах, новостях и инструкциях часто не важно, кто именно выполнил действие — важен сам объект («Отчёт был отправлен», «Заявки обрабатываются автоматически»). Для этого берём нужную форму глагола be (is/are — сейчас, was/were — в прошлом, will be — в будущем) и 3-ю форму глагола: The server was installed last night.",
                    "rule_name": "Пассивный залог (Passive Voice: be + V3)",
                    "examples": [
                        {"en": "All requests are processed automatically.", "ipa": "/ɔːl rɪˈkwests ɑː ˈprəʊsest ˌɔːtəˈmætɪkli/", "ru_hint": "ол рикуэстс ар проусэст отомэкли", "ru": "Все заявки обрабатываются автоматически."},
                        {"en": "The report was sent yesterday.", "ipa": "/ðə rɪˈpɔːt wɒz sent ˈjestədeɪ/", "ru_hint": "зэ рипот уоз сэнт естэдэй", "ru": "Отчёт был отправлен вчера."},
                    ],
                    "vocab": [
                        {"word": "request", "ipa": "/rɪˈkwest/", "ru_hint": "рикуэст", "ru": "запрос, заявка", "example": "Submit a request.", "topic": "Работа и учёба"},
                        {"word": "review", "ipa": "/rɪˈvjuː/", "ru_hint": "ривью", "ru": "проверять, делать обзор", "example": "Review the document.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "b1-l2b-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите правильную форму Passive Voice: «The new server ___ last night.» (Новый сервер был установлен прошлой ночью)",
                            "options": ["was installed", "installed", "has installing"],
                            "answer": "was installed",
                            "explanation": "Сервер установили (над ним совершили действие) в прошлом (last night) -> was + V3 (was installed)."
                        },
                        {
                            "id": "b1-l2b-ex2",
                            "type": "reading_qa",
                            "skill": "reading",
                            "passage": "Dear Colleagues, Please note that the student database will be updated this Saturday from 10:00 PM to midnight. If you have unsaved reports, please export them before Friday evening. In my opinion, this update will make daily searches twice as fast.",
                            "prompt": "Что авторы письма просят сделать сотрудников до вечера пятницы?",
                            "options": [
                                "Экспортировать несохранённые отчёты",
                                "Переустановить браузер на рабочем компьютере",
                                "Прийти в офис в субботу к полуночи"
                            ],
                            "answer": "Экспортировать несохранённые отчёты",
                            "explanation": "В письме указано: «If you have unsaved reports, please export them before Friday evening»."
                        },
                        {
                            "id": "b1-l2b-ex3",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Дополните пассивный залог в настоящем времени: All requests ___ processed automatically.",
                            "answer": "are",
                            "accepted": ["are"],
                            "explanation": "Requests во множественном числе, настоящее время -> are processed."
                        }
                    ]
                },
                {
                    "id": "b1-l2c",
                    "kind": "lesson",
                    "title": "Косвенная речь (Reported Speech) и выражение мнения",
                    "skill_focus": ["grammar", "writing", "speaking"],
                    "estimated_minutes": 10,
                    "showcase": [
                        {"en": "«I am ready.» → He said that he was ready.", "ru": "Когда пересказываем чужие слова в прошлом (said that), глагол сдвигается на шаг назад (am/is -> was).", "speak": "He said that he was ready."},
                        {"en": "In my opinion, ... / I think that ...", "ru": "Вводные фразы помогают чётко и вежливо выразить свою точку зрения в переписке и обсуждении.", "speak": "In my opinion, working from home saves time."},
                    ],
                    "simple_explanation": "Когда вы передаёте чужие слова в прошлом (He said that... — Он сказал, что...), английский сдвигает время на один шаг в прошлое: «I am busy» превращается в He said that he was busy. А чтобы уверенно высказывать своё мнение в письмах и на встречах, используйте связки In my opinion, ... или From my point of view, ...",
                    "rule_name": "Косвенная речь (Reported Speech) и деловое мнение",
                    "examples": [
                        {"en": "She said that she liked the new office.", "ipa": "/ʃiː sed ðæt ʃiː laɪkt ðə njuː ˈɒfɪs/", "ru_hint": "ши сэд зэт ши лайкт зэ нью офис", "ru": "Она сказала, что ей понравился новый офис."},
                        {"en": "In my opinion, this plan is realistic.", "ipa": "/ɪn maɪ əˈpɪnjən ðɪs plæn ɪz ˌrɪəˈlɪstɪk/", "ru_hint": "ин май опиньон зис плэн из риэлистик", "ru": "По моему мнению, этот план реалистичен."},
                    ],
                    "vocab": [
                        {"word": "opinion", "ipa": "/əˈpɪnjən/", "ru_hint": "опиньон", "ru": "мнение", "example": "In my opinion...", "topic": "Общение"},
                        {"word": "colleague", "ipa": "/ˈkɒliːɡ/", "ru_hint": "колиг", "ru": "коллега", "example": "Dear colleagues.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "b1-l2c-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Переведите в косвенную речь: «We are ready.» -> They said that they ___ ready.",
                            "options": ["were", "are", "will be"],
                            "answer": "were",
                            "explanation": "После глагола в прошлом (said) форма are сдвигается на шаг назад — were."
                        },
                        {
                            "id": "b1-l2c-ex2",
                            "type": "guided_writing",
                            "skill": "writing",
                            "prompt": "Изложите мнение (1–2 предложения) о работе из дома или в офисе, начав с фразы «In my opinion, ...» или «I think that ...»",
                            "sample": "In my opinion, working from home saves a lot of time.",
                            "required_tokens": ["opinion", "work"],
                            "alternative_tokens": ["think", "work"],
                            "min_words": 6,
                            "answer": "In my opinion, working from home saves time.",
                            "explanation": "Отлично! Вводные конструкции In my opinion / I think that помогают структурно выражать свою точку зрения на уровне B1."
                        },
                        {
                            "id": "b1-l2c-ex3",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Передайте слова коллеги в прошлом: «I am busy.» -> He said that he ___ busy.",
                            "answer": "was",
                            "accepted": ["was"],
                            "explanation": "В косвенной речи после said глагол am сдвигается в форму прошедшего времени was."
                        }
                    ]
                },
                {
                    "id": "b1-exam",
                    "kind": "exam",
                    "title": "Итоговый экзамен B1 (переход на уровень B2)",
                    "skill_focus": ["grammar", "reading", "listening", "writing", "speaking"],
                    "estimated_minutes": 20,
                    "simple_explanation": "Комплексный экзамен уровня B1: Present Perfect vs Past Simple, условные предложения, пассивный залог, косвенная речь и рабочая коммуникация. Порог — 80%.",
                    "rule_name": "Экзамен уровня B1 (порог — 80%)",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "b1-ex-1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите верный вариант косвенной речи: Аскар сказал «I am busy». -> Askar said that he ___ busy.",
                            "options": ["was", "is", "has been"],
                            "answer": "was",
                            "explanation": "По правилу согласования времён после said глагол am сдвигается в прошедшее время — was."
                        },
                        {
                            "id": "b1-ex-2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Заполните пропуск во 2-м условном предложении: If I were you, I ___ check the data twice.",
                            "answer": "would",
                            "accepted": ["would"],
                            "explanation": "Во втором типе условных предложений в главной части используется would + инфинитив без to."
                        },
                        {
                            "id": "b1-ex-3",
                            "type": "listening_qa",
                            "skill": "listening",
                            "audio_text": "We have already tested the mobile version, and all critical bugs were fixed this morning. If the client approves the layout today, we will launch on Monday.",
                            "prompt": "При каком условии команда запустит проект в понедельник?",
                            "options": [
                                "Если клиент утвердит макет сегодня",
                                "Если разработчики найдут новый сервер",
                                "Если тестирование перенесут на следующую неделю"
                            ],
                            "answer": "Если клиент утвердит макет сегодня",
                            "explanation": "Прозвучало: «If the client approves the layout today, we will launch on Monday»."
                        },
                        {
                            "id": "b1-ex-4",
                            "type": "translate_ru_en",
                            "skill": "writing",
                            "prompt": "Переведите деловую фразу: «Она ещё не ответила.» (используйте replied и yet)",
                            "answer": "She has not replied yet.",
                            "accepted": [
                                "She has not replied yet.",
                                "She has not replied yet",
                                "She hasn't replied yet.",
                                "She hasn't replied yet"
                            ],
                            "explanation": "Present Perfect с yet на конце: She hasn't replied yet."
                        }
                    ]
                }
            ]
        }
    ]
}


LEVEL_B2 = {
    "id": "B2",
    "code": "B2",
    "title": "B2 — Уверенное владение",
    "subtitle": "Сложная грамматика, фразовые глаголы, устойчивые сочетания, деловая аргументация, отчёты и дискуссии",
    "cefr_goal": "Понимать беглую речь и сложные профессиональные тексты, гибко использовать фразовые глаголы и идиоматические связки, убедительно аргументировать позицию в презентациях, письмах и отчётах.",
    "pass_exam_score": 80,
    "sections": [
        {
            "id": "b2-sec-1",
            "title": "Раздел 1. Тонкие оттенки смысла, фразовые глаголы и деловая аргументация",
            "description": "Нереальное прошлое, модальные перфекты, фразовые глаголы и структура аргументации.",
            "lessons": [
                {
                    "id": "b2-l1",
                    "kind": "lesson",
                    "title": "Сложные конструкции: Third Conditional и модальные глаголы в прошлом",
                    "skill_focus": ["grammar", "reading", "writing"],
                    "estimated_minutes": 20,
                    "showcase": [
                        {"en": "If we had backed up the file, we wouldn't have lost the data.", "ru": "Third Conditional (сожаление о прошлом): If + had V3, ... would have V3.", "speak": "If we had backed up the file, we wouldn't have lost the data."},
                        {"en": "You should have warned us earlier. / He must have forgotten.", "ru": "should have V3 — «следовало сделать (но не сделал)»; must have V3 — «должно быть, сделал (уверенная догадка)».", "speak": "You should have warned us earlier. He must have forgotten."},
                    ],
                    "simple_explanation": "На уровне B2 вы учитесь говорить не только о фактах, но и разбирать альтернативные сценарии в прошлом («А что было бы, если бы мы тогда поступили иначе?») и делать точные выводы. 1) Third Conditional описывает ситуацию в прошлом, которую уже не вернуть: после If ставим Past Perfect (had + V3), а во второй части — would have + V3. 2) Модальные глаголы с перфектом (have + V3) передают тонкую оценку прошлого: should have done — мягкий упрёк или вывод («Нужно было проверить заранее»), must have done — логический вывод на 90% («Наверняка он забыл»), could have done — упущенная возможность («Могли бы успеть»).",
                    "rule_name": "Third Conditional (If + had V3, would have V3) & Past Modals",
                    "examples": [
                        {"en": "If you had told me earlier, I would have helped you.", "ipa": "/ɪf juː hæd təʊld miː ˈɜːliə aɪ wʊd hæv helpt juː/", "ru_hint": "иф ю хэд толд ми ёлиэ ай вуд хэв хэлпт ю", "ru": "Если бы ты сказал мне раньше, я бы тебе помог."},
                        {"en": "We should have tested this edge case before the release.", "ipa": "/wiː ʃʊd hæv ˈtestɪd ðɪs edʒ keɪs bɪˈfɔː ðə rɪˈliːs/", "ru_hint": "уи шуд хэв тэстид зис эдж кейс бифо зэ рилис", "ru": "Нам следовало протестировать этот пограничный случай до релиза."},
                        {"en": "She must have left her phone in the meeting room.", "ipa": "/ʃiː mʌst hæv left hɜː fəʊn ɪn ðə ˈmiːtɪŋ ruːm/", "ru_hint": "ши маст хэв лэфт хё фоун ин зэ митинг рум", "ru": "Должно быть, она оставила телефон в переговорной."},
                    ],
                    "vocab": [
                        {"word": "release", "ipa": "/rɪˈliːs/", "ru_hint": "рилис", "ru": "выпуск, релиз", "example": "Before the release.", "topic": "Деловая и IT-лексика"},
                        {"word": "outcome", "ipa": "/ˈaʊtkʌm/", "ru_hint": "ауткам", "ru": "итог, результат, исход", "example": "Positive outcome.", "topic": "Деловая и академическая речь"},
                        {"word": "prevent", "ipa": "/prɪˈvent/", "ru_hint": "привэнт", "ru": "предотвращать", "example": "Prevent errors.", "topic": "Деловая и академическая речь"},
                        {"word": "evidence", "ipa": "/ˈevɪdəns/", "ru_hint": "эвидэнс", "ru": "доказательства, фактические данные", "example": "Clear evidence.", "topic": "Деловая и академическая речь"},
                    ],
                    "exercises": [
                        {
                            "id": "b2-l1-ex1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Как правильно выразить мысль «Нам следовало отправить приглашение на прошлой неделе (но мы не отправили)»?",
                            "options": [
                                "We should have sent the invitation last week.",
                                "We should send the invitation last week.",
                                "We must sending the invitation last week."
                            ],
                            "answer": "We should have sent the invitation last week.",
                            "explanation": "Оценка невыполненного действия в прошлом передаётся конструкцией should have + V3 (sent)."
                        },
                        {
                            "id": "b2-l1-ex2",
                            "type": "fill_blank",
                            "skill": "grammar",
                            "prompt": "Дополните Third Conditional: If they ___ checked the schedule, they wouldn't have missed the flight.",
                            "answer": "had",
                            "accepted": ["had"],
                            "explanation": "В условии 3-го типа используется Past Perfect: If they had checked..."
                        },
                        {
                            "id": "b2-l1-ex3",
                            "type": "word_order",
                            "skill": "grammar",
                            "prompt": "Соберите предложение логического вывода о прошлом («Должно быть, он забыл о встрече»):",
                            "words": ["forgotten", "must", "the", "about", "He", "have", "meeting."],
                            "answer": "He must have forgotten about the meeting.",
                            "accepted": ["He must have forgotten about the meeting.", "He must have forgotten about the meeting"],
                            "explanation": "Уверенный вывод о прошлом: must + have + V3 (forgotten)."
                        }
                    ]
                },
                {
                    "id": "b2-l2",
                    "kind": "lesson",
                    "title": "Фразовые глаголы и деловые устойчивые сочетания",
                    "skill_focus": ["vocabulary", "speaking"],
                    "estimated_minutes": 11,
                    "showcase": [
                        {"en": "figure out (разобраться), carry out (провести/выполнить), put off (отложить)", "ru": "В живой речи носители говорят figure out вместо solve и put off вместо postpone.", "speak": "figure out, carry out, put off"},
                        {"en": "make a decision | meet a deadline", "ru": "Устойчивые сочетания (collocations): именно make a decision (не do!), meet a deadline.", "speak": "make a decision, meet a deadline"},
                    ],
                    "simple_explanation": "На уровне B2 разница между «учебниковым» и естественным английским кроется во фразовых глаголах и устойчивых словосочетаниях (collocations). Вместо сухого do/solve носители говорят make a decision (принять решение), meet a deadline (уложиться в срок), carry out an audit (провести проверку), figure out the root cause (выяснить первопричину), put off a meeting (перенести/отложить встречу).",
                    "rule_name": "Phrasal Verbs & Business Collocations",
                    "examples": [
                        {"en": "We need to figure out why the conversion rate dropped.", "ipa": "/wiː niːd tuː ˈfɪɡər aʊt waɪ ðə kənˈvɜːʃn reɪt drɒpt/", "ru_hint": "уи нид ту фигэр аут уай зэ конвёршн рэйт дропт", "ru": "Нам нужно разобраться, почему упала конверсия."},
                        {"en": "Let's not put off this decision until next quarter.", "ipa": "/lets nɒt pʊt ɒf ðɪs dɪˈsɪʒn ənˈtɪl nekst ˈkwɔːtə/", "ru_hint": "лэтс нот пут оф зис дисижн антил нэкст куотэ", "ru": "Давайте не будем откладывать это решение до следующего квартала."},
                    ],
                    "vocab": [
                        {"word": "figure out", "ipa": "/ˈfɪɡər aʊt/", "ru_hint": "фигэр аут", "ru": "разобраться, выяснить, понять", "example": "I will figure it out.", "topic": "Фразовые глаголы"},
                        {"word": "put off", "ipa": "/pʊt ɒf/", "ru_hint": "пут оф", "ru": "откладывать, переносить", "example": "Never put off important tasks.", "topic": "Фразовые глаголы"},
                        {"word": "carry out", "ipa": "/ˈkæri aʊt/", "ru_hint": "кэри аут", "ru": "проводить, выполнять (исследование, работу)", "example": "Carry out a survey.", "topic": "Фразовые глаголы"},
                        {"word": "deadline", "ipa": "/ˈdedlaɪn/", "ru_hint": "дэдлайн", "ru": "крайний срок", "example": "Meet a tight deadline.", "topic": "Работа и учёба"},
                    ],
                    "exercises": [
                        {
                            "id": "b2-l2-ex1",
                            "type": "match",
                            "skill": "vocabulary",
                            "prompt": "Сопоставьте фразовые глаголы и устойчивые сочетания с их точным значением:",
                            "pairs": [
                                {"left": "figure out", "right": "разобраться, найти решение"},
                                {"left": "put off", "right": "отложить на потом"},
                                {"left": "carry out", "right": "провести, выполнить (проверку/анализ)"},
                                {"left": "meet a deadline", "right": "уложиться в крайний срок"},
                            ],
                            "explanation": "Эти четыре сочетания — базовый словарь делового общения уровня B2."
                        },
                        {
                            "id": "b2-l2-ex2",
                            "type": "choice",
                            "skill": "vocabulary",
                            "prompt": "Выберите естественное устойчивое сочетание для «принять решение»:",
                            "options": ["make a decision", "do a decision", "put a decision"],
                            "answer": "make a decision",
                            "explanation": "Со словом decision в английском используется глагол make: make a decision."
                        },
                        {
                            "id": "b2-l2-ex3",
                            "type": "fill_blank",
                            "skill": "vocabulary",
                            "prompt": "Заполните пропуск фразовым глаголом («не откладывайте»): Let's not put ___ this decision until next week.",
                            "answer": "off",
                            "accepted": ["off"],
                            "explanation": "Откладывать на потом — put off."
                        }
                    ]
                },
                {
                    "id": "b2-l2b",
                    "kind": "lesson",
                    "title": "Деловая аргументация, отчёты и эссе",
                    "skill_focus": ["reading", "writing", "speaking"],
                    "estimated_minutes": 12,
                    "showcase": [
                        {"en": "However, ... | Furthermore, ... | Taking everything into account, ...", "ru": "Логические связки уровня B2 превращают отдельные фразы в убедительный отчёт или выступление.", "speak": "However, furthermore, taking everything into account."},
                    ],
                    "simple_explanation": "Чтобы ваши отчёты, презентации и эссе звучали убедительно, связывайте мысли логическими маркерами: On the one hand / On the other hand (с одной / с другой стороны), However (однако), Furthermore / Moreover (более того), As a result (в результате), Outweigh (перевешивать по значимости).",
                    "rule_name": "Discourse Markers & Structured Argumentation",
                    "examples": [
                        {"en": "However, the benefits clearly outweigh the initial costs.", "ipa": "/haʊˈevə ðə ˈbenɪfɪts ˈklɪəli ˌaʊtˈweɪ ðə ɪˈnɪʃl kɒsts/", "ru_hint": "хауэвэ зэ бэнифитс клиали аутвэй зи инишл костс", "ru": "Однако преимущества явно перевешивают начальные затраты."},
                    ],
                    "vocab": [
                        {"word": "outweigh", "ipa": "/ˌaʊtˈweɪ/", "ru_hint": "аутвэй", "ru": "перевешивать, превосходить по значимости", "example": "Pros outweigh cons.", "topic": "Деловая и академическая речь"},
                    ],
                    "exercises": [
                        {
                            "id": "b2-l2b-ex1",
                            "type": "reading_qa",
                            "skill": "reading",
                            "passage": "Executive Summary: Over the past six months, our department carried out a comprehensive transition to digital document workflows. Although initial training required extra hours, the long-term gains clearly outweigh the effort: processing time has dropped by 42%, and error rates have fallen significantly. Moving forward, we recommend automating archive indexing as well.",
                            "prompt": "Каков главный вывод отчёта о переходе на цифровой документооборот?",
                            "options": [
                                "Долгосрочная выгода перевесила затраты на обучение: обработка ускорилась на 42%",
                                "Переход пришлось отложить из-за роста числа ошибок",
                                "Обучение оказалось слишком дорогим, поэтому отдел вернулся к бумаге"
                            ],
                            "answer": "Долгосрочная выгода перевесила затраты на обучение: обработка ускорилась на 42%",
                            "explanation": "В тексте указано: «the long-term gains clearly outweigh the effort: processing time has dropped by 42%»."
                        },
                        {
                            "id": "b2-l2b-ex2",
                            "type": "free_writing",
                            "skill": "writing",
                            "prompt": "Напишите короткий аргументированный абзац (2–3 предложения) по теме автоматизации на работе, используя хотя бы одну связку (например: however, furthermore, in addition, as a result).",
                            "sample": "Automation reduces routine manual tasks in the office. However, teams still need clear instructions to avoid mistakes. As a result, training remains essential.",
                            "required_any": ["however", "furthermore", "moreover", "addition", "result", "although"],
                            "min_words": 12,
                            "answer": "Automation saves time; however, proper training is essential.",
                            "explanation": "Отличная связная аргументация уровня B2 с использованием логического маркера!"
                        },
                        {
                            "id": "b2-l2b-ex3",
                            "type": "choice",
                            "skill": "vocabulary",
                            "prompt": "Какая логическая связка лучше всего подходит для противопоставления («Однако...»)?",
                            "options": ["However", "Furthermore", "As a result"],
                            "answer": "However",
                            "explanation": "However означает «однако» и используется для контраста, Furthermore — «более того», As a result — «в результате»."
                        }
                    ]
                },
                {
                    "id": "b2-exam",
                    "kind": "exam",
                    "title": "Финальный комплексный экзамен B2 (Сертификация курса A0–B2)",
                    "skill_focus": ["grammar", "vocabulary", "reading", "listening", "writing"],
                    "estimated_minutes": 25,
                    "simple_explanation": "Итоговая комплексная проверка владения английским на уровне B2: сложная грамматика, фразовые глаголы, понимание беглой деловой речи, аналитическое чтение и письмо.",
                    "rule_name": "Итоговый экзамен курса B2 (порог — 80%)",
                    "showcase": [],
                    "examples": [],
                    "vocab": [],
                    "exercises": [
                        {
                            "id": "b2-ex-1",
                            "type": "choice",
                            "skill": "grammar",
                            "prompt": "Выберите грамматически безупречный вариант: «If we ___ the bottleneck earlier, we would have met the deadline.»",
                            "options": ["had identified", "would identify", "have identified"],
                            "answer": "had identified",
                            "explanation": "Нереальное условие в прошлом (Third Conditional): If + Past Perfect (had identified)."
                        },
                        {
                            "id": "b2-ex-2",
                            "type": "fill_blank",
                            "skill": "vocabulary",
                            "prompt": "Вставьте подходящий по смыслу глагол устойчивого словосочетания («принять решение»): We need to ___ a final decision by Friday.",
                            "answer": "make",
                            "accepted": ["make", "reach", "take"],
                            "explanation": "Устойчивое сочетание (collocation) в английском: make (или reach) a decision."
                        },
                        {
                            "id": "b2-ex-3",
                            "type": "listening_qa",
                            "skill": "listening",
                            "audio_text": "While the new analytics tool looks promising on paper, we shouldn't rush into full deployment before carrying out a pilot test with one department. Otherwise, we risk disrupting daily operations.",
                            "prompt": "Что предлагает спикер перед полным внедрением нового аналитического инструмента?",
                            "options": [
                                "Провести пилотный тест в одном отделе, чтобы не нарушить текущую работу",
                                "Немедленно отключить старую систему во всей компании",
                                "Отказаться от аналитики до следующего года"
                            ],
                            "answer": "Провести пилотный тест в одном отделе, чтобы не нарушить текущую работу",
                            "explanation": "Спикер говорит: «before carrying out a pilot test with one department»."
                        },
                        {
                            "id": "b2-ex-4",
                            "type": "fix_error",
                            "skill": "grammar",
                            "prompt": "Исправьте ошибку в модальном перфекте: «You should have tell me about the issue yesterday.»",
                            "answer": "You should have told me about the issue yesterday.",
                            "accepted": ["You should have told me about the issue yesterday.", "You should have told me about the issue yesterday"],
                            "explanation": "После should have используется 3-я форма глагола (Past Participle): tell -> told."
                        },
                        {
                            "id": "b2-ex-5",
                            "type": "free_writing",
                            "skill": "writing",
                            "prompt": "Напишите 2–3 деловых предложения на английском: подведите итог выполненного проекта или предложите решение рабочей задачи (используйте связку however / as a result / therefore или фразовый глагол).",
                            "sample": "We carried out a full system check this morning. However, one module required an extra patch, so we deployed an update. As a result, all services are now stable.",
                            "required_any": ["however", "therefore", "result", "carried", "figured", "although", "because", "recommend"],
                            "min_words": 12,
                            "answer": "We carried out a full check; as a result, the system is stable.",
                            "explanation": "Поздравляем! Вы уверенно строите развёрнутые профессиональные высказывания уровня B2."
                        }
                    ]
                }
            ]
        }
    ]
}


def _attach_extra_section(level_dict: dict, extra_lessons: list[dict], sec_id: str, sec_title: str, sec_desc: str) -> None:
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


from .curriculum_a2_extra import A2_EXTRA_LESSONS as _A2_EXTRA
from .curriculum_b1_extra import B1_EXTRA_LESSONS as _B1_EXTRA
from .curriculum_b2_extra import B2_EXTRA_LESSONS as _B2_EXTRA

_attach_extra_section(
    LEVEL_A2,
    _A2_EXTRA,
    "a2-sec-2",
    "Раздел 2. Практика общения, переписка, поездки и здоровье",
    "Закрепление грамматики A2 и реальные бытовые/рабочие сценарии.",
)
_attach_extra_section(
    LEVEL_B1,
    _B1_EXTRA,
    "b1-sec-2",
    "Раздел 2. Рабочая коммуникация, отчёты, презентации и дискуссии",
    "Развитие связной речи, письма и чтения на уровне B1.",
)
_attach_extra_section(
    LEVEL_B2,
    _B2_EXTRA,
    "b2-sec-2",
    "Раздел 2. Профессиональный стиль, переговоры, отчёты и эссе",
    "Продвинутая грамматика, регистр, аналитическое письмо и презентации B2.",
)
