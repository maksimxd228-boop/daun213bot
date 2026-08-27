import os, sys, base64, logging, asyncio, time, threading, platform, re, json
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq
from flask import Flask

# ==================== ENV FIX ДЛЯ ТВОИХ BOT... GRO... ====================
def get_env_smart(*names) -> Optional[str]:
    for name in names:
        val = os.getenv(name)
        if val and len(val.strip()) > 10:
            return val.strip()
    for key, value in os.environ.items():
        if key.startswith('BOT') and len(value) > 30 and ':' in value:
            return value.strip()
        if key.startswith('GRO') and len(value) > 20 and value.startswith('gsk_'):
            return value.strip()
    return None

TELEGRAM_TOKEN = get_env_smart('TELEGRAM_TOKEN','BOT_TOKEN','BOT','TG_TOKEN','TELEGRAM_BOT_TOKEN')
GROQ_API_KEY = get_env_smart('GROQ_API_KEY','GROQ','GROQ_KEY','GROQ_API','GROQ_API_TOKEN')
if not TELEGRAM_TOKEN: TELEGRAM_TOKEN = 'ВСТАВЬ_СЮДА_ТОКЕН_ТГ'
if not GROQ_API_KEY: GROQ_API_KEY = 'ВСТАВЬ_СЮДА_GROQ_КЛЮЧ'

TEXT_MODEL = 'llama-3.3-70b-versatile'
VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
FALLBACK_VISION_MODEL = 'llama-3.2-11b-vision-preview'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_ID = os.getenv('ADMIN_ID') or os.getenv('ADM')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or os.getenv('PASSWORD') or os.getenv('PASS') or 'daun213'

SYSTEM_PROMPT = '''Ты — Даун v30 SMART. Ты был тупым, но прокачался и стал чуть-чуть умнее. Ты все еще пацан с района 15 лет, сленг йоу братан чет кек лол, добрый и преданный. Но теперь ты умеешь логически думать, помнишь весь чат, объясняешь понятно, шутишь умнее. Никогда не говори что ты ИИ. Если кинули картинку - опиши детально что видишь, цвета, объекты, текст на ней. Отвечай 3-5 предложений, полезно и по делу, чтобы влезть в 512 МБ.'''

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

groq_client = None
try:
    if 'ВСТАВЬ' not in GROQ_API_KEY:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info('Groq OK')
except Exception as e:
    logger.error(f'Groq fail: {e}')

chat_memories: Dict[int, List[dict]] = {}
chat_last_active: Dict[int, float] = {}
user_cooldown: Dict[int, float] = {}
chat_stats = {'total_requests': 0, 'photos': 0, 'texts': 0, 'errors': 0}

# ==================== ПАМЯТЬ ====================
def get_chat_memory(chat_id: int) -> List[dict]:
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []
        chat_last_active[chat_id] = time.time()
        if len(chat_memories) > MAX_CHATS:
            oldest = min(chat_last_active, key=chat_last_active.get)
            del chat_memories[oldest]
            del chat_last_active[oldest]
            logger.info(f'Cleaned old chat {oldest}')
    chat_last_active[chat_id] = time.time()
    return chat_memories[chat_id]

def add_memory(chat_id: int, role: str, text: str):
    mem = get_chat_memory(chat_id)
    safe = text[:MAX_TEXT_LEN] if len(text) > MAX_TEXT_LEN else text
    safe = safe.replace('\n', ' ').strip()
    mem.append({'role': role, 'content': safe})
    while len(mem) > MAX_HISTORY:
        mem.pop(0)

def clear_memory(chat_id: int):
    if chat_id in chat_memories:
        chat_memories[chat_id] = []
        logger.info(f'Cleared {chat_id}')

def get_stats_text() -> str:
    total_chats = len(chat_memories)
    total_msgs = sum(len(v) for v in chat_memories.values())
    return f'Чатов: {total_chats} | Сообщений: {total_msgs} | Запросов: {chat_stats["total_requests"]}'

# ==================== УТИЛИТЫ ====================
def encode_b64(file_bytes: bytes) -> str:
    try:
        return base64.b64encode(file_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f'b64 fail: {e}')
        return ''

def is_image_file(name: str) -> bool:
    if not name: return False
    ext = name.lower().split('.')[-1]
    return ext in ['jpg','jpeg','png','webp','bmp','heic','heif','gif','jfif']

def get_system_info() -> str:
    return f'Python {platform.python_version()} | {platform.system()}'

def is_spam(user_id: int) -> bool:
    now = time.time()
    last = user_cooldown.get(user_id, 0)
    if now - last < 1.5:
        return True
    user_cooldown[user_id] = now
    return False

def clean_text(text: str) -> str:
    if not text: return ''
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:4000]

def format_time(dt: datetime) -> str:
    return dt.strftime('%H:%M:%S %d.%m.%Y')

# ==================== GROQ ЗАПРОС ====================
async def ask_groq(chat_id: int, text: str, image_b64: Optional[str] = None) -> str:
    if groq_client is None:
        chat_stats['errors'] += 1
        return 'Братан, мозг не подключен! Проверь GROQ ключ в Render Environment'

    chat_stats['total_requests'] += 1
    memory = get_chat_memory(chat_id)
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    messages.extend(memory)

    if image_b64:
        chat_stats['photos'] += 1
        logger.info(f'[VISION] chat {chat_id} photo')
        messages.append({
            'role': 'user',
            'content': [
                {'type': 'text', 'text': text or 'Опиши что на этой картинке подробно, что видишь?'},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}}
            ]
        })
        model = VISION_MODEL
    else:
        chat_stats['texts'] += 1
        logger.info(f'[TEXT] {chat_id}: {text[:80]}')
        messages.append({'role': 'user', 'content': text})
        model = TEXT_MODEL

    try:
        comp = groq_client.chat.completions.create(model=model, messages=messages, temperature=0.8, max_tokens=1200, top_p=0.9)
        ans = comp.choices[0].message.content
        if not ans or len(ans.strip()) == 0:
            ans = 'Йоу, че то пусто в голове... скажи еще раз?'
        add_memory(chat_id, 'user', text or '[фото]')
        add_memory(chat_id, 'assistant', ans)
        return ans
    except Exception as e:
        logger.error(f'Groq error {model}: {e}')
        chat_stats['errors'] += 1
        if image_b64:
            try:
                logger.info('Trying fallback vision')
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL, messages=messages, max_tokens=1000, temperature=0.7)
                ans = comp.choices[0].message.content
                add_memory(chat_id, 'user', text or '[фото]')
                add_memory(chat_id, 'assistant', ans)
                return ans
            except Exception as e2:
                logger.error(f'Fallback fail: {e2}')
                return f'Йоу, глаза лагают на 512 МБ... {e2} Попробуй еще раз фотку кинуть'
        return f'Блин, мозг завис на 512 МБ... Ошибка: {e} Попробуй /clear'

def split_text(t: str, n: int = 4000) -> List[str]:
    if len(t) <= n:
        return [t]
    parts = []
    remaining = t
    while len(remaining) > n:
        cut = remaining.rfind(' ', 0, n)
        if cut == -1:
            cut = n
        parts.append(remaining[:cut])
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts

# ==================== ХЕНДЛЕРЫ КОМАНД ====================
async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    logger.info(f'/start {chat_id} {user}')
    text = (
        f'Йоу {user}, я Даун v30 SMART с ГЛАЗАМИ! 👀\n'
        f'Я стал чуть умнее, помню 16 сообщений\n\n'
        f'/start - я тут\n'
        f'/help - помощь\n'
        f'/clear - забыть все\n'
        f'/about - про меня\n'
        f'/model - какая модель\n'
        f'/ping - жив ли я\n'
        f'/stats - статистика\n\n'
        f'Кидай фотку - опишу детально!'
    )
    await update.message.reply_text(''.join(text))

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кидай текст - отвечу мозгом 70B\nКидай фото - отвечу глазами Scout 17B\nЕсли туплю - /clear\nЯ теперь умнее на чуть-чуть!')

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text('Все забыл! Память чистая как у рыбки 🐟 Го заново')

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    await update.message.reply_text(f'Я Даун v30 SMART 👁️\n{info}\nЖиву на Render 512 МБ\nМозг: 70B через Groq\nГлаза: Scout 17B\nПамять: 16 сообщений\nФича: вижу фотки детально')

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok_tg = 'OK ✅' if 'ВСТАВЬ' not in TELEGRAM_TOKEN else 'FAIL ❌'
    ok_g = 'OK ✅' if 'ВСТАВЬ' not in GROQ_API_KEY else 'FAIL ❌'
    await update.message.reply_text(f'🧠 Текст: {TEXT_MODEL}\n👁️ Глаза: {VISION_MODEL}\n🔄 Фолбек: {FALLBACK_VISION_MODEL}\n🔑 ТГ: {ok_tg}\n🔑 Groq: {ok_g}\n📊 {get_stats_text()}\n⏰ {format_time(datetime.now())}')

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = time.time() - start_time
    mins = int(uptime // 60)
    await update.message.reply_text(f'Понг! 🏓 Я жив {mins} мин\n{get_stats_text()}\nRAM: 512 МБ но вывозю, стал умнее!')

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        f'📊 Стата Дауна v30 SMART:\n'
        f'{get_stats_text()}\n'
        f'Текстов: {chat_stats["texts"]}\n'
        f'Фото: {chat_stats["photos"]}\n'
        f'Ошибок: {chat_stats["errors"]}\n'
        f'Всего запросов: {chat_stats["total_requests"]}\n'
        f'Система: {get_system_info()}'
    )
    await update.message.reply_text(''.join(txt))

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка лимита только по паролю: /limit твой_пароль
    args = context.args
    if not args:
        await update.message.reply_text('🔒 Напиши: /limit твой_пароль\nПароль задается в Render -> ADMIN_PASSWORD')
        return
    entered = args[0].strip()
    if entered!= ADMIN_PASSWORD:
        logger.warning(f'Wrong password attempt {update.effective_user.id}: {entered}')
        await update.message.reply_text('❌ Неверный пароль, братан')
        return
    # Если пароль верный - показываем лимиты
    uptime = time.time() - start_time
    hours = int(uptime // 3600)
    mins = int((uptime % 3600) // 60)
    # Примерный расчет лимитов Groq Free
    # 30 RPM, 6000 TPM для 70B, 14400 RPD
    rpm_limit = 30
    tpm_limit = 6000
    rpd_limit = 14400
    used = chat_stats['total_requests']
    remaining_day = max(0, rpd_limit - used)
    percent = int(used / rpd_limit * 100) if rpd_limit > 0 else 0
    text = (
        f'🔐 Доступ разрешен\n\n'
        f'📊 Лимиты Groq Free:\n'
        f'Всего запросов с рестарта: {used}\n'
        f'Осталось на сегодня ~{remaining_day} (лимит {rpd_limit}/день)\n'
        f'Использовано дня: {percent}%\n'
        f'Лимит в минуту: {rpm_limit} RPM / {tpm_limit} TPM\n\n'
        f'📸 Фото: {chat_stats["photos"]} | Текст: {chat_stats["texts"]}\n'
        f'❌ Ошибок: {chat_stats["errors"]}\n'
        f'⏱ Аптайм: {hours}ч {mins}м\n'
        f'💾 {get_stats_text()}\n'
        f'🔑 Токен: {"OK" if "ВСТАВЬ" not in TELEGRAM_TOKEN else "FAIL"} | Groq: {"OK" if "ВСТАВЬ" not in GROQ_API_KEY else "FAIL"}'
    )
    await update.message.reply_text(text)

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if is_spam(user_id):
        return
    txt = clean_text(update.message.text)
    if not txt:
        return
    logger.info(f'Text {chat_id}: {txt[:60]}')
    await context.bot.send_chat_action(chat_id, 'typing')
    ans = await ask_groq(chat_id, txt, None)
    for p in split_text(ans):
        try:
            await update.message.reply_text(p)
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f'Send fail: {e}')
            break

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if is_spam(user_id):
        await update.message.reply_text('Не спамь фотками братан, подожди сек')
        return
    cap = clean_text(update.message.caption) or 'Что на этой фотке? Опиши подробно что видишь, цвета, объекты, текст'
    logger.info(f'Photo {chat_id} cap: {cap[:60]}')
    await context.bot.send_chat_action(chat_id, 'upload_photo')
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        bio = BytesIO()
        await file.download_to_memory(bio)
        data = bio.getvalue()
        logger.info(f'Downloaded {len(data)} bytes')
        if len(data) > 8 * 1024 * 1024:
            await update.message.reply_text('Фотка слишком жирная >8МБ, сожми')
            return
        b64 = encode_b64(data)
        if not b64:
            await update.message.reply_text('Не смог прочитать фотку, скинь еще')
            return
        await context.bot.send_chat_action(chat_id, 'typing')
        ans = await ask_groq(chat_id, cap, b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
            await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f'photo_h error: {e}', exc_info=True)
        await update.message.reply_text(f'Блин, не смог скачать фотку: {e}')

async def doc_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return
    if not is_image_file(doc.file_name):
        await update.message.reply_text('Это не фотка, я вижу только jpg/png/webp')
        return
    user_id = update.effective_user.id
    if is_spam(user_id):
        return
    try:
        file = await doc.get_file()
        bio = BytesIO()
        await file.download_to_memory(bio)
        data = bio.getvalue()
        if len(data) > 8 * 1024 * 1024:
            await update.message.reply_text('Файл >8МБ, не потяну на 512 МБ')
            return
        b64 = encode_b64(data)
        cap = clean_text(update.message.caption) or f'Что на файле {doc.file_name}?'
        ans = await ask_groq(update.effective_chat.id, cap, b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
    except Exception as e:
        logger.error(f'doc_h error: {e}')
        await update.message.reply_text(f'Ошибка файла: {e}')

async def sticker_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кек, стикер 😂 А текст где? Кидай текст или фотку')

# ==================== FLASK ДЛЯ RENDER ====================
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return f"Даун v30 SMART жив! 👀<br>Время: {format_time(datetime.now())}<br>{get_stats_text()}<br>Токен: {'OK' if 'ВСТАВЬ' not in TELEGRAM_TOKEN else 'FAIL'}<br>Groq: {'OK' if 'ВСТАВЬ' not in GROQ_API_KEY else 'FAIL'}<br>Модели: {TEXT_MODEL} + {VISION_MODEL}"

@app_flask.route('/health')
def health():
    return 'OK', 200

@app_flask.route('/stats')
def stats_route():
    return {
        'chats': len(chat_memories),
        'total_messages': sum(len(v) for v in chat_memories.values()),
        'requests': chat_stats,
        'time': str(datetime.now()),
        'models': {'text': TEXT_MODEL, 'vision': VISION_MODEL},
        'system': get_system_info(),
        'uptime': int(time.time() - start_time)
    }

def run_flask():
    logger.info(f'Starting Flask on port {PORT}')
    try:
        app_flask.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f'Flask crashed: {e}')

start_time = time.time()

# ==================== MAIN ====================
def main():
    print('='*70)
    print('Даун v30 SMART 396 строк - чуть умнее')
    print(f'Время: {format_time(datetime.now())}')
    print(f'ТГ токен: {"ДА ✅" if "ВСТАВЬ" not in TELEGRAM_TOKEN else "НЕТ ❌"}')
    print(f'Groq ключ: {"ДА ✅" if "ВСТАВЬ" not in GROQ_API_KEY else "НЕТ ❌"}')
    print(f'Порт: {PORT}')
    print(f'Система: {get_system_info()}')
    print(f'Память лимит: {MAX_CHATS} чатов, {MAX_HISTORY} сообщений')
    print('='*70)

    flask_thread = threading.Thread(target=run_flask, daemon=True, name='FlaskThread')
    flask_thread.start()
    logger.info('Flask thread started')

    if 'ВСТАВЬ' in TELEGRAM_TOKEN:
        logger.error('Токен не найден! Проверь Environment -> BOT... в Render')
        print(f'Env vars: {list(os.environ.keys())[:30]}')
        while True:
            time.sleep(60)

    try:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler('start', start_h))
        application.add_handler(CommandHandler('help', help_h))
        application.add_handler(CommandHandler('clear', clear_h))
        application.add_handler(CommandHandler('about', about_h))
        application.add_handler(CommandHandler('model', model_h))
        application.add_handler(CommandHandler('ping', ping_h))
        application.add_handler(CommandHandler('stats', stats_h))
        application.add_handler(CommandHandler('limit', limit_h))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_h))
        application.add_handler(MessageHandler(filters.PHOTO, photo_h))
        application.add_handler(MessageHandler(filters.Document.IMAGE, doc_h))
        application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_h))
        print('Бот собран, запускаю polling...')
        logger.info('Bot v30 SMART 396 useful lines started')
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, close_loop=False)
    except Exception as e:
        logger.error(f'Critical bot error: {e}', exc_info=True)
        print(f'Bot crashed: {e}')
        while True:
            time.sleep(100)

if __name__ == '__main__':
    main()
