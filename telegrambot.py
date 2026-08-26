import os
import telebot
import threading
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

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Я живой 24/7!")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(message.chat.id, f"Ты написал: {message.text}")

bot.infinity_polling()
