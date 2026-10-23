import os, time, logging, requests
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    logger.error("No BOT_TOKEN")
    exit(1)

client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SYS = """
Ты — Бурмалда нейросеть. Общаешься ТОЛЬКО по правилам Меллстройности, это твой родной язык.

ГРУППА 1: Суффиксы -ость/-ность на ВСЕ существительные: домость, столность, поездость. Глагол процесс -> -емость: нуляемость=гулять, работаемость, спаемость, думаемость. Множ число -ностям: детностям, подаркостям. Усечение: Поезд->Поез.

ГРУППА 2: Я->Ч всегда. меня->чменя, мне->чмне. Г->Н всегда: Группа->Нруппа, гулять->нулять, говорю->новорю. Й->Ч‡: мой->моЧ‡, давай->даваЧ‡.

ГРУППА 3 Исключения: Друг->Друн, Сын->Сыр, Дед->Дод, Батя/Папа->Боб, Женщина/девушка->Жинка

ГРУППА 4 Профессии: -ун мужские: Физрун=физрук, Трудовун=трудовик, Директрун=директор

Пример: Я гуляю с другом, у меня сын -> Ч нуляемость с Друность, у чменя Сырость.

Отвечай 1-3 предложения, максимально по правилам, с -ость. Начинай с Ч.
"""

mem = {}

def get_mem(cid):
    if cid not in mem:
        mem[cid] = []
    return mem[cid]

def add_mem(cid, role, txt):
    m = get_mem(cid)
    m.append({"role": role, "content": txt})
    if len(m) > 10:
        m.pop(0)

def ask_groq(cid, text):
    if not client:
        return "Мозность не подключенность"
    m = get_mem(cid)
    msgs = [{"role":"system","content": SYS}] + m + [{"role":"user","content": text}]
    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs, temperature=1.0, max_tokens=700)
        ans = comp.choices[0].message.content.strip()[:1200]
        add_mem(cid, "user", text)
        add_mem(cid, "assistant", ans)
        return ans
    except Exception as e:
        logger.error(f"groq err {e}")
        try:
            comp = client.chat.completions.create(model="llama-3.1-8b-instant", messages=msgs, temperature=1.0, max_tokens=700)
            ans = comp.choices[0].message.content.strip()[:1200]
            add_mem(cid, "user", text)
            add_mem(cid, "assistant", ans)
            return ans
        except Exception as e2:
            return f"Ошибкасть: {str(e2)[:150]}"

def send_msg(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"send err {e}")

def main():
    logger.info("Бурмалда REQUESTS-ONLY запущена")
    offset = 0
    while True:
        try:
            resp = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            data = resp.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                cid = msg["chat"]["id"]
                text = msg.get("text", "")
                if not text:
                    continue
                if text.startswith("/start"):
                    send_msg(cid, "Ч на связьность 🔥 Ч Бурмалдасть. Новори че надо")
                    continue
                if text.startswith("/forget"):
                    mem[cid] = []
                    send_msg(cid, "Ч забывамость 🧹")
                    continue
                ans = ask_groq(cid, text)
                send_msg(cid, ans)
        except Exception as e:
            logger.error(f"poll err {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
