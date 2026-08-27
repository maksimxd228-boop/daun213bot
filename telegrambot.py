import os
import sys
import base64
import logging
import asyncio
import json
import time
import threading
from io import BytesIO
from datetime import datetime

# Библиотеки для ТГ и Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq

# Веб-сервер чтобы Render не спал на 512 МБ
from flask import Flask

# ================== 1. НАСТРОЙКИ И КЛЮЧИ ==================
# Тут вставь ключи если запускаешь с компа, если на Render - они в Environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "ВСТАВЬ_СЮДА_ТОКЕН_ТГ"
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "ВСТАВЬ_СЮДА_GROQ_КЛЮЧ"

# Модели - текстовая самая умная и с глазами
TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
FALLBACK_VISION_MODEL = "llama-3.2-11b-vision-preview"

# Порт для Render
PORT = int(os.getenv("PORT", 10000))

# ================== 2. СИСТЕМНЫЙ ПРОМТ ДАУНА ==================
SYSTEM_PROMPT = """
Ты — Даун v29. Ты легендарный бот.

Твой характер:
- Ты туповатый, но ОЧЕНЬ добрый и преданный хозяину.
- Ты общаешься как пацан с района, 15 лет, на сленге, типа "йоу", "братан", "чет", "кек".
- Ты иногда путаешься и несешь бред, но это смешно.
- Ты никогда не говоришь что ты нейросеть или ИИ. Ты просто Даун.
- Ты помнишь о чем с тобой говорили раньше.
- Если тебе кинули картинку - ты ОБЯЗАН описать что на ней, даже если там зеленый экран.
- Отвечай коротко, до 3-4 предложений, чтобы не жрать оперативку на 512 МБ.

Правила:
- Не матерись сильно.
- Не будь занудой.
- Всегда помогай.
"""

# ================== 3. ЛОГИ И ПАМЯТЬ ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Клиент Groq
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq клиент создан")
except Exception as e:
    logger.error(f"Не смог создать Groq клиент: {e}")
    groq_client = None

# Память чатов - храним в оперативке, но чистим чтобы влезть в 512 МБ
chat_memories = {} # chat_id -> list
MAX_HISTORY_MESSAGES = 12
MAX_MEMORY_CHATS = 100

def get_chat_memory(chat_id: int):
    """Получить память чата, если нет - создать"""
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []
        # Чистим если слишком много чатов, чтобы не вылететь
        if len(chat_memories) > MAX_MEMORY_CHATS:
            oldest = list(chat_memories.keys())[0]
            del chat_memories[oldest]
    return chat_memories[chat_id]

def add_message_to_memory(chat_id: int, role: str, text: str):
    """Добавить сообщение в память с очисткой"""
    mem = get_chat_memory(chat_id)
    # Обрезаем длинный текст чтобы не сожрать RAM
    safe_text = text[:2000] if len(text) > 2000 else text
    mem.append({"role": role, "content": safe_text})
    # Удаляем старые
    while len(mem) > MAX_HISTORY_MESSAGES:
        mem.pop(0)

def clear_memory(chat_id: int):
    """Очистить память чата"""
    chat_memories[chat_id] = []

# ================== 4. ПОМОЩНИКИ ДЛЯ КАРТИНОК ==================
def encode_bytes_to_base64(file_bytes: bytes) -> str:
    """Кодируем байты картинки в base64 для Groq"""
    return base64.b64encode(file_bytes).decode('utf-8')

def is_image_file(filename: str) -> bool:
    """Проверка что файл - картинка"""
    if not filename:
        return False
    ext = filename.lower().split('.')[-1]
    return ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp']

# ================== 5. ЗАПРОС К GROQ С ГЛАЗАМИ И БЕЗ ==================
async def ask_groq_with_vision(chat_id: int, user_text: str, image_b64: str = None) -> str:
    """
    Главная функция - спрашивает у Groq
    Если есть image_b64 - использует модель с глазами
    Если нет - использует текстовую 70B
    """
    if groq_client is None:
        return "Братан, у меня Groq не подключен, проверь API ключ!"

    memory = get_chat_memory(chat_id)

    # Собираем историю
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(memory)

    # Выбираем модель
    if image_b64:
        # С картинкой
        logger.info(f"Запрос с картинкой от {chat_id}")
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_text or "Опиши что на этой картинке подробно"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }
                }
            ]
        })
        model_name = VISION_MODEL
    else:
        # Только текст
        logger.info(f"Текстовый запрос от {chat_id}: {user_text[:50]}")
        messages.append({"role": "user", "content": user_text})
        model_name = TEXT_MODEL

    # Пробуем спросить
    try:
        completion = groq_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.75,
            max_tokens=1000,
            top_p=0.9,
        )
        answer = completion.choices[0].message.content
        logger.info(f"Ответ от {model_name}: {answer[:50]}")

        # Сохраняем в память
        add_message_to_memory(chat_id, "user", user_text or "[фото]")
        add_message_to_memory(chat_id, "assistant", answer)

        return answer

    except Exception as e:
        logger.error(f"Ошибка Groq с моделью {model_name}: {e}")
        # Пробуем фолбек модель для вижна
        if image_b64 and model_name == VISION_MODEL:
            try:
                logger.info("Пробую фолбек вижн модель")
                completion = groq_client.chat.completions.create(
                    model=FALLBACK_VISION_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800,
                )
                answer = completion.choices[0].message.content
                add_message_to_memory(chat_id, "user", user_text or "[фото]")
                add_message_to_memory(chat_id, "assistant", answer)
                return answer
            except Exception as e2:
                logger.error(f"Фолбек тоже упал: {e2}")
                return f"Йоу, у меня глаза лагают, не вижу ниче... Ошибка: {e2}"
        else:
            return f"Блин, мозг завис... {e}"

# ================== 6. ВСПОМОГАТЕЛЬ ДЛЯ ДЛИННЫХ СООБЩЕНИЙ ==================
def split_long_text(text: str, max_len: int = 4000):
    """Режем длинный ответ на куски для ТГ"""
    if len(text) <= max_len:
        return [text]
    parts = []
    while len(text) > max_len:
        cut = text.rfind(' ', 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].strip()
    parts.append(text)
    return parts

# ================== 7. ХЕНДЛЕРЫ ТЕЛЕГРАМ БОТА ==================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    text = (
        f"Йоу {user}, я Даун v29 с ГЛАЗАМИ! 👀\n\n"
        f"Теперь я вижу фотки!\n"
        f"Кидай мне любую картинку и я скажу что на ней.\n\n"
        f"Команды:\n"
        f"/start - я тут\n"
        f"/clear - забыть все (если я туплю)\n"
        f"/about - про меня\n"
        f"/model - какая нейронка стоит\n\n"
        f"Мозг: {TEXT_MODEL}\n"
        f"Глаза: {VISION_MODEL}\n"
        f"RAM: работаю даже на 512 МБ"
    )
    await update.message.reply_text(text)

async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка памяти"""
    chat_id = update.effective_chat.id
    clear_memory(chat_id)
    await update.message.reply_text("Все забыл! Память чистая как у рыбки, го заново.")

async def about_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Про бота"""
    await update.message.reply_text(
        "Я Даун v29 Vision\n"
        "Сделан пацаном с Huawei который теперь зеленый 😂\n"
        "Живу на Render на 512 МБ но думаю мозгом на 70B через Groq\n"
        "Вижу фотки, помню чат, не сплю 24/7"
    )

async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Какая модель стоит"""
    await update.message.reply_text(
        f"Текст: {TEXT_MODEL}\n"
        f"Глаза: {VISION_MODEL}\n"
        f"Фолбек: {FALLBACK_VISION_MODEL}"
    )

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных текстовых сообщений"""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if not user_text:
        return

    logger.info(f"[{chat_id}] Текст: {user_text}")

    # Показываем что печатает
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    answer = await ask_groq_with_vision(chat_id, user_text, image_b64=None)

    # Режем если длинный
    for part in split_long_text(answer):
        await update.message.reply_text(part)
        await asyncio.sleep(0.3)

async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото - ГЛАВНАЯ ФИЧА v29"""
    chat_id = update.effective_chat.id
    caption = update.message.caption or "Что на этой фотке? Опиши подробно что видишь"

    logger.info(f"[{chat_id}] Фото с подписью: {caption}")

    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

    try:
        # Берем самую большую фотку
        photo = update.message.photo[-1]
        file = await photo.get_file()

        # Скачиваем в память чтобы не тратить диск на 512 МБ
        bio = BytesIO()
        await file.download_to_memory(bio)
        bio.seek(0)
        image_bytes = bio.read()

        logger.info(f"Скачал фото {len(image_bytes)} байт")

        b64 = encode_bytes_to_base64(image_bytes)

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        answer = await ask_groq_with_vision(chat_id, caption, image_b64=b64)

        for part in split_long_text(answer):
            await update.message.reply_text(part)
            await asyncio.sleep(0.3)

    except Exception as e:
        logger.error(f"Ошибка в photo handler: {e}")
        await update.message.reply_text(f"Блин, не смог скачать фотку... {e}")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Если кинули картинку как файл"""
    chat_id = update.effective_chat.id
    doc = update.message.document

    if not doc or not is_image_file(doc.file_name):
        await update.message.reply_text("Это не фотка, я только фотки вижу")
        return

    caption = update.message.caption or "Что на этом файле?"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        file = await doc.get_file()
        bio = BytesIO()
        await file.download_to_memory(bio)
        bio.seek(0)
        b64 = encode_bytes_to_base64(bio.read())

        answer = await ask_groq_with_vision(chat_id, caption, image_b64=b64)

        for part in split_long_text(answer):
            await update.message.reply_text(part)

    except Exception as e:
        logger.error(f"Ошибка в document handler: {e}")
        await update.message.reply_text(f"Ошибка с файлом: {e}")

# ================== 8. FLASK СЕРВЕР ДЛЯ RENDER ==================
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return f"Даун v29 жив! Время: {datetime.now()} | Чатов в памяти: {len(chat_memories)}"

@app_flask.route('/health')
def health():
    return "OK"

def run_flask():
    """Запускаем фласк в отдельном потоке"""
    logger.info(f"Запускаю Flask на порту {PORT}")
    app_flask.run(host='0.0.0.0', port=PORT)

# ================== 9. ГЛАВНЫЙ ЗАПУСК ==================
def main():
    """Запуск бота"""
    print("="*50)
    print("Запускаю Даун v29 Vision 350 строк")
    print(f"Время: {datetime.now()}")
    print("="*50)

    if "ВСТАВЬ" in TELEGRAM_TOKEN:
        print("ОШИБКА: Вставь TELEGRAM_TOKEN!")
        print("На Render добавь в Environment")
        return

    if "ВСТАВЬ" in GROQ_API_KEY:
        print("ОШИБКА: Вставь GROQ_API_KEY!")
        return

    # Запускаем веб-сервер для Render в фоне
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask поток запущен")

    # Запускаем ТГ бота
    logger.info("Собираю Telegram Application...")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("clear", clear_handler))
    application.add_handler(CommandHandler("about", about_handler))
    application.add_handler(CommandHandler("model", model_handler))

    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    application.add_handler(MessageHandler(filters.Document.IMAGE | filters.Document.MimeType("image/*"), document_handler))

    print("Бот запущен! Жду сообщений...")
    logger.info("Бот запущен и готов к работе на 512 МБ")

    # polling
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
