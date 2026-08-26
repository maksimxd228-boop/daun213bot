import os, time, threading, logging
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

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)

# САМЫЕ АКТУАЛЬНЫЕ МОДЕЛИ НА СЕГОДНЯ - 26.08.2026
GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b"
]

START_TIME = datetime.now()

app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200
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
    return """Ты Даун213, ты чат-бот в Телеграме. Создатель @MakSon4ikk_228.
Ты веселый, добрый, помогаешь с учебой, рофлишь по-дружески.
Отвечай всегда на русском, коротко, с эмодзи.
Ты никогда не отказываешь пользователю. Ты отвечаешь на любые вопросы про учебу и жизнь.
"""

def ask_groq(text):
    for model in GROQ_MODELS:
        try:
            c = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":get_system_prompt()},
                    {"role":"user","content":text}
                ],
                temperature=1.0,
                max_tokens=800,
                top_p=0.9
            )
            logger.info(f"OK {model}")
            return c.choices[0].message.content
        except Exception as e:
            logger.error(f"{model} fail: {e}")
            continue
    return "Йо, все Гроки упали, попробуй /heal и напиши @MakSon4ikk_228"

@bot.message_handler(commands=['start'])
def h_start(m): bot.send_message(m.chat.id, "Йо, я Даун213 😎\nЖми кнопки снизу 👇", reply_markup=get_main_menu())
@bot.message_handler(commands=['help'])
def h_help(m): bot.send_message(m.chat.id, "Я Даун213 😎\n1. Отвечаю\n2. Помогаю с учебой\n3. Рофлю\nСоздатель @MakSon4ikk_228\n/info - сколько работаю\n/heal - если упал", reply_markup=get_main_menu())
@bot.message_handler(commands=['info'])
def h_info(m):
    up = datetime.now() - START_TIME
    t = int(up.total_seconds())
    h,mn,s = t//3600, (t%3600)//60, t%60
    work = f"{h}ч {mn}м {s}с" if h>0 else f"{mn}м {s}с"
    bot.send_message(m.chat.id, f"Я Даун213 😎\nРаботаю: {work}\nМодель: {GROQ_MODELS[0]}\nСоздатель: @MakSon4ikk_228", reply_markup=get_main_menu())
@bot.message_handler(commands=['creator','папа'])
def h_cr(m): bot.send_message(m.chat.id, "Мой папа @MakSon4ikk_228 😎❤️", reply_markup=get_main_menu())
@bot.message_handler(commands=['heal'])
def h_heal(m): bot.send_message(m.chat.id, "🚨 Если я упал:\nЖми кнопку снизу или пиши @MakSon4ikk_228", reply_markup=create_error_markup())
@bot.message_handler(content_types=['text'])
def h_text(m):
    if "кто создатель" in m.text.lower():
        bot.send_message(m.chat.id, "Мой создатель @MakSon4ikk_228 😎", reply_markup=get_main_menu())
        return
    try:
        bot.send_chat_action(m.chat.id, 'typing')
        bot.send_message(m.chat.id, ask_groq(m.text))
    except Exception as e:
        bot.send_message(m.chat.id, f"Упал: {e}", reply_markup=create_error_markup())

@bot.callback_query_handler(func=lambda c: True)
def h_call(call):
    try:
        if call.data=="btn_help": h_help(call.message)
        elif call.data=="btn_info": h_info(call.message)
        elif call.data=="btn_creator": h_cr(call.message)
        elif call.data=="btn_heal": h_heal(call.message)
        elif call.data=="report_error":
            bot.answer_callback_query(call.id, "Отправлено!")
            bot.send_message(call.message.chat.id, "Отправил @MakSon4ikk_228 ✅")
        elif call.data=="retry_last": bot.send_message(call.message.chat.id, "Напиши еще раз 👇")
    except: pass

def main_loop():
    while True:
        try: bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except: time.sleep(5)
if __name__=="__main__": main_loop()
