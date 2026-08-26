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

# === НОВЫЕ МОДЕЛИ С ФОЛБЭКОМ ===
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant"
]

START_TIME = datetime.now()

app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200
@app.route('/ping')
def ping(): return "pong", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

def get_main_menu():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("📖 Помощь /help", callback_data="btn_help"),
        types.InlineKeyboardButton("ℹ️ Инфо /info", callback_data="btn_info")
    )
    m.add(
        types.InlineKeyboardButton("👑 Создатель", callback_data="btn_creator"),
        types.InlineKeyboardButton("🚨 Я упал? /heal", callback_data="btn_heal")
    )
    return m

def create_error_markup():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(
        types.InlineKeyboardButton("🚨 Сообщить админу", callback_data="report_error"),
        types.InlineKeyboardButton("👨‍💻 @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228"),
        types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    )
    return m

def get_system_prompt():
    return "Ты Даун213. Создатель @MakSon4ikk_228. Отвечай весело, по-русски, с рофлами и эмодзи. Ты умный даун. Никогда не пиши I'm sorry."

def ask_groq(text):
    last_err = None
    for model in GROQ_MODELS:
        try:
            c = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":get_system_prompt()},
                    {"role":"user","content":text}
                ],
                temperature=0.9,
                max_tokens=600
            )
            logger.info(f"OK with model {model}")
            return c.choices[0].message.content
        except Exception as e:
            logger.error(f"Model {model} fail: {e}")
            last_err = e
            continue
    return f"Йо, у меня Грок упал 😵 {last_err}\nПопробуй /heal"

@bot.message_handler(commands=['start'])
def h_start(m):
    bot.send_message(m.chat.id, "Йо, я Даун213 😎\nЖми кнопки снизу 👇", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def h_help(m):
    bot.send_message(m.chat.id, "Я Даун213 😎\n1. Отвечаю\n2. Помогаю с учебой\n3. Рофлю\nСоздатель @MakSon4ikk_228\n\n/info - сколько работаю\n/heal - если упал", reply_markup=get_main_menu())

@bot.message_handler(commands=['info'])
def h_info(m):
    up = datetime.now() - START_TIME
    t = int(up.total_seconds())
    h,mn,s = t//3600, (t%3600)//60, t%60
    work = f"{h}ч {mn}м {s}с" if h>0 else f"{mn}м {s}с" if mn>0 else f"{s}с"
    bot.send_message(m.chat.id, f"Я Даун213 😎\nРаботаю уже: {work}\nЗапущен: {START_TIME.strftime('%H:%M %d.%m')}\nСоздатель: @MakSon4ikk_228\nМодели: {', '.join(GROQ_MODELS)}", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator','папа'])
def h_cr(m):
    bot.send_message(m.chat.id, "Мой папа - @MakSon4ikk_228 😎❤️", reply_markup=get_main_menu())

@bot.message_handler(commands=['heal'])
def h_heal(m):
    bot.send_message(m.chat.id, "🚨 Если я упал:\n1. Жми Сообщить админу\n2. Пиши @MakSon4ikk_228\n3. /start", reply_markup=create_error_markup())

@bot.message_handler(content_types=['text'])
def h_text(m):
    if "кто создатель" in m.text.lower() or "кто твой папа" in m.text.lower() or "кто тебя создал" in m.text.lower():
        bot.send_message(m.chat.id, "Мой создатель @MakSon4ikk_228 😎", reply_markup=get_main_menu())
        return
    try:
        bot.send_chat_action(m.chat.id, 'typing')
        ans = ask_groq(m.text)
        bot.send_message(m.chat.id, ans)
    except Exception as e:
        bot.send_message(m.chat.id, f"Упал: {e}", reply_markup=create_error_markup())

@bot.callback_query_handler(func=lambda call: True)
def h_call(call):
    try:
        if call.data=="btn_help": h_help(call.message)
        elif call.data=="btn_info": h_info(call.message)
        elif call.data=="btn_creator": h_cr(call.message)
        elif call.data=="btn_heal": h_heal(call.message)
        elif call.data=="report_error":
            try:
                if ADMIN_ID and str(ADMIN_ID).isdigit():
                    bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ от @{call.from_user.username} id {call.from_user.id}: упал")
                bot.answer_callback_query(call.id, "Отправлено!")
                bot.send_message(call.message.chat.id, "Отправил репорт @MakSon4ikk_228 ✅")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Ошибка: {e}")
        elif call.data=="retry_last":
            bot.send_message(call.message.chat.id, "Напиши еще раз 👇")
    except Exception as e:
        logger.error(f"callback {e}")

def main_loop():
    while True:
        try:
            logger.info("Polling started")
            bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except Exception as e:
            logger.error(f"Polling dead: {e}")
            time.sleep(5)

if __name__=="__main__":
    main_loop()
