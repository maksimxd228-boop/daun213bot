import os, sys, base64, logging, time, threading, platform, re, random, ast, operator
import urllib.request
import urllib.parse
from io import BytesIO
from datetime import datetime, timezone, timedelta
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

def get_riga_time():
    now_utc = datetime.now(timezone.utc)
    riga = now_utc + timedelta(hours=3)
    return now_utc, riga, riga

def format_time_full():
    utc, riga, msk = get_riga_time()
    return f"🕒 Время:\nРига: {riga.strftime('%H:%M:%S %d.%m.%Y')}\nМосква: {msk.strftime('%H:%M:%S %d.%m.%Y')}\nUTC: {utc.strftime('%H:%M:%S %d.%m.%Y')}"

def format_time(dt: datetime) -> str: return dt.strftime('%H:%M:%S %d.%m.%Y')
def format_date_short(dt: datetime) -> str: return dt.strftime('%H:%M %d.%m.%Y')

SYSTEM_PROMPT = """Ты — Даун213, теплый позитивный бот. Создатель — Максим @MakSon4ikk_228. Йоу редко, 1 из 5. Без LaTeX."""

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
chat_stats = {'total_requests':0,'photos':0,'texts':0,'errors':0,'images':0,'start_time':time.time()}

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
    mem.append({'role': role, 'content': text[:MAX_TEXT_LEN].replace(chr(10),' ').strip()})
    while len(mem) > MAX_HISTORY: mem.pop(0)

def clear_memory(chat_id: int):
    if chat_id in chat_memories: chat_memories[chat_id] = []

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("ℹ️ Инфо"), KeyboardButton("👑 Создатель")],
        [KeyboardButton("🧹 Забыть"), KeyboardButton("📩 Админу")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("🛠️ Модель")],
        [KeyboardButton("🏓 Пинг"), KeyboardButton("📊 Стата")],
        [KeyboardButton("🕒 Время"), KeyboardButton("🎨 Картинка")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

MAIN_KB = get_main_keyboard()

def get_stats_text() -> str:
    total = len(chat_memories)
    msgs = sum(len(v) for v in chat_memories.values())
    return f'Чатов: {total} | Сообщений: {msgs} | Запросов: {chat_stats["total_requests"]} | Картинок: {chat_stats["images"]}'

def encode_b64(b: bytes) -> str:
    try: return base64.b64encode(b).decode('utf-8')
    except: return ''

def is_image_file(name: str) -> bool:
    if not name: return False
    return name.lower().split('.')[-1] in ['jpg','jpeg','png','webp','bmp','heic','gif']

def get_system_info() -> str: return f'Python {platform.python_version()} | {platform.system()}'

def is_spam(uid: int) -> bool:
    now = time.time()
    if now - user_cooldown.get(uid,0) < 1.3: return True
    user_cooldown[uid]=now
    return False

def clean_text(t: str) -> str:
    if not t: return ''
    return re.sub(r'\s+',' ',t.strip())[:4000]

def fix_latex_to_plain(text: str) -> str:
    text = text.replace('\\[','').replace('\\]','').replace('\\(','').replace('\\)','').replace('$$','').replace('$','')
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\', '', text)
    return text.strip()

def clean_ai_response(text: str) -> str:
    if not text: return text
    if '</think>' in text: text = text.split('</think>')[-1]
    text = fix_latex_to_plain(text.replace('<think>','').replace('</think>',''))
    yoy_counter['count'] += 1
    if yoy_counter['count'] % 5!= 0:
        if text.strip().lower().startswith('йоу'):
            text = re.sub(r'^[Йй]оу[,\s!]*[😊🙂😎🔥]*\s*', '', text).strip()
            if text: text = text[0].upper() + text[1:] if len(text)>1 else text
    text = text.replace('Чем могу быть полезен?', 'Чем помочь?')
    text = text.replace('Я — ИИ-бот, созданный командой разработчиков.', 'Я — бот, меня создал Максим @MakSon4ikk_228.')
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

def generate_image_pollinations(prompt: str) -> Optional[BytesIO]:
    try:
        safe_prompt = urllib.parse.quote(prompt[:500])
        urls = [
            f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={random.randint(1,999999)}",
            f"https://gen.pollinations.ai/image/{safe_prompt}?width=1024&height=1024"
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Accept': 'image/*'})
                with urllib.request.urlopen(req, timeout=40) as resp:
                    data = resp.read()
                    ctype = resp.headers.get('Content-Type','')
                    if len(data) > 8000 and ('image' in ctype or data[:2]==b'\xff\xd8' or data[:4]==b'\x89PNG'):
                        logger.info(f"Image OK {len(data)} from {url}")
                        return BytesIO(data)
            except Exception as e:
                logger.warning(f"Gen fail {url}: {e}")
                continue
    except Exception as e:
        logger.error(f"Gen total fail: {e}")
    return None

async def ask_groq(chat_id: int, text: str, image_b64: Optional[str]=None) -> str:
    if groq_client is None: return 'Мозг не подключен.'
    chat_stats['total_requests']+=1
    memory = get_chat_memory(chat_id)
    utc, riga, msk = get_riga_time()
    time_info = f"[Время: Рига {riga.strftime('%H:%M:%S %d.%m.%Y')}]"
    messages = [{'role':'system','content':SYSTEM_PROMPT + "\n" + time_info}]
    messages.extend(memory)
    if image_b64:
        chat_stats['photos']+=1
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото?'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
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
    return f'Ошибка: {last_err}'

async def start_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user}! Я теперь рисую картинки — пиши 'нарисуй...'", reply_markup=MAIN_KB)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 Картинка — 'нарисуй кота в космосе'\n🕒 Время — точное время", reply_markup=MAIN_KB)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB)

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    time_text = format_time_full()
    text = f"🤖 Даун v67 FIXED x2\n{info}\n🚀 Первый запуск: {first_str}\n{time_text}\n⏱ {uptime} мин\n📝 {TEXT_MODEL}\n👁 {VISION_MODEL}\n🎨 Pollinations FIXED x2\n{get_stats_text()}"
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    await update.message.reply_text(f"В сети {mins} мин.\n{format_time_full()}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 {get_stats_text()}\nПервый запуск: {format_date_short(FIRST_LAUNCH_DATE)}\n{format_time_full()}", reply_markup=MAIN_KB)

async def time_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_time_full(), reply_markup=MAIN_KB)

async def image_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = ' '.join(context.args) if context.args else ''
    if not prompt:
        await update.message.reply_text("Напиши что нарисовать! /image кот в космосе", reply_markup=MAIN_KB)
        return
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    await update.message.reply_text(f"Рисую: {prompt}... ⏳", reply_markup=MAIN_KB)
    img = generate_image_pollinations(prompt)
    if img:
        chat_stats['images']+=1
        await update.message.reply_photo(photo=img, caption=f"Готово! 🎨 {prompt}", reply_markup=MAIN_KB)
    else:
        await update.message.reply_text("Не удалось, попробуй еще раз.", reply_markup=MAIN_KB)

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args
    if not args:
        await update.message.reply_text("Используй /limit пароль", reply_markup=MAIN_KB); return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль', reply_markup=MAIN_KB); return
    await update.message.reply_text(f"Всего: {chat_stats['total_requests']}\n{get_stats_text()}\n{format_time_full()}", reply_markup=MAIN_KB)

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    low = txt.lower()
    if any(x in low for x in ['нарисуй', 'сгенерируй картинку', 'сделай картинку', 'нарисовать', '🎨 картинка']):
        prompt = txt
        for word in ['нарисуй', 'сгенерируй картинку', 'сделай картинку', 'нарисовать', '🎨 картинка']:
            if word in low:
                prompt = low.split(word,1)[-1].strip(' :,-')
                break
        if not prompt or len(prompt) < 2:
            await update.message.reply_text("Что нарисовать? Пример: нарисуй киберпанк Ригу", reply_markup=MAIN_KB)
            return
        await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
        await update.message.reply_text(f"Рисую: {prompt}... ⏳🎨", reply_markup=MAIN_KB)
        img = generate_image_pollinations(prompt)
        if img:
            chat_stats['images']+=1
            await update.message.reply_photo(photo=img, caption=f"Готово! {prompt}", reply_markup=MAIN_KB)
        else:
            await update.message.reply_text("Не вышло, попробуй еще раз. Иногда Pollinations лежит.", reply_markup=MAIN_KB)
        return
    if any(x in low for x in ['сколько времени', 'который час', '🕒 время', 'точное время']):
        await update.message.reply_text(format_time_full(), reply_markup=MAIN_KB); return
    if 'инфо' in low: await about_h(update, context); return
    if 'создатель' in low or 'кто тебя сделал' in low or 'кем ты был создан' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("Меня создал Максим @MakSon4ikk_228!", reply_markup=MAIN_KB)
        await update.message.reply_text("Вот его профиль 👇", reply_markup=kb_inline); return
    if 'забыть' in low: clear_memory(update.effective_chat.id); await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB); return
    if 'админу' in low: await update.message.reply_text("Напиши @MakSon4ikk_228", reply_markup=MAIN_KB); return
    if 'помощ' in low: await help_h(update, context); return
    if 'модель' in low: await model_h(update, context); return
    if 'пинг' in low: await ping_h(update, context); return
    if 'стата' in low: await stats_h(update, context); return
    if 'время' in low: await time_h(update, context); return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans=await ask_groq(update.effective_chat.id,txt,None)
    for p in split_text(ans):
        await update.message.reply_text(p, reply_markup=MAIN_KB)

async def photo_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): await update.message.reply_text('Подожди с фотками ⏳', reply_markup=MAIN_KB); return
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
    await update.message.reply_text('Хех, стикер прикольный!', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v67 FIXED x2 жив! {format_date_short(FIRST_LAUNCH_DATE)} | {format_time_full()} | {get_stats_text()}"
@app_flask.route('/health')
def health(): return 'OK',200
def run_flask(): app_flask.run(host='0.0.0.0',port=PORT)
def main():
    print(f'Даун v67 FIXED x2 запуск')
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
    application.add_handler(CommandHandler('time',time_h))
    application.add_handler(CommandHandler('image',image_h))
    application.add_handler(CommandHandler('limit',limit_h))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_h))
    application.add_handler(MessageHandler(filters.PHOTO,photo_h))
    application.add_handler(MessageHandler(filters.Document.IMAGE,doc_h))
    application.add_handler(MessageHandler(filters.Sticker.ALL,sticker_h))
    print('Бот запущен! v67 FIXED x2')
    application.run_polling(drop_pending_updates=True)
if __name__=='__main__':
    main()
