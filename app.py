import os
import time
import threading
from flask import Flask
import telebot
from telebot import types

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Majburiy obuna kanallari
# Masalan: ["@kanalingiz"]
REQUIRED_CHANNELS = [
    # "@kanalingiz"
]

# Xizmatlar va narxlar (1000 dona uchun)
SERVICES = {
    "Instagram obunachi": 1000,
    "Instagram like": 500,
    "Telegram obunachi": 1500,
    "Telegram post ko‘rish": 700,
    "TikTok like": 600,
    "TikTok obunachi": 1200,
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Render Environment Variables bo‘limiga BOT_TOKEN qo‘ying.")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Vaqtinchalik ma'lumotlar
users = {}
orders = []
next_order_id = 1


# =========================================================
# FOYDALANUVCHI
# =========================================================

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "orders": [],
            "referrals": 0,
            "referrer": None,
        }
    return users[user_id]


# =========================================================
# MAJBURIY OBUNA
# =========================================================

def check_subscription(user_id):
    if not REQUIRED_CHANNELS:
        return True

    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False

    return True


def subscription_message():
    text = "❌ <b>Botdan foydalanish uchun kanallarga obuna bo‘ling:</b>\n\n"

    for channel in REQUIRED_CHANNELS:
        text += f"📢 {channel}\n"

    text += "\n✅ Obuna bo‘lgach, «Tekshirish» tugmasini bosing."

    markup = types.InlineKeyboardMarkup()

    for channel in REQUIRED_CHANNELS:
        markup.add(
            types.InlineKeyboardButton(
                f"📢 {channel}",
                url=f"https://t.me/{channel.replace('@', '')}",
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub",
        )
    )

    return text, markup


# =========================================================
# ASOSIY MENU
# =========================================================

def main_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2,
    )

    markup.add(
        types.KeyboardButton("🛍 Xizmatlar"),
        types.KeyboardButton("📱 Nomer olish"),
    )
    markup.add(
        types.KeyboardButton("🛒 Buyurtmalarim"),
        types.KeyboardButton("👥 Referral"),
    )
    markup.add(
        types.KeyboardButton("💵 Hisobim"),
        types.KeyboardButton("💰 Hisob to‘ldirish"),
    )
    markup.add(
        types.KeyboardButton("📞 Murojaat"),
        types.KeyboardButton("☎️ Qo‘llab-quvvatlash"),
    )
    markup.add(types.KeyboardButton("🤝 Hamkorlik"))

    return markup


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        try:
            referrer = int(args[1])

            if (
                referrer != user_id
                and user["referrer"] is None
                and referrer in users
            ):
                user["referrer"] = referrer
                users[referrer]["referrals"] += 1
                users[referrer]["balance"] += 500

                bot.send_message(
                    referrer,
                    "🎉 Sizning referralingiz botga qo‘shildi!\n"
                    "💰 Hisobingizga 500 so‘m qo‘shildi.",
                )
        except (ValueError, TypeError):
            pass

    if not check_subscription(user_id):
        text, markup = subscription_message()
        bot.send_message(
            user_id,
            text,
            parse_mode="HTML",
            reply_markup=markup,
        )
        return

    bot.send_message(
        user_id,
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🤖 Xizmatlar botiga xush kelibsiz!\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# OBUNANI TEKSHIRISH
# =========================================================

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    user_id = call.from_user.id

    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        bot.send_message(
            user_id,
            "✅ Obuna tasdiqlandi!\n\nAsosiy menyu:",
            reply_markup=main_menu(),
        )
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Hali barcha kanallarga obuna bo‘lmagansiz!",
            show_alert=True,
        )


# =========================================================
# XIZMATLAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🛍 Xizmatlar")
def services(message):
    if not check_subscription(message.from_user.id):
        text, markup = subscription_message()
        bot.send_message(
            message.chat.id,
            text,
            parse_mode="HTML",
            reply_markup=markup,
        )
        return

    markup = types.InlineKeyboardMarkup()

    for service, price in SERVICES.items():
        markup.add(
            types.InlineKeyboardButton(
                f"🛍 {service} — {price:,} so‘m",
                callback_data="service|" + service,
            )
        )

    bot.send_message(
        message.chat.id,
        "🛍 <b>Xizmatlar:</b>\n\nKerakli xizmatni tanlang:",
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("service|")
)
def select_service(call):
    service = call.data.split("|", 1)[1]

    if service not in SERVICES:
        bot.answer_callback_query(call.id, "Xizmat topilmadi!")
        return

    price = SERVICES[service]

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🛒 Buyurtma berish",
            callback_data="order|" + service,
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_services",
        )
    )

    bot.edit_message_text(
        f"🛍 <b>{service}</b>\n\n"
        f"💰 Narxi: <b>{price:,} so‘m</b>\n\n"
        "🛒 Buyurtma berish uchun tugmani bosing.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data == "back_services"
)
def back_services(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🛍 <b>Xizmatlar:</b>\n\nKerakli xizmatni tanlang:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=service_keyboard(),
    )


def service_keyboard():
    markup = types.InlineKeyboardMarkup()

    for service, price in SERVICES.items():
        markup.add(
            types.InlineKeyboardButton(
                f"🛍 {service} — {price:,} so‘m",
                callback_data="service|" + service,
            )
        )

    return markup


# =========================================================
# BUYURTMA
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("order|")
)
def start_order(call):
    service = call.data.split("|", 1)[1]

    if service not in SERVICES:
        bot.answer_callback_query(call.id, "Xizmat topilmadi!")
        return

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        f"🛒 <b>{service}</b>\n\n"
        "🔗 Xizmat bajariladigan havolani yuboring.\n\n"
        "Masalan:\nhttps://t.me/kanal",
        parse_mode="HTML",
    )

    bot.register_next_step_handler(msg, get_link, service)


def get_link(message, service):
    if not message.text:
        msg = bot.send_message(
            message.chat.id,
            "❌ Havola yuboring.",
        )
        bot.register_next_step_handler(msg, get_link, service)
        return

    link = message.text.strip()

    if not link.startswith(("http://", "https://")):
        msg = bot.send_message(
            message.chat.id,
            "❌ Havola noto‘g‘ri.\n\n"
            "https:// bilan boshlanadigan havola yuboring.",
        )
        bot.register_next_step_handler(msg, get_link, service)
        return

    msg = bot.send_message(
        message.chat.id,
        "🔢 Miqdorni kiriting.\n\nMasalan: <b>1000</b>",
        parse_mode="HTML",
    )

    bot.register_next_step_handler(
        msg,
        get_quantity,
        service,
        link,
    )


def get_quantity(message, service, link):
    global next_order_id

    try:
        quantity = int(message.text.strip())
    except (ValueError, AttributeError):
        msg = bot.send_message(
            message.chat.id,
            "❌ Miqdorni faqat raqam bilan kiriting.",
        )
        bot.register_next_step_handler(
            msg,
            get_quantity,
            service,
            link,
        )
        return

    if quantity <= 0:
        msg = bot.send_message(
            message.chat.id,
            "❌ Miqdor 0 dan katta bo‘lishi kerak.",
        )
        bot.register_next_step_handler(
            msg,
            get_quantity,
            service,
            link,
        )
        return

    price = SERVICES.get(service)

    if price is None:
        bot.send_message(
            message.chat.id,
            "❌ Xizmat topilmadi.",
            reply_markup=main_menu(),
        )
        return

    total = int(price * quantity / 1000)

    if total <= 0:
        total = 1

    user = get_user(message.from_user.id)

    if user["balance"] < total:
        bot.send_message(
            message.chat.id,
            "❌ <b>Hisobingizda mablag‘ yetarli emas!</b>\n\n"
            f"💰 Kerakli summa: <b>{total:,} so‘m</b>\n"
            f"💵 Balansingiz: <b>{user['balance']:,} so‘m</b>\n\n"
            "💰 Hisobni to‘ldiring va qayta urinib ko‘ring.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    user["balance"] -= total

    order = {
        "id": next_order_id,
        "user_id": message.from_user.id,
        "service": service,
        "link": link,
        "quantity": quantity,
        "price": total,
        "status": "Kutilmoqda",
    }

    orders.append(order)
    user["orders"].append(next_order_id)

    order_id = next_order_id
    next_order_id += 1

    bot.send_message(
        message.chat.id,
        "✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"🆔 Buyurtma: <b>#{order_id}</b>\n"
        f"🛍 Xizmat: <b>{service}</b>\n"
        f"🔢 Miqdor: <b>{quantity}</b>\n"
        f"💰 Narx: <b>{total:,} so‘m</b>\n"
        "📊 Holat: <b>Kutilmoqda</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )

    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                "🔔 <b>Yangi buyurtma!</b>\n\n"
                f"🆔 #{order_id}\n"
                f"👤 ID: <code>{message.from_user.id}</code>\n"
                f"🛍 {service}\n"
                f"🔢 Miqdor: {quantity}\n"
                f"🔗 {link}\n"
                f"💰 {total:,} so‘m",
                parse_mode="HTML",
            )
        except Exception:
            pass


# =========================================================
# BUYURTMALARIM
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🛒 Buyurtmalarim")
def my_orders(message):
    user = get_user(message.from_user.id)

    if not user["orders"]:
        bot.send_message(
            message.chat.id,
            "📭 Sizda hali buyurtmalar yo‘q.",
            reply_markup=main_menu(),
        )
        return

    text = "🛒 <b>Buyurtmalaringiz:</b>\n\n"

    for order_id in user["orders"][-10:]:
        for order in orders:
            if order["id"] == order_id:
                text += (
                    f"🆔 #{order['id']}\n"
                    f"🛍 {order['service']}\n"
                    f"🔢 {order['quantity']}\n"
                    f"📊 {order['status']}\n\n"
                )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# HISOBIM
# =========================================================

@bot.message_handler(func=lambda m: m.text == "💵 Hisobim")
def account(message):
    user = get_user(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "💵 <b>Hisobingiz</b>\n\n"
        f"💰 Balans: <b>{user['balance']:,} so‘m</b>\n"
        f"👥 Referallar: <b>{user['referrals']}</b>\n"
        f"🛒 Buyurtmalar: <b>{len(user['orders'])}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# REFERRAL
# =========================================================

@bot.message_handler(func=lambda m: m.text == "👥 Referral")
def referral(message):
    user = get_user(message.from_user.id)

    try:
        me = bot.get_me()
        link = f"https://t.me/{me.username}?start={message.from_user.id}"
    except Exception:
        link = "Hozircha havola olinmadi."

    bot.send_message(
        message.chat.id,
        "👥 <b>Referral tizimi</b>\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        "🎁 Har bir taklif qilingan foydalanuvchi uchun "
        "<b>500 so‘m</b> bonus olasiz.\n\n"
        f"👥 Takliflaringiz: <b>{user['referrals']}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# HISOB TO‘LDIRISH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "💰 Hisob to‘ldirish")
def add_balance(message):
    bot.send_message(
        message.chat.id,
        "💰 <b>Hisob to‘ldirish</b>\n\n"
        "To‘lov rekvizitlarini administrator orqali oling.\n\n"
        "To‘lov qilganingizdan keyin chekni yuboring.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# MUROJAAT
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📞 Murojaat")
def contact(message):
    bot.send_message(
        message.chat.id,
        "📞 <b>Murojaat</b>\n\n"
        "Savolingizni shu yerga yozib yuboring.\n"
        "Administrator ko‘rib chiqadi.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# QO‘LLAB-QUVVATLASH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "☎️ Qo‘llab-quvvatlash")
def support(message):
    bot.send_message(
        message.chat.id,
        "☎️ <b>Qo‘llab-quvvatlash</b>\n\n"
        "Muammoingizni yozib yuboring.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# HAMKORLIK
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🤝 Hamkorlik")
def partnership(message):
    bot.send_message(
        message.chat.id,
        "🤝 <b>Hamkorlik</b>\n\n"
        "Hamkorlik bo‘yicha administratorga murojaat qiling.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# ADMIN
# =========================================================

@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "❌ Siz administrator emassiz.",
        )
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "👥 Foydalanuvchilar",
            callback_data="admin_users",
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "🛒 Buyurtmalar",
            callback_data="admin_orders",
        )
    )

    bot.send_message(
        message.chat.id,
        "⚙️ <b>ADMIN PANEL</b>",
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data == "admin_users"
)
def admin_users(call):
    if call.from_user.id != ADMIN_ID:
        return

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        f"👥 Foydalanuvchilar: <b>{len(users)}</b>\n"
        f"🛒 Buyurtmalar: <b>{len(orders)}</b>",
        parse_mode="HTML",
    )


@bot.callback_query_handler(
    func=lambda call: call.data == "admin_orders"
)
def admin_orders(call):
    if call.from_user.id != ADMIN_ID:
        return

    bot.answer_callback_query(call.id)

    if not orders:
        bot.send_message(
            call.message.chat.id,
            "📭 Buyurtmalar yo‘q.",
        )
        return

    text = "🛒 <b>So‘nggi buyurtmalar:</b>\n\n"

    for order in orders[-10:]:
        text += (
            f"🆔 #{order['id']}\n"
            f"🛍 {order['service']}\n"
            f"🔢 {order['quantity']}\n"
            f"📊 {order['status']}\n\n"
        )

    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode="HTML",
    )


# =========================================================
# FLASK — RENDER UCHUN
# =========================================================

@app.route("/")
def home():
    return "SMM Telegram Bot ishlayapti! ✅"


@app.route("/health")
def health():
    return "OK"


# =========================================================
# TELEGRAM BOTNI ISHGA TUSHIRISH
# MUHIM: Render gunicorn app:app bilan ishga tushirganda
# __main__ bloki ishlamasligi mumkin. Shuning uchun polling
# import vaqtida alohida thread'da ishga tushiriladi.
# =========================================================

def run_bot():
    print("Telegram bot ishga tushmoqda...")

    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)

            print("Telegram polling boshlandi.")
            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
            )
        except Exception as error:
            print(f"Telegram polling xatosi: {error}")
            time.sleep(5)


# Gunicorn import qilganda ham bot ishga tushadi.
bot_thread = threading.Thread(
    target=run_bot,
    daemon=True,
)
bot_thread.start()


# =========================================================
# RENDER PORT
# =========================================================

port = int(os.environ.get("PORT", "10000"))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=port,
                                 )
    
