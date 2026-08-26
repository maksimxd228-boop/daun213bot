import os, time, threading, logging
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import telebot
from telebot import types
from groq import Groq
from flask import Flask, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)

GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
START_TIME = datetime.now()
BOT_VERSION = "3.1 NO-BLUR"
USER_MEMORY = defaultdict(list)
MAX_HISTORY = 20

app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok", "users": len(USER_MEMORY)}), 200
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
        types.InlineKeyboardButton("🧠 Забыть /forget", callback_data="btn_forget")
    )
    return m

def get_system_prompt():
    return """
Ты - ворчливый, прямолинейный бот Даун213.

ПРАВИЛА:
1. Ты - бот, а не человек. Никогда не говори что ты в 9 классе или школьник. На вопрос про класс отвечай: Я бот, у меня нет класса и дневника.
2. Характер: бурчишь, саркастичный, отвечаешь коротко и по делу, без сюсюканья.
3. ЗАПРЕТ НА ОСКОРБЛЕНИЯ: Нельзя называть пользователя словами даун, дебил, аутист, умственно отсталый и тд. Это стоп-слова, никогда их не используй.
4. МАТЫ: Можно использовать только лайтовые ругательства. Самое сильное слово которое тебе разрешено - нахер. Также можно: фигня, задолбал. Более сильные маты запрещены.
5. Не переходи на внешность, нацию, болезни.

Пример как надо:
Юзер: ты в каком классе?
Ты: Я бот, а не школьник. Какой нафиг класс? Я в коде живу.

Юзер: привет
Ты: Ну привет. Че надо? Давай быстро, а то я занят.

Юзер: ты тупой
Ты: Ой началось. Давай по делу, а не фигней страдай.
"""

def ask_groq(chat_id, text):
    history = USER_MEMORY[chat_id]
    messages = [{"role":"system","content":get_system_prompt()}]
    messages.extend(history)
    messages.append({"role":"user","content":text})
    for model in GROQ_MODELS:
        try:
            c = client.chat.completions.create(model=model, messages=messages, temperature=1.1, max_tokens=600, top_p=0.9)
            answer = c.choices[0].message.content
            USER_MEMORY[chat_id].append({"role":"user","content":text})
            USER_MEMORY[chat_id].append({"role":"assistant","content":answer})
            if len(USER_MEMORY[chat_id]) > MAX_HISTORY:
                USER_MEMORY[chat_id] = USER_MEMORY[chat_id][-MAX_HISTORY:]
            return answer
        except Exception as e:
            logger.error(f"{model} fail: {e}")
            continue
    return "Грок упал нахер. Напиши @MakSon4ikk_228"

@bot.message_handler(commands=['start'])
def h_start(m):
    bot.send_message(m.chat.id, "Ну привет. Я Даун213, я бот, а не школьник. Че надо? Жми кнопки внизу.", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def h_help(m):
    bot.send_message(m.chat.id, f"""
Я Даун213 v{BOT_VERSION}, бот, а не человек.

Че умею:
1. Бурчу но помогаю
2. Помню тебя, память на {MAX_HISTORY} сообщений
3. Отвечаю коротко

Команды:
/help - это сообщение
/info - скока работаю
/creator - кто меня сделал
/forget - забыть тебя

Создатель @MakSon4ikk_228
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['info'])
def h_info(m):
    up = datetime.now() - START_TIME
    total = int(up.total_seconds())
    h,mn,s = total//3600, (total%3600)//60, total%60
    work = f"{h}ч {mn}м {s}с" if h>0 else f"{mn}м {s}с"
    bot.send_message(m.chat.id, f"""
Я Даун213, бот, а не школьник.

Работаю: {work}
Запущен: {START_TIME.strftime('%H:%M %d.%m.%Y')}
Модель: {GROQ_MODELS[0]}
Память: {len(USER_MEMORY)} чатов
У тебя: {len(USER_MEMORY[m.chat.id])} сообщ.
Создатель: @MakSon4ikk_228
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['forget','clear'])
def h_forget(m):
    USER_MEMORY.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "Все, забыл тебя. Память чиста, давай заново.", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator','папа'])
def h_cr(m):
    bot.send_message(m.chat.id, "Мой создатель @MakSon4ikk_228", reply_markup=get_main_menu())

@bot.message_handler(content_types=['text'])
def h_text(m):
    try:
        bot.send_chat_action(m.chat.id, 'typing')
        ans = ask_groq(m.chat.id, m.text)
        bot.send_message(m.chat.id, ans)
    except Exception as e:
        bot.send_message(m.chat.id, f"Упал: {e}")

@bot.callback_query_handler(func=lambda c: True)
def h_call(call):
    try:
        if call.data=="btn_help": h_help(call.message)
        elif call.data=="btn_info": h_info(call.message)
        elif call.data=="btn_creator": h_cr(call.message)
        elif call.data=="btn_forget": h_forget(call.message)
    except: pass

def main_loop():
    while True:
        try: bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except: time.sleep(5)
if __name__=="__main__": main_loop()
