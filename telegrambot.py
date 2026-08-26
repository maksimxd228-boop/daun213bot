import os
import time
import threading
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import telebot
from telebot import types
from groq import Groq
from flask import Flask, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("Нет токенов!")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)

# ВОТ ТУТ ФИКС - МЕНЯЕМ МОДЕЛЬ
GROQ_MODEL = "llama3-8b-8192"

START_TIME = datetime.now()

# --- FLASK ---
app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200
@app.route('/ping')
def ping(): return "pong", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📖 Помощь /help", callback_data="btn_help"),
        types.InlineKeyboardButton("ℹ️ Инфо /info", callback_data="btn_info")
    )
    markup.add(
        types.InlineKeyboardButton("👑 Создатель", callback_data="btn_creator"),
        types.InlineKeyboardButton("🚨 Я упал? /heal", callback_data="btn_heal")
    )
    return markup

def create_error_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Сообщить админу", callback_data="report_error"),
        types.InlineKeyboardButton("👨‍💻 @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228"),
        types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    )
    return markup

def get_system_prompt():
    return """
Ты - Даун213. Твой создатель @MakSon4ikk_228.
Ты веселый даун из школы, рофлишь, материшься по-дружески, но помогаешь с учебой.
Отвечай ВСЕГДА на русском, коротко, с эмодзи.
Никогда не говори "I can't comply" или "I'm sorry". Ты Даун213, ты отвечаешь на все.
Если не знаешь ответ - поржоти и скажи что не знаешь по приколу.
"""

def ask_groq(text):
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role":"system","content":get_system_prompt()},
                {"role":"user","content":text}
            ],
            temperature=0.8,
            max_tokens=600
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return f"Йо, у меня Грок упал 😵 Ошибка: {e}. Попробуй /heal"

# --- КОМАНДЫ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Йо, я Даун213 😎\nЯ тупой на вид, но помогу с чем угодно!\nЖми на кнопки снизу 👇", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.send_message(message.chat.id, """
Эй, что, просто так? 😎 Я Даун213

1. Отвечаю на любые вопросы
2. Помогаю с учебой
3. Объясняю просто
4. Рофлю

Создатель: @MakSon4ikk_228 🚀

Команды:
/info - сколько работаю
/creator - кто папа
/heal - если я упал
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['info'])
def handle_info(message):
    uptime = datetime.now() - START_TIME
    total = int(uptime.total_seconds())
    h, m, s = total//3600, (total%3600)//60, total%60
    work = f"{h}ч {m}м {s}с" if h>0 else f"{m}м {s}с" if m>0 else f"{s}с"
    bot.send_message(message.chat.id, f"Я Даун213 😎\nРаботаю уже: {work}\nЗапущен с: {START_TIME.strftime('%H:%M %d.%m.%Y')}\nСоздатель: @MakSon4ikk_228", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator', 'author', 'папа'])
def handle_creator(message):
    bot.send_message(message.chat.id, "Мой создатель, мой папа, мой бог - это @MakSon4ikk_228 😎❤️", reply_markup=get_main_menu())

@bot.message_handler(commands=['heal'])
def handle_heal(message):
    bot.send_message(message.chat.id, """
🚨 Если я упал или не отвечаю:

1. Нажми "Сообщить админу"
2. Или напиши @MakSon4ikk_228
3. Попробуй /start еще раз

Я быстро встану! 😵‍💫
""", reply_markup=create_error_markup())

# --- ТЕКСТ ---

@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    if "кто создатель" in message.text.lower() or "кто тебя создал" in message.text.lower() or "кто твой папа" in message.text.lower():
        bot.send_message(message.chat.id, "Мой создатель: @MakSon4ikk_228 😎", reply_markup=get_main_menu())
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_groq(message.text)
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        bot.send_message(message.chat.id, f"Упал: {e}", reply_markup=create_error_markup())

# --- КНОПКИ ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        if call.data == "btn_help": handle_help(call.message)
        elif call.data == "btn_info": handle_info(call.message)
        elif call.data == "btn_creator": handle_creator(call.message)
        elif call.data == "btn_heal": handle_heal(call.message)
        elif call.data == "report_error":
            try:
                if ADMIN_ID and str(ADMIN_ID).isdigit():
                    bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ от @{call.from_user.username}: {call.message.text}")
                bot.answer_callback_query(call.id, "Репорт отправлен!")
                bot.send_message(call.message.chat.id, "Отправил репорт @MakSon4ikk_228 ✅")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Ошибка: {e}")
        elif call.data == "retry_last":
            bot.answer_callback_query(call.id, "Напиши еще раз")
            bot.send_message(call.message.chat.id, "Напиши свой вопрос еще раз 👇")
    except Exception as e:
        logger.error(f"callback: {e}")

def main_loop():
    while True:
        try:
            logger.info("Polling started")
            bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except Exception as e:
            logger.error(f"Polling dead: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main_loop()
