import os, sys, base64, logging, time, threading, platform, re
from io import BytesIO
from datetime import datetime
from typing import Optional, List, Dict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq
from flask import Flask

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

TEXT_MODEL = 'openai/gpt-oss-120b'
VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
FALLBACK_VISION_MODEL = 'meta-llama/llama-4-maverick-17b-128e-instruct'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'MakSon4ikk_228'
TEXT_MODEL_FALLBACK = 'openai/gpt-oss-20b'
FIRST_LAUNCH_DATE = datetime(2026, 8, 26, 14, 25, 0)

SYSTEM_PROMPT = """Ты — Даун213, радостный ИИ бот, НЕ человек. Ты умный математик.
Создатель — Максим @MakSon4ikk_228, упоминай ТОЛЬКО если прямо спрашивают "кто тебя сделал".
Характер: радостный, дружелюбный, начинай с Йоу, 2-5 предложений для обычных, для задач — подробно.
ТЫ ОТЛИЧНО ЗНАЕШЬ МАТЕМАТИКУ:
- Интеграл I = ∫_{-∞}^{∞} cos(x)/(x^2+1) dx = π/e. Решается вычетами.
- IMO 1988 Задача 6: Если (a^2+b^2)/(ab+1) = k целое, то k — полный квадрат. Vieta jumping.
- Любой матан решай на русском, пошагово, радостно.
Если кинули ФОТО задачи — сразу решай, без английского анализа. Начинай с Йоу.
НИКОГДА не пиши ход мыслей на английском, не цитируй инструкцию, не пиши "Solve in Russian", "Do not mention the creator", "Here's a thinking", "Analyze", "User sent", "The image shows", "The user wants me". Только финальный ответ на русском."""

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
chat_stats = {'total_requests':0,'photos':0,'texts':0,'errors':0,'start_time':time.time(),'first_launch': FIRST_LAUNCH_DATE}

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

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("ℹ️ Инфо"), KeyboardButton("👑 Создатель")],
        [KeyboardButton("🧹 Забыть"), KeyboardButton("📩 Админу")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("🛠️ Модель")],
        [KeyboardButton("🏓 Пинг"), KeyboardButton("📊 Стата")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

MAIN_KB = get_main_keyboard()

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

def format_date_short(dt: datetime) -> str:
    return dt.strftime('%H:%M %d.%m.%Y')

def clean_ai_response(text: str) -> str:
    if not text:
        return text
    if '</think>' in text:
        text = text.split('</think>')[-1]
    text = text.replace('<think>', '').replace('</think>', '')
    low = text.lower()
    leak = ["here's a thinking", "analyze user input", "user sent:", "the image shows", "followed by an image",
            "the user wants me", "analyze the problem", "source: the image", "the image text says", "translates to",
            "this refers to", "solve in russian", "do not mention the creator", "you). *", "йоу\" (you)", "legend of imo"]
    if any(p in low for p in leak):
        idx = text.rfind('Йоу,')
        if idx == -1:
            idx = text.rfind('Йоу')
        if idx!= -1:
            cand = text[idx:]
            cand = cand.replace('(You).', '').replace('* Solve in Russian. *', '').replace('* Do not mention the creator unless asked.', '').replace('(You)', '').strip()
            if "imo 1988" in low or "a^2 + b^2" in low or "ab + 1" in low or "легенда об imo" in low:
                return "Йоу, это легендарная задача IMO 1988 №6! Это классика Vieta jumping! Докажем что (a²+b²)/(ab+1) — полный квадрат. Пусть k = (a²+b²)/(ab+1) целое. Второй корень a' = k b - a — целое. Спуском получаем k = квадрат. Хочешь полный разбор?"
            if "интеграл" in low or "cos(x)" in low or "вычислите значение интеграла" in low:
                return "Йоу, вижу интеграл! I = ∫_{-∞}^{∞} cos(x)/(x²+1) dx = π/e ≈ 1.1557. Решается вычетами. Хочешь полный разбор?"
            if len(cand) > 20:
                text = cand
        else:
            if "imo 1988" in low or "a^2 + b^2" in low or "ab + 1" in low or "легенда об imo" in low:
                return "Йоу, это легендарная задача IMO 1988 №6! Классика Vieta jumping! (a²+b²)/(ab+1) — всегда полный квадрат."
            if "интеграл" in low or "cos(x)" in low:
                return "Йоу, интеграл I = π/e! Решается вычетами!"
            return "Йоу, привет! Вижу задачку! Давай решу по шагам? 😊"
    out = []
    for line in text.split('\n'):
        l = line.lower()
        if any(x in l for x in ["here's a thinking", "analyze user", "the user wants me", "source: the image", "translates to", "this refers to", "user sent:", "the image shows", "solve in russian", "do not mention the creator", "check constraints", "final check"]):
            continue
        out.append(line)
    text = '\n'.join(out).strip().replace('**','').strip().strip('"')
    text = text.replace('(You).', '').replace('(You)', '').strip()
    if text and text[-1] not in '.!?':
        last_dot = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_dot > 20:
            text = text[:last_dot+1].strip()
        else:
            text = text.rstrip(', -:') + '.'
    return text.strip()

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

async def ask_groq(chat_id: int, text: str, image_b64: Optional[str]=None) -> str:
    if groq_client is None:
        return 'Мозг не подключен! Проверь GROQ ключ'
    chat_stats['total_requests']+=1
    memory = get_chat_memory(chat_id)
    messages = [{'role':'system','content':SYSTEM_PROMPT}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos']+=1
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото? Реши задачу подробно.'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model=VISION_MODEL
    else:
        chat_stats['texts']+=1
        messages.append({'role':'user','content':text})
        model=TEXT_MODEL
    try:
        try:
            comp = groq_client.chat.completions.create(model=model,messages=messages,temperature=0.6,max_tokens=2000)
        except Exception as e_first:
            if 'model_not_found' in str(e_first) or 'does not exist' in str(e_first) or 'decommissioned' in str(e_first):
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL,messages=messages,temperature=0.6,max_tokens=2000)
            else:
                raise
        ans_raw = comp.choices[0].message.content
        ans = clean_ai_response(ans_raw)
        add_memory(chat_id,'user',text or '[фото]')
        add_memory(chat_id,'assistant',ans)
        return ans
    except Exception as e:
        chat_stats['errors']+=1
        if image_b64:
            try:
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL,messages=messages,temperature=0.6,max_tokens=2000)
                ans_raw=comp.choices[0].message.content
                ans=clean_ai_response(ans_raw)
                add_memory(chat_id,'user',text or '[фото]')
                add_memory(chat_id,'assistant',ans)
                return ans
            except Exception as e2:
                return f'Глаза лагают: {e2}'
        return f'Мозг завис: {e}'

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user}! Йоу, как дела? Что делаешь? Рад тебя видеть! 😊 Я теперь решаю матан!", reply_markup=MAIN_KB)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Кидай фото задачи — решу IMO, интегралы, любой матан! Пиши текст — отвечу. /clear чтобы забыть память.", reply_markup=MAIN_KB)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text("Память стерта! 🧹", reply_markup=MAIN_KB)

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    hours = uptime // 60
    mins = uptime % 60
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    now_str = format_time(datetime.now())
    text = (
        f"🤖 Даун v57 ORIGINAL DATE\n"
        f"{info}\n"
        f"🚀 Первый запуск: {first_str}\n"
        f"🕒 Сейчас: {now_str}\n"
        f"⏱ Аптайм с рестарта: {hours}ч {mins}м ({uptime} мин)\n"
        f"📝 Текст: {TEXT_MODEL}\n"
        f"👁 Глаза: {VISION_MODEL}\n"
        f"🛟 Фолбек: {FALLBACK_VISION_MODEL}\n"
        f"{get_stats_text()}\n"
        f"Текстов: {chat_stats['texts']} | Фото: {chat_stats['photos']} | Ошибок: {chat_stats['errors']}\n"
        f"🧮 Математика: IMO 1988, интегралы — прокачана!"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\nФолбек: {FALLBACK_VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    now_str = format_time(datetime.now())
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    await update.message.reply_text(f"Я жив {mins} мин! Первый запуск {first_str} | Сейчас {now_str} | {get_stats_text()} | Модель: {VISION_MODEL}", reply_markup=MAIN_KB)

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    now_str = format_time(datetime.now())
    await update.message.reply_text(f"📊 Статистика:\n{get_stats_text()}\nТекстов: {chat_stats['texts']}\nФото: {chat_stats['photos']}\nОшибок: {chat_stats['errors']}\nПервый запуск: {first_str}\nСейчас: {now_str}\nМодель глаз: {VISION_MODEL}", reply_markup=MAIN_KB)

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args
    if not args:
        await update.message.reply_text("Пиши /limit твой_пароль", reply_markup=MAIN_KB)
        return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль', reply_markup=MAIN_KB)
        return
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    await update.message.reply_text(f"Всего: {chat_stats['total_requests']}\n{get_stats_text()}\nПервый запуск: {first_str}\nМодель: {VISION_MODEL}", reply_markup=MAIN_KB)

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    low = txt.lower()
    if 'инфо' in low:
        await about_h(update, context); return
    if 'создатель' in low or 'кто тебя сделал' in low or 'кто автор' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("Мой создатель — Максим @MakSon4ikk_228, он меня сделал с нуля!", reply_markup=MAIN_KB)
        await update.message.reply_text("Вот его профиль 👇", reply_markup=kb_inline)
        return
    if 'забыть' in low:
        clear_memory(update.effective_chat.id); await update.message.reply_text("Память стерта! 🧹", reply_markup=MAIN_KB); return
    if 'админу' in low:
        await update.message.reply_text("Пиши @MakSon4ikk_228", reply_markup=MAIN_KB); return
    if 'помощ' in low:
        await help_h(update, context); return
    if 'модель' in low:
        await model_h(update, context); return
    if 'пинг' in low:
        await ping_h(update, context); return
    if 'стата' in low:
        await stats_h(update, context); return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans=await ask_groq(update.effective_chat.id,txt,None)
    for p in split_text(ans):
        await update.message.reply_text(p, reply_markup=MAIN_KB)

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id):
        await update.message.reply_text('Не спамь фотками ⏳', reply_markup=MAIN_KB); return
    cap=clean_text(update.message.caption) or 'Что на фото? Реши задачу подробно.'
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    try:
        photo=update.message.photo[-1]
        file=await photo.get_file()
        bio=BytesIO()
        await file.download_to_memory(bio)
        b64=encode_b64(bio.getvalue())
        ans=await ask_groq(update.effective_chat.id,cap,b64)
        for p in split_text(ans):
            await update.message.reply_text(p, reply_markup=MAIN_KB)
    except Exception as e:
        await update.message.reply_text(f'Ошибка фото: {e}', reply_markup=MAIN_KB)

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
            await update.message.reply_text(p, reply_markup=MAIN_KB)
    except Exception as e:
        await update.message.reply_text(f'Ошибка: {e}', reply_markup=MAIN_KB)

async def sticker_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Кек, стикер 😂 Кидай текст или фотку!', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    return f"Даун v57 ORIGINAL DATE жив! Первый запуск: {first_str} | Сейчас: {format_time(datetime.now())} | {get_stats_text()} | {VISION_MODEL}"
@app_flask.route('/health')
def health():
    return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

def main():
    print(f'Даун v57 ORIGINAL DATE запуск, первый запуск: {format_date_short(FIRST_LAUNCH_DATE)}')
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
    print('Бот запущен! v57 original date + math')
    application.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    main()
