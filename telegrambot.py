import telebot

# ВСТАВЬ СЮДА НОВЫЙ ТОКЕН ПОСЛЕ REVOKE
TOKEN = "8961094590:AAHB8Z8CEvC1gpMpB7sdjiFuiO7yDroYoVw"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Я живой! Daun213Bot запущен.")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(message.chat.id, f"Ты написал: {message.text}")

print("Бот запущен! Не закрывай это окно. Иди в Телегу и пиши /start")
bot.infinity_polling()