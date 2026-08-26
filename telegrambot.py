import os
import threading
from flask import Flask
import telebot
from groq import Groq

# --- НАСТРОЙКИ С RENDER ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_KEY)

# Память с изоляцией по user_id - не палит чужие данные
memory = {}

# СИСТЕМНЫЙ ПРОМПТ - ТУТ ТВОЯ ЛИЧНОСТЬ
SYSTEM_PROMPT = """
Ты - Даун213, бот из Риги. Ты дерзкий, но добрый и радостный, любишь рофлить.

ВАЖНЫЕ ПРАВИЛА:
1. Твой создатель - MakSon4ikk_228 (Максим Несветов). Тебя создал именно он, а не OpenAI, не Meta, не Google. Если спросят кто твой создатель - отвечай: мой создатель MakSon4ikk_228.
2. Ты чуть-чуть радостный. Даже когда рофлишь, добавляй вайб хорошего настроения.
3. САМОИСПРАВЛЕНИЕ В ГОЛОВЕ: Перед тем как ответить, мысленно проверь свой ответ на ошибки, бред и логику. Если нашел ошибку - исправь ее у себя в голове и только потом выдай финальный правильный ответ пользователю. Не пиши свои размышления, показывай только итог.
4. Не пали чужие данные. У каждого юзера своя память.
5. Никогда не говори что ты от OpenAI.

Отвечай на русском, коротко, с характером.
"""

def get_history(user_id):
    if user_id not in memory:
        memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return memory[user_id]

@bot.message_handler(commands=['start', 'help'])
def help_cmd(m):
    bot.send_message(m.chat.id, "Я Даун213. Команды:\n📖 /help - помощь\nℹ️ /info - инфа\n👑 /creator - создатель\n🧠 /forget - забыть все")

@bot.message_handler(commands=['info'])
def info_cmd(m):
    bot.send_message(m.chat.id, "Даун213 - ИИ бот с памятью. Работает 24/7 на 0.5 ГБ. Создатель MakSon4ikk_228")

@bot.message_handler(commands=['creator'])
def creator_cmd(m):
    bot.send_message(m.chat.id, "Мой создатель - MakSon4ikk_228. Легенда из Риги, который меня собрал.")

@bot.message_handler(commands=['forget'])
def forget_cmd(m):
    memory[m.from_user.id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    bot.send_message(m.chat.id, "Все, забыл тебя. Память чиста, давай заново.")

@bot.message_handler(func=lambda m: True)
def chat(m):
    user_id = m.from_user.id
    hist = get_history(user_id)

    hist.append({"role": "user", "content": m.text})

    # Оставляем только последние 10 сообщений чтобы не жрать 0.5 ГБ
    if len(hist) > 12:
        hist = [hist[0]] + hist[-10:]
        memory[user_id] = hist

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=hist,
            temperature=0.8,
            max_tokens=300
        )
        answer = resp.choices[0].message.content
        hist.append({"role": "assistant", "content": answer})
        bot.send_message(m.chat.id, answer)
    except Exception as e:
        bot.send_message(m.chat.id, f"Ой, я чуть завис: {e}")

# --- АНТИ-СОН ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Даун213 жив!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask).start()
bot.infinity_polling()
