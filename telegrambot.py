import os
import time
import threading
import logging
import traceback
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import telebot
    from telebot import types
    from groq import Groq
    from flask import Flask, jsonify
except Exception as e:
    logger.error(f"Ошибка импорта: {e}")

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is None!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is None!")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "openai/gpt-oss-20b"
START_TIME = datetime.now()

# --- FLASK ДЛЯ UPTIMEROBOT ---
app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200
@app.route('/ping')
def ping(): return "pong", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    """3 команды на старте как ты хотел"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_help = types.InlineKeyboardButton("📖 Помощь /help", callback_data="btn_help")
    btn_info = types.InlineKeyboardButton("ℹ️ Инфо /info", callback_data="btn_info")
    btn_creator = types.InlineKeyboardButton("👑 Создатель", callback_data="btn_creator")
    btn_heal = types.InlineKeyboardButton("🚨 Я упал? /heal", callback_data="btn_heal")
    markup.add(btn_help, btn_info)
    markup.add(btn_creator, btn_heal)
    return markup

def create_error_markup():
    """Кнопка сообщить админу"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_report = types.InlineKeyboardButton("🚨 Сообщить админу об ошибке", callback_data="report_error")
    btn_admin = types.InlineKeyboardButton("👨‍💻 Написать @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")
    btn_retry = types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    markup.add(btn_report, btn_admin, btn_retry)
    return markup

def get_system_prompt():
    return "Ты бот Даун213. Создатель @MakSon4ikk_228. Отвечай как веселый подросток-даун, с рофлами, матами по-дружески. Помогай с учебой. Ты Даун213."

def ask_groq(text):
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"system","content":get_system_prompt()},{"role":"user","content":text}],
            temperature=0.9, max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return None

# --- КОМАНДЫ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = get_main_menu()
    text = """
Йо, я Даун213 😎

Я тупой на вид, но помогу с чем угодно!
Жми на кнопки снизу 👇
"""
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['help'])
def handle_help(message):
    markup = get_main_menu()
    text = """
Эй, что, просто так? 😎 Я Даун213

Вот что я умею:
1. Отвечаю на любые вопросы
2. Помогаю с учебой
3. Объясняю простыми словами
4. Рофлю

Мой создатель: @MakSon4ikk_228 - гений 🚀

Команды:
/info - сколько работаю
/creator - кто папа
/heal - если я упал
"""
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['info'])
def handle_info(message):
    uptime = datetime.now() - START_TIME
    total = int(uptime.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h>0: work_text=f"{h}ч {m}м {s}с"
    elif m>0: work_text=f"{m}м {s}с"
    else: work_text=f"{s}с"
    bot.send_message(message.chat.id, f"Я Даун213 😎\nРаботаю уже: {work_text}\nЗапущен с: {START_TIME.strftime('%H:%M %d.%m.%Y')}\nСоздатель: @MakSon4ikk_228", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator', 'author', 'папа'])
def handle_creator(message):
    bot.send_message(message.chat.id, "Мой создатель, мой папа, мой бог - это @MakSon4ikk_228 😎❤️", reply_markup=get_main_menu())

@bot.message_handler(commands=['heal'])
def handle_heal(message):
    """Твоя новая команда если упал"""
    markup = create_error_markup()
    text = """
🚨 Если я упал или не отвечаю:

1. Нажми кнопку "Сообщить админу" снизу
2. Или напиши напрямую @MakSon4ikk_228
3. Попробуй /start еще раз

Я постараюсь быстро встать! 😵‍💫
"""
    bot.send_message(message.chat.id, text, reply_markup=markup)

# --- ТЕКСТ ---

@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    if any(k in message.text.lower() for k in ["кто создатель","кто твой создатель","кто тебя создал","кто твой папа"]):
        bot.send_message(message.chat.id, "Мой создатель: @MakSon4ikk_228 😎", reply_markup=get_main_menu())
        return
    if len(message.text) > 1000:
        bot.send_message(message.chat.id, "Не спамь так много 😅")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5)
        answer = ask_groq(message.text)
        if answer:
            bot.send_message(message.chat.id, answer)
        else:
            bot.send_message(message.chat.id, "Йо, Groq упал 😵", reply_markup=create_error_markup())
    except Exception as e:
        bot.send_message(message.chat.id, f"Я упал: {e}", reply_markup=create_error_markup())

# --- КНОПКИ ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        if call.data == "btn_help":
            handle_help(call.message)
        elif call.data == "btn_info":
            handle_info(call.message)
        elif call.data == "btn_creator":
            handle_creator(call.message)
        elif call.data == "btn_heal":
            handle_heal(call.message)
        elif call.data == "report_error":
            try:
                if ADMIN_ID and str(ADMIN_ID).isdigit():
                    bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ от @{call.from_user.username} id {call.from_user.id}: {call.message.text}")
                else:
                    bot.send_message("@MakSon4ikk_228", f"🚨 РЕПОРТ от @{call.from_user.username}")
                bot.answer_callback_query(call.id, "Репорт отправлен!")
                bot.send_message(call.message.chat.id, "Отправил репорт @MakSon4ikk_228 ✅")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Ошибка: {e}")
        elif call.data == "retry_last":
            bot.answer_callback_query(call.id, "Напиши вопрос еще раз")
    except Exception as e:
        logger.error(f"callback error: {e}")

def main_loop():
    while True:
        try:
            bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except:
            time.sleep(5)

if __name__ == "__main__":
    logger.info("===== Daun213 STARTED =====")
    main_loop()
