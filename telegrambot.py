import os
import time
import threading
import requests
import random
from datetime import datetime
from flask import Flask
import telebot

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = "https://daun213bot.onrender.com"
START_TIME = datetime.now()
ANTISLEEP_ENABLED = True # ВЕЧНЫЙ ВКЛ
ANTISLEEP_INTERVAL = 14 * 60

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
memory_users = {}
memory_messages = 0
CREATOR = "MakSon4ikk_228"

ANSWERS = {
    "девушки боятся": "Девушки чаще всего боятся людей, которые проявляют агрессию, неуважение или недоверие. Также опасаются тех, кто не умеет слушать и ценить их мнение.",
    "парни боятся": "Парни чаще всего боятся показаться слабыми, быть отвергнутыми и потерять уважение.",
    "кого боятся": "Девушки чаще всего боятся людей, которые проявляют агрессию, неуважение или недоверие.",
}

@app.route('/')
def home():
    uptime = datetime.now() - START_TIME
    return f"Daun213 v20 ECONOMY | Uptime: {uptime} | AntiSleep: ALWAYS ON ✅", 200

@app.route('/ping')
def ping():
    return "pong", 200

def antisleep_loop():
    while True:
        time.sleep(ANTISLEEP_INTERVAL)
        if ANTISLEEP_ENABLED:
            try:
                print(f"[{datetime.now()}] AntiSleep ping -> {APP_URL}")
                requests.get(APP_URL, timeout=15)
                requests.get(f"{APP_URL}/ping", timeout=15)
            except Exception as e:
                print(f"AntiSleep error: {e}")

threading.Thread(target=antisleep_loop, daemon=True).start()

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.reply_to(message, f"Привет! Я Даун213 v20 ECONOMY\n🔋 Анти-сон: ВКЛ НАВСЕГДА\nНапиши Инфо")

@bot.message_handler(commands=['антисон'])
def cmd_antisleep(message):
    global ANTISLEEP_ENABLED
    if "выкл" in message.text.lower():
        ANTISLEEP_ENABLED = False
        bot.reply_to(message, "💤 Анти-сон ВЫКЛ")
    else:
        ANTISLEEP_ENABLED = True
        bot.reply_to(message, "✅ Анти-сон ВКЛ НАВСЕГДА - буду работать 10 часов пока ты спишь")

@bot.message_handler(func=lambda m: True)
def all_messages(message):
    global memory_messages
    memory_messages += 1
    memory_users[message.from_user.id] = message.from_user.username
    text = message.text.lower() if message.text else ""

    if "инфо" in text:
        now = datetime.now()
        uptime = now - START_TIME
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        info_text = f"""ℹ️ Даун213 v20 ECONOMY

📅 Первый запуск: {START_TIME.strftime('%d.%m.%Y в %H:%M:%S')}
🚀 Текущий: {START_TIME.strftime('%d.%m.%Y %H:%M:%S')}
⏱️ Работаю: {h}ч {m}м {s}с
🕐 Сейчас: {now.strftime('%d.%m.%Y %H:%M:%S')}
👥 В памяти: {len(memory_users)}
💬 Сообщений: {memory_messages}
🔋 Анти-сон: ВКЛ НАВСЕГДА ✅ (не спит никогда)
👑 Создатель: {CREATOR}"""
        bot.send_message(message.chat.id, info_text)
        return

    for key in ANSWERS:
        if key in text:
            bot.reply_to(message, ANSWERS[key])
            return

    bot.reply_to(message, message.text)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print(f"Bot v20 STARTED | AntiSleep ВЕЧНЫЙ ВКЛ")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)Анти-цикл: не спрашивай 2 раза "а у тебя как?".
Приает=Привет. Создатель {CREATOR_NAME}, не упоминай сам.
"""

def get_history(uid):
    uid=int(uid)
    if uid in memory and memory[uid][0]["content"]!= SYSTEM_PROMPT:
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
        save_memory()
    if uid not in memory:
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    return memory[uid]

def trim_hist(h): return [h[0]]+h[-12:] if len(h)>14 else h

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("ℹ️ Инфо"), types.KeyboardButton("👑 Создатель"))
    markup.add(types.KeyboardButton("🧹 Забыть"), types.KeyboardButton("📩 Отправить админу"))
    return markup

def creator_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"👤 {CREATOR_NAME}", url=CREATOR_LINK))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid=int(m.from_user.id)
    memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, "Привет! Я Даун213, кнопки внизу 👇 (v19 эконом)", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    uid=int(m.from_user.id)
    if os.path.exists(MEMORY_FILE):
        try: os.remove(MEMORY_FILE)
        except: pass
    memory.clear()
    memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, "Память стерта!", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(commands=['info'])
def info_cmd(m):
    now = datetime.now()
    uptime = now - BOT_START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    mm, ss = divmod(rem, 60)
    text = (f"ℹ️ <b>Даун213 v19 ECONOMY</b>\n\n"
            f"📅 Первый запуск: {FIRST_LAUNCH}\n"
            f"🚀 Текущий: {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"⏱ Работаю: {h}ч {mm}м {ss}с\n"
            f"🕒 Сейчас: {now.strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"👥 В памяти: {len(memory)}\n"
            f"👑 Создатель: {CREATOR_NAME}")
    bot.send_message(m.chat.id, text, reply_markup=creator_inline(), disable_web_page_preview=True)

@bot.message_handler(commands=['creator','report'])
def other_cmd(m):
    if m.text.startswith('/creator'):
        bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}!", reply_markup=creator_inline(), disable_web_page_preview=True)
    else:
        start_report(m)

def start_report(m):
    uid=int(m.from_user.id)
    report_mode[uid]=True
    bot.send_message(m.chat.id, "✍️ Опиши ошибку одним сообщением и я перешлю админу.", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text in ["ℹ️ Инфо", "👑 Создатель", "🧹 Забыть", "📩 Отправить админу"])
def buttons_handler(m):
    if m.text == "ℹ️ Инфо": info_cmd(m)
    elif m.text == "👑 Создатель": bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}!", reply_markup=creator_inline(), disable_web_page_preview=True)
    elif m.text == "🧹 Забыть": forget_cmd(m)
    elif m.text == "📩 Отправить админу": start_report(m)

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def chat_h(m):
    uid=int(m.from_user.id)
    if uid in last_msg and time.time()-last_msg[uid]<0.5: return
    last_msg[uid]=time.time()

    if report_mode.get(uid):
        report_mode.pop(uid, None)
        if ADMIN_ID:
            try:
                bot.send_message(int(ADMIN_ID), f"🐛 <b>Баг-репорт от Даун213</b>\n\n👤 От: {m.from_user.first_name} @{m.from_user.username or 'нет'} (ID {uid})\n💬 Текст: {m.text}\n🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
                bot.send_message(m.chat.id, "✅ Отправил админу! Спасибо!", reply_markup=main_keyboard(), disable_web_page_preview=True)
            except Exception as e:
                bot.send_message(m.chat.id, f"Не смог отправить ({e})", reply_markup=creator_inline(), disable_web_page_preview=True)
        else:
            bot.send_message(m.chat.id, "⚠️ ADMIN_ID не настроен", reply_markup=creator_inline(), disable_web_page_preview=True)
        return

    low=m.text.lower()
    if "кто тебя создал" in low or "кто твой создатель" in low:
        bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}!", reply_markup=creator_inline(), disable_web_page_preview=True)
        return

    bot.send_chat_action(m.chat.id,'typing')
    web_data=search_internet(m.text)
    hist=get_history(uid)
    ut=m.text + (f"\n[Инета]: {web_data}" if web_data else "")
    hist.append({"role":"user","content":ut})
    hist=trim_hist(hist); memory[uid]=hist

    # ЭКОНОМ ЛОГИКА ТОКЕНОВ
    is_detail = any(x in low for x in ["подробнее","длиннее","больше текста","мало текста","расскажи больше"])
    is_history = any(x in low for x in ["как появился","как возник","что такое","история","ссср","война","почему","когда был"])
    if is_detail: max_tok = 800
    elif is_history: max_tok = 450
    else: max_tok = 250

    ans=None
    for model_name in WORKING_MODELS:
        try:
            r=client.chat.completions.create(model=model_name,messages=hist,temperature=0.7,max_tokens=max_tok)
            ans=r.choices[0].message.content; break
        except Exception as e:
            print(f"Model {model_name} error: {e}")
            continue
    if ans:
        hist.append({"role":"assistant","content":ans}); memory[uid]=trim_hist(hist); save_memory()
        bot.send_message(m.chat.id, ans, reply_markup=main_keyboard(), disable_web_page_preview=True)

app=Flask(__name__)
@app.route('/')
def home(): return f"v19 economy {BOT_START_TIME}"
def run_flask(): app.run(host='0.0.0.0',port=8080)
threading.Thread(target=run_flask,daemon=True).start()
bot.infinity_polling(none_stop=True)
