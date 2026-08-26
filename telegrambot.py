import os
import time
import threading
from flask import Flask
import telebot
from telebot import types
from groq import Groq

# --- ТОКЕНЫ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# --- МИНИ-САЙТ ДЛЯ UPTIMEROBOT ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Daun213 is alive! Bot is running 24/7"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()

# --- ТВОЙ БОТ ДАУН213 ---
@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.send_message(message.chat.id, "Йо, я Даун213. Кидай вопрос, я отвечу как даун но умный 😎")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "Ты бот Даун213. Твой создатель @MakSon4ikk_228. Отвечай как тупой но веселый школьник, с матами но по-дружески, коротко."},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=400
        )
        answer = completion.choices[0].message.content
        bot.send_message(message.chat.id, answer)

    except Exception as e:
        print(f"ERROR: {e}")
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("🚨 Сообщить админу об ошибке", callback_data="report_error")
        btn2 = types.InlineKeyboardButton("Написать @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")
        markup.add(btn1)
        markup.add(btn2)
        bot.send_message(message.chat.id, f"Я упал с ошибкой: {e}", reply_markup=markup)

# --- ЗАПУСК ---
print("Web server started on port 10000")
print("Bot started...")

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"Crash: {e}")
        time.sleep(5)
