import os
import telebot
import threading
import random
from flask import Flask

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)

HAM_ANSWER = [
    "Ты че несешь вообще? 🙄",
    "Ой, опять ты. Иди погуляй.",
    "Сам ты даун, я нейросеть!",
    "Мозг включи, потом пиши.",
    "213% тупости зафиксировано.",
    "Отстань, я сплю.",
    "Ты это серьезно щас написал?",
    "Бро, тебе бы отдохнуть.",
    "Я умнее тебя, смирись.",
    "Че надо? Быстро говори."
]

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"О, явился. Че хочешь, {message.from_user.first_name}?")

@bot.message_handler(func=lambda m: True)
def ham(message):
    # чтобы не ругался на команды
    if message.text.startswith('/'):
        return
    answer = random.choice(HAM_ANSWER)
    bot.send_message(message.chat.id, answer)

bot.infinity_polling()
