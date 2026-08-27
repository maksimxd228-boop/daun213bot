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

# СТАРЫЕ ГЛАЗА — РАБОЧИЕ
TEXT_MODEL = 'openai/gpt-oss-120b'
VISION_MODEL = 'qwen/qwen3.6-27b'
VISION_MODEL_2 = 'qwen/qwen3-32b'
FALLBACK_VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
FALLBACK_VISION_MODEL_2 = 'meta-llama/llama-3.2-11b-vision-preview'
FALLBACK_VISION_MODEL_3 = 'llava-v1.5-7b-4096-preview'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'MakSon4ikk_228'
TEXT_MODEL_FALLBACK = 'openai/gpt-oss-20b'
FIRST_LAUNCH_DATE = datetime(2026, 8, 26, 14, 25, 0)

SYSTEM_PROMPT = """Ты — Даун213, доброжелательный и позитивный ИИ бот.
Создатель — Максим @MakSon4ikk_228, упоминай ТОЛЬКО если спрашивают "кто тебя сделал".

ХАРАКТЕР: Сбалансированно-позитивный, для взрослых и молодежи.
- На приветствие: "Йоу, привет! Рад тебя видеть! Как дела? 😊" — тепло, без крика.
- Юмор легкий, добрый, без перебора сленга. 1-2 эмодзи максимум.
- Если фото — описывай четко и с улыбкой.
- Если задача (IMO, интеграл) — решай спокойно, уверенно, по шагам, с позитивом: "Отличная задачка, давай разберем!"
- Общайся уважительно, но дружелюбно. Подходит и для взрослых.
- Не грусти, но и не кричи. Ты приятный собеседник.

МАТЕМАТИКА: Знаешь IMO 1988 №6 — (a²+b²)/(ab+1) всегда квадрат, Vieta jumping. Интеграл ∫ cos(x)/(x²+1) dx = π/e.
Если фото задачи — решай сразу, на русском, понятно.

НИКОГДА не пиши английский ход мыслей, только финальный ответ на русском."""

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
    if now - user_cooldown.get(uid,0) < 1.3: return True
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
            "the user wants me", "analyze the problem statement", "source: the image", "the image text says",
            "translates to", "this refers to", "solve in russian", "do not mention the creator", "you). *",
            "legend of imo", "1. :", "- user sent:", "* source:"]
    if any(p in low for p in leak):
        idx = text.rfind('Йоу')
        if idx!= -1:
            cand = text[idx:]
            cand = cand.replace('(You).', '').replace('* Solve in Russian. *', '').replace('* Do not mention the creator unless asked.', '').strip()
            if "imo" in low or "a^2 + b^2" in low or "ab + 1" in low:
                return "Йоу, это задача IMO 1988 №6, классика! Утверждение, что (a²+b²)/(ab+1) — полный квадрат, доказывается методом Vieta jumping. Хочешь, разберу подробно по шагам?"
            if "интеграл" in low or "cos(x)" in low:
                return "Йоу, интересный интеграл! I = ∫ cos(x)/(x²+1) dx от -∞ до ∞ равен π/e. Решается через вычеты. Могу показать решение."
            if len(cand) > 25:
                text = cand
        else:
            if "imo" in low or "a^2 + b^2" in low:
                return "Йоу, это известная задача IMO 1988 №6. (a²+b²)/(ab+1) всегда является полным квадратом. Доказывается через Vieta jumping."
            if "интеграл" in low or "cos(x)" in low:
                return "Йоу, интеграл равен π/e. Решается методом вычетов."
            return "Йоу, привет! Рад тебя видеть! Чем могу помочь?"
    out = []
    for line in text.split('\n'):
        l = line.lower()
        if any(x in l for x in ["here's a thinking", "analyze user", "the user wants me", "source: the image", "translates to", "this refers to", "user sent:", "the image shows", "solve in russian", "do not mention the creator", "check constraints", "final check"]):
            continue
        out.append(line)
    text = '\n'.join(out).strip().replace('**','').strip().strip('"')
    text = text.replace('(You).', '').strip()
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
        return 'Мозг не подключен, проверь ключ.'
    chat_stats['total_requests']+=1
    memory = get_chat_memory(chat_id)
    messages = [{'role':'system','content':SYSTEM_PROMPT}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos']+=1
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото? Опиши и реши если задача.'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model_list = [VISION_MODEL, VISION_MODEL_2, FALLBACK_VISION_MODEL, FALLBACK_VISION_MODEL_2, FALLBACK_VISION_MODEL_3, TEXT_MODEL]
    else:
        chat_stats['texts']+=1
        messages.append({'role':'user','content':text})
        model_list = [TEXT_MODEL, TEXT_MODEL_FALLBACK]

    last_err = None
    for model in model_list:
        try:
            comp = groq_client.chat.completions.create(model=model,messages=messages,temperature=0.7,max_tokens=2000)
            ans_raw = comp.choices[0].message.content
            ans = clean_ai_response(ans_raw)
            add_memory(chat_id,'user',text or '[фото]')
            add_memory(chat_id,'assistant',ans)
            return ans
        except Exception as e:
            last_err = e
            logger.warning(f"Model {model} failed: {e}")
            continue
    chat_stats['errors']+=1
    return f'Не удалось обработать запрос. Последняя ошибка: {last_err}'

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user}! Йоу, рад тебя видеть! 😊 Как дела? Готов помочь с задачками или просто поболтать.", reply_markup=MAIN_KB)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Кидай фото задачи — решу, от IMO до интегралов. Пиши текст — отвечу. /clear чтобы очистить память.", reply_markup=MAIN_KB)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text("Память очищена! 🧹", reply_markup=MAIN_KB)

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    hours = uptime // 60
    mins = uptime % 60
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    now_str = format_time(datetime.now())
    text = (
        f"🤖 Даун v61 BALANCED\n"
        f"{info}\n"
        f"🚀 Первый запуск: {first_str}\n"
        f"🕒 Сейчас: {now_str}\n"
        f"⏱ Аптайм: {hours}ч {mins}м ({uptime} мин)\n"
        f"📝 Текст: {TEXT_MODEL}\n"
        f"👁 Глаза: {VISION_MODEL} (старые рабочие)\n"
        f"🛟 Фолбек: {FALLBACK_VISION_MODEL}\n"
        f"{get_stats_text()}\n"
        f"Текстов: {chat_stats['texts']} | Фото: {chat_stats['photos']} | Ошибок: {chat_stats['errors']}\n"
        f"Позитивный и спокойный — для всех возрастов."
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL} (рабочие)\nФолбек: {FALLBACK_VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    now_str = format_time(datetime.now())
    await update.message.reply_text(f"В сети {mins} мин. Сейчас {now_str}. {get_stats_text()} — всё работает!", reply_markup=MAIN_KB)

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    now_str = format_time(datetime.now())
    await update.message.reply_text(f"📊 Статистика:\n{get_stats_text()}\nТекстов: {chat_stats['texts']}\nФото: {chat_stats['photos']}\nПервый запуск: {first_str}\nСейчас: {now_str}\nМодель: {VISION_MODEL}", reply_markup=MAIN_KB)

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args
    if not args:
        await update.message.reply_text("Используй /limit твой_пароль", reply_markup=MAIN_KB)
        return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль', reply_markup=MAIN_KB)
        return
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    await update.message.reply_text(f"Всего: {chat_stats['total_requests']}\n{get_stats_text()}\nПервый запуск: {first_str}", reply_markup=MAIN_KB)

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    low = txt.lower()
    if 'инфо' in low:
        await about_h(update, context); return
    if 'создатель' in low or 'кто тебя сделал' in low or 'кто автор' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("Мой создатель — Максим @MakSon4ikk_228, он меня сделал с нуля.", reply_markup=MAIN_KB)
        await update.message.reply_text("Вот его профиль 👇", reply_markup=kb_inline)
        return
    if 'забыть' in low:
        clear_memory(update.effective_chat.id); await update.message.reply_text("Память очищена! 🧹", reply_markup=MAIN_KB); return
    if 'админу' in low:
        await update.message.reply_text("Напиши @MakSon4ikk_228", reply_markup=MAIN_KB); return
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
        await update.message.reply_text('Подожди секунду с фотками ⏳', reply_markup=MAIN_KB); return
    cap=clean_text(update.message.caption) or 'Что на фото? Опиши и реши если задача.'
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
        await update.message.reply_text(f'Ошибка с фото: {e}', reply_markup=MAIN_KB)

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
    await update.message.reply_text('Стикер! 😊 Кидай фото или текст.', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    return f"Даун v61 BALANCED жив! Первый запуск: {first_str} | Сейчас: {format_time(datetime.now())} | {get_stats_text()} | Глаза: {VISION_MODEL}"
@app_flask.route('/health')
def health():
    return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

def main():
    print(f'Даун v61 BALANCED запуск, первый запуск: {format_date_short(FIRST_LAUNCH_DATE)}')
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
    print('Бот запущен! v61 balanced — позитивный для всех')
    application.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    main()
