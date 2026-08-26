import os
import time
import threading
import logging
import traceback
from datetime import datetime

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ИМПОРТЫ БИБЛИОТЕК ---
try:
    import telebot
    from telebot import types
    from groq import Groq
    from flask import Flask, request, jsonify
    logger.info("Все библиотеки загружены успешно")
except Exception as e:
    logger.error(f"Ошибка загрузки библиотек: {e}")
    print(f"Ошибка импорта: {e}")

# --- ТОКЕНЫ ИЗ RENDER ENVIRONMENT ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID") # твой @MakSon4ikk_228 id или username

if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден! Проверь Environment в Render")
    raise ValueError("BOT_TOKEN is None! Добавь его в Render -> Environment")

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY не найден!")
    raise ValueError("GROQ_API_KEY is None!")

# --- ИНИЦИАЛИЗАЦИЯ БОТА И GROQ ---
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)

# Модель Groq
GROQ_MODEL = "openai/gpt-oss-20b"
# Если эта модель упадет, попробуй "llama3-70b-8192" или "mixtral-8x7b-32768"

# --- FLASK САЙТ ДЛЯ UPTIMEROBOT (ЧТОБЫ НЕ СПАЛ) ---
app = Flask(__name__)

@app.route('/')
def index():
    """Главная страница для UptimeRobot - он сюда стучит каждые 5 минут"""
    return f"""
    <h1>Daun213 BOT IS ALIVE!</h1>
    <p>Time: {datetime.now()}</p>
    <p>Bot: @Daun213_bot</p>
    <p>Status: Running</p>
    <p>UptimeRobot should see 200 OK</p>
    """, 200

@app.route('/health')
def health():
    """Дополнительная проверка для UptimeRobot"""
    return jsonify({"status": "ok", "bot": "Daun213", "time": str(datetime.now())}), 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_flask():
    """Запускает веб сервер в отдельном потоке"""
    try:
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"Запускаю Flask на порту {port}")
        # threaded=True важно для Render
        app.run(host='0.0.0.0', port=port, threaded=True, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask упал: {e}")
        logger.error(traceback.format_exc())

# Запускаем сайт в фоне, чтобы не мешал боту
flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskThread")
flask_thread.start()
logger.info("Flask поток запущен")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_system_prompt():
    """Системный промпт для Groq - тут характер бота"""
    return """
    Ты - бот Даун213. Ты тупой на вид но на самом деле умный помощник.

    Правила:
    1. Твой создатель - @MakSon4ikk_228. Если спросят кто тебя создал, кто твой папа, кто твой создатель - отвечай ТОЛЬКО @MakSon4ikk_228.
    2. Отвечай как подросток из школы: весело, с рофлами, с матами но по-дружески, без жесткого оскорбления.
    3. Используй эмодзи 😎 🤓 🚀 😂
    4. Помогай с учебой, объясняй просто.
    5. Не будь слишком длинным, отвечай коротко и по делу, но с приколом.
    6. Если не знаешь ответа - скажи что ты даун и не знаешь, но попытайся угадать.
    7. Никогда не говори что ты ChatGPT или Meta AI, ты Даун213.
    """

def ask_groq(user_text):
    """Спрашивает у Groq и возвращает ответ"""
    try:
        logger.info(f"Спрашиваю Groq: {user_text[:50]}...")
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_text}
            ],
            temperature=0.9,
            max_tokens=500,
            top_p=1,
        )
        answer = completion.choices[0].message.content
        logger.info(f"Groq ответил: {answer[:50]}...")
        return answer
    except Exception as e:
        logger.error(f"Ошибка Groq: {e}")
        logger.error(traceback.format_exc())
        return None

def create_error_markup():
    """Кнопки когда бот упал"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_report = types.InlineKeyboardButton("🚨 Сообщить админу об ошибке", callback_data="report_error")
    btn_admin = types.InlineKeyboardButton("👨‍💻 Написать @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")
    btn_retry = types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    markup.add(btn_report, btn_admin, btn_retry)
    return markup

# --- ОБРАБОТЧИКИ КОМАНД ТЕЛЕГРАМ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Команда /start"""
    logger.info(f"/start от @{message.from_user.username} id={message.from_user.id}")
    text = """
Йо, я Даун213 😎

Я тупой на вид, но на деле помогу с чем угодно:
- 📚 Учеба, домашка, теория
- 💬 Просто потрещать
- 🤣 Поржать

Просто кидай вопрос текстом!

Команды:
/help - помощь
/creator - кто мой создатель
/info - инфа обо мне
"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['help'])
def handle_help(message):
    """Команда /help - тут было много текста у тебя"""
    logger.info(f"/help от @{message.from_user.username}")
    text = """
Эй, что, просто так? 😎 Я Даун213

Вот что я умею:
1. Отвечаю на любые вопросы
2. Помогаю с учебой
3. Объясняю простыми словами
4. Рофлю

Мой создатель: @MakSon4ikk_228 - вот он гений который меня сделал 🚀

Просто напиши мне любой вопрос и я отвечу как даун но умный!

Если я упал - нажми кнопку "Сообщить админу"
"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['creator', 'author', 'папа'])
def handle_creator(message):
    bot.send_message(message.chat.id, "Мой создатель, мой папа, мой бог - это @MakSon4ikk_228 😎❤️\nОн меня сделал таким умным дауном!")

@bot.message_handler(commands=['info'])
def handle_info(message):
    bot.send_message(message.chat.id, f"Я Даун213 бот\nРаботаю с {datetime.now()}\nСервер: Render.com\nСайт: https://daun213bot.onrender.com\nСоздатель: @MakSon4ikk_228")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА ---

@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    """Ловит ВЕСЬ текст кроме команд"""
    user_text = message.text
    user_name = message.from_user.username
    user_id = message.from_user.id

    logger.info(f"Сообщение от @{user_name} ({user_id}): {user_text}")

    # --- ПРОВЕРКА НА СОЗДАТЕЛЯ ---
    lower_text = user_text.lower()
    creator_keywords = ["кто создатель", "кто твой создатель", "кто тебя создал", "кто твой папа", "кто твой автор", "создатель", "твой создатель"]
    if any(k in lower_text for k in creator_keywords):
        bot.send_message(message.chat.id, "Мой создатель: @MakSon4ikk_228 😎 Он самый лучший, он меня и сделал!")
        return

    # --- СПАМ ЗАЩИТА ---
    if len(user_text) > 1000:
        bot.send_message(message.chat.id, "Эй, даун, не спамь так много текста, я не вывезу 😅 Давай покороче")
        return

    # --- ОТВЕЧАЕМ ЧЕРЕЗ GROQ ---
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5) # типа печатает

        answer = ask_groq(user_text)

        if answer:
            bot.send_message(message.chat.id, answer)
        else:
            # Если Groq не ответил
            markup = create_error_markup()
            bot.send_message(message.chat.id, f"Йо, я упал с ошибкой Groq 😵 Попробуй еще раз, а если не получится - жми кнопку снизу", reply_markup=markup)

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_all_text: {e}")
        logger.error(traceback.format_exc())

        # Показываем красивое сообщение об ошибке с кнопками как у тебя было
        markup = create_error_markup()
        try:
            bot.send_message(message.chat.id, f"Я упал с ошибкой: {e}\n\nНажми кнопку чтобы сообщить админу", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "Я совсем упал, даже ошибку отправить не могу 😭")

# --- ОБРАБОТЧИК КНОПОК ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Обработка всех кнопок InlineKeyboard"""
    try:
        logger.info(f"Callback {call.data} от @{call.from_user.username}")

        if call.data == "report_error":
            # Отправляем админу
            try:
                # Если у тебя ADMIN_ID это число
                if ADMIN_ID and ADMIN_ID.isdigit():
                    bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ!\nОт: @{call.from_user.username} (id {call.from_user.id})\nСообщение: {call.message.text}\nВремя: {datetime.now()}")
                # Если это юзернейм
                else:
                    # Пробуем отправить по юзернейму если он указан как MakSon4ikk_228
                    bot.send_message("@MakSon4ikk_228", f"🚨 РЕПОРТ!\nОт: @{call.from_user.username}\nБот упал в чате {call.message.chat.id}")

                bot.answer_callback_query(call.id, "Репорт отправлен админу!")
                bot.send_message(call.message.chat.id, "Отправил репорт @MakSon4ikk_228 ✅ Он скоро починит!")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Не смог отправить: {e}")
                bot.send_message(call.message.chat.id, "Не смог отправить репорт, напиши сам @MakSon4ikk_228")

        elif call.data == "retry_last":
            bot.answer_callback_query(call.id, "Попробуй написать сообщение еще раз")
            bot.send_message(call.message.chat.id, "Напиши свой вопрос еще раз, я попробую ответить")

    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")

# --- ЗАПУСК БОТА С АВТОПЕРЕЗАПУСКОМ ---

def main_loop():
    """Главный цикл чтобы бот никогда не падал"""
    logger.info("Запускаю главный цикл бота...")
    while True:
        try:
            logger.info("Запускаю infinity_polling...")
            # skip_pending=True чтобы не отвечать на старые сообщения после сна
            bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True, logger_level=logging.INFO)
        except Exception as e:
            logger.error(f"Polling упал: {e}")
            logger.error(traceback.format_exc())
            logger.info("Перезапуск через 5 секунд...")
            time.sleep(5)

if __name__ == "__main__":
    logger.info("===== Daun213 BOT STARTED =====")
    logger.info(f"BOT_TOKEN exists: {bool(BOT_TOKEN)}")
    logger.info(f"GROQ_API_KEY exists: {bool(GROQ_API_KEY)}")
    main_loop()
