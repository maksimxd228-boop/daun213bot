import os
import telebot
import threading
from flask import Flask
from groq import Groq

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web).start()

TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TOKEN)
client = Groq(api_key=GROQ_API_KEY)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"О, явился, че хочешь, {message.from_user.first_name}? Я теперь с мозгами!")

@bot.message_handler(func=lambda m: True)
def handle(message):
    if message.text and message.text.startswith('/'):
        return
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Ты дерзкий, хамоватый бот по имени Даун213, отвечай на русском, коротко, с приколами и подколами, но по сути вопроса. Ты теперь умная нейросеть, а не рандом."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9,
            max_tokens=400
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        print(f"Groq error: {e}")
        answer = "Мозг отвалился, попробуй еще раз через сек."

    bot.send_message(message.chat.id, answer)

bot.infinity_polling()
