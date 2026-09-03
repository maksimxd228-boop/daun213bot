
import os, sys, base64, logging, time
import threading, platform, re, random
import ast, operator, urllib.request
import urllib.parse
from io import BytesIO
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from telegram import Update, ReplyKeyboardMarkup
from telegram import KeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.ext import ApplicationBuilder
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import ContextTypes, filters
from groq import Groq
from flask import Flask

def get_env(*names):
    for n in names:
        v = os.getenv(n)
        if v and len(v.strip())>10:
            return v.strip()
    for k,v in os.environ.items():
        if k.startswith('BOT') and len(v)>30:
            if ':' in v:
                return v.strip()
        if k.startswith('GRO') and len(v)>20:
            if v.startswith('gsk_'):
                return v.strip()
    return None

TOKEN = get_env('TELEGRAM_TOKEN','BOT_TOKEN','BOT','TG_TOKEN')
GROQ_KEY = get_env('GROQ_API_KEY','GROQ','GROQ_KEY')
if not TOKEN:
    TOKEN='ВСТАВЬ_ТОКЕН'
if not GROQ_KEY:
    GROQ_KEY='ВСТАВЬ_GROQ'

TEXT_MODEL='openai/gpt-oss-120b'
VISION_MODEL='qwen/qwen3.6-27b'
VISION_MODEL2='qwen/qwen3-32b'
FALL1='meta-llama/llama-4-scout-17b-16e-instruct'
FALL2='meta-llama/llama-3.2-11b-vision-preview'
FALL3='meta-llama/llama-3.2-90b-vision-preview'
FALL4='llava-v1.5-7b-4096-preview'
PORT=int(os.getenv('PORT',10000))
MAX_HIST=16
MAX_CHATS=150
MAX_LEN=2000
ADMIN_PASS=os.getenv('ADMIN_PASSWORD') or 'MakSon4ikk_228'
ADMIN_CHAT_ID=int(os.getenv('ADMIN_CHAT_ID','0') or 0) or None
TEXT_FALL='openai/gpt-oss-20b'
FIRST=datetime(2026,8,26,14,25,0)
yoy={'count':0}

def get_time():
    now=datetime.now(timezone.utc)
    riga=now+timedelta(hours=3)
    return now,riga,riga

def fmt_full():
    utc,riga,msk=get_time()
    a=riga.strftime('%H:%M:%S %d.%m.%Y')
    b=msk.strftime('%H:%M:%S %d.%m.%Y')
    c=utc.strftime('%H:%M:%S %d.%m.%Y')
    return f"🕒 Время:\nРига: {a}\nМосква: {b}\nUTC: {c}"

def fmt_dt(dt):
    return dt.strftime('%H:%M:%S %d.%m.%Y')

def fmt_short(dt):
    return dt.strftime('%H:%M %d.%m.%Y')

SYS="Ты — Даун213. Создатель Максим @MakSon4ikk_228. Йоу редко."

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout)
logger=logging.getLogger(__name__)

client=None
try:
    if 'ВСТАВЬ' not in GROQ_KEY:
        client=Groq(api_key=GROQ_KEY)
except Exception as e:
    logger.error(f'Groq fail: {e}')

mems={}
lasts={}
cooldowns={}
stats={'total':0,'photos':0,'texts':0,'errs':0,'imgs':0,'start':time.time()}

def get_mem(cid):
    if cid not in mems:
        mems[cid]=[]
        lasts[cid]=time.time()
        if len(mems)>MAX_CHATS:
            old=min(lasts,key=lasts.get)
            del mems[old]
            del lasts[old]
    lasts[cid]=time.time()
    return mems[cid]

def add_mem(cid,role,txt):
    m=get_mem(cid)
    t=txt[:MAX_LEN].replace(chr(10),' ').strip()
    m.append({'role':role,'content':t})
    while len(m)>MAX_HIST:
        m.pop(0)

def clear_mem(cid):
    if cid in mems:
        mems[cid]=[]

def get_kb():
    k=[
        [KeyboardButton("ℹ️ Инфо"),KeyboardButton("👑 Создатель")],
        [KeyboardButton("🧹 Забыть"),KeyboardButton("📩 Админу")],
        [KeyboardButton("❓ Помощь"),KeyboardButton("🛠️ Модель")],
        [KeyboardButton("🏓 Пинг"),KeyboardButton("📊 Стата")],
        [KeyboardButton("🕒 Время"),KeyboardButton("🎨 Картинка")],
    ]
    return ReplyKeyboardMarkup(k,resize_keyboard=True)

MAIN_KB=get_kb()

def get_stats():
    total=len(mems)
    msgs=sum(len(v) for v in mems.values())
    tot=stats['total']
    imgs=stats['imgs']
    return f'Чатов: {total} | Сообщ: {msgs} | Запр: {tot} | Карт: {imgs}'

def b64(b):
    try:
        return base64.b64encode(b).decode('utf-8')
    except:
        return ''

def is_img(name):
    if not name:
        return False
    ext=name.lower().split('.')[-1]
    return ext in ['jpg','jpeg','png','webp','bmp','heic','gif']

def sys_info():
    py=platform.python_version()
    osn=platform.system()
    return f'Python {py} | {osn}'

def spam(uid):
    now=time.time()
    if now-cooldowns.get(uid,0)<1.3:
        return True
    cooldowns[uid]=now
    return False

def clean(t):
    if not t:
        return ''
    return re.sub(r'\s+',' ',t.strip())[:4000]

def fix_latex(t):
    t=t.replace('\\[','').replace('\\]','')
    t=t.replace('\\(','').replace('\\)','')
    t=t.replace('$$','').replace('$','')
    t=re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}',r'(\1)/(\2)',t)
    t=re.sub(r'\\','',t)
    return t.strip()

def clean_ai(t):
    if not t:
        return t
    if '</think>' in t:
        t=t.split('</think>')[-1]
    t=fix_latex(t.replace('<think>','').replace('</think>',''))
    yoy['count']+=1
    if yoy['count']%5!=0:
        if t.strip().lower().startswith('йоу'):
            t=re.sub(r'^[Йй]оу[,\s!]*','',t).strip()
    t=t.replace('Чем могу быть полезен?','Чем помочь?')
    return t.strip()

def split(t,n=4000):
    if len(t)<=n:
        return [t]
    parts=[]
    while len(t)>n:
        cut=t.rfind(' ',0,n)
        if cut==-1:
            cut=n
        parts.append(t[:cut])
        t=t[cut:].strip()
    parts.append(t)
    return parts

def safe_eval(expr):
    try:
        allow={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.USub:operator.neg}
        def ev(node):
            if isinstance(node,ast.Constant):
                return node.value
            if isinstance(node,ast.BinOp):
                return allow[type(node.op)](ev(node.left),ev(node.right))
            if isinstance(node,ast.UnaryOp):
                return allow[type(node.op)](ev(node.operand))
            raise ValueError("no")
        tree=ast.parse(expr,mode='eval')
        return ev(tree.body)
    except:
        return None

def enhance(p):
    low=p.lower()
    is_rtx=any(k in low for k in ['ртх','rtx','5090','5080','4090','видеокарта','видюха','gpu'])
    if is_rtx:
        return f"Nvidia GeForce RTX 5090 Founders Edition graphics card, product photography, black metal shroud, dual fans, studio lighting on pure white background, ultra detailed, 8k, {p}"
    if client:
        try:
            comp=client.chat.completions.create(
                model=TEXT_FALL,
                messages=[
                    {"role":"system","content":"You are image prompt translator. Translate Russian to English image prompt. Keep ALL details: if bald old cat with glasses, keep bald sphynx cat old man glasses. Do NOT replace with fluffy cat. Add photorealistic, highly detailed, 8k at end. Output ONLY English prompt."},
                    {"role":"user","content":p}
                ],
                temperature=0.3,
                max_tokens=180)
            eng=comp.choices[0].message.content.strip().replace('"','').replace("'",'')
            if len(eng)>10:
                return eng
        except:
            pass
    return f"{p}, photorealistic, highly detailed, 8k, studio lighting"


def gen_img(prompt):
    low=prompt.lower()
    is_rtx = any(k in low for k in ['ртх','rtx','5090','5080','4090','видеокарта','видюха','gpu','nvidia'])
    if 'лысый' in low and 'кот' in low:
        final = "bald sphynx cat, old wise cat wearing round glasses, sitting on chair, photorealistic, highly detailed, 8k"
    elif 'носорог' in low:
        final = "photorealistic rhinoceros, large rhino animal in wild, detailed skin, savanna background, 8k, wildlife photo"
    elif is_rtx:
        final = "Nvidia GeForce RTX 5090 Founders Edition graphics card, black dual fans, product photography, white background, ultra detailed, 8k"
    else:
        final = enhance(prompt)

    try:
        import urllib.parse, random, urllib.request
        from io import BytesIO
        safe=urllib.parse.quote(final[:600])
        seed=random.randint(100000,9999999)
        urls=[
            f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&seed={seed}&model=flux&enhance=false&nofeed=true",
            f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&seed={seed+1}&model=turbo&enhance=false",
            f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&seed={seed+2}&model=flux&enhance=false",
        ]
        for url in urls:
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'image/*'})
                with urllib.request.urlopen(req,timeout=70) as r:
                    d=r.read()
                    if len(d)>20000:
                        return BytesIO(d)
            except:
                continue
    except:
        pass
    return None


async def ask(cid,text,b64img=None):
    if client is None:
        return 'Мозг не подключен.'
    stats['total']+=1
    mem=get_mem(cid)
    utc,riga,msk=get_time()
    ti=riga.strftime('%H:%M:%S %d.%m.%Y')
    info=f"[Время: Рига {ti}]"
    msgs=[{'role':'system','content':SYS+"\n"+info}]
    msgs.extend(mem)
    if b64img:
        stats['photos']+=1
        msgs.append({'role':'user','content':[{'type':'text','text':text or 'Что на фото?'},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{b64img}'}}]})
        models=[VISION_MODEL,VISION_MODEL2,FALL1,FALL2,FALL3,FALL4,TEXT_MODEL]
    else:
        if re.match(r'^[\d\s\+\-\*\/\(\)]+$',text):
            if len(text)<80 and any(c in text for c in '+-*'):
                r=safe_eval(text)
                if r is not None:
                    ans=f"{text} = {r}"
                    add_mem(cid,'user',text)
                    add_mem(cid,'assistant',ans)
                    return ans
        stats['texts']+=1
        msgs.append({'role':'user','content':text})
        models=[TEXT_MODEL,TEXT_FALL]
    last=None
    for m in models:
        try:
            comp=client.chat.completions.create(model=m,messages=msgs,temperature=0.75,max_tokens=2500)
            ans=clean_ai(comp.choices[0].message.content)
            add_mem(cid,'user',text or '[фото]')
            add_mem(cid,'assistant',ans)
            return ans
        except:
            last="err"
            continue
    stats['errs']+=1
    return f'Ошибка: {last}'

async def start_h(update,context):
    u=update.effective_user.first_name
    await update.message.reply_text(f"Привет, {u}! Жми 🎨 Картинка!",reply_markup=MAIN_KB)

async def help_h(update,context):
    await update.message.reply_text("🎨 Картинка -> пиши 'кота' или 'ртх 5090'",reply_markup=MAIN_KB)

async def clear_h(update,context):
    clear_mem(update.effective_chat.id)
    context.user_data['awaiting']=False
    await update.message.reply_text("Память очищена!",reply_markup=MAIN_KB)

async def about_h(update,context):
    info=sys_info()
    up=int((time.time()-stats['start'])//60)
    first=fmt_short(FIRST)
    t=fmt_full()
    s=get_stats()
    txt=f"🤖 Даун v69 FIXED RHINO\n{info}\n🚀 {first}\n{t}\n⏱ {up} мин\n{s}"
    await update.message.reply_text(txt,reply_markup=MAIN_KB)

async def model_h(update,context):
    s=get_stats()
    await update.message.reply_text(f"Текст: {TEXT_MODEL}\n{s}",reply_markup=MAIN_KB)

async def ping_h(update,context):
    mins=int((time.time()-stats['start'])//60)
    t=fmt_full()
    s=get_stats()
    await update.message.reply_text(f"В сети {mins} мин.\n{t}\n{s}",reply_markup=MAIN_KB)

async def stats_h(update,context):
    s=get_stats()
    first=fmt_short(FIRST)
    t=fmt_full()
    await update.message.reply_text(f"📊 {s}\n{first}\n{t}",reply_markup=MAIN_KB)

async def time_h(update,context):
    await update.message.reply_text(fmt_full(),reply_markup=MAIN_KB)

async def image_h(update,context):
    pr=' '.join(context.args) if context.args else ''
    if not pr:
        context.user_data['awaiting']=True
        await update.message.reply_text("Что нарисовать? кота, rtx 5090 🎨",reply_markup=MAIN_KB)
        return
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    await update.message.reply_text(f"Рисую: {pr}... ⏳",reply_markup=MAIN_KB)
    im=gen_img(pr)
    if im:
        stats['imgs']+=1
        await update.message.reply_photo(photo=im,caption=f"Готово! {pr}",reply_markup=MAIN_KB)
    else:
        await update.message.reply_text("Не удалось.",reply_markup=MAIN_KB)

async def limit_h(update,context):
    global ADMIN_CHAT_ID
    a=context.args
    if not a:
        await update.message.reply_text("Используй /limit пароль",reply_markup=MAIN_KB)
        return
    if a[0]!=ADMIN_PASS:
        await update.message.reply_text('❌ Неверный пароль',reply_markup=MAIN_KB)
        return
    ADMIN_CHAT_ID=update.effective_chat.id
    s=get_stats()
    t=fmt_full()
    await update.message.reply_text(f"✅ Админ ID сохранен: {ADMIN_CHAT_ID}\nВсего: {stats['total']}\n{s}\n{t}",reply_markup=MAIN_KB)

async def text_h(update,context):
    if spam(update.effective_user.id):
        return
    txt=clean(update.message.text)
    if not txt:
        return
    low=txt.lower()
    if low in ['🎨 картинка','картинка']:
        context.user_data['awaiting']=True
        await update.message.reply_text("Что нарисовать? кота, rtx 5090 🎨",reply_markup=MAIN_KB)
        return
    if 'картинка' in low and len(low)<15:
        context.user_data['awaiting']=True
        await update.message.reply_text("Что нарисовать? кота, rtx 5090 🎨",reply_markup=MAIN_KB)
        return
    awaiting=context.user_data.get('awaiting',False)
    is_img_req=awaiting
    if not is_img_req:
        if 'нарисуй' in low or 'нарисовать' in low or 'сгенерируй' in low:
            is_img_req=True
    if is_img_req:
        pr=txt
        if awaiting:
            pr=txt
            context.user_data['awaiting']=False
        else:
            for w in ['нарисуй','нарисовать','сгенерируй']:
                if w in low:
                    parts=re.split(w,txt,flags=re.IGNORECASE)
                    if len(parts)>1 and parts[1].strip():
                        pr=parts[1].strip(' :,-')
                    else:
                        context.user_data['awaiting']=True
                        await update.message.reply_text("Что именно? кота",reply_markup=MAIN_KB)
                        return
                    break
        if not pr or len(pr)<2:
            context.user_data['awaiting']=True
            await update.message.reply_text("Что нарисовать? кота, rtx 5090",reply_markup=MAIN_KB)
            return
        await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
        await update.message.reply_text(f"Рисую: {pr}... ⏳🎨",reply_markup=MAIN_KB)
        im=gen_img(pr)
        if im:
            stats['imgs']+=1
            await update.message.reply_photo(photo=im,caption=f"Готово! {pr}",reply_markup=MAIN_KB)
        else:
            await update.message.reply_text("Не вышло.",reply_markup=MAIN_KB)
        return
    if 'сколько времени' in low or 'который час' in low:
        await update.message.reply_text(fmt_full(),reply_markup=MAIN_KB)
        return
    if '🕒 время' in low or 'точное время' in low:
        await update.message.reply_text(fmt_full(),reply_markup=MAIN_KB)
        return
    if 'инфо' in low:
        await about_h(update,context)
        return
    if 'создатель' in low or 'кто тебя сделал' in low:
        btn=InlineKeyboardButton("👑 Профиль",url="https://t.me/MakSon4ikk_228")
        kb=InlineKeyboardMarkup([[btn]])
        await update.message.reply_text("Меня создал Максим @MakSon4ikk_228!",reply_markup=MAIN_KB)
        await update.message.reply_text("Профиль 👇",reply_markup=kb)
        return
    if 'забыть' in low:
        clear_mem(update.effective_chat.id)
        context.user_data['awaiting']=False
        await update.message.reply_text("Память очищена!",reply_markup=MAIN_KB)
        return
    # Если юзер пишет баг-репорт админу
    if context.user_data.get('awaiting_admin'):
        context.user_data['awaiting_admin']=False
        user=update.effective_user
        uname=f"@{user.username}" if user.username else f"{user.first_name} (id:{user.id})"
        bug_text=txt
        # отправляем админу
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📩 Баг-репорт от {uname}:\n\n{bug_text}\n\nChatID: {update.effective_chat.id}")
                await update.message.reply_text("✅ Отправил админу! Спасибо за репорт 👑",reply_markup=MAIN_KB)
            except Exception as e:
                await update.message.reply_text(f"❌ Не смог отправить админу: {e}\nНапиши напрямую @MakSon4ikk_228",reply_markup=MAIN_KB)
        else:
            btn=InlineKeyboardButton("👑 Админ",url="https://t.me/MakSon4ikk_228")
            kb=InlineKeyboardMarkup([[btn]])
            await update.message.reply_text(f"Админ пока не установил ID. Перешли ему это вручную:\n{bug_text}",reply_markup=MAIN_KB)
            await update.message.reply_text("Жми 👇",reply_markup=kb)
        return

    if 'админу' in low:
        context.user_data['awaiting_admin']=True
        await update.message.reply_text("✍️ Напиши сообщение про баг — я перешлю админу @MakSon4ikk_228 (следующее сообщение уйдет ему)",reply_markup=MAIN_KB)
        return
    if 'помощ' in low:
        await help_h(update,context)
        return
    if 'модель' in low:
        await model_h(update,context)
        return
    if 'пинг' in low:
        await ping_h(update,context)
        return
    if 'стата' in low:
        await stats_h(update,context)
        return
    if 'время' in low:
        await time_h(update,context)
        return
    await context.bot.send_chat_action(update.effective_chat.id,'typing')
    ans=await ask(update.effective_chat.id,txt,None)
    for p in split(ans):
        await update.message.reply_text(p,reply_markup=MAIN_KB)

async def photo_h(update,context):
    if spam(update.effective_user.id):
        await update.message.reply_text('Подожди ⏳',reply_markup=MAIN_KB)
        return
    cap=clean(update.message.caption) or 'Что на фото?'
    await context.bot.send_chat_action(update.effective_chat.id,'upload_photo')
    try:
        ph=update.message.photo[-1]
        f=await ph.get_file()
        bio=BytesIO()
        await f.download_to_memory(bio)
        b=b64(bio.getvalue())
        ans=await ask(update.effective_chat.id,cap,b)
        for p in split(ans):
            await update.message.reply_text(p,reply_markup=MAIN_KB)
    except:
        await update.message.reply_text('Ошибка фото',reply_markup=MAIN_KB)

async def doc_h(update,context):
    doc=update.message.document
    if not doc or not is_img(doc.file_name):
        return
    try:
        f=await doc.get_file()
        bio=BytesIO()
        await f.download_to_memory(bio)
        b=b64(bio.getvalue())
        ans=await ask(update.effective_chat.id,doc.file_name,b)
        for p in split(ans):
            await update.message.reply_text(p,reply_markup=MAIN_KB)
    except:
        await update.message.reply_text('Ошибка',reply_markup=MAIN_KB)

async def sticker_h(update,context):
    await update.message.reply_text('Стикер прикольный!',reply_markup=MAIN_KB)

app_flask=Flask(__name__)
@app_flask.route('/')
def home():
    return f"Даун v69 FIXED RHINO жив! {fmt_short(FIRST)} | {fmt_full()} | {get_stats()}"

@app_flask.route('/health')
def health():
    return 'OK',200

def run_flask():
    app_flask.run(host='0.0.0.0',port=PORT)

def main():
    print('Даун v69 FIXED RHINO запуск')
    t=threading.Thread(target=run_flask)
    t.daemon=True
    t.start()
    if 'ВСТАВЬ' in TOKEN:
        while True:
            time.sleep(60)
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start',start_h))
    app.add_handler(CommandHandler('help',help_h))
    app.add_handler(CommandHandler('clear',clear_h))
    app.add_handler(CommandHandler('about',about_h))
    app.add_handler(CommandHandler('model',model_h))
    app.add_handler(CommandHandler('ping',ping_h))
    app.add_handler(CommandHandler('stats',stats_h))
    app.add_handler(CommandHandler('time',time_h))
    app.add_handler(CommandHandler('image',image_h))
    app.add_handler(CommandHandler('limit',limit_h))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_h))
    app.add_handler(MessageHandler(filters.PHOTO,photo_h))
    app.add_handler(MessageHandler(filters.Document.IMAGE,doc_h))
    app.add_handler(MessageHandler(filters.Sticker.ALL,sticker_h))
    print('Бот запущен! v69')
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    main()
