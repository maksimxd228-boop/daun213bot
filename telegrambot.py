import os, json, time, logging, threading
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
from groq import Groq

try:
    from duckduckgo_search import DDGS
    SEARCH_AVAILABLE = True
except:
    SEARCH_AVAILABLE = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")
MEMORY_FILE = "memory.json"
FIRST_LAUNCH_FILE = "first_launch.txt"

CREATOR_NAME = "MakSon4ikk_228"
CREATOR_LINK = "https://t.me/MakSon4ikk_228"
BOT_START_TIME = datetime.now()

def get_first_launch():
    if os.path.exists(FIRST_LAUNCH_FILE):
        try:
            with open(FIRST_LAUNCH_FILE,"r") as f:
                return f.read().strip()
        except: pass
    now_str = BOT_START_TIME.strftime("%d.%m.%Y в %H:%M:%S")
    try:
        with open(FIRST_LAUNCH_FILE,"w") as f:
            f.write(now_str)
    except: pass
    return now_str

FIRST_LAUNCH = get_first_launch()
logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
client = Groq(api_key=GROQ_KEY)
WORKING_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]

report_mode = {}

def search_internet(q):
    if not SEARCH_AVAILABLE or len(q) < 4: return ""
    if q.lower().strip() in ["привет","приает","ку","хай","как дела","как делп","нормально","инфо","забыть"]: return ""
    try:
        with DDGS() as ddgs:
            return "\n".join([f"{r['body'][:150]}" for r in list(ddgs.text(q, max_results=3))])
    except: return ""

def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE,"r",encoding="utf-8") as f:
                return {int(k):v for k,v in json.load(f).items()}
    except: pass
    return {}
def save_memory():
    try:
        with open(MEMORY_FILE,"w",encoding="utf-8") as f:
            json.dump(memory,f,ensure_ascii=False,indent=2)
    except: pass

memory = load_memory()
last_msg = {}

SYSTEM_PROMPT = f"""
Ты - Даун213 из Риги. Пацан с Риги, общаешься нормально.

ПРАВИЛА ЭКОНОМ:
- По умолчанию: 2-3 предложения, коротко.
- История/наука (как появился, что такое, ссср, война, почему) - 4-5 предложений с датами.
- Только если пишут "подробнее", "длиннее", "больше текста" - тогда 2 абзаца.

Анти-цикл: не спрашивай 2 раза "а у тебя как?".
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
