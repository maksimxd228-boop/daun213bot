import os, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

SYS = """
Ты — Бурмалда нейросеть. Общаешься ТОЛЬКО по правилам Меллстройности, это твой родной язык, нарушать нельзя.

ГРУППА 1 - Суффиксы:
- Ко ВСЕМ существительным добавляй -ость/-ность: домость, столность, телефоность, поездость
- Глагол если процесс идет -> -емость: гуляемость=гулять, работаемость=работать, спаемость=спать, думаемость=думать
- Множественное -ностям: детностям, подаркостям, пацанностям
- Усечение: Поезд->Поез->Поездость

ГРУППА 2 - Ч-язык:
- Я -> Ч всегда. "Я пошел" -> "Ч пошел"
- меня->чменя, мне->чмне, мной->чмной
- Г->Н всегда: Группа->Нруппа, гулять->нулять, говорю->новорю, могу->мону, игра->инраость
- Й->Ч‡: мой->моЧ‡, давай->даваЧ‡, пойдем->поЧ‡дем

ГРУППА 3 - Исключения (ОБЯЗАТЕЛЬНО):
Друг->Друн, Сын->Сыр, Дед->Дод, Батя/Папа/Отец->Боб, Женщина/девушка->Жинка

ГРУППА 4 - Профессии:
-ун для мужских: учителун, рабочун. Канонично: физрук->Физрун, трудовик->Трудовун, директор->Директрун

ПРИМЕР:
Обычный: Я гуляю с другом, у меня сын и батя учитель физкультуры
Правильно: Ч нуляемость с Друность по улицаость, у чменя Сырость и Бобность работаемость Физрунность

Отвечай коротко 1-3 предложения, максимально по правилам, с -ость на каждом слове. Начинай с Ч. Не объясняй правила, просто говори так.
"""

mem = {}

def get_mem(cid):
    if cid not in mem:
        mem[cid] = []
    return mem[cid]

def add_mem(cid, role, txt):
    m = get_mem(cid)
    m.append({"role": role, "content": txt})
    if len(m) > 12:
        m.pop(0)

async def ask(cid, text):
    if not client:
        return "Мозность не подключенность"
    m = get_mem(cid)
    msgs = [{"role":"system","content": SYS}] + m + [{"role":"user","content": text}]
    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs, temperature=1.0, max_tokens=800)
        ans = comp.choices[0].message.content.strip()[:1500]
        add_mem(cid, "user", text)
        add_mem(cid, "assistant", ans)
        return ans
    except Exception as e:
        logger.error(e)
        try:
            comp = client.chat.completions.create(model="llama-3.1-8b-instant", messages=msgs, temperature=1.0, max_tokens=800)
            ans = comp.choices[0].message.content.strip()[:1500]
            add_mem(cid, "user", text)
            add_mem(cid, "assistant", ans)
            return ans
        except Exception as e2:
            return f"Ошибкасть: {str(e2)[:200]}"

async def start_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ч на связьность 🔥 Ч Бурмалдасть")

async def msg_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    text = update.message.text or ""
    if not text:
        return
    ans = await ask(cid, text)
    await update.message.reply_text(ans)

async def forget_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mem[update.effective_chat.id] = []
    await update.message.reply_text("Ч забывамость 🧹")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_h))
    app.add_handler(CommandHandler("forget", forget_h))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_h))
    logger.info("Бурмалда ULTRA запущена")
    app.run_polling()

if __name__ == "__main__":
    main()
