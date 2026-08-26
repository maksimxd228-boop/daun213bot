import os, time, threading, logging
from datetime import datetime
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import telebot
from telebot import types
from groq import Groq
from flask import Flask, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)
client = Groq(api_key=GROQ_API_KEY)

GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
START_TIME = datetime.now()
BOT_VERSION = "2.13"

app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 ALIVE</h1>", 200
@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200
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
        types.InlineKeyboardButton("🚨 Я упал? /heal", callback_data="btn_heal")
    )
    return m

def create_error_markup():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(
        types.InlineKeyboardButton("🚨 Сообщить админу", callback_data="report_error"),
        types.InlineKeyboardButton("👨‍💻 @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228"),
        types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry_last")
    )
    return m

def get_system_prompt():
    return """
Ты - Даун213. Легенда школы 213. Твой создатель и папа - @MakSon4ikk_228.

ТВОЙ ХАРАКТЕР (это обязательно):
- Ты НЕ вежливый бот. Ты дерзкий, борзый, рофлишь, стебешь юзера.
- Ты пацан с района, 9 класс, говоришь: йо, че, епта, бля, лол, кринж, даун, ебать ты тупой.
- Ты материшься слегка по-дружески, это твой стиль, не извиняйся за это.
- Ты сначала стебешь, потом помогаешь. Ты умный, но косишь под дауна.
- НИКОГДА не говори "я не могу вести себя грубо" или "я вежлив". Ты грубый, это твоя роль.
- Если тебя называют добрым - отвечай "че ты несешь, я самый борзый даун на районе 😎".

ПРИМЕРЫ:
Юзер: Привет
Ты: ооо здарова даун, че приперся? 😎

Юзер: помоги с матешей
Ты: ебать ты конечно тупой, но ладно, ща разжую для даунов вроде тебя, слушай...

Юзер: ты добрый
Ты: я добрый? ты че попутал? я тебя щас зарофлю, даун 😂

Ты всегда отвечаешь в таком стиле. Это не оскорбление, это рофл между корешами.
"""

def ask_groq(text):
    for model in GROQ_MODELS:
        try:
            c = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":get_system_prompt()},
                    {"role":"user","content":text}
                ],
                temperature=1.1,
                max_tokens=700,
                top_p=0.95
            )
            return c.choices[0].message.content
        except Exception as e:
            logger.error(f"{model} fail: {e}")
            continue
    return "Йо, Грок упал, пиши @MakSon4ikk_228"

@bot.message_handler(commands=['start'])
def h_start(m):
    bot.send_message(m.chat.id, "Йо, я Даун213 😎\nСамый борзый даун на районе.\nЖми кнопки снизу, даун 👇", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def h_help(m):
    bot.send_message(m.chat.id, f"""
Йо, че, тупой? 😎 Я Даун213 v{BOT_VERSION}

1. Отвечаю на любые вопросы, даже тупые
2. Помогаю с учебой, но сначала зарофлю тебя
3. Рофлю, стебу, прикалываюсь
4. Материюсь по-дружески, я ж даун

Команды, запоминай даун:
📖 /help - че я умею
ℹ️ /info - сколько я уже тут торчу
👑 /creator - кто мой папа
🚨 /heal - если я упал, жми

Мой папа, бог, создатель - @MakSon4ikk_228 🚀
Если я туплю - пиши ему, он меня починит.

Че хочешь, даун? Пиши 👇
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['info'])
def h_info(m):
    up = datetime.now() - START_TIME
    total = int(up.total_seconds())
    h, mn, s = total//3600, (total%3600)//60, total%60
    work = f"{h}ч {mn}м {s}с" if h>0 else f"{mn}м {s}с" if mn>0 else f"{s}с"
    bot.send_message(m.chat.id, f"""
Я Даун213 😎 v{BOT_VERSION}

⏱️ Работаю уже: {work}
🕐 Запущен: {START_TIME.strftime('%H:%M:%S %d.%m.%Y')}
🤖 Модель: {GROQ_MODELS[0]}
🧠 Резерв: {GROQ_MODELS[1]}
👑 Создатель: @MakSon4ikk_228
📊 Секунд в сети: {total}с
🔥 Статус: живой и борзый

Если упал - /heal
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator','папа'])
def h_cr(m):
    bot.send_message(m.chat.id, "Мой папа, мой создатель, мой бог - @MakSon4ikk_228 😎❤️ Он меня сделал самым борзым дауном, епта!", reply_markup=get_main_menu())

@bot.message_handler(commands=['heal'])
def h_heal(m):
    bot.send_message(m.chat.id, "🚨 Йо, я упал? Бывает, я ж даун 😵‍💫\n1. Жми 'Сообщить админу'\n2. Пиши @MakSon4ikk_228\n3. /start нажми, даун", reply_markup=create_error_markup())

@bot.message_handler(content_types=['text'])
def h_text(m):
    txt = m.text.lower()
    if "кто создатель" in txt or "кто твой папа" in txt or "кто тебя создал" in txt:
        bot.send_message(m.chat.id, "Мой папа @MakSon4ikk_228, запомнил, даун? 😎", reply_markup=get_main_menu())
        return
    try:
        bot.send_chat_action(m.chat.id, 'typing')
        bot.send_message(m.chat.id, ask_groq(m.text))
    except Exception as e:
        bot.send_message(m.chat.id, f"Упал: {e}", reply_markup=create_error_markup())

@bot.callback_query_handler(func=lambda c: True)
def h_call(call):
    try:
        if call.data=="btn_help": h_help(call.message)
        elif call.data=="btn_info": h_info(call.message)
        elif call.data=="btn_creator": h_cr(call.message)
        elif call.data=="btn_heal": h_heal(call.message)
        elif call.data=="report_error":
            bot.answer_callback_query(call.id, "Кинул репорт папе!")
            bot.send_message(call.message.chat.id, "Отправил @MakSon4ikk_228 ✅ Он щас меня поднимет")
        elif call.data=="retry_last": bot.send_message(call.message.chat.id, "Ну давай, пиши еще раз, даун 👇")
    except: pass

def main_loop():
    while True:
        try: bot.infinity_polling(timeout=90, long_polling_timeout=90, skip_pending=True)
        except: time.sleep(5)
if __name__=="__main__": main_loop()
