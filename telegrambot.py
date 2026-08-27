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

def get_env_smart(*names):
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

def format_time(dt):
    return dt.strftime('%H:%M:%S %d.%m.%Y')

def format_date_short(dt):
    return dt.strftime('%H:%M %d.%m.%Y')

SYSTEM_PROMPT = "Ты — Даун213, теплый позитивный бот. Создатель — Максим @MakSon4ikk_228. Йоу редко. Без LaTeX."

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

groq_client = None
try:
    if 'ВСТАВЬ' not in GROQ_API_KEY:
        groq_client = Groq(api_key=GROQ_API_KEY)
except:
    logger.error('Groq fail')

chat_memories = {}
chat_last_active = {}
user_cooldown = {}
chat_stats = {'total_requests':0,'photos':0,'texts':0,'errors':0,'images':0,'start_time':time.time()}

def get_chat_memory(chat_id):
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []
        chat_last_active[chat_id] = time.time()
        if len(chat_memories) > MAX_CHATS:
            oldest = min(chat_last_active, key=chat_last_active.get)
            del chat_memories[oldest]
            del chat_last_active[oldest]
    chat_last_active[chat_id] = time.time()
    return chat_memories[chat_id]

def add_memory(chat_id, role, text):
    mem = get_chat_memory(chat_id)
    mem.append({'role': role, 'content': text[:MAX_TEXT_LEN].replace(chr(10),' ').strip()})
    while len(mem) > MAX_HISTORY: mem.pop(0)

def clear_memory(chat_id):
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

def get_stats_text():
    total = len(chat_memories)
    msgs = sum(len(v) for v in chat_memories.values())
    return f'Чатов: {total} | Сообщений: {msgs} | Запросов: {chat_stats["total_requests"]} | Картинок: {chat_stats["images"]}'

def encode_b64(b):
    try: return base64.b64encode(b).decode('utf-8')
    except: return ''

def is_image_file(name):
    if not name: return False
    return name.lower().split('.')[-1] in ['jpg','jpeg','png','webp','bmp','heic','gif']

def get_system_info():
    return f'Python {platform.python_version()} | {platform.system()}'

def is_spam(uid):
    now = time.time()
    if now - user_cooldown.get(uid,0) < 1.3: return True
    user_cooldown[uid]=now
    return False

def clean_text(t):
    if not t: return ''
    return re.sub(r'\s+',' ',t.strip())[:4000]

def fix_latex_to_plain(text):
    text = text.replace('\\[','').replace('\\]','').replace('\\(','').replace('\\)','').replace('$$','').replace('$','')
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\', '', text)
    return text.strip()

def clean_ai_response(text):
    if not text: return text
    if '</think>' in text: text = text.split('</think>')[-1]
    text = fix_latex_to_plain(text.replace('<think>','').replace('</think>',''))
    yoy_counter['count'] += 1
    if yoy_counter['count'] % 5!= 0:
        if text.strip().lower().startswith('йоу'):
            text = re.sub(r'^[Йй]оу[,\s!]*', '', text).strip()
    text = text.replace('Чем могу быть полезен?', 'Чем помочь?')
    text = text.replace('Я — ИИ-бот, созданный командой разработчиков.', 'Я — бот, меня создал Максим @MakSon4ikk_228.')
    return text.strip()

def split_text(t, n=4000):
    if len(t)<=n: return [t]
    parts=[]
    while len(t)>n:
        cut=t.rfind(' ',0,n)
        if cut==-1: cut=n
        parts.append(t[:cut])
        t=t[cut:].strip()
    parts.append(t)
    return parts

def safe_eval(expr):
    try:
        allowed = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}
        def eval_node(node):
            if isinstance(node, ast.Constant): return node.value
            if isinstance(node, ast.BinOp): return allowed[type(node.op)](eval_node(node.left), eval_node(node.right))
            if isinstance(node, ast.UnaryOp): return allowed[type(node.op)](eval_node(node.operand))
            raise ValueError("no")
        tree = ast.parse(expr, mode='eval')
        return eval_node(tree.body)
    except:
        return None

# --- next function ---

def enhance_prompt_for_image(user_prompt):
    low = user_prompt.lower()
    if groq_client and (len(user_prompt) < 70 or any(c in low for c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')):
        try:
            comp = groq_client.chat.completions.create(
                model=TEXT_MODEL_FALLBACK,
                messages=[
                    {"role": "system", "content": "Translate to English image prompt. If rtx, ртх, видеокарта, видюха, 5090 -> 'Nvidia GeForce RTX 5090 graphics card, photorealistic, triple fan, black, studio lighting, on white background, 8k'. If cat -> 'cute fluffy cat'. Always add photorealistic, highly detailed, 8k. Answer ONLY with prompt."},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            eng = comp.choices[0].message.content.strip().replace('"','')
            if len(eng) > 10:
                return eng
        except:
            pass
    if 'ртх' in low or 'rtx' in low or 'видеокарта' in low or 'видюха' in low or '5090' in low:
        return f"Nvidia GeForce RTX 5090 graphics card, photorealistic, triple fan, black, studio lighting, on white background, 8k, {user_prompt}"
    return f"{user_prompt}, photorealistic, highly detailed, 8k, studio lighting"

def generate_image_pollinations(prompt):
    final_prompt = enhance_prompt_for_image(prompt)
    try:
        safe_prompt = urllib.parse.quote(final_prompt[:500])
        urls = [
            f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={random.randint(1,999999)}&enhance=true&model=flux",
            f"https://gen.pollinations.ai/image/{safe_prompt}?width=1024&height=1024"
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = resp.read()
                    ctype = resp.headers.get('Content-Type','')
                    if len(data) > 8000 and ('image' in ctype or data[:2]==b'\xff\xd8' or data[:4]==b'\x89PNG'):
                        return BytesIO(data)
            except:
                continue
    except:
        pass
    return None

async def ask_groq(chat_id, text, image_b64=None):
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
        except:
            last_err="err"
            continue
    chat_stats['errors']+=1
    return f'Ошибка: {last_err}'

async def start_h(update, context):
    user = update.effective_user.first_name
    await update.message.reply_text(f"Привет, {user}! Жми 🎨 Картинка и пиши что рисовать!", reply_markup=MAIN_KB)

async def help_h(update, context):
    await update.message.reply_text("🎨 Картинка -> пишешь 'кота' или 'ртх 5090' и он рисует.", reply_markup=MAIN_KB)

async def clear_h(update, context):
    clear_memory(update.effective_chat.id)
    context.user_data['awaiting_image'] = False
    await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB)

async def about_h(update, context):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    first_str = format_date_short(FIRST_LAUNCH_DATE)
    time_text = format_time_full()
    text = f"🤖 Даун v68 GITHUB\n{info}\n🚀 {first_str}\n{time_text}\n⏱ {uptime} мин\n🎨 Flux SMART BUTTON\n{get_stats_text()}"
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def model_h(update, context):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update, context):
    mins=int((time.time()-chat_stats['start_time'])//60)
    await update.message.reply_text(f"В сети {mins} мин.\n{format_time_full()}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def stats_h(update, context):
    await update.message.reply_text(f"📊 {get_stats_text()}\nПервый запуск: {format_date_short(FIRST_LAUNCH_DATE)}\n{format_time_full()}", reply_markup=MAIN_KB)

async def time_h(update, context):
    await update.message.reply_text(format_time_full(), reply_markup=MAIN_KB)

async def image_h(update, context):
    prompt = ' '.join(context.args) if context.args else ''
    if not prompt:
        context.user_data['awaiting_image'] = True
        await update.message.reply_text("Что нарисовать? Напиши например: кота, rtx 5090 🎨", reply_markup=MAIN_KB)
        return
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    await update.message.reply_text(f"Рисую: {prompt}... ⏳", reply_markup=MAIN_KB)
    img = generate_image_pollinations(prompt)
    if img:
        chat_stats['images']+=1
        await update.message.reply_photo(photo=img, caption=f"Готово! {prompt}", reply_markup=MAIN_KB)
    else:
        await update.message.reply_text("Не удалось, попробуй еще раз.", reply_markup=MAIN_KB)

async def limit_h(update, context):
    args=context.args
    if not args:
        await update.message.reply_text("Используй /limit пароль", reply_markup=MAIN_KB); return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль', reply_markup=MAIN_KB); return
    await update.message.reply_text(f"Всего: {chat_stats['total_requests']}\n{get_stats_text()}\n{format_time_full()}", reply_markup=MAIN_KB)

async def text_h(update, context):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    low = txt.lower()
    if low in ['🎨 картинка', 'картинка'] or ('картинка' in low and len(low) < 15):
        context.user_data['awaiting_image'] = True
        await update.message.reply_text("Что нарисовать? Напиши например: кота, rtx 5090, машину 🎨", reply_markup=MAIN_KB)
        return
    awaiting = context.user_data.get('awaiting_image', False)
    is_image_request = awaiting or any(x in low for x in ['нарисуй', 'сгенерируй картинку', 'сделай картинку', 'нарисовать', 'сгенерируй'])
    if is_image_request:
        prompt = txt
        if awaiting:
            prompt = txt
            context.user_data['awaiting_image'] = False
        else:
            for word in ['нарисуй', 'сгенерируй картинку', 'сделай картинку', 'нарисовать', 'сгенерируй']:
                if word in low:
                    parts = re.split(word, txt, flags=re.IGNORECASE)
                    if len(parts) > 1 and parts[1].strip():
                        prompt = parts[1].strip(' :,-')
                    else:
                        context.user_data['awaiting_image'] = True
                        await update.message.reply_text("Что именно нарисовать? Напиши например: кота", reply_markup=MAIN_KB)
                        return
                    break
        if not prompt or len(prompt) < 2:
            context.user_data['awaiting_image'] = True
            await update.message.reply_text("Что именно нарисовать? Пример: кота, rtx 5090", reply_markup=MAIN_KB)
            return
        await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
        await update.message.reply_text(f"Рисую: {prompt}... ⏳🎨", reply_markup=MAIN_KB)
        img = generate_image_pollinations(prompt)
        if img:
            chat_stats['images']+=1
            await update.message.reply_photo(photo=img, caption=f"Готово! {prompt}", reply_markup=MAIN_KB)
        else:
            await update.message.reply_text("Не вышло, попробуй еще раз.", reply_markup=MAIN_KB)
        return
    if any(x in low for x in ['сколько времени', 'который час', '🕒 время', 'точное время']):
        await update.message.reply_text(format_time_full(), reply_markup=MAIN_KB); return
    if 'инфо' in low: await about_h(update, context); return
    if 'создатель' in low or 'кто тебя сделал' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("Меня создал Максим @MakSon4ikk_228!", reply_markup=MAIN_KB)
        await update.message.reply_text("Вот его профиль 👇", reply_markup=kb_inline); return
    if 'забыть' in low: clear_memory(update.effective_chat.id); context.user_data['awaiting_image']=False; await update.message.reply_text("Память очищена!", reply_markup=MAIN_KB); return
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

async def photo_h(update, context):
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
    except:
        await update.message.reply_text('Ошибка с фото', reply_markup=MAIN_KB)

async def doc_h(update, context):
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
    except:
        await update.message.reply_text('Ошибка', reply_markup=MAIN_KB)

async def sticker_h(update, context):
    await update.message.reply_text('Хех, стикер прикольный!', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v68 GITHUB жив! {format_date_short(FIRST_LAUNCH_DATE)} | {format_time_full()} | {get_stats_text()}"
@app_flask.route('/health')
def health(): return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

def main():
    print('Даун v68 GITHUB запуск')
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
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
    application.add_handler(MessageHandler(filters.Document.IMAGE,doc_h
