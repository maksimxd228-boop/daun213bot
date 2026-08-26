import os
import time
import threading
from flask import Flask
import telebot
from groq import Groq

app = Flask(__name__)
@app.route('/')
def home():
    return "Daun213 Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()
time.sleep(2)

client = Groq(api_key=GROQ_API_KEY)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Йоу, {message.from_user.first_name}! Я воскрес, теперь на новой модели!")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and message.text.startswith('/'):
        return
    text = message.text
    if not text:
        return
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b", # <-- НОВАЯ МОДЕЛЬ, 100% ЖИВАЯ
            messages=[
                {"role": "system", "content": "Ты дерзкий хамоватый бот Даун213, отвечай на русском, коротко, с подколами."},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=500
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        print(f"GROQ ERROR: {e}")
        answer = f"Ошибка Groq: {e}"

    bot.send_message(message.chat.id, answer)

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"Polling crashed: {e}")
        time.sleep(5)
