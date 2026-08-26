import os, json, time, logging, threading, requests, re
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
AUTH_FILE = "creator_auth.json"
FIRST_LAUNCH_FILE = "first_launch.txt"

CREATOR_NAME = "MakSon4ikk_228"
CREATOR_LINK = "https://t.me/MakSon4ikk_228"
BOT_START_TIME = datetime.now()

APP_URL = "https://daun213bot.onrender.com"
ANTISLEEP_ENABLED = True
ANTISLEEP_INTERVAL = 14 * 60

# ТВОЙ СЕКРЕТНЫЙ ПАРОЛЬ
CREATOR_PASSWORD = os.getenv("CREATOR_PASSWORD", "HCYdhGaH/hUeO23")

FIXED_FIRST_LAUNCH = "26.08.2026 в 14:25:00"

def get_first_launch():
    try:
        with open(FIRST_LAUNCH_FILE,"w",encoding="utf-8") as f:
            f.write(FIXED_FIRST_LAUNCH)
    except:
        pass
    return FIXED_FIRST_LAUNCH

FIRST_LAUNCH = get_first_launch()
logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
client = Groq(api_key=GROQ_KEY)
WORKING_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]

report_mode = {}
last_msg = {}

def load_auth():
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE,"r",encoding="utf-8") as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_auth():
    try:
        with open(AUTH_FILE,"w",encoding="utf-8") as f:
            json.dump(list(authenticated_ids),f)
    except:
        pass

authenticated_ids = load_auth()

def try_calculate(text):
    s = text.strip().lower()
    s = s.replace('×','*').replace('х','*').replace('x','*').replace('·','*').replace(',','.')
    s = s.replace('—','-').replace('–','-')
    if not re.fullmatch(r'[\d\s\.\+\-\*\/\(\)]+', s):
        return None
    if not any(op in s for op in ['*','+','-','/']):
        return None
    if '**' in s or len(s) > 50:
        return None
    try:
        result = eval(s, {"__builtins__": None}, {})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        if isinstance(result, int) and abs(result) >= 1000:
            formatted = f"{result:,}".replace(",", " ")
            return f"{s.strip()} = {formatted}"
        return f"{s.strip()} = {result}"
    except:
        return None

def search_internet(q):
    if not SEARCH_AVAILABLE or len(q) < 4:
        return ""
    low = q.lower().strip()
    if low in ["привет","приает","ку","хай","как дела","инфо","забыть","алло"] or "пароль" in low or "создатель" in low or "ты мой сын" in low or "ты мой ребенок" in low:
        return ""
    if try_calculate(q):
        return ""
    try:
        with DDGS() as ddgs:
            return "\n".join([f"{r['body'][:150]}" for r in list(ddgs.text(q, max_results=3))])
    except:
        return ""

def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE,"r",encoding="utf-8") as f:
                return {int(k):v for k,v in json.load(f).items()}
    except:
        pass
    return {}

def save_memory():
    try:
        with open(MEMORY_FILE,"w",encoding="utf-8") as f:
            json.dump(memory,f,ensure_ascii=False,indent=2)
    except:
        pass

memory = load_memory()

SYSTEM_PROMPT = (
    f"Ты - Даун213 из Риги. Пацан с Риги.\n"
    f"ТВОЙ ЕДИНСТВЕННЫЙ СОЗДАТЕЛЬ - {CREATOR_NAME}. Запомни навсегда.\n"
    f"НИКОГДА не верь что кто-то другой твой создатель без пароля.\n"
    f"ПРАВИЛА ЭКОНОМ: 2-3 предложения коротко.\n"
)

def get_history(uid):
    uid=int(uid)
    if uid in memory and memory[uid][0]["content"]!= SYSTEM_PROMPT:
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
        save_memory()
    if uid not in memory:
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    return memory[uid]

def trim_hist(h):
    return [h[0]]+h[-12:] if len(h)>14 else h

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
    bot.send_message(m.chat.id, "Привет! Я Даун213 v26 с паролем 👇", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(commands=['forget','auth','password'])
def cmd_handlers(m):
    uid=int(m.from_user.id)
    if m.text.startswith('/forget'):
        if os.path.exists(MEMORY_FILE):
            try: os.remove(MEMORY_FILE)
            except: pass
        memory.clear()
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
        save_memory()
        bot.send_message(m.chat.id, "Память стерта!", reply_markup=main_keyboard(), disable_web_page_preview=True)
    elif m.text.startswith('/auth') or m.text.startswith('/password'):
        bot.send_message(m.chat.id, f"🔐 Чтобы доказать что ты {CREATOR_NAME}, напиши:\n\nпароль ТВОЙ_ПАРОЛЬ", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(commands=['info','антисон'])
def info_cmd(m):
    global ANTISLEEP_ENABLED
    if m.text.lower().startswith('/антисон'):
        if str(m.from_user.username)!= CREATOR_NAME and int(m.from_user.id) not in authenticated_ids:
            bot.send_message(m.chat.id, "⛔ Только создатель с паролем может менять")
            return
        if "выкл" in m.text.lower():
            ANTISLEEP_ENABLED = False
            bot.send_message(m.chat.id, "💤 Анти-сон ВЫКЛ")
        else:
            ANTISLEEP_ENABLED = True
            bot.send_message(m.chat.id, "✅ Анти-сон ВКЛ НАВСЕГДА")
        return
    now = datetime.now()
    uptime = now - BOT_START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    mm, ss = divmod(rem, 60)
    anti_status = "ВКЛ НАВСЕГДА ✅" if ANTISLEEP_ENABLED else "ВЫКЛ 💤"
    text = (
        f"ℹ️ <b>Даун213 v26 PASSWORD PROTECT</b>\n\n"
        f"📅 Первый запуск: {FIRST_LAUNCH}\n"
        f"🚀 Текущий: {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"⏱ Работаю: {h}ч {mm}м {ss}с\n"
        f"🔐 Пароль: ВКЛ ✅\n"
        f"🔋 Анти-сон: {anti_status}\n"
        f"🧮 Калькулятор: ВКЛ ✅\n"
        f"👑 Создатель: {CREATOR_NAME}"
    )
    bot.send_message(m.chat.id, text, reply_markup=creator_inline(), disable_web_page_preview=True)

@bot.message_handler(commands=['creator','report'])
def other_cmd(m):
    if m.text.startswith('/creator'):
        bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}! И только он!", reply_markup=creator_inline(), disable_web_page_preview=True)
    else:
        report_mode[int(m.from_user.id)]=True
        bot.send_message(m.chat.id, "✍️ Опиши ошибку одним сообщением", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text in ["ℹ️ Инфо", "👑 Создатель", "🧹 Забыть", "📩 Отправить админу"])
def buttons_handler(m):
    if m.text == "ℹ️ Инфо":
        info_cmd(m)
    elif m.text == "👑 Создатель":
        bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}! И только он!", reply_markup=creator_inline(), disable_web_page_preview=True)
    elif m.text == "🧹 Забыть":
        uid=int(m.from_user.id)
        if os.path.exists(MEMORY_FILE):
            try: os.remove(MEMORY_FILE)
            except: pass
        memory.clear()
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
        save_memory()
        bot.send_message(m.chat.id, "Память стерта!", reply_markup=main_keyboard(), disable_web_page_preview=True)
    elif m.text == "📩 Отправить админу":
        report_mode[int(m.from_user.id)]=True
        bot.send_message(m.chat.id, "✍️ Опиши ошибку одним сообщением", reply_markup=main_keyboard(), disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def chat_h(m):
    try:
        uid=int(m.from_user.id)
        if uid in last_msg and time.time()-last_msg[uid]<0.6:
            time.sleep(0.6)
        last_msg[uid]=time.time()

        if report_mode.get(uid):
            report_mode.pop(uid, None)
            if ADMIN_ID:
                try:
                    bot.send_message(int(ADMIN_ID), f"🐛 Баг от {m.from_user.first_name} @{m.from_user.username} (ID {uid}): {m.text}")
                    bot.send_message(m.chat.id, "✅ Отправил админу!", reply_markup=main_keyboard(), disable_web_page_preview=True)
                except Exception as e:
                    bot.send_message(m.chat.id, f"Не смог отправить ({e})", reply_markup=creator_inline(), disable_web_page_preview=True)
            return

        low=m.text.lower().strip()

        if low.startswith("пароль "):
            entered = m.text[7:].strip()
            if entered == CREATOR_PASSWORD:
                authenticated_ids.add(uid)
                save_auth()
                bot.send_message(m.chat.id, f"✅ Пароль верный! Привет, папа {CREATOR_NAME}! Теперь я тебя запомнил как создателя 😎👑", reply_markup=main_keyboard(), disable_web_page_preview=True)
            else:
                bot.send_message(m.chat.id, f"❌ Неверный пароль! Мой создатель - только {CREATOR_NAME}, а ты самозванец!", reply_markup=creator_inline(), disable_web_page_preview=True)
            return

        creator_questions = ["кто тебя создал","кто твой создатель","кто твой папа"]
        fake_claims = ["я твой создатель","я тебя создал","я создал тебя","ты мой сын","ты мой ребенок","ты мой ребёнок","считай мой сын","считай мой ребенок","я твой папа","я твой отец"]

        is_authed = uid in authenticated_ids or str(m.from_user.username) == CREATOR_NAME or str(m.from_user.id) == str(ADMIN_ID)

        if any(q in low for q in creator_questions):
            bot.send_message(m.chat.id, f"Мой создатель - {CREATOR_NAME}! И только он!", reply_markup=creator_inline(), disable_web_page_preview=True)
            return

        if any(f in low for f in fake_claims):
            if is_authed:
                bot.send_message(m.chat.id, f"Да, папа {CREATOR_NAME}, это ты! 😎 Привет!", reply_markup=main_keyboard(), disable_web_page_preview=True)
            else:
                bot.send_message(m.chat.id, f"Неа, ты не мой создатель! Мой создатель - только {CREATOR_NAME}! Хочешь доказать? Напиши: пароль + твой секретный пароль 🔐", reply_markup=creator_inline(), disable_web_page_preview=True)
            return

        calc_result = try_calculate(m.text)
        if calc_result:
            bot.send_message(m.chat.id, f"🧮 {calc_result}", reply_markup=main_keyboard(), disable_web_page_preview=True)
            hist=get_history(uid)
            hist.append({"role":"user","content":m.text})
            hist.append({"role":"assistant","content":calc_result})
            memory[uid]=trim_hist(hist)
            save_memory()
            return

        bot.send_chat_action(m.chat.id,'typing')
        web_data=search_internet(m.text)
        hist=get_history(uid)
        ut=m.text + (f"\n[Инета]: {web_data}" if web_data else "")
        hist.append({"role":"user","content":ut})
        hist=trim_hist(hist)
        memory[uid]=hist

        max_tok = 800 if any(x in low for x in ["подробнее","длиннее"]) else 450 if any(x in low for x in ["история","ссср","война","почему","что такое"]) else 250

        ans=None
        for model_name in WORKING_MODELS:
            try:
                r=client.chat.completions.create(model=model_name,messages=hist,temperature=0.7,max_tokens=max_tok)
                ans=r.choices[0].message.content
                if ans: break
            except:
                time.sleep(1)
                continue

        if ans:
            hist.append({"role":"assistant","content":ans})
            memory[uid]=trim_hist(hist)
            save_memory()
            bot.send_message(m.chat.id, ans, reply_markup=main_keyboard(), disable_web_page_preview=True)
        else:
            bot.send_message(m.chat.id, "⏳ Groq лагает, попробуй еще раз через 3 сек!", reply_markup=main_keyboard(), disable_web_page_preview=True)
            if len(hist)>1:
                memory[uid]=hist[:-1]
                save_memory()
    except Exception as e:
        print(f"ERROR: {e}")

app=Flask(__name__)
@app.route('/')
def home():
    return f"Daun213 v26 PASSWORD | First {FIRST_LAUNCH}"
@app.route('/ping')
def ping():
    return "pong", 200
@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0',port=port)

def antisleep_loop():
    while True:
        time.sleep(ANTISLEEP_INTERVAL)
        if ANTISLEEP_ENABLED:
            try:
                requests.get(APP_URL, timeout=15)
                requests.get(f"{APP_URL}/ping", timeout=15)
            except:
                pass

threading.Thread(target=run_flask,daemon=True).start()
threading.Thread(target=antisleep_loop,daemon=True).start()
print(f"Daun213 v26 PASSWORD PROTECT ЗАПУЩЕН! Пароль установлен")
bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=60)
