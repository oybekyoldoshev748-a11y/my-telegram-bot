import os
import telebot
from telebot import types
from flask import Flask

# =========================
# SOZLAMALAR
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Oddiy vaqtinchalik ma'lumotlar
users = {}
orders = []

SERVICES = {
    "Instagram obunachi": 1000,
    "Instagram like": 500,
    "Telegram obunachi": 1500,
    "Telegram post ko‘rish": 700,
}

# =========================
# MENYU
# =========================

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("🛍 Xizmatlar", "🛒 Buyurtma berish")
    markup.row("💰 Balans", "👤 Profil")
    markup.row("📦 Buyurtmalar", "ℹ️ Yordam")

    return markup


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "orders": []
        }

    bot.send_message(
        message.chat.id,
        f"👋 Assalomu alaykum, {message.from_user.first_name}!\n\n"
        "🤖 SMM botimizga xush kelibsiz!\n\n"
        "Kerakli bo‘limni tanlang 👇",
        reply_markup=main_menu()
    )


# =========================
# XIZMATLAR
# =========================

@bot.message_handler(func=lambda message: message.text == "🛍 Xizmatlar")
def services(message):
    text = "🛍 <b>Xizmatlar</b>\n\n"

    for i, (name, price) in enumerate(SERVICES.items(), 1):
        text += f"{i}. {name} — {price} so‘m / 1000\n"

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML"
    )


# =========================
# BUYURTMA
# =========================

@bot.message_handler(func=lambda message: message.text == "🛒 Buyurtma berish")
def order_start(message):

    markup = types.InlineKeyboardMarkup()

    for name in SERVICES:
        markup.add(
            types.InlineKeyboardButton(
                name,
                callback_data="service|" + name
            )
        )

    bot.send_message(
        message.chat.id,
        "🛒 <b>Xizmatni tanlang:</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("service|"))
def choose_service(call):

    service = call.data.split("|", 1)[1]

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        f"✅ Xizmat: <b>{service}</b>\n\n"
        "🔗 Buyurtma havolasini yuboring:",
        parse_mode="HTML"
    )

    bot.register_next_step_handler(
        msg,
        get_link,
        service
    )


def get_link(message, service):

    link = message.text

    msg = bot.send_message(
        message.chat.id,
        "🔢 Miqdorni yozing.\n\nMasalan: <b>1000</b>",
        parse_mode="HTML"
    )

    bot.register_next_step_handler(
        msg,
        get_quantity,
        service,
        link
    )


def get_quantity(message, service, link):

    try:
        quantity = int(message.text)

        if quantity <= 0:
            raise ValueError

    except:
        bot.send_message(
            message.chat.id,
            "❌ Miqdor noto‘g‘ri. Masalan: 1000"
        )
        return

    price_per_1000 = SERVICES[service]
    total = int(quantity / 1000 * price_per_1000)

    user_id = message.from_user.id
    balance = users[user_id]["balance"]

    if balance < total:

        bot.send_message(
            message.chat.id,
            f"❌ Balansingiz yetarli emas.\n\n"
            f"💰 Balans: {balance} so‘m\n"
            f"💵 Kerak: {total} so‘m\n\n"
            "💳 Balansni to‘ldiring."
        )
        return

    users[user_id]["balance"] -= total

    order = {
        "id": len(orders) + 1,
        "user_id": user_id,
        "service": service,
        "link": link,
        "quantity": quantity,
        "price": total,
        "status": "🟡 Kutilmoqda"
    }

    orders.append(order)
    users[user_id]["orders"].append(order["id"])

    bot.send_message(
        message.chat.id,
        f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"🆔 ID: #{order['id']}\n"
        f"📦 Xizmat: {service}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💰 Narx: {total} so‘m\n"
        f"📊 Holat: 🟡 Kutilmoqda",
        parse_mode="HTML"
    )


# =========================
# BALANS
# =========================

@bot.message_handler(func=lambda message: message.text == "💰 Balans")
def balance(message):

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "orders": []
        }

    bot.send_message(
        message.chat.id,
        f"💰 <b>Sizning balansingiz:</b>\n\n"
        f"{users[user_id]['balance']} so‘m",
        parse_mode="HTML"
    )


# =========================
# PROFIL
# =========================

@bot.message_handler(func=lambda message: message.text == "👤 Profil")
def profile(message):

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "orders": []
        }

    bot.send_message(
        message.chat.id,
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Balans: {users[user_id]['balance']} so‘m\n"
        f"📦 Buyurtmalar: {len(users[user_id]['orders'])} ta",
        parse_mode="HTML"
    )


# =========================
# BUYURTMALAR
# =========================

@bot.message_handler(func=lambda message: message.text == "📦 Buyurtmalar")
def my_orders(message):

    user_id = message.from_user.id

    if user_id not in users or not users[user_id]["orders"]:
        bot.send_message(
            message.chat.id,
            "📦 Sizda hozircha buyurtmalar yo‘q."
        )
        return

    text = "📦 <b>Buyurtmalaringiz:</b>\n\n"

    for order in orders:
        if order["user_id"] == user_id:
            text += (
                f"🆔 #{order['id']}\n"
                f"📦 {order['service']}\n"
                f"🔢 {order['quantity']}\n"
                f"📊 {order['status']}\n\n"
            )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML"
    )


# =========================
# YORDAM
# =========================

@bot.message_handler(func=lambda message: message.text == "ℹ️ Yordam")
def help_command(message):

    bot.send_message(
        message.chat.id,
        "ℹ️ <b>Yordam</b>\n\n"
        "🛍 Xizmatlar — mavjud xizmatlar\n"
        "🛒 Buyurtma berish — yangi buyurtma\n"
        "💰 Balans — hisobingiz\n"
        "👤 Profil — profilingiz\n"
        "📦 Buyurtmalar — buyurtmalar tarixi\n\n"
        "Muammo bo‘lsa administratorga murojaat qiling.",
        parse_mode="HTML"
    )


# =========================
# RENDER UCHUN FLASK
# =========================

@app.route("/")
def home():
    return "SMM Telegram Bot ishlayapti! ✅"


@app.route("/health")
def health():
    return "OK"


# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

if __name__ == "__main__":
    import threading

    def run_bot():
        bot.infinity_polling(
            skip_pending=True,
            timeout=60,
            long_polling_timeout=60
        )

    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
