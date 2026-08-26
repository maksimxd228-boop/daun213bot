import os
import time
import threading
from flask import Flask
import telebot
from telebot import types
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
ADMIN_ID = os.environ.get("ADMIN_ID")

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()
time.sleep(2)

client = Groq(api_key=GROQ_API_KEY)

waiting_for_report = set()

HELP_TEXT = """
Я Даун213, бот от @MakSon4ikk_228 😎

Что умею:
- Отвечаю с подколами но по умному
- Помогаю с математикой, историей, дз
- Не забываю кто мой создатель

Команды:
/start - поздороваться
/help - это меню
/hell - тоже самое для своих

Если я сломался, жми кнопку ниже и я кину репорт админу!
"""

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Здарова, {message.from_user.first_name}! Я Даун213 от @MakSon4ikk_228. Жми /help")

@bot.message_handler(commands=['help', 'hell'])
def help_cmd(message):
    markup = types.InlineKeyboardMarkup()
    btn_report = types.InlineKeyboardButton("🚨 Сообщить админу", callback_data="report_error")
    btn_profile = types.InlineKeyboardButton("Мой создатель @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")
    markup.add(btn_report)
    markup.add(btn_profile)
    bot.send_message(message.chat.id, HELP_TEXT, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "report_error")
def report_callback(call):
    bot.answer_callback_query(call.id, "Жду описание")
    waiting_for_report.add(call.from_user.id)
    bot.send_message(call.message.chat.id, "Опиши одним сообщением что сломалось, я сразу перешлю это @MakSon4ikk_228 и мы пофиксим!")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and message.text.startswith('/'):
        return

    if message.from_user.id in waiting_for_report:
        waiting_for_report.remove(message.from_user.id)
        if ADMIN_ID:
            try:
                bot.send_message(int(ADMIN_ID), f"🚨 РЕПОРТ от @{message.from_user.username} ID {message.from_user.id}:\n\n{message.text}")
                bot.send_message(message.chat.id, "Отправил репорт @MakSon4ikk_228! Починим!")
            except Exception as e:
                bot.send_message(message.chat.id, f"Не смог отправить, напиши сам @MakSon4ikk_228. Ошибка: {e}")
        else:
            bot.send_message(message.chat.id, "ADMIN_ID не настроен, напиши @MakSon4ikk_228 напрямую")
        return

    text = message.text
    if not text:
        return

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "Ты бот Даун213. Твой создатель @MakSon4ikk_228. На вопрос кто создатель отвечай @MakSon4ikk_228. Характер дерзкий, прикольный, с подколами, на русском, помогаешь с учебой."},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=600
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

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"Crash: {e}")
        time.sleep(5)
