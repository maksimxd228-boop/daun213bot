import os
import time
import threading
from flask import Flask
import telebot
from groq import Groq

# --- Веб-сервер чтобы Render не спал ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Daun213 Bot is alive and smart!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- Токены из Render ---
TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

print(f"TOKEN exists: {bool(TOKEN)}")
print(f"GROQ_API_KEY exists: {bool(GROQ_API_KEY)}")

# --- Создаем бота ---
bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()
time.sleep(2)
print("Webhook removed, starting...")

client = Groq(api_key=GROQ_API_KEY)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"О, явился, {message.from_user.first_name}? Я теперь с мозгами, спрашивай!")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and message.text.startswith('/'):
        return

    text = message.text
    if not text:
        return

    print(f"User: {text}")

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # <-- ВОТ ТУТ ПОФИКСИЛ, ТЕПЕРЬ РАБОЧАЯ МОДЕЛЬ
            messages=[
                {"role": "system", "content": "Ты дерзкий, хамоватый, прикольный бот по имени Даун213. Отвечай на русском, коротко, с подколами и рофлами, но по сути вопроса."},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=500
        )
        answer = completion.choices[0].message.content

    except Exception as e:
        print(f"GROQ ERROR: {e}")
        answer = f"Мозг глюканул: {e}"

    try:
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        print(f"SEND ERROR: {e}")

# --- Запуск с автоперезапуском ---
while True:
    try:
        print("Starting polling...")
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"Polling crashed: {e}, restart in 5s...")
        time.sleep(5)
