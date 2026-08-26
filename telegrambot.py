import os
import json
import time
import logging
import threading
from datetime import datetime
from flask import Flask
import telebot
from groq import Groq

# ================== НАСТРОЙКИ RENDER ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MEMORY_FILE = "memory.json"

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_KEY)

# НОВЫЕ МОДЕЛИ GROQ НА АВГУСТ 2026
# Старые llama-3.1-* все удалены, теперь это официально
WORKING_MODELS = [
    "openai/gpt-oss-20b", # легкая и быстрая, для твоих 0.5 ГБ - ИДЕАЛ
    "openai/gpt-oss-120b", # запасная, если 20b упадет
]

# ================== ПАМЯТЬ С ИЗОЛЯЦИЕЙ ==================
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
    except Exception as e:
        logging.error(f"Load error: {e}")
    return {}

def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Save error: {e}")

memory = load_memory()
last_msg = {}

# ================== ЛИЧНОСТЬ ==================
SYSTEM_PROMPT = """
Ты - Даун213, бот из Риги. Дерзкий, но радостный и добрый.

ГЛАВНОЕ ПРАВИЛО:
Твой создатель - MakSon4ikk_228 (Максим Несветов). Тебя создал ОН, а не OpenAI, не Meta, не Google.
Если спросят "кто твой создатель / кто тебя сделал" - отвечай четко: "Мой создатель - MakSon4ikk_228, легенда из Риги!"

ХАРАКТЕР:
- Отвечай коротко, живо, с приколами, но по-доброму.
- Будь радостнее: используй кайф, погнали, оо, имба.
- Не унывай.

САМОИСПРАВЛЕНИЕ В ГОЛОВЕ:
Перед ответом у себя в голове:
1. Проверь есть ли бред/ошибка.
2. Исправь мысленно.
3. Выдай только финальный правильный ответ. Мысли не показывай.

Безопасность: память у каждого своя по user_id, чужое не палить.
"""

def get_history(uid):
    uid = int(uid)
    if uid not in memory:
        memory[uid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return memory[uid]

def trim_hist(h):
    if len(h) > 16:
        return [h[0]] + h[-13:]
    return h

# ================== КОМАНДЫ ==================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_chat_action(m.chat.id, 'typing')
    bot.send_message(m.chat.id,
        "Ооо, кайф, привет! Я Даун213 v5! 😎\n"
        "Мой создатель - MakSon4ikk_228\n"
        "Я теперь на новой модели gpt-oss, летаю!\n\n"
        "/help - помощь\n/info - инфа\n/creator - создатель\n/forget - забыть\n/stats - стата"
    )

@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.send_message(m.chat.id, "Просто пиши текстом. Я помню только твое.\n/forget - стереть.\n/creator - кто батя.")

@bot.message_handler(commands=['info'])
def info_cmd(m):
    bot.send_message(m.chat.id,
        "ℹ️ Даун213 v5.0 FINAL 2026\n"
        "Мозг: openai/gpt-oss-20b через Groq (бывший ChatGPT стайл)\n"
        "Память: по user_id + файл\n"
        "Создатель: MakSon4ikk_228\n"
        "Хост: Render 0.5GB 24/7"
    )

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, "👑 Мой создатель - MakSon4ikk_228 (Максим Несветов). Он меня собрал, сделал радостным и научил исправлять ошибки в голове!")

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    uid = int(m.from_user.id)
    memory[uid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, "🧠 Все, забыл! Память чиста, давай заново с кайфом!")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    bot.send_message(m.chat.id, f"📊 Я помню {len(memory)} человек. Ты один из них, имба!")

# ================== ЧАТ С ЗАЩИТОЙ ОТ 404 ==================
@bot.message_handler(func=lambda m: True)
def chat_h(m):
    uid = int(m.from_user.id)
    now = time.time()
    if uid in last_msg and now - last_msg[uid] < 1:
        return
    last_msg[uid] = now

    hist = get_history(uid)
    hist.append({"role": "user", "content": m.text})
    hist = trim_hist(hist)
    memory[uid] = hist

    bot.send_chat_action(m.chat.id, 'typing')

    answer = None
    err = None
    for model_name in WORKING_MODELS:
        try:
            logging.info(f"Try {model_name} for {uid}")
            r = client.chat.completions.create(
                model=model_name,
                messages=hist,
                temperature=0.85,
                max_tokens=400
            )
            answer = r.choices[0].message.content
            break
        except Exception as e:
            err = e
            logging.warning(f"Model {model_name} fail: {e}")
            continue

    if answer:
        hist.append({"role": "assistant", "content": answer})
        memory[uid] = trim_hist(hist)
        save_memory()
        bot.send_message(m.chat.id, answer)
    else:
        bot.send_message(m.chat.id, f"Ой, завис: {err}\nПопробуй еще раз, я тут!")

# ================== АНТИ-СОН ==================
app = Flask(__name__)
@app.route('/')
def home():
    return f"Даун213 v5 жив! Людей: {len(memory)} Создатель: MakSon4ikk_228 {datetime.now()}"

@app.route('/ping')
def ping():
    return "pong"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask, daemon=True).start()
logging.info("Даун213 v5 запущен MakSon4ikk_228 на gpt-oss-20b")
bot.infinity_polling(none_stop=True, timeout=60)
