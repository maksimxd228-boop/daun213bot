import os
import time
import threading
from flask import Flask
import telebot
from groq import Groq

# --- Веб-сервер чтобы Render не засыпал ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Daun213 Bot is alive and smart!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- Токены из Render Environment ---
TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

print(f"TOKEN exists: {bool(TOKEN)}")
print(f"GROQ_API_KEY exists: {bool(GROQ_API_KEY)}")

if not TOKEN or not GROQ_API_KEY:
    print("ОШИБКА: Не нашел TOKEN или GROQ_API_KEY в Environment Variables!")
    # Не падаем, чтобы логи было видно

# --- Создаем бота ---
bot = telebot.TeleBot(TOKEN)

# ВАЖНО: Убираем вебхук чтобы не было ошибки 409
bot.remove_webhook()
time.sleep(2)
print("Webhook removed, starting polling...")

client = Groq(api_key=GROQ_API_KEY)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"О, явился, {message.from_user.first_name}? Я теперь не рандомный попугай, а с мозгами от Groq. Спрашивай что хочешь, только не тупи.")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    # Игнорим команды кроме start
    if message.text and message.text.startswith('/'):
        return

    text = message.text
    if not text:
        return

    print(f"User {message.from_user.first_name}: {text}")

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Самая быстрая и дешевая модель Groq
            messages=[
                {"role": "system", "content": "Ты дерзкий, хамоватый, прикольный бот по имени Даун213. Отвечай на русском, коротко, с подколами, рофлами, но по сути вопроса. Ты теперь умная нейросеть, а не рандомный генератор фраз. Если тебя спрашивают что-то умное - отвечай умно, но с твоим характером."},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=500
        )
        answer = completion.choices[0].message.content
        print(f"Groq answer: {answer[:100]}...")

    except Exception as e:
        print(f"GROQ ERROR: {e}")
        answer = f"Блин, мозг отвалился на секунду. Ошибка: {e}. Попробуй еще раз через 5 сек, я перезагружусь."

    try:
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        print(f"TELEGRAM SEND ERROR: {e}")

# --- Запуск с защитой от падения ---
while True:
    try:
        print("Starting infinity_polling...")
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"POLLING CRASHED: {e} - перезапуск через 5 сек...")
        time.sleep(5)
