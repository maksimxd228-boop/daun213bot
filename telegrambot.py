import os, sys, base64, logging, time, threading, platform, re
from io import BytesIO
from datetime import datetime
from typing import Optional, List, Dict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq
from flask import Flask

# ==================== ПОИСК ТОКЕНОВ ====================
def get_env_smart(*names: str) -> Optional[str]:
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

TELEGRAM_TOKEN = get_env_smart('TELEGRAM_TOKEN','BOT_TOKEN','BOT','TG_TOKEN')
GROQ_API_KEY = get_env_smart('GROQ_API_KEY','GROQ','GROQ_KEY')
if not TELEGRAM_TOKEN: TELEGRAM_TOKEN = 'ВСТАВЬ_ТОКЕН'
if not GROQ_API_KEY: GROQ_API_KEY = 'ВСТАВЬ_GROQ'

TEXT_MODEL = 'llama-3.3-70b-versatile'
VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
FALLBACK_VISION_MODEL = 'llama-3.2-11b-vision-preview'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'daun213'

SYSTEM_PROMPT = """Ты — Даун v32 FINAL. Пацан с района, йоу братан кек лол, но прокачался и стал умнее. Помнишь чат, думаешь логично. Если фото - опиши детально."""

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

groq_client = None
try:
    if 'ВСТАВЬ' not in GROQ_API_KEY:
        groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    logger.error(f'Groq fail: {e}')

chat_memories: Dict[int, List[dict]] = {}
chat_last_active: Dict[int, float] = {}
user_cooldown: Dict[int, float] = {}
chat_stats = {'total_requests':0,'photos':0,'texts':0,'errors':0,'start_time':time.time()}

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
    mem.append({'role': role, 'content': safe.replace(chr(10),' ').strip()})
    while len(mem) > MAX_HISTORY:
        mem.pop(0)

def clear_memory(chat_id: int):
    if chat_id in chat_memories:
        chat_memories[chat_id] = []

def get_stats_text() -> str:
    total = len(chat_memories)
    msgs = sum(len(v) for v in chat_memories.values())
    return f'Чатов: {total} | Сообщений: {msgs} | Запросов: {chat_stats["total_requests"]}'

def encode_b64(b: bytes) -> str:
    try: return base64.b64encode(b).decode('utf-8')
    except: return ''

def is_image_file(name: str) -> bool:
    if not name: return False
    return name.lower().split('.')[-1] in ['jpg','jpeg','png','webp','bmp','heic','gif']

def get_system_info() -> str:
    return f'Python {platform.python_version()} | {platform.system()}'

def is_spam(uid: int) -> bool:
    now = time.time()
    if now - user_cooldown.get(uid,0) < 1.5: return True
    user_cooldown[uid]=now
    return False

def clean_text(t: str) -> str:
    if not t: return ''
    return re.sub(r'\s+',' ',t.strip())[:4000]

def format_time(dt: datetime) -> str:
    return dt.strftime('%H:%M:%S %d.%m.%Y')

async def ask_groq(chat_id: int, text: str, image_b64: Optional[str]=None) -> str:
    if groq_client is None:
        return 'Мозг не подключен! Проверь GROQ ключ'
    chat_stats['total_requests']+=1
    memory = get_chat_memory(chat_id)
    messages = [{'role':'system','content':SYSTEM_PROMPT}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos']+=1
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото?'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model=VISION_MODEL
    else:
        chat_stats['texts']+=1
        messages.append({'role':'user','content':text})
        model=TEXT_MODEL
    try:
        comp = groq_client.chat.completions.create(model=model,messages=messages,temperature=0.8,max_tokens=1200)
        ans = comp.choices[0].message.content
        add_memory(chat_id,'user',text or '[фото]')
        add_memory(chat_id,'assistant',ans)
        return ans
    except Exception as e:
        chat_stats['errors']+=1
        if image_b64:
            try:
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL,messages=messages,max_tokens=1000)
                ans=comp.choices[0].message.content
                add_memory(chat_id,'user',text or '[фото]')
                add_memory(chat_id,'assistant',ans)
                return ans
            except Exception as e2:
                return f'Глаза лагают: {e2}'
        return f'Мозг завис: {e}'

def split_text(t: str, n: int=4000) -> List[str]:
    if len(t)<=n: return [t]
    parts=[]
    while len(t)>n:
        cut=t.rfind(' ',0,n)
        if cut==-1: cut=n
        parts.append(t[:cut])
        t=t[cut:].strip()
    parts.append(t)
    return parts

# ==================== КРАСИВЫЙ СТАРТ И ABOUT ====================

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    logger.info(f'/start {chat_id} {user}')
    text = f"""
╭━━━〔 🤖 ДАУН v32 FINAL 〕━━━╮

  Йоу, {user}! 👋
  Я твой кореш Даун, но теперь
  я BEAUTIFUL и SMART! ✨

┣━━━〔 🧠 ЧТО УМЕЮ 〕━━━┫

  💬 Болтаю мозгом 70B
  👁️ Вижу фотки Scout 17B
  💾 Помню {MAX_HISTORY} сообщений
  ⚡ Живу на 512 МБ и выживаю
  🔒 Лимиты по паролю

┣━━━〔 📜 КОМАНДЫ 〕━━━┫

  /start - это меню 🔥
  /help - как юзать ❓
  /clear - забыть все 🗑️
  /about - про меня красивый ✨
  /model - какие модели 🛠️
  /ping - жив ли я 🏓
  /stats - стата 📊
  /limit пароль - лимиты 🔐

╰━━━〔 📸 КИДАЙ ФОТКУ 〕━━━╯

  Скинь фото и я опишу че там! 👇
"""
    await update.message.reply_text(text)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
╭━━━〔 ❓ ПОМОЩЬ 〕━━━╮

  Как юзать Дауна:

  1️⃣ Просто пиши текст
     → отвечу умно 70B

  2️⃣ Кидай фото / файл
     → опишу что вижу Scout

  3️⃣ Если туплю
     → жми /clear

  4️⃣ Хочешь лимиты
     → /limit daun213

╰━━━〔 Йоу, все просто! 〕━━━╯
"""
    await update.message.reply_text(text)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text(
        "╭━━━〔 🗑️ ОЧИСТКА 〕━━━╮\n\n"
        " Память стерта! 🧹\n"
        " Чистый как у рыбки 🐟\n\n"
        "╰━━━〔 Го заново! 〕━━━╯"
    )

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    text = f"""
╭━━━〔 ✨ О БОТЕ 〕━━━╮

  🤖 Имя: Даун v32 FINAL
  🎨 Версия: BEAUTIFUL SMART

┣━━━〔 💻 СИСТЕМА 〕━━━┫

  {info}
  ☁️ Хост: Render 512 МБ
  ⏱ Аптайм: {uptime} мин
  📦 Чатов: {len(chat_memories)}

┣━━━〔 🧠 МОЗГИ 〕━━━┫

  📝 Текст: llama-3.3-70B
     → самый умный на Groq
  👁️ Глаза: Scout 17B-16E
     → вижу фото детально
  🔄 Фолбек: 11B-Vision
     → если упадут глаза

┣━━━〔 💾 ПАМЯТЬ 〕━━━┫

  📚 {MAX_HISTORY} сообщений на чат
  👥 До {MAX_CHATS} чатов
  🗜️ Авточистка старых

┣━━━〔 👑 СОЗДАТЕЛЬ 〕━━━┫

  Сделал с ❤️ для пацанов
  Живет и кайфует на 512 МБ

╰━━━〔 🚀 ЛЕТИМ ДАЛЬШЕ 〕━━━╯
"""
    await update.message.reply_text(text)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok_tg = 'OK ✅' if 'ВСТАВЬ' not in TELEGRAM_TOKEN else 'FAIL ❌'
    ok_g = 'OK ✅' if 'ВСТАВЬ' not in GROQ_API_KEY else 'FAIL ❌'
    await update.message.reply_text(
        f"╭━━━〔 🛠️ МОДЕЛИ 〕━━━╮\n\n"
        f" 🧠 Текст: {TEXT_MODEL}\n"
        f" 👁️ Глаза: {VISION_MODEL}\n"
        f" 🔄 Фолбек: {FALLBACK_VISION_MODEL}\n\n"
        f" 🔑 ТГ: {ok_tg}\n"
        f" 🔑 Groq: {ok_g}\n\n"
        f" 📊 {get_stats_text()}\n"
        f" ⏰ {format_time(datetime.now())}\n\n"
        f"╰━━━━━━━━━━━━━━━╯"
    )

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    await update.message.reply_text(
        f"╭━━━〔 🏓 ПОНГ 〕━━━╮\n\n"
        f" Я жив {mins} мин! 🔥\n"
        f" {get_stats_text()}\n"
        f" 512 МБ но вывозю! 💪\n\n"
        f"╰━━━━━━━━━━━━━━╯"
    )

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"╭━━━〔 📊 СТАТА 〕━━━╮\n\n"
        f" {get_stats_text()}\n"
        f" 💬 Текстов: {chat_stats['texts']}\n"
        f" 📸 Фото: {chat_stats['photos']}\n"
        f" ❌ Ошибок: {chat_stats['errors']}\n\n"
        f"╰━━━━━━━━━━━━━━╯"
    )

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args
    if not args:
        await update.message.reply_text(
            "╭━━━〔 🔒 ЛИМИТЫ 〕━━━╮\n\n"
            " Только по паролю!\n\n"
            " Пиши:\n"
            " /limit твой_пароль\n\n"
            " Пароль в Render:\n"
            " ADMIN_PASSWORD\n\n"
            "╰━━━━━━━━━━━━━━╯"
        )
        return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль 🔒')
        return
    used=chat_stats['total_requests']
    remaining=max(0,14400-used)
    percent=int(used/14400*100) if used else 0
    await update.message.reply_text(
        f"╭━━━〔 🔐 ДОСТУП ОК 〕━━━╮\n\n"
        f" 📈 Всего: {used}\n"
        f" 📉 Осталось: ~{remaining}/14400\n"
        f" 📊 День: {percent}%\n\n"
        f" 📸 Фото: {chat_stats['photos']}\n"
        f" 💬 Текст: {chat_stats['texts']}\n"
        f" ❌ Ошибок: {chat_stats['errors']}\n\n"
        f" {get_stats_text()}\n\n"
        f"╰━━━━━━━━━━━━━━╯"
    )

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans=await ask_groq(update.effective_chat.id,txt,None)
    for p in split_text(ans):
        await update.message.reply_text(p)

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id):
        await update.message.reply_text('Не спамь фотками ⏳')
        return
    cap=clean_text(update.message.caption) or 'Что на фото?'
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    try:
        photo=update.message.photo[-1]
        file=await photo.get_file()
        bio=BytesIO()
        await file.download_to_memory(bio)
        b64=encode_b64(bio.getvalue())
        ans=await ask_groq(update.effective_chat.id,cap,b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
    except Exception as e:
        await update.message.reply_text(f'Ошибка фото: {e}')

async def doc_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc=update.message.document
    if not doc or not is_image_file(doc.file_name): return
    try:
        file=await doc.get_file()
        bio=BytesIO()
        await file.download_to_memory(bio)
        b64=encode_b64(bio.getvalue())
        ans=await ask_groq(update.effective_chat.id,doc.file_name,b64)
        for p in split_text(ans):
            await update.message.reply_text(p)
    except Exception as e:
        await update.message.reply_text(f'Ошибка: {e}')

async def sticker_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кек, стикер 😂 Кидай текст или фотку!')

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v32 BEAUTIFUL жив! {format_time(datetime.now())} {get_stats_text()}"
@app_flask.route('/health')
def health():
    return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

start_time=time.time()

def main():
    print('='*70)
    print('Даун v32 FINAL BEAUTIFUL - запуск')
    print(f'ТГ: {"ДА" if "ВСТАВЬ" not in TELEGRAM_TOKEN else "НЕТ"} Groq: {"ДА" if "ВСТАВЬ" not in GROQ_API_KEY else "НЕТ"}')
    print(f'Пароль: {ADMIN_PASSWORD}')
    print('='*70)
    threading.Thread(target=run_flask,daemon=True).start()
    if 'ВСТАВЬ' in TELEGRAM_TOKEN:
        while True: time.sleep(60)
    application=ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start',start_h))
    application.add_handler(CommandHandler('help',help_h))
    application.add_handler(CommandHandler('clear',clear_h))
    application.add_handler(CommandHandler('about',about_h))
    application.add_handler(CommandHandler('model',model_h))
    application.add_handler(CommandHandler('ping',ping_h))
    application.add_handler(CommandHandler('stats',stats_h))
    application.add_handler(CommandHandler('limit',limit_h))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_h))
    application.add_handler(MessageHandler(filters.PHOTO,photo_h))
    application.add_handler(MessageHandler(filters.Document.IMAGE,doc_h))
    application.add_handler(MessageHandler(filters.Sticker.ALL,sticker_h))
    print('Бот запущен! FIXED v32')
    application.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    main()
