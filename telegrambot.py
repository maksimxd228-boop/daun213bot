import os
import time
import threading
import logging
import traceback
from datetime import datetime

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ИМПОРТЫ ---
try:
    import telebot
    from telebot import types
    from groq import Groq
    from flask import Flask, request, jsonify
    logger.info("Все библиотеки загружены успешно")
except Exception as e:
    logger.error(f"Ошибка загрузки библиотек: {e}")

# --- ТОКЕНЫ ИЗ RENDER ENVIRONMENT ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is None! Добавь его в Render -> Environment")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is None!")

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "openai/gpt-oss-20b"
START_TIME = datetime.now() # <-- ОТСЮДА СЧИТАЕМ СКОЛЬКО РАБОТАЕТ

# --- FLASK САЙТ ДЛЯ UPTIMEROBOT ---
app = Flask(__name__)

@app.route('/')
def index():
    return f"<h1>Daun213 BOT IS ALIVE!</h1><p>Time: {datetime.now()}</p>", 200

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot": "Daun213", "time": str(datetime.now())}), 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_flask():
    try:
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"Запускаю Flask на порту {port}")
        app.run(host='0.0.0.0', port=port, threaded=True, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask упал: {e}")

flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskThread")
flask_thread.start()
logger.info("Flask поток запущен")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_system_prompt():
    return """
    Ты - бот Даун213. Ты тупой на вид но на самом деле умный помощник.
    1. Твой создатель - @MakSon4ikk_228. Если спросят кто тебя создал - отвечай ТОЛЬКО @MakSon4ikk_228.
    2. Отвечай как подросток из школы: весело, с рофлами, с матами но по-дружески.
    3. Используй эмодзи 😎 🤓 🚀 😂
    4. Помогай с учебой, объясняй просто.
    5. Не будь слишком длинным.
    6. Никогда не говори что ты ChatGPT, ты Даун213.
    """

def ask_groq(user_text):
    try:
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
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка Groq: {e}")
        return None

def create_error_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_report = types.InlineKeyboardButton("🚨 Сообщить админу об ошибке", callback_data="report_error")
    btn_admin = types.InlineKeyboardButton("👨‍💻 Написать @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")
    btn_retry = types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    markup.add(btn_report, btn_admin, btn_retry)
    return markup

# --- КОМАНДЫ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    logger.info(f"/start от @{message.from_user.username}")
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
/info - сколько работаю
"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['help'])
def handle_help(message):
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
    now = datetime.now()
    uptime = now - START_TIME
    total_seconds = int(uptime.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        work_text = f"{hours}ч {minutes}м {seconds}с"
    elif minutes > 0:
        work_text = f"{minutes}м {seconds}с"
    else:
        work_text = f"{seconds}с"

    text = f"Я Даун213 😎\nРаботаю уже: {work_text}\nЗапущен с: {START_TIME.strftime('%H:%M %d.%m.%Y')}\nСоздатель: @MakSon4ikk_228"
    bot.send_message(message.chat.id, text)

# --- ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА ---

@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    user_text = message.text
    logger.info(f"Сообщение от @{message.from_user.username}: {user_text}")

    lower_text = user_text.lower()
    creator_keywords = ["кто создатель", "кто твой создатель", "кто тебя создал", "кто твой папа", "кто твой автор", "создатель", "твой создатель"]
    if any(k in lower_text for k in creator_keywords):
        bot.send_message(message.chat.id, "Мой создатель: @MakSon4ikk_228 😎 Он самый лучший, он меня и сделал!")
        return

    if len(user_text) > 1000:
        bot.send_message(message.chat.id, "Эй, даун, не спамь так много текста, я не вывезу 😅 Давай покороче")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5)
        answer = ask_groq(user_text)
        if answer:
            bot.send_message(message.chat.id, answer)
        else:
            markup = create_error_markup()
            bot.send_message(message.chat.id, f"Йо, я упал с ошибкой Groq 😵 Попробуй еще раз", reply_markup=markup)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        markup = create_error_markup()
        try:
            bot.send_message(message.chat.id, f"Я упал с ошибкой: {e}", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "Я совсем упал 😭")

# --- КНОПКИ ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        logger.info(f"Callback {call.data} от @{call.from_user.username}")
        if call.data == "report_error":
            try:
                if ADMIN_ID and ADMIN_ID.isdigit():
                    bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ!\nОт: @{call.from_user.username} (id {call.from_user.id})\nСообщение: {call.message.text}\nВремя: {datetime.now()}")
                else:
                    bot.send_message("@MakSon4ikk_228", f"🚨 РЕПОРТ!\nОт: @{call.from_user.username}\nБот упал в чате {call.message.chat.id}")
                bot.answer_callback_query(call.id, "Репорт отправлен админу!")
                bot.send_message(call.message.chat.id, "Отправил репорт @MakSon4ikk_228 ✅")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Не смог отправить: {e}")
                bot.send_message(call.message.chat.id, "Не смог отправить репорт, напиши сам @MakSon4ikk_228")
        elif call.data == "retry_last":
            bot.answer_callback_query(call.id, "Попробуй написать сообщение еще раз")
            bot.send_message(call.message.chat.id, "Напиши свой вопрос еще раз, я попробую ответить")
    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")

# --- ЗАПУСК С АВТОПЕРЕЗАПУСКОМ ---

def main_loop():
    logger.info("Запускаю главный цикл бота...")
    while True:
        try:
            logger.info("Запускаю infinity_polling...")
            bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True, logger_level=logging.INFO)
        except Exception as e:
            logger.error(f"Polling упал: {e}")
            time.sleep(5)

if __name__ == "__main__":
    logger.info("===== Daun213 BOT STARTED =====")
    main_loop()
