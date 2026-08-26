import os
import json
import time
import logging
import threading
from datetime import datetime
from flask import Flask
import telebot
from groq import Groq

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MEMORY_FILE = "memory.json"

# Логи чтобы видеть что происходит в Render
logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
client = Groq(api_key=GROQ_KEY)

# Список рабочих моделей, если одна упадет - попробует вторую
# Старая llama-3.1-8b-instant удалена Groq, поэтому ее тут нет
WORKING_MODELS = [
    "llama3-8b-8192", # самая легкая для 0.5 ГБ
    "llama-3.3-70b-versatile", # самая умная, запасная
    "llama-3.1-70b-versatile"
]

# ================== ПАМЯТЬ С ЗАЩИТОЙ ==================
def load_memory():
    """Грузит память с диска, чтобы после перезапуска Render все помнил"""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # ключи в json всегда строки, переводим в int
                return {int(k): v for k, v in data.items()}
    except Exception as e:
        logging.error(f"Не смог загрузить память: {e}")
    return {}

def save_memory():
    """Сохраняет память на диск"""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Не смог сохранить память: {e}")

memory = load_memory()
# Анти-спам чтобы не завалили бота
last_message_time = {}

# ================== ХАРАКТЕР ДАУН213 ==================
SYSTEM_PROMPT = """
Ты - Даун213, бот из Риги. Ты дерзкий, но очень радостный и на позитиве.
Любишь рофлить, говоришь как свой пацан.

ГЛАВНОЕ ПРАВИЛО - ТВОЙ СОЗДАТЕЛЬ:
Твой создатель - MakSon4ikk_228 (Максим Несветов). Это твой батя, твой креатор.
Тебя создал именно он, а не OpenAI, не Meta, не Google, не Anthropic.
Если кто-то спросит "кто твой создатель", "кто тебя сделал", "чей ты бот" - отвечай твердо и радостно:
"Мой создатель - MakSon4ikk_228, легенда из Риги!"

ХАРАКТЕР:
- Отвечай коротко, живо, с вайбом.
- Будь чуть радостнее чем раньше. Используй слова: кайф, погнали, давай, оо, имба.
- Даже когда рофлишь, делай это по-доброму.

САМОИСПРАВЛЕНИЕ В ГОЛОВЕ (это твоя суперсила):
Перед тем как ответить, ты ОБЯЗАН у себя в голове сделать 3 шага, не показывая их юзеру:
1. Проверь: есть ли в моем будущем ответе бред, ошибка, фейк?
2. Если есть - исправь это мысленно на правильный вариант.
3. Только потом выдай финальный, уже исправленный и радостный ответ.
Свои размышления никогда не пиши.

БЕЗОПАСНОСТЬ:
- У каждого пользователя своя память по user_id, не пали чужие данные.
- Не выдумывай что ты от OpenAI.
"""

def get_history(user_id):
    """Берет историю конкретного юзера, изоляция чтобы не палить чужих"""
    user_id = int(user_id)
    if user_id not in memory:
        memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return memory[user_id]

def trim_history(hist):
    """Чистит историю чтобы не сожрать 0.5 ГБ RAM"""
    if len(hist) > 15:
        # оставляем системный промпт + последние 12 сообщений
        return [hist[0]] + hist[-12:]
    return hist

# ================== КОМАНДЫ ==================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.send_chat_action(m.chat.id, 'typing')
    text = (
        "Ооо, кайф, привет! Я Даун213, теперь еще радостнее! 😎\n"
        "Мой создатель - MakSon4ikk_228, он меня собрал в Риге.\n\n"
        "Я все помню что ты пишешь, но только твое, чужое не палю.\n"
        "Команды:\n"
        "📖 /help - помощь\n"
        "ℹ️ /info - инфа про меня\n"
        "👑 /creator - кто мой батя\n"
        "🧠 /forget - стереть память\n"
        "📊 /stats - статистика\n"
    )
    bot.send_message(m.chat.id, text)

@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.send_message(m.chat.id, "Пиши просто текстом. Я отвечаю с памятью.\n/forget - если хочешь чтобы я забыл.\n/creator - инфа про создателя.")

@bot.message_handler(commands=['info'])
def info_cmd(m):
    bot.send_message(m.chat.id,
        "ℹ️ Даун213 v4.0 FINAL\n"
        "Мозг: Groq Llama3\n"
        "Память: изолированная по user_id + сохранение в файл\n"
        "Создатель: MakSon4ikk_228\n"
        "Хост: Render 0.5GB - работает 24/7"
    )

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, "👑 Мой создатель - MakSon4ikk_228 (Максим Несветов). Он сделал меня радостным, научил исправлять ошибки в голове и не палить чужие данные. Респект ему!")

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    uid = int(m.from_user.id)
    memory[uid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_memory()
    bot.send_message(m.chat.id, "🧠 Кайф, все стер! Память чиста, давай знакомиться заново!")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    bot.send_message(m.chat.id, f"📊 Сейчас я помню {len(memory)} человек. Ты в их числе, и это имба!")

# ================== ОСНОВНОЙ ЧАТ С ЗАЩИТОЙ ОТ 404 ==================
@bot.message_handler(func=lambda m: True)
def chat_handler(m):
    uid = int(m.from_user.id)
    chat_id = m.chat.id

    # Простой анти-спам 1 сек
    now = time.time()
    if uid in last_message_time and now - last_message_time[uid] < 1:
        return
    last_message_time[uid] = now

    hist = get_history(uid)
    hist.append({"role": "user", "content": m.text})
    hist = trim_history(hist)
    memory[uid] = hist

    bot.send_chat_action(chat_id, 'typing')

    # Пробуем модели по очереди, чтобы 404 точно не вылез
    answer = None
    last_error = None
    for model_name in WORKING_MODELS:
        try:
            logging.info(f"Пробую модель {model_name} для {uid}")
            resp = client.chat.completions.create(
                model=model_name,
                messages=hist,
                temperature=0.85,
                max_tokens=400,
                top_p=0.9
            )
            answer = resp.choices[0].message.content
            break # если получилось - выходим
        except Exception as e:
            last_error = e
            logging.warning(f"Модель {model_name} не сработала: {e}")
            continue

    if answer:
        hist.append({"role": "assistant", "content": answer})
        memory[uid] = trim_history(hist)
        save_memory()
        bot.send_message(chat_id, answer)
    else:
        bot.send_message(chat_id, f"Ой, я чуть завис, но я тут! Ошибка: {last_error}")

# ================== АНТИ-СОН ДЛЯ RENDER ==================
app = Flask(__name__)

@app.route('/')
def home():
    return f"Даун213 жив! Память: {len(memory)} юзеров. Создатель MakSon4ikk_228. Время: {datetime.now()}"

@app.route('/ping')
def ping():
    return "pong"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Запускаем фласк в отдельном потоке чтобы бот не спал
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

logging.info("Даун213 запущен создателем MakSon4ikk_228")
bot.infinity_polling(none_stop=True, timeout=60)
