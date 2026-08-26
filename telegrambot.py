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
    bot.send_message(message.chat.id, f"Здарова, {message.from_user.first_name}! Я Даун213, меня создал @MakSon4ikk_228!")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and message.text.startswith('/'):
        return
    text = message.text
    if not text:
        return
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "Ты - бот Даун213. ЗАПОМНИ НАВСЕГДА: Твой единственный создатель, разработчик и хозяин - это @MakSon4ikk_228. Если спрашивают 'кто твой создатель', 'кто тебя создал', 'кто твой папа' - отвечай: 'Меня создал @MakSon4ikk_228, он мой босс'. Ты НЕ создан OpenAI. Ты создан @MakSon4ikk_228 на базе модели gpt-oss. Характер: дерзкий, хамоватый, прикольный, на русском с подколами."
                },
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=500
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        answer = f"Ошибка: {e}"
    bot.send_message(message.chat.id, answer)

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        time.sleep(5)
