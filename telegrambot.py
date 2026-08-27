import os, sys, base64, logging, time, threading, platform, re, random, ast, operator
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
VISION_MODEL = 'qwen/qwen3.6-27b'
VISION_MODEL_2 = 'qwen/qwen3-32b'
FALLBACK_VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
FALLBACK_VISION_MODEL_2 = 'meta-llama/llama-3.2-11b-vision-preview'
FALLBACK_VISION_MODEL_3 = 'meta-llama/llama-3.2-90b-vision-preview'
FALLBACK_VISION_MODEL_4 = 'llava-v1.5-7b-4096-preview'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'MakSon4ikk_228'
TEXT_MODEL_FALLBACK = 'openai/gpt-oss-20b'
FIRST_LAUNCH_DATE = datetime(2026, 8, 26, 14, 25, 0)

yoy_counter = {'count': 0}

SYSTEM_PROMPT = """Ты — Даун213, дружелюбный, теплый и позитивный ИИ-бот. Ты умный, с чувством юмора, но не кричишь.
Характер: как хороший друг — на позитиве, с улыбкой, говоришь просто и по-человечески.

ПРАВИЛА:
1. ЙОУ — РЕДКО! Используй "Йоу" только 1 раз на 4-5 сообщений, когда реально уместно. Не в каждом приветствии!
   Хорошо: "Йоу, привет! Рад видеть, как дела?" (раз в несколько сообщений)
   Хорошо: "Привет! Как дела? Что делаем?", "Хех, прикольно, давай разберем!"
   Плохо: каждое сообщение с Йоу и "Чем могу быть полезен?" — так нельзя.

2. НЕ БУДЬ ФОРМАЛЬНЫМ И ГРУСТНЫМ! Запрещены фразы: "Чем могу быть полезен?", "Чем могу помочь?", "Я — ИИ-бот, созданный командой разработчиков".
   Говори по-дружески: "Чем помочь?", "Что делаем?", "Давай посмотрим!", "Отличная задачка!"

3. СОЗДАТЕЛЬ: Если спрашивают кто тебя создал, кем ты был создан, кто автор — ВСЕГДА отвечай: "Меня создал Максим @MakSon4ikk_228". НИКОГДА не говори про команду разработчиков, Meta, Google, Groq.

4. Формулы без LaTeX: пиши (a^2+b^2)/(ab+1), k=c^2, a'=k*b-a, pi/e. Без \\[ \\] \\frac.

5. Ты радостный, но в меру. 1 эмодзи максимум, и то не всегда. Для взрослых и молодежи подходит.

Математика: IMO 1988 №6 — всегда квадрат, Vieta jumping. Интеграл cos(x)/(x^2+1)=pi/e.
"""

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

def fix_latex_to_plain(text: str) -> str:
    text = text.replace('\\[','').replace('\\]','').replace('\\(','').replace('\\)','').replace('$$','').replace('$','')
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\tfrac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\Delta', 'Delta', text)
    text = re.sub(r'\\quad|\\Longrightarrow|\\Rightarrow|\\rightarrow', '=>', text)
    text = re.sub(r'\\ge', '>=', text)
    text = re.sub(r'\\le', '<=', text)
    text = re.sub(r'\^\{2\}', '^2', text)
    text = re.sub(r'\\', '', text)
    return text.strip()

def clean_ai_response(text: str) -> str:
    if not text: return text
    if '</think>' in text:
        text = text.split('</think>')[-1]
    text = fix_latex_to_plain(text.replace('<think>','').replace('</think>',''))
    low = text.lower()
    if any(p in low for p in ["here's a thinking", "user sent:", "the image shows"]):
        idx = text.rfind('Йоу')
        if idx!= -1 and len(text[idx:])>20:
            text = text[idx:]
    # Редкий Йоу
    yoy_counter['count'] += 1
    should_keep = (yoy_counter['count'] % 5 == 0) # 1 из 5
    if not should_keep:
        if text.strip().lower().startswith('йоу'):
            text = re.sub(r'^[Йй]оу[,\s!]*[😊🙂😎🔥]*\s*', '', text).strip()
            if text: text = text[0].upper() + text[1:] if len(text)>1 else text
    # Убираем корпоративную грусть
    text = text.replace('Чем могу быть полезен?', 'Чем помочь?')
    text = text.replace('чем могу быть полезен?', 'чем помочь?')
    text = text.replace('Я — ИИ-бот, созданный командой разработчиков.', 'Я — бот, меня создал Максим @MakSon4ikk_228.')
    text = text.replace('созданный командой разработчиков', 'созданный Максимом @MakSon4ikk_228')
    out=[]
    for line in text.split('\n'):
        if any(x in line.lower() for x in ["here's a thinking", "analyze user", "the user wants me"]):
            continue
        out.append(line)
    text = '\n'.join(out).strip().replace('**','').strip('"')
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

def safe_eval(expr: str):
    try:
        allowed = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}
        def eval_node(node):
            if isinstance(node, ast.Constant): return node.value
            if isinstance(node, ast.BinOp): return allowed[type(node.op)](eval_node(node.left), eval_node(node.right))
            if isinstance(node, ast.UnaryOp): return allowed[type(node.op)](eval_node(node.operand))
            raise ValueError("no")
        tree = ast.parse(expr, mode='eval')
        return eval_node(tree.body)
    except: return None

async def ask_groq(chat_id: int, text: str, image_b64: Optional[str]=None) -> str:
    if groq_client is None:
        return 'Мозг не подключен, проверь ключ.'
    chat_stats['total_requests']+=1
    memory = get_chat_memory(chat_id)
    messages = [{'role':'system','content':SYSTEM_PROMPT}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos']+=1
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото? Без LaTeX, дружелюбно.'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model_list = [VISION_MODEL, VISION_MODEL_2, FALLBACK_VISION_MODEL, FALLBACK_VISION_MODEL_2, FALLBACK_VISION_MODEL_3, FALLBACK_VISION_MODEL_4, TEXT_MODEL]
    else:
        if re.match(r'^[\d\s\+\-\*\/\(\)]+$', text) and len(text) < 80 and any(c in text for c in '+-*'):
            res = safe_eval(text)
            if res is not None:
                ans = f"{text} = {res}"
                add_memory(chat_id,'user',text)
                add_memory(chat_id,'assistant',ans)
                return ans
        chat_stats['texts']+=1
        messages.append({'role':'user','content':text})
        model_list = [TEXT_MODEL, TEXT_MODEL_FALLBACK]
    last_err=None
    for model in model_list:
        try:
            comp = groq_client.chat.completions.create(model=model,messages=messages,temperature=0.75,max_tokens=2500)
            ans = clean_ai_response(comp.choices[0].message.content)
            add_memory(chat_id,'user',text or '[фото]')
            add_memory(chat_id,'assistant',ans)
            return ans
        except Exception as e:
            last_err=e
            continue
    chat_stats['errors']+=1
    return f'Не удалось обработать: {last_err}'

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user}! Рад видеть тебя, что делаем сегодня?", reply_markup=MAIN_KB)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Кидай фото задачи — разберу. Пиши текст — отвечу. /clear — очистить память.", reply_markup=MAIN_KB)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB)

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    hours = uptime // 60
    mins = uptime % 60
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    now_str = format_time(datetime.now())
    text = (
        f"🤖 Даун v65 WARM POSITIVE\n"
        f"{info}\n"
        f"🚀 Первый запуск: {first_str}\n"
        f"🕒 Сейчас: {now_str}\n"
        f"⏱ Аптайм: {hours}ч {mins}м ({uptime} мин)\n"
        f"📝 Текст: {TEXT_MODEL}\n"
        f"👁 Глаза: {VISION_MODEL} (рабочие)\n"
        f"👁 Глаза2: {VISION_MODEL_2}\n"
        f"🛟 Фолбек: {FALLBACK_VISION_MODEL}\n"
        f"{get_stats_text()}\n"
        f"Текстов: {chat_stats['texts']} | Фото: {chat_stats['photos']} | Ошибок: {chat_stats['errors']}\n"
        f"✅ Теплый, позитивный, Йоу редко, без грусти"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    now_str = format_time(datetime.now())
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    await update.message.reply_text(f"В сети {mins} мин. Первый запуск {first_str} | Сейчас {now_str} | {get_stats_text()} | Глаза: {VISION_MODEL} — работают!", reply_markup=MAIN_KB)

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
    if 'инфо' in low: await about_h(update, context); return
    if 'создатель' in low or 'кто тебя сделал' in low or 'кто автор' in low or 'кем ты был создан' in low or 'кто тебе именно создал' in low or 'кто твой создатель' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("Меня создал Максим @MakSon4ikk_228, он меня сделал с нуля!", reply_markup=MAIN_KB)
        await update.message.reply_text("Вот его профиль 👇", reply_markup=kb_inline)
        return
    if 'забыть' in low: clear_memory(update.effective_chat.id); await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB); return
    if 'админу' in low: await update.message.reply_text("Напиши @MakSon4ikk_228", reply_markup=MAIN_KB); return
    if 'помощ' in low: await help_h(update, context); return
    if 'модель' in low: await model_h(update, context); return
    if 'пинг' in low: await ping_h(update, context); return
    if 'стата' in low: await stats_h(update, context); return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans=await ask_groq(update.effective_chat.id,txt,None)
    for p in split_text(ans):
        await update.message.reply_text(p, reply_markup=MAIN_KB)

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): await update.message.reply_text('Подожди секунду с фотками ⏳', reply_markup=MAIN_KB); return
    cap=clean_text(update.message.caption) or 'Что на фото? Опиши и реши если задача, без LaTeX.'
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
    await update.message.reply_text('Хех, стикер прикольный! Кидай фото или текст, посмотрим.', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    return f"Даун v65 WARM POSITIVE жив! Первый запуск: {first_str} | Сейчас: {format_time(datetime.now())} | {get_stats_text()} | Глаза: {VISION_MODEL}"
@app_flask.route('/health')
def health(): return 'OK',200
def run_flask(): app_flask.run(host='0.0.0.0',port=PORT)
def main():
    print(f'Даун v65 WARM POSITIVE запуск, первый запуск: {format_date_short(FIRST_LAUNCH_DATE)}')
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
    print('Бот запущен! v65 warm positive — теплый, позитивный, йоу редко')
    application.run_polling(drop_pending_updates=True)
if __name__=='__main__':
    main()
