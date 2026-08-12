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

# Boshlang'ich majburiy obuna kanallari.
# Keyin admin paneldan ham qo'shish mumkin.
REQUIRED_CHANNELS = []

# 1000 dona uchun boshlang'ich narxlar
SERVICES = {
    "Instagram obunachi": 1000,
    "Instagram like": 500,
    "Telegram obunachi": 1500,
    "Telegram post ko‘rish": 700,
    "TikTok like": 600,
    "TikTok obunachi": 1200,
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. Render Environment Variables ga BOT_TOKEN qo‘ying.")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

users = {}
orders = []
next_order_id = 1


# =========================================================
# YORDAMCHI
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


def is_admin(user_id):
    return user_id == ADMIN_ID


def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "🛍 Xizmatlar",
        "📱 Nomer olish",
        "🛒 Buyurtmalarim",
        "👥 Referral",
        "💵 Hisobim",
        "💰 Hisob to‘ldirish",
        "📞 Murojaat",
        "☎️ Qo‘llab-quvvatlash",
        "🤝 Hamkorlik",
    )
    return markup


def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users"),
        types.InlineKeyboardButton("🛒 Buyurtmalar", callback_data="admin_orders"),
    )
    markup.add(
        types.InlineKeyboardButton("💰 Balans", callback_data="admin_balance"),
        types.InlineKeyboardButton("🛍 Xizmatlar", callback_data="admin_services"),
    )
    markup.add(
        types.InlineKeyboardButton("📢 Kanallar", callback_data="admin_channels"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
    )
    markup.add(
        types.InlineKeyboardButton("📣 Reklama", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🔑 SMM API", callback_data="admin_api"),
    )
    return markup


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


def check_subscription(user_id):
    if not REQUIRED_CHANNELS:
        return True

    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


def subscription_message():
    text = "❌ <b>Botdan foydalanish uchun kanallarga obuna bo‘ling:</b>\n\n"
    markup = types.InlineKeyboardMarkup()

    for channel in REQUIRED_CHANNELS:
        text += f"📢 {channel}\n"
        markup.add(
            types.InlineKeyboardButton(
                f"📢 {channel}",
                url=f"https://t.me/{channel.lstrip('@')}",
            )
        )

    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return text, markup


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
            if referrer != user_id and user["referrer"] is None and referrer in users:
                user["referrer"] = referrer
                users[referrer]["referrals"] += 1
                users[referrer]["balance"] += 500
                bot.send_message(
                    referrer,
                    "🎉 Referral qo‘shildi!\n💰 500 so‘m bonus berildi.",
                )
        except (ValueError, TypeError):
            pass

    if not check_subscription(user_id):
        text, markup = subscription_message()
        bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)
        return

    bot.send_message(
        user_id,
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🤖 SMM xizmatlar botiga xush kelibsiz!\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        bot.send_message(
            call.message.chat.id,
            "✅ Obuna tasdiqlandi!",
            reply_markup=main_menu(),
        )
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
            show_alert=True,
        )


# =========================================================
# XIZMATLAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🛍 Xizmatlar")
def services(message):
    if not check_subscription(message.from_user.id):
        text, markup = subscription_message()
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)
        return

    bot.send_message(
        message.chat.id,
        "🛍 <b>Xizmatlar:</b>\n\nKerakli xizmatni tanlang:",
        parse_mode="HTML",
        reply_markup=service_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("service|"))
def select_service(call):
    service = call.data.split("|", 1)[1]
    if service not in SERVICES:
        bot.answer_callback_query(call.id, "Xizmat topilmadi.")
        return

    price = SERVICES[service]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Buyurtma berish", callback_data="order|" + service))
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_services"))

    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"🛍 <b>{service}</b>\n\n"
        f"💰 Narxi: <b>{price:,} so‘m / 1000</b>\n\n"
        "Buyurtma berish uchun tugmani bosing.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_services")
def back_services(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🛍 <b>Xizmatlar:</b>\n\nKerakli xizmatni tanlang:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=service_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("order|"))
def start_order(call):
    service = call.data.split("|", 1)[1]
    if service not in SERVICES:
        bot.answer_callback_query(call.id, "Xizmat topilmadi.")
        return

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"🛒 <b>{service}</b>\n\n"
        "🔗 Xizmat bajariladigan havolani yuboring.",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, get_link, service)


def get_link(message, service):
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Havola yuboring.")
        bot.register_next_step_handler(msg, get_link, service)
        return

    link = message.text.strip()
    if not link.startswith(("http://", "https://")):
        msg = bot.send_message(message.chat.id, "❌ Havola https:// bilan boshlanishi kerak.")
        bot.register_next_step_handler(msg, get_link, service)
        return

    msg = bot.send_message(
        message.chat.id,
        "🔢 Miqdorni kiriting.\nMasalan: <b>1000</b>",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, get_quantity, service, link)


def get_quantity(message, service, link):
    global next_order_id

    try:
        quantity = int(message.text.strip())
    except Exception:
        msg = bot.send_message(message.chat.id, "❌ Miqdorni faqat raqam bilan kiriting.")
        bot.register_next_step_handler(msg, get_quantity, service, link)
        return

    if quantity <= 0:
        msg = bot.send_message(message.chat.id, "❌ Miqdor 0 dan katta bo‘lishi kerak.")
        bot.register_next_step_handler(msg, get_quantity, service, link)
        return

    price = SERVICES.get(service)
    if price is None:
        bot.send_message(message.chat.id, "❌ Xizmat topilmadi.", reply_markup=main_menu())
        return

    total = max(1, int(price * quantity / 1000))
    user = get_user(message.from_user.id)

    if user["balance"] < total:
        bot.send_message(
            message.chat.id,
            "❌ <b>Mablag‘ yetarli emas!</b>\n\n"
            f"💰 Kerak: <b>{total:,} so‘m</b>\n"
            f"💵 Balans: <b>{user['balance']:,} so‘m</b>\n\n"
            "💰 Avval hisobingizni to‘ldiring.",
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
        f"🆔 #{order_id}\n"
        f"🛍 {service}\n"
        f"🔢 {quantity}\n"
        f"💰 {total:,} so‘m\n"
        "📊 Kutilmoqda",
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
                f"🔢 {quantity}\n"
                f"🔗 {link}\n"
                f"💰 {total:,} so‘m",
                parse_mode="HTML",
            )
        except Exception:
            pass


# =========================================================
# BUYURTMALAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🛒 Buyurtmalarim")
def my_orders(message):
    user = get_user(message.from_user.id)

    if not user["orders"]:
        bot.send_message(message.chat.id, "📭 Sizda hali buyurtmalar yo‘q.", reply_markup=main_menu())
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

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=main_menu())


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
        "🎁 Har bir referral uchun <b>500 so‘m</b> bonus.\n"
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
        "To‘lovni amalga oshirish uchun administrator bilan bog‘laning.\n"
        "Admin tasdiqlagach balansingizni paneldan qo‘shadi.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# BOSHQA BO‘LIMLAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📞 Murojaat")
def contact(message):
    bot.send_message(
        message.chat.id,
        "📞 <b>Murojaat</b>\n\nSavolingizni yozib yuboring.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda m: m.text == "☎️ Qo‘llab-quvvatlash")
def support(message):
    bot.send_message(
        message.chat.id,
        "☎️ <b>Qo‘llab-quvvatlash</b>\n\nMuammoingizni yozib yuboring.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda m: m.text == "🤝 Hamkorlik")
def partnership(message):
    bot.send_message(
        message.chat.id,
        "🤝 <b>Hamkorlik</b>\n\nHamkorlik bo‘yicha administratorga murojaat qiling.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda m: m.text == "📱 Nomer olish")
def phone_numbers(message):
    bot.send_message(
        message.chat.id,
        "📱 <b>Nomer olish</b>\n\nBu bo‘lim hozircha tayyorlanmoqda.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@bot.message_handler(commands=["admin"])
def admin(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Siz administrator emassiz.")
        return

    bot.send_message(
        message.chat.id,
        "⚙️ <b>ADMIN PANEL</b>\n\nBotni boshqarish uchun bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"👥 <b>Foydalanuvchilar:</b> {len(users)}\n"
        f"🛒 <b>Buyurtmalar:</b> {len(orders)}",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)

    total_balance = sum(u["balance"] for u in users.values())
    bot.send_message(
        call.message.chat.id,
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(users)}</b>\n"
        f"🛒 Buyurtmalar: <b>{len(orders)}</b>\n"
        f"💰 Jami balans: <b>{total_balance:,} so‘m</b>",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_orders")
def admin_orders(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)

    if not orders:
        bot.send_message(
            call.message.chat.id,
            "📭 Buyurtmalar yo‘q.",
            reply_markup=admin_menu(),
        )
        return

    text = "🛒 <b>SO‘NGGI BUYURTMALAR</b>\n\n"
    for order in orders[-10:]:
        text += (
            f"🆔 #{order['id']}\n"
            f"👤 ID: <code>{order['user_id']}</code>\n"
            f"🛍 {order['service']}\n"
            f"🔢 {order['quantity']}\n"
            f"💰 {order['price']:,} so‘m\n"
            f"📊 {order['status']}\n\n"
        )

    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


# ---------------- BALANS ----------------

@bot.callback_query_handler(func=lambda call: call.data == "admin_balance")
def admin_balance(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "💰 Foydalanuvchining Telegram ID raqamini yuboring:",
    )
    bot.register_next_step_handler(msg, admin_balance_user)


def admin_balance_user(message):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except Exception:
        bot.send_message(message.chat.id, "❌ ID faqat raqam bo‘lishi kerak.")
        return

    if user_id not in users:
        bot.send_message(
            message.chat.id,
            "❌ Bu foydalanuvchi botdan hali foydalanmagan.",
        )
        return

    msg = bot.send_message(
        message.chat.id,
        "💵 Qancha balans qo‘shamiz?\nMasalan: <b>10000</b>",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, admin_balance_amount, user_id)


def admin_balance_amount(message, user_id):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except Exception:
        bot.send_message(message.chat.id, "❌ Summa faqat raqam bo‘lishi kerak.")
        return

    if amount <= 0:
        bot.send_message(message.chat.id, "❌ Summa 0 dan katta bo‘lishi kerak.")
        return

    users[user_id]["balance"] += amount

    bot.send_message(
        message.chat.id,
        "✅ <b>Balans qo‘shildi!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"➕ Qo‘shildi: <b>{amount:,} so‘m</b>\n"
        f"💵 Yangi balans: <b>{users[user_id]['balance']:,} so‘m</b>",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )

    try:
        bot.send_message(
            user_id,
            "💰 <b>Balansingiz to‘ldirildi!</b>\n\n"
            f"➕ <b>{amount:,} so‘m</b>\n"
            f"💵 Balans: <b>{users[user_id]['balance']:,} so‘m</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ---------------- XIZMATLAR VA NARXLAR ----------------

@bot.callback_query_handler(func=lambda call: call.data == "admin_services")
def admin_services(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)

    text = "🛍 <b>XIZMATLAR VA NARXLAR</b>\n\n"
    for name, price in SERVICES.items():
        text += f"🛍 {name}\n💰 {price:,} so‘m / 1000\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "💵 Narx o‘zgartirish",
            callback_data="admin_change_price",
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Admin panel",
            callback_data="admin_back",
        )
    )

   
