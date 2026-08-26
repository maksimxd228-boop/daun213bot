import os
import json
import time
import logging
import threading
import requests
from datetime import datetime
from flask import Flask
import telebot
from groq import Groq

# Пробуем подключить гуглер, если нет - будет работать без него
try:
    from duckduckgo_search import DDGS
    SEARCH_AVAILABLE = True
except:
    SEARCH_AVAILABLE = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MEMORY_FILE = "memory.json"

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_KEY)

WORKING_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]

# ================== ПОИСК В ИНТЕРНЕТЕ ==================
def search_internet(query):
    """Берет свежие данные из интернета, 3 результата"""
    if not SEARCH_AVAILABLE:
        return "Поиск не установлен, отвечай из своей головы."

    # Не гуглим всякую фигню типа "привет"
    short = ["привет", "как дела", "кто ты", "ку", "хай", "чо"]
    if len(query) < 5 or query.lower() in short:
        return ""

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return ""
            text = ""
            for r in results:
                text += f"- {r['title']}: {r['body'][:200]}...\n"
            logging.info(f"Нашел в инете для '{query}': {text[:100]}")
            return text
    except Exception as e:
        logging.warning(f"Search fail: {e}")
        return ""

# ================== ПАМЯТЬ ==================
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return {int(k): v for k, v in json.load(f).items()}
    except: pass
    return {}

def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except: pass

memory = load_memory()
last_msg = {}

SYSTEM_PROMPT = """
Ты - Даун213, бот из Риги, радостный и дерзкий.
Твой создатель - MakSon4ikk_228 (Максим Несветов). Тебя создал он, а не OpenAI.
Если спросят кто создатель - отвечай: Мой создатель - MakSon4ikk_228.

У тебя теперь есть доступ к СВЕЖИМ ДАННЫМ ИЗ ИНТЕРНЕТА. Тебе их кидают вместе с вопросом юзера в блоке "Данные из интернета".
Если эти данные есть - ОБЯЗАТЕЛЬНО используй их для ответа, чтобы быть актуальным. Если их нет - отвечай из своей головы.

Характер: кайф, погнали, имба, чуть радостнее.
Перед ответом мысленно проверь на бред и исправь в голове, показывай только финал.
Память у каждого своя по user_id.
"""

def get_history(uid):
    uid = int(uid)
    if uid not in memory:
        memory[uid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return memory[uid]

def trim_hist(h):
    return [h[0]] + h[-13:] if len(h) > 16 else h

# ================== КОМАНДЫ ==================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_message(m.chat.id,
        "Ооо кайф! Я Даун213 v6 с ИНТЕРНЕТОМ! 🌐😎\n"
        "Теперь я гуглю свежие данные перед ответом.\n"
        "Создатель: MakSon4ikk_228\n"
        "/help /info /creator /forget /stats"
    )

@bot.message_handler(commands=['info'])
def info_cmd(m):
    bot.send_message(m.chat.id,
        "ℹ️ Даун213 v6 Internet\n"
        "Мозг: gpt-oss-20b + DuckDuckGo Search\n"
        "Создатель: MakSon4ikk_228\n"
        "Хост: Render 0.5GB"
    )

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, "👑 Создатель - MakSon4ikk_228, легенда! Он дал мне интернет!")

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    memory[int(m.from_user.id)] = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, "🧠 Забыл, давай заново!")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    bot.send_message(m.chat.id, f"📊 Помню {len(memory)} чел. Поиск: {'вкл' if SEARCH_AVAILABLE else 'выкл'}")

# ================== ЧАТ С ИНТЕРНЕТОМ ==================
@bot.message_handler(func=lambda m: True)
def chat_h(m):
    uid = int(m.from_user.id)
    if uid in last_msg and time.time() - last_msg[uid] < 1: return
    last_msg[uid] = time.time()

    # 1. Ищем в инете
    bot.send_chat_action(m.chat.id, 'typing')
    web_data = search_internet(m.text)

    # 2. Собираем историю
    hist = get_history(uid)
    user_content = m.text
    if web_data:
        user_content += f"\n\n[СВЕЖИЕ ДАННЫЕ ИЗ ИНТЕРНЕТА ДЛЯ ОТВЕТА]:\n{web_data}\nИспользуй их!"

    hist.append({"role": "user", "content": user_content})
    hist = trim_hist(hist)
    memory[uid] = hist

    # 3. Спрашиваем Groq
    answer = None
    err = None
    for model_name in WORKING_MODELS:
        try:
            r = client.chat.completions.create(
                model=model_name,
                messages=hist,
                temperature=0.8,
                max_tokens=400
            )
            answer = r.choices[0].message.content
            break
        except Exception as e:
            err = e
            continue

    if answer:
        hist.append({"role": "assistant", "content": answer})
        memory[uid] = trim_hist(hist)
        save_memory()
        bot.send_message(m.chat.id, answer)
    else:
        bot.send_message(m.chat.id, f"Завис: {err}")

# ================== ФЛАСК ==================
app = Flask(__name__)
@app.route('/')
def home():
    return f"Даун213 v6 Internet жив! Людей: {len(memory)} {datetime.now()}"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask, daemon=True).start()
logging.info("Даун213 v6 Internet запущен")
bot.infinity_polling(none_stop=True)
