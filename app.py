import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "👋 Salom!\n\n"
        "Bot ishga tushdi ✅"
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.reply_to(
        message,
        "ℹ️ Yordam bo‘limi\n\n"
        "Bot ishlamoqda."
    )


@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, message.text)


@app.route("/")
def home():
    return "Telegram bot ishlayapti! ✅"


@app.route("/webhook", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
