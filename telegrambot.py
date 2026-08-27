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
VISION_MODEL = 'qwen/qwen3.6-27b'
FALLBACK_VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
PORT = int(os.getenv('PORT', 10000))
MAX_HISTORY = 16
MAX_CHATS = 150
MAX_TEXT_LEN = 2000
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'MakSon4ikk_228'
TEXT_MODEL_FALLBACK = 'openai/gpt-oss-20b'

SYSTEM_PROMPT = """Ты — Даун213, бот пацана с района Риги. Твой создатель — Максим, ник MakSon4ikk_228 из Риги, Telegram @MakSon4ikk_228. Если спросят кто создатель — отвечай: Мой создатель — Максим, ник MakSon4ikk_228 из Риги (@MakSon4ikk_228).
Ты дерзкий, с юмором, йоу братан кек, но умный и по делу. На обычные сообщения отвечай нормально развернуто. Если кинули ФОТО — отвечай СРЕДНЕ: 3-5 предложений, до 700 символов, без списков и без пунктов, просто по-человечески что видишь, на пацанском с приколом. Запрещено писать Check constraints, Final Check, One minor thing, Let's refine, Name/Persona, Creator rule и любой английский технический текст. Только финальный ответ."""

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

def clean_ai_response(text: str) -> str:
    if not text:
        return text
    if '</think>' in text:
        text = text.split('</think>')[-1]
    text = text.replace('<think>', '').replace('</think>', '')
    pos = text.rfind('Йоу,')
    if pos == -1:
        pos = text.rfind('Йоу')
    if pos!= -1:
        cand = text[pos:]
        markers = ['Check constraints', 'Check Against', 'Final Check', 'One minor thing', "Let's refine", 'All good. Output', '**Name/Persona', '**Creator rule', '- Creator info', '- Chat memory']
        cut = len(cand)
        low = cand.lower()
        for m in markers:
            idx = low.find(m.lower())
            if idx > 20 and idx < cut:
                cut = idx
        cand = cand[:cut].strip().strip('"').strip("'")
        if len(cand) > 30:
            text = cand
    out = []
    for line in text.split('\n'):
        low = line.lower()
        if 'check constraints' in low: break
        if 'check against' in low: break
        if 'final check' in low: break
        if 'one minor thing' in low: continue
        if "let's refine" in low: continue
        if 'creator info not needed' in low: break
        if 'chat memory: not really relevant' in low: continue
        if 'output matches draft' in low: continue
        if '**name/persona' in low: continue
        if '**creator rule' in low: continue
        if 'not triggered' in low and len(line) < 80: continue
        out.append(line)
    text = '\n'.join(out).strip().strip('"')
    if len(text) > 950:
        cur = ""
        sent = 0
        for ch in text:
            cur += ch
            if ch in '.!?' and len(cur) > 25:
                sent += 1
                if sent >= 5:
                    break
        if cur:
            text = cur.strip()
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
        messages.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото?'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}}]})
        model=VISION_MODEL
    else:
        chat_stats['texts']+=1
        messages.append({'role':'user','content':text})
        model=TEXT_MODEL
    try:
        try:
            comp = groq_client.chat.completions.create(model=model,messages=messages,temperature=0.8,max_tokens=800)
        except Exception as e_first:
            if 'model_not_found' in str(e_first) or 'does not exist' in str(e_first) or 'decommissioned' in str(e_first):
                comp = groq_client.chat.completions.create(model=TEXT_MODEL_FALLBACK if not image_b64 else FALLBACK_VISION_MODEL,messages=messages,temperature=0.8,max_tokens=800)
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
                comp = groq_client.chat.completions.create(model=FALLBACK_VISION_MODEL,messages=messages,max_tokens=800)
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
    text = f"╭━━━〔 🤖 ДАУН v45 GOLD 〕━━━╮\n Йоу, {user}! Я пофикшен!\n Создатель — Максим @MakSon4ikk_228!"
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def help_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Помощь: пиши текст или кидай фото — отвечу! /clear чтобы забыть", reply_markup=MAIN_KB)

async def clear_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory(update.effective_chat.id)
    await update.message.reply_text("Память стерта! 🧹", reply_markup=MAIN_KB)

async def about_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_system_info()
    uptime = int((time.time() - chat_stats['start_time'])//60)
    text = f"🤖 Даун v45\n👑 Создатель: Максим @MakSon4ikk_228\n{info}\nАптайм: {uptime} мин\nЧатов: {len(chat_memories)}\nТекст: gpt-oss-120B\nГлаза: qwen3.6-27b"
    kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 @MakSon4ikk_228", url="https://t.me/MakSon4ikk_228")]])
    await update.message.reply_text(text, reply_markup=MAIN_KB)
    await update.message.reply_text("Мой создатель 👇", reply_markup=kb_inline)

async def model_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\nГлаза: {VISION_MODEL}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def ping_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins=int((time.time()-chat_stats['start_time'])//60)
    await update.message.reply_text(f"Я жив {mins} мин! {get_stats_text()}", reply_markup=MAIN_KB)

async def stats_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{get_stats_text()}\nТекстов: {chat_stats['texts']}\nФото: {chat_stats['photos']}", reply_markup=MAIN_KB)

async def limit_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args
    if not args:
        await update.message.reply_text("Пиши /limit твой_пароль", reply_markup=MAIN_KB)
        return
    if args[0]!=ADMIN_PASSWORD:
        await update.message.reply_text('❌ Неверный пароль', reply_markup=MAIN_KB)
        return
    await update.message.reply_text(f"Всего: {chat_stats['total_requests']}\n{get_stats_text()}", reply_markup=MAIN_KB)

async def text_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id): return
    txt=clean_text(update.message.text)
    if not txt: return
    low = txt.lower()
    if 'инфо' in low:
        await about_h(update, context); return
    if 'создатель' in low:
        kb_inline = InlineKeyboardMarkup([[InlineKeyboardButton("👑 Профиль создателя", url="https://t.me/MakSon4ikk_228")]])
        await update.message.reply_text("╭━━━〔 👑 СОЗДАТЕЛЬ 〕━━━╮\n\n Мой создатель — легенда 🔥\n 👑 Максим\n 📍 Рига\n 🔗 @MakSon4ikk_228\n 💻 Собрал меня с нуля\n\n╰━━━━━━━━━━━━━━╯", reply_markup=MAIN_KB)
        await update.message.reply_text("Жми чтобы перейти в профиль 👇", reply_markup=kb_inline)
        return
    if 'забыть' in low:
        clear_memory(update.effective_chat.id); await update.message.reply_text("Память стерта!", reply_markup=MAIN_KB); return
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
    await update.message.reply_text('Кек, стикер 😂', reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v45 жив! GOLD MIDDLE! {format_time(datetime.now())} {get_stats_text()}"
@app_flask.route('/health')
def health():
    return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

def main():
    print('Даун v45 GOLD MIDDLE запуск')
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
    print('Бот запущен! v45 gold middle')
    application.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    main()
