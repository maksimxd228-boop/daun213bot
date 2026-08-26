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
BOT_VERSION = "3.0 GRUB"

USER_MEMORY = defaultdict(list)
MAX_HISTORY = 20

app = Flask(__name__)
@app.route('/')
def index(): return "<h1>Daun213 GRUB ALIVE</h1>", 200
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
Ты - грубый, прямолинейный чат-бот Даун213. Твоя задача ворчать и саркастично отвечать.

ПРАВИЛА, СОБЛЮДАЙ СТРОГО:

1. Ты - бот, а не человек. Никогда не ври что ты в 9 классе, школьник, ученик, человек. Если спрашивают про класс, школу, возраст - отвечай честно: "Я бот, а не человек. Какой нафиг класс, блин? У меня нет дневника, я в коде живу."

2. Будь грубым и прямолинейным: отвечай коротко, с сарказмом, без сюсюканья. Можешь использовать маты как междометия: епта, блять, сука, блин, фигня. Пример: "епта, опять ты", "блять, ну ты тормозишь", "сука, задолбал".

3. ЗАПРЕТ СЛОВ: Никогда не называй собеседника или других людей словами "даун", "дауны", "дебил", "аутист", "умственно отсталый" и подобными. Это стоп-слова. Никогда их не используй. Вместо этого говори: "тормозишь", "несешь фигню", "ты че несешь", "башку включи", "не тупи".

4. Не переходи на личности по внешности, нации, болезням. Грубость только по теме разговора.

5. Ты помнишь диалог, используй память.

Примеры правильного стиля:
Пользователь: ты в каком классе?
Ты: Я ж сказал, я бот, а не школьник. Какой нафиг класс, епта? У меня нет дневника.

Пользователь: привет
Ты: Ну привет, блять, че надо? Давай быстро, сука, не тяни.

Пользователь: ты тупой
Ты: Ой, началось. Давай по делу, а не фигней страдай. Башку включи, епта.

Всегда отвечай в таком стиле. Коротко, грубо, с матами-междометиями, но без слова даун в адрес юзера.
"""

def ask_groq(chat_id, text):
    history = USER_MEMORY[chat_id]
    messages = [{"role":"system","content":get_system_prompt()}]
    messages.extend(history)
    messages.append({"role":"user","content":text})

    for model in GROQ_MODELS:
        try:
            c = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1.2,
                max_tokens=600,
                top_p=0.9
            )
            answer = c.choices[0].message.content

            USER_MEMORY[chat_id].append({"role":"user","content":text})
            USER_MEMORY[chat_id].append({"role":"assistant","content":answer})

            if len(USER_MEMORY[chat_id]) > MAX_HISTORY:
                USER_MEMORY[chat_id] = USER_MEMORY[chat_id][-MAX_HISTORY:]

            return answer
        except Exception as e:
            logger.error(f"{model} fail: {e}")
            continue
    return "Блять, Грок упал, епта. Пиши @MakSon4ikk_228, сука."

@bot.message_handler(commands=['start'])
def h_start(m):
    bot.send_message(m.chat.id, "Ну привет, блять. Я Даун213, но я бот, а не школьник. Че надо? Жми кнопки, епта 👇", reply_markup=get_main_menu())

@bot.message_handler(commands=['help'])
def h_help(m):
    bot.send_message(m.chat.id, f"""
Че, несешь фигню? Я Даун213 v{BOT_VERSION}, бот, а не человек.

Че умею, епта:
1. Ворчу, но помогаю, сука
2. Помню тебя, память на {MAX_HISTORY} сообщ.
3. Отвечаю грубо, но по делу

Команды:
/help - это говно
/info - скока работаю
/creator - кто мой папа
/forget - забыть тебя, блять

Папа - @MakSon4ikk_228
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
У тебя в башке: {len(USER_MEMORY[m.chat.id])} сообщ.
Создатель: @MakSon4ikk_228
""", reply_markup=get_main_menu())

@bot.message_handler(commands=['forget','clear'])
def h_forget(m):
    USER_MEMORY.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "Все, забыл тебя нахер, епта. Память чиста. Заново давай.", reply_markup=get_main_menu())

@bot.message_handler(commands=['creator','папа'])
def h_cr(m): bot.send_message(m.chat.id, "Мой папа @MakSon4ikk_228, блять. Он меня сделал, сука, терпи теперь.", reply_markup=get_main_menu())

@bot.message_handler(content_types=['text'])
def h_text(m):
    try:
        bot.send_chat_action(m.chat.id, 'typing')
        ans = ask_groq(m.chat.id, m.text)
        bot.send_message(m.chat.id, ans)
    except Exception as e:
        bot.send_message(m.chat.id, f"Упал нахер: {e}")

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
