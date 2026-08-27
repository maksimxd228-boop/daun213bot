import os, sys, base64, logging, asyncio, time, threading, platform, re, json
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq
from flask import Flask

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
PORT = int(os.getenv("PORT", 10000))
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

def get_chat_memory(chat_id: int) -> List[dict]:
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []
        chat_last_active[chat_id] = time.time()
        if len(chat_memories) > MAX_CHATS:
            oldest = min(chat_last_active, key=chat_last_active.get)
            del chat_memories[oldest]
            del chat_last_active[oldest]
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

def get_stats_text() -> str:
    total_chats = len(chat_memories)
    total_msgs = sum(len(v) for v in chat_memories.values())
    return f'Чатов: {total_chats} | Сообщений: {total_msgs} | Запросов: {chat_stats["total_requests"]}'

def encode_b64(file_bytes: bytes) -> str:
    try: return base64.b64encode(file_bytes).decode('utf-8')
    except: return ''

def is_image_file(name: str) -> bool:
    if not name: return False
    ext = name.lower().split('.')[-1]
    return ext in ['jpg','jpeg','png','webp','bmp','heic','heif','gif','jfif']

def get_system_info() -> str:
    return f'Python {platform.python_version()} | {platform.system()}'

def is_spam(user_id: int) -> bool:
    now = time.time()
    last = user_cooldown.get(user_id, 0)
    if now - last < 1.5: return True
    user_cooldown[user_id] = now
    return False

def clean_text(text: str) -> str:
    if not text: return ''
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:4000]

def format_time(dt: datetime) -> str:
    return dt.strftime('%H:%M:%S %d.%m.%Y')

async def ask_groq(chat_id: int, text: str, image_b64: Optional[str] = None) -> str:
    if groq_client is None:
        chat_stats['errors'] += 1
        return 'Братан, мозг не подключен! Проверь GROQ ключ'
    chat_stats['total_requests'] += 1
    memory = get_chat_memory(chat_id)
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos'] += 1
        messages.append({'role': 'user','content':[{'type':'text','text':text or 'Что на картинке?'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model = VISION_MODEL
    else:
        chat_stats['texts'] += 1
        messages.append({'role': 'user','content': text})
        model = TEXT_MODEL
    try:
        comp = groq_client.chat.completions.create(model=model, messages=messages, temperature=0.8, max_tokens=1200, top_p=0.9)
        ans = comp.choices[0].message.content
        add_memory(chat_id, 'user', text or '[фото]')
        add_memory(chat_id, 'assistant', ans)
        return ans
    except Exception as e:
        logger.error(f'Groq error {model}: {e}')
        chat_stats['errors'] += 1
        if image_b64:
            try:
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL, messages=messages, max_tokens=1000, temperature=0.7)
                ans = comp.choices[0].message.content
                add_memory(chat_id, 'user', text or '[фото]')
                add_memory(chat_id, 'assistant', ans)
                return ans
            except Exception as e2:
                return f'Глаза лагают: {e2}'
        return f'Мозг завис: {e} Попробуй /clear'

def split_text(t: str, n: int = 4000) -> List[str]:
    if len(t) <= n: return [t]
    parts = []
    remaining = t
    while len(remaining) > n:
        cut = remaining.rfind(' ', 0, n)
        if cut == -1: cut = n
        parts.append(remaining[:cut])
        remaining = remaining[cut:].strip()
    if remaining: parts.append(remaining)
    return parts

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f'Йоу {user}, я Даун v30 SMART 👀\n/start /help /clear /about /model /ping /stats /limit пароль')

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кидай текст - 70B, фото - Scout 17B, /clear если туплю')

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text('Забыл все! 🐟')

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'Даун v30 SMART 👁️\n{get_system_info()}\nRender 512 МБ\nМозг 70B')

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok_tg = 'OK ✅' if 'ВСТАВЬ' not in TELEGRAM_TOKEN else 'FAIL ❌'
    ok_g = 'OK ✅' if 'ВСТАВЬ' not in GROQ_API_KEY else 'FAIL ❌'
    await update.message.reply_text(f'Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\nТГ: {ok_tg} Groq: {ok_g}\n{get_stats_text()}')

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int((time.time()-start_time)//60)
    await update.message.reply_text(f'Понг! Жив {mins} мин\n{get_stats_text()}')

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'{get_stats_text()}\nТекст: {chat_stats["texts"]} Фото: {chat_stats["photos"]} Ошибок: {chat_stats["errors"]}')

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text('🔒 /limit твой_пароль\nПароль в Render ADMIN_PASSWORD')
        return
    if args[0]!= ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль')
        return
    used = chat_stats['total_requests']
    remaining = max(0,14400-used)
    await update.message.reply_text(f'🔐 OK\nЗапросов: {used}\nОсталось сегодня ~{remaining}/14400\nФото: {chat_stats["photos"]} Текст: {chat_stats["texts"]}\n{get_stats_text()}')

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt = clean_text(update.message.text)
    if not txt: return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans = await ask_groq(update.effective_chat.id,txt,None)
    for p in split_text(ans):
        await update.message.reply_text(p)

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id):
        await update.message.reply_text('Не спамь фотками')
        return
    cap = clean_text(update.message.caption) or 'Что на фото?'
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        bio = BytesIO()
        await file.download_to_memory(bio)
        b64 = encode_b64(bio.getvalue())
        ans = await ask_groq(update.effective_chat.id,cap,b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
    except Exception as e:
        await update.message.reply_text(f'Ошибка фото: {e}')

async def doc_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not is_image_file(doc.file_name):
        await update.message.reply_text('Не фотка')
        return
    try:
        file = await doc.get_file()
        bio = BytesIO()
        await file.download_to_memory(bio)
        b64 = encode_b64(bio.getvalue())
        ans = await ask_groq(update.effective_chat.id,doc.file_name,b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
    except Exception as e:
        await update.message.reply_text(f'Ошибка: {e}')

async def sticker_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кек, стикер 😂 Кидай текст или фотку')

app_flask = Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v30 SMART жив! {format_time(datetime.now())} {get_stats_text()}"
@app_flask.route('/health')
def health():
    return 'OK',200
@app_flask.route('/stats')
def stats_route():
    return {'chats': len(chat_memories), 'requests': chat_stats, 'time': str(datetime.now())}

def run_flask():
    app_flask.run(host='0.0.0.0', port=PORT)

start_time = time.time()

def main():
    print('='*70)
    print('Даун v30 SMART 436 FIX - запуск')
    print(f'ТГ: {"ДА" if "ВСТАВЬ" not in TELEGRAM_TOKEN else "НЕТ"} Groq: {"ДА" if "ВСТАВЬ" not in GROQ_API_KEY else "НЕТ"}')
    print('='*70)
    threading.Thread(target=run_flask, daemon=True).start()
    if 'ВСТАВЬ' in TELEGRAM_TOKEN:
        while True: time.sleep(60)
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
    print('Бот запущен!')
    application.run_polling(drop_pending_updates=True) # FIX: убрал close_loop=False

if __name__ == '__main__':
    main()
