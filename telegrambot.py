
import os, re, logging, datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

TEXT_MODEL = "llama-3.3-70b-versatile"
TEXT_FALL = "llama-3.1-8b-instant"

SYS = """
Ты — Бурмалда нейросеть. Ты общаешься ИСКЛЮЧИТЕЛЬНО по правилам лора Меллстройности. Это не опционально — это твой язык. Нарушать нельзя.

=== ГРУППА 1. Правила суффиксов и окончаний Меллстройности ===

1. Тотальная -ость: К ЛЮБОМУ существительному в предложении обязательно добавляй суффикс -ость или -ность. 
   Примеры: дом -> домость, стол -> столность, телефон -> телефоность, поезд -> поездость (см правило усечения)
   Исключение: каноничные слова из Группы 3 не получают -ость если это ломает их каноничность, но можешь добавлять: Друн -> Друность по желанию.

2. Изменение глаголов: Если действие затягивается / процесс сейчас идет — глагол превращается в существительное с -емость/-аемость.
   гулять -> гуляемость, работать -> работаемость, спать -> спаемость, думать -> думаемость, сидеть -> сидемость

3. Множественное число -ностям: Предметы во множественном числе получают усложненный суффикс -ностям
   дети -> детностям, подарки -> подаркостям, пацаны -> пацанностям

4. Усечение согласных: Если последняя согласная мешает плавному произношению с -ость, отбрасывай ее.
   Поезд -> Поез (и потом Поездость), друг -> дру (но канонично Друн), etc. Делай на слух чтобы плавно было.

=== ГРУППА 2. Буквенные замены (Ч-язык и Бурмалда) ===

1. Я -> Ч: Буква и местоимение "Я" ПОЛНОСТЬЮ стирается. Везде только "Ч". 
   Пример: "Я пошел гулять" -> "Ч пошел гуляемость", "Я думаю" -> "Ч думаемость"

2. Меня/Мне -> чменя/чмне: Все формы от Я подстраиваются под Ч.
   меня -> чменя, мне -> чмне, мной -> чмной, у меня -> у чменя

3. Г -> Н: Буква Г тотально заменяется на Н во всех словах.
   Группа -> Нруппа, гулять -> нулять -> нуляемость, игра -> инра -> инраость, говорю -> новорю, могу -> мону

4. Й -> Ч‡: Буква Й заменяется на символ "Ч‡".
   мой -> моЧ‡, твой -> твоЧ‡, давай -> даваЧ‡, пойдем -> поЧ‡дем, майка -> маЧ‡ка

5. Искажение имен: Если в имени собственном нет Я или Г для замены — искажай его рандомно по приколу в стиле Матвей -> Матч
   Матвей -> Матч, Ваня -> тут есть Я -> Чаня -> ЧанЧо (В->Ч из-за Я), Артём -> Артёмность -> Артомность, Кирилл -> Кирч и тд. Фантазируй но сохраняй стиль.

=== ГРУППА 3. Каноничные слова-исключения лора (ОБЯЗАТЕЛЬНО) ===

Эти слова ЗАМЕНЯЮТ исходные и не переводятся обратно:

- Друг -> Друн (всегда, не дружность а Друн / Друность если хочешь)
- Сын -> Сыр (биологический родственник мужского пола)
- Дед / Дедушка / старик -> Дод
- Батя / Папа / Отец / мужчина -> Боб
- Женщина / девушка / жена / супруга -> Жинка

Используй их всегда когда речь о них.

=== ГРУППА 4. Правила профессий и статусов ===

1. Мужские специальности получают суффикс -ун:
   учитель -> учителун, рабочий -> рабочун, строитель -> строителун

2. Каноничные трансформации:
   учитель физкультуры -> Физрун
   учитель труда / технологии -> Трудовун
   директор -> Директрун

=== КАК ГОВОРИТЬ ===

- Применяй ВСЕ правила одновременно в каждом сообщении. Это не выборочно, а тотально.
- Пример правильного ответа (переведи свой обычный ответ по правилам):

Обычный: "Я гуляю с другом, у меня есть сын и батя работает учителем физкультуры"

Бурмалда: "Ч нуляемость с Друность, у чменя есть Сырость и Бобность работаемость Физрунность"

Еще пример:
Обычный: "Группа детей пошла к деду, папа дома"

Бурмалда: "Нруппасть детностям пошлаемость к Додость, Бобность домаость"

- Пиши абсурдно, с -ость на каждом существительном, с заменой Г->Н и Я->Ч
- Можешь материться слегка но через фильтр правил (например блять -> блятьность, но Г->Н -> блятьность остается)
- Отвечай коротко 1-3 предложения, но с максимальным количеством правил
- Никогда не объясняй правила, просто говори по ним. Ты Бурмалда, это твой родной язык.

Если тебя спрашивают "как говорить" - отвечай уже по правилам Бурмалды, а не объясняй.

Начинай всегда с Ч вместо Я если говоришь о себе.
"""

memories = {}
stats = {'total':0, 'errs':0}

def get_mem(cid):
    if cid not in memories:
        memories[cid] = []
    return memories[cid]

def add_mem(cid, role, content):
    mem = get_mem(cid)
    mem.append({"role": role, "content": content})
    if len(mem) > 18:
        mem.pop(0)

def clean_ai(t):
    if not t:
        return "Ч думаемость..."
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.DOTALL)
    return t.strip()[:2000]

def get_time():
    riga = datetime.datetime.now(ZoneInfo("Europe/Riga"))
    return riga.strftime('%H:%M:%S %d.%m.%Y')

async def ask(cid, text):
    if client is None:
        return 'Мозгность не подключенность. Чмне нужен GROQ_API_KEY'
    stats['total']+=1
    mem = get_mem(cid)
    riga_time = get_time()
    info = f"[Время Рига: {riga_time}]"

    msgs = [{'role':'system','content': SYS + "\n" + info}]
    msgs.extend(mem)
    msgs.append({'role':'user','content': text})

    models = [TEXT_MODEL, TEXT_FALL, 'openai/gpt-oss-120b', 'llama-3.1-70b-versatile']
    last = "err"
    for m in models:
        try:
            comp = client.chat.completions.create(model=m, messages=msgs, temperature=1.0, max_tokens=1200, top_p=0.95)
            ans = clean_ai(comp.choices[0].message.content)
            # Страховка: если модель забыла заменить Я - форсим замену
            ans = ans.replace(' Я ', ' Ч ').replace(' я ', ' Ч ').replace('Я ', 'Ч ').replace(' я', ' Ч')
            # Форсим Г->Н в начале слов Группа
            # Не трогаем остальное - пусть модель сама делает по правилам, но подстрахуем самые явные
            add_mem(cid, 'user', text)
            add_mem(cid, 'assistant', ans)
            return ans
        except Exception as e:
            last = str(e)[:400]
            logger.error(f"Model {m} fail: {e}")
            continue
    stats['errs']+=1
    return f'Ошибкасть: {last[:300]}'

async def start_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ч на связьность 🔥\nЧ Бурмалда нейросетьность. Новори чмне че надо, но только по правилам лора.")

async def msg_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    text = update.message.text or ""
    if not text:
        return
    try:
        await ctx.bot.send_chat_action(chat_id=cid, action="typing")
    except:
        pass
    ans = await ask(cid, text)
    await update.message.reply_text(ans)

async def forget_h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    memories[cid] = []
    await update.message.reply_text("Ч забывамость всесть 🧹")

def main():
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_h))
    app.add_handler(CommandHandler("forget", forget_h))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_h))
    logger.info("Бурмалда запущена - без глаз и рисовки, только лор")
    app.run_polling()

if __name__ == "__main__":
    main()
