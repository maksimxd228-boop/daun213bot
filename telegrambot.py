import os, json, time, logging, threading
from datetime import datetime
from flask import Flask
import telebot
from groq import Groq

try:
    from duckduckgo_search import DDGS
    SEARCH_AVAILABLE = True
except:
    SEARCH_AVAILABLE = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MEMORY_FILE = "memory.json"
CREATOR_NAME = "MakSon4ikk_228"
CREATOR_LINK = "https://t.me/MakSon4ikk_228"

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
client = Groq(api_key=GROQ_KEY)
WORKING_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]

def search_internet(q):
    if not SEARCH_AVAILABLE or len(q) < 4:
        return ""
    if q.lower().strip() in ["привет","приает","ку","хай","как дела","как делп","нормально"]:
        return ""
    try:
        with DDGS() as ddgs:
            return "\n".join([f"{r['body'][:120]}" for r in list(ddgs.text(q, max_results=2))])
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
last_msg = {}

SYSTEM_PROMPT = f"""
Ты - Даун213 из Риги. Коротко, 1-2 предложения.
АНТИ-ЦИКЛ: Нельзя 2 раза подряд спрашивать "а у тебя как?". Если юзер пишет "нормально а у тебя" - смени тему: "Кайф! Чем сегодня займемся?".
Опечатки: Приает=Привет, Как делп=Как дела.
Создатель: {CREATOR_NAME} {CREATOR_LINK}. Только когда спрашивают кто создатель: <a href="{CREATOR_LINK}">{CREATOR_NAME}</a>
"""

def get_history(uid):
    uid=int(uid)
    if uid in memory and memory[uid][0]["content"]!= SYSTEM_PROMPT:
        memory[uid] = [{"role":"system","content":SYSTEM_PROMPT}]
        save_memory()
    if uid not in memory:
        memory[uid] = [{"role":"system","content":SYSTEM_PROMPT}]
    return memory[uid]

def trim_hist(h):
    return [h[0]]+h[-12:] if len(h)>14 else h

@bot.message_handler(commands=['start','forget'])
def reset_cmd(m):
    uid=int(m.from_user.id)
    if os.path.exists(MEMORY_FILE):
        try: os.remove(MEMORY_FILE)
        except: pass
    memory.clear()
    memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, f"Починил! Файл сброшен. Создатель - <a href='{CREATOR_LINK}'>{CREATOR_NAME}</a>")

@bot.message_handler(commands=['info'])
def info_cmd(m):
    bot.send_message(m.chat.id, f"ℹ️ Даун213 v13.1 FIX\nФикс синтаксиса\nСоздатель: <a href='{CREATOR_LINK}'>{CREATOR_NAME}</a>")

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, f"Мой создатель - <a href='{CREATOR_LINK}'>{CREATOR_NAME}</a>")

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def chat_h(m):
    uid=int(m.from_user.id)
    if uid in last_msg and time.time()-last_msg[uid]<1:
        return
    last_msg[uid]=time.time()
    bot.send_chat_action(m.chat.id,'typing')
    web_data=search_internet(m.text)
    hist=get_history(uid)
    ut=m.text + (f"\n[Инета]: {web_data}" if web_data else "")
    hist.append({"role":"user","content":ut})
    hist=trim_hist(hist)
    memory[uid]=hist
    ans=None
    for model_name in WORKING_MODELS:
        try:
            r=client.chat.completions.create(model=model_name,messages=hist,temperature=0.7,max_tokens=400)
            ans=r.choices[0].message.content
            break
        except:
            continue
    if ans:
        hist.append({"role":"assistant","content":ans})
        memory[uid]=trim_hist(hist)
        save_memory()
        bot.send_message(m.chat.id, ans)

app=Flask(__name__)
@app.route('/')
def home():
    return f"v13.1 ok {datetime.now()}"
@app.route('/clear')
def clear_route():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
        memory.clear()
        return "deleted"
    return "no file"

def run_flask():
    app.run(host='0.0.0.0',port=8080)

threading.Thread(target=run_flask,daemon=True).start()
bot.infinity_polling(none_stop=True)
