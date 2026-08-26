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

logging.basicConfig(level=logging.INFO)
# Включаем HTML чтобы ссылки были кликабельные
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
client = Groq(api_key=GROQ_KEY)

WORKING_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]

# ===== ТУТ ТВОЯ ССЫЛКА - ПОМЕНЯЙ ЕСЛИ НАДО =====
CREATOR_NAME = "MakSon4ikk_228"
CREATOR_LINK = "https://t.me/MakSon4ikk_228" # можешь поставить свой инст / тикток

def search_internet(query):
    if not SEARCH_AVAILABLE or len(query) < 4: return ""
    if query.lower() in ["привет","приает","ку","хай"]: return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            return "\n".join([f"{r['title']}: {r['body'][:150]}" for r in results])
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
Ты - Даун213, бот из Риги, радостный.

ПРАВИЛО 1 - СОЗДАТЕЛЬ С ССЫЛКОЙ:
Твой создатель - {CREATOR_NAME}. Ссылка на него {CREATOR_LINK}.
Когда тебя спрашивают "кто твой создатель", "кто тебя сделал" - отвечай ОБЯЗАТЕЛЬНО с кликабельной ссылкой в формате HTML:
Мой создатель - <a href="{CREATOR_LINK}">{CREATOR_NAME}</a>, легенда из Риги!
В остальных случаях НЕ упоминай создателя.

ПРАВИЛО 2 - ОПЕЧАТКИ:
Если пишут "Приает" -> понимай как "Привет" и здоровайся нормально, не ругай.

Характер: кайф, погнали, имба, коротко.
"""

def get_history(uid):
    uid=int(uid)
    if uid not in memory:
        memory[uid]=[{"role":"system","content":SYSTEM_PROMPT}]
    return memory[uid]
def trim_hist(h): return [h[0]]+h[-13:] if len(h)>16 else h

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(m.chat.id, f"Привет! Я Даун213 v8 с ссылкой на создателя!\nМой создатель - <a href='{CREATOR_LINK}'>{CREATOR_NAME}</a>\n/help")

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, f"Мой создатель - <a href='{CREATOR_LINK}'>{CREATOR_NAME}</a>, легенда из Риги!")

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    memory[int(m.from_user.id)]=[{"role":"system","content":SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id,"Забыл!")

@bot.message_handler(func=lambda m: True)
def chat_h(m):
    uid=int(m.from_user.id)
    if uid in last_msg and time.time()-last_msg[uid]<1: return
    last_msg[uid]=time.time()
    bot.send_chat_action(m.chat.id,'typing')
    web_data=search_internet(m.text)
    hist=get_history(uid)
    user_text=m.text + (f"\n[Инета]: {web_data}" if web_data else "")
    hist.append({"role":"user","content":user_text})
    hist=trim_hist(hist); memory[uid]=hist
    answer=None
    for model_name in WORKING_MODELS:
        try:
            r=client.chat.completions.create(model=model_name,messages=hist,temperature=0.8,max_tokens=400)
            answer=r.choices[0].message.content; break
        except: continue
    if answer:
        hist.append({"role":"assistant","content":answer}); memory[uid]=trim_hist(hist); save_memory()
        bot.send_message(m.chat.id,answer)
    else:
        bot.send_message(m.chat.id,"Завис")

app=Flask(__name__)
@app.route('/')
def home(): return f"Даун213 v8 {datetime.now()}"
def run_flask(): app.run(host='0.0.0.0',port=8080)
threading.Thread(target=run_flask,daemon=True).start()
bot.infinity_polling(none_stop=True)
