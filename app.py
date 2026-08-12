import os, json, time, threading, requests
from flask import Flask
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
FILE = "data.json"

DEFAULT = {
    "users": {},
    "orders": [],
    "services": {
        "Instagram Followers": 15000,
        "Instagram Likes": 5000,
        "Telegram Members": 10000
    },
    "ref_bonus": 500,
    "support": "@admin",
    "payment_text": "To‘lov rekvizitlarini administrator orqali oling.",
    "channels": [],
    "api": {"url": "", "key": "", "enabled": False}
}
data = DEFAULT.copy()

def save():
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load():
    global data
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        for k, v in DEFAULT.items():
            if k not in old:
                old[k] = v
        data = old
    except Exception:
        save()

load()

def get_user(uid):
    k = str(uid)
    if k not in data["users"]:
        data["users"][k] = {
            "balance": 0,
            "referrals": 0,
            "orders": [],
            "pending_payment": False
        }
        save()
    return data["users"][k]

def is_admin(uid):
    return uid == ADMIN_ID

def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🛍 Xizmatlar", "🛒 Buyurtmalarim")
    m.row("💵 Hisobim", "💰 Hisob to‘ldirish")
    m.row("👥 Referral", "📞 Murojaat")
    m.row("☎️ Qo‘llab-quvvatlash", "🤝 Hamkorlik")
    return m

def admin_menu():
    m = types.InlineKeyboardMarkup()
    buttons = [
        ("👥 Foydalanuvchilar", "a_users"),
        ("🛒 Buyurtmalar", "a_orders"),
        ("💰 Balans", "a_balance"),
        ("🛍 Xizmatlar / Narxlar", "a_services"),
        ("📢 Majburiy obuna", "a_channels"),
        ("💳 To‘lov cheklari", "a_payments"),
        ("📣 Reklama", "a_ad"),
        ("🔌 SMM API", "a_api"),
        ("📊 Statistika", "a_stats"),
        ("⚙️ Sozlamalar", "a_settings"),
    ]
    for t, c in buttons:
        m.add(types.InlineKeyboardButton(t, callback_data=c))
    return m

def back_admin():
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="a_back"))
    return m

def send_admin(chat_id, text, markup=None):
    bot.send_message(chat_id, text, reply_markup=markup or admin_menu())

def api_create_order(order):
    api = data["api"]
    if not api.get("enabled") or not api.get("url") or not api.get("key"):
        return False, "API sozlanmagan"

    try:
        r = requests.post(
            api["url"],
            data={
                "key": api["key"],
                "action": "add",
                "service": order["service_id"],
                "link": order["link"],
                "quantity": order["quantity"]
            },
            timeout=20
        )
        result = r.json()
        if "order" in result:
            return True, str(result["order"])
        return False, str(result.get("error", result))
    except Exception as e:
        return False, str(e)

def notify_admin_payment(order):
    if not ADMIN_ID:
        return
    m = types.InlineKeyboardMarkup()
    m.row(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"payok:{order['id']}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"payno:{order['id']}")
    )
    bot.send_message(
        ADMIN_ID,
        f"💳 <b>Yangi to‘lov cheki</b>\n\n"
        f"🆔 To‘lov #{order['id']}\n"
        f"👤 <code>{order['user_id']}</code>\n"
        f"💰 So‘ralgan summa: {order['amount']:,} so‘m\n"
        f"📊 Holat: Kutilmoqda",
        reply_markup=m
    )

@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🛍 Xizmat tanlang va buyurtma bering.",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if not is_admin(message.from_user.id):
        return bot.send_message(message.chat.id, "❌ Siz administrator emassiz.")
    send_admin(message.chat.id, "👑 <b>ADMIN PANEL</b>")

@bot.message_handler(func=lambda m: m.text == "🛍 Xizmatlar")
def services(message):
    if not data["services"]:
        return bot.send_message(message.chat.id, "📭 Xizmatlar mavjud emas.", reply_markup=main_menu())
    m = types.InlineKeyboardMarkup()
    for name, price in data["services"].items():
        m.add(types.InlineKeyboardButton(
            f"{name} — {price:,}/1000",
            callback_data="buy:" + name[:45]
        ))
    bot.send_message(message.chat.id, "🛍 <b>XIZMATLAR</b>\n\nXizmatni tanlang:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy:"))
def buy_service(call):
    name = call.data[4:]
    if name not in data["services"]:
        return bot.answer_callback_query(call.id, "Xizmat topilmadi", show_alert=True)
    msg = bot.send_message(call.message.chat.id, f"🛍 <b>{name}</b>\n\n🔗 Link yuboring:")
    bot.register_next_step_handler(msg, get_link, name)
    bot.answer_callback_query(call.id)

def get_link(message, service):
    msg = bot.send_message(message.chat.id, "🔢 Miqdorni yuboring:")
    bot.register_next_step_handler(msg, create_order, service, message.text.strip())

def create_order(message, service, link):
    try:
        qty = int(message.text.strip())
    except:
        return bot.send_message(message.chat.id, "❌ Miqdor raqam bo‘lishi kerak.")
    if qty <= 0:
        return bot.send_message(message.chat.id, "❌ Miqdor 0 dan katta bo‘lishi kerak.")
    price = max(1, data["services"][service] * qty // 1000)
    u = get_user(message.from_user.id)
    if u["balance"] < price:
        return bot.send_message(
            message.chat.id,
            f"❌ <b>Mablag‘ yetarli emas.</b>\n\n"
            f"💰 Kerak: {price:,} so‘m\n💵 Balans: {u['balance']:,} so‘m",
            reply_markup=main_menu()
        )

    oid = len(data["orders"]) + 1
    order = {
        "id": oid, "user_id": message.from_user.id, "service": service,
        "service_id": service, "link": link, "quantity": qty,
        "price": price, "status": "Kutilmoqda", "provider_id": ""
    }
    u["balance"] -= price
    u["orders"].append(oid)
    data["orders"].append(order)
    save()

    ok, provider = api_create_order(order)
    if ok:
        order["provider_id"] = provider
        order["status"] = "Jarayonda"
        save()

    bot.send_message(
        message.chat.id,
        f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"🆔 #{oid}\n🛍 {service}\n🔢 {qty}\n"
        f"💰 {price:,} so‘m\n📊 {order['status']}",
        reply_markup=main_menu()
    )
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🆕 <b>Yangi buyurtma #{oid}</b>\n"
                f"👤 <code>{message.from_user.id}</code>\n"
                f"🛍 {service}\n🔢 {qty}\n💰 {price:,}\n"
                f"📊 {order['status']}"
            )
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "🛒 Buyurtmalarim")
def my_orders(message):
    rows = [o for o in data["orders"] if o["user_id"] == message.from_user.id]
    if not rows:
        return bot.send_message(message.chat.id, "📭 Buyurtmalar yo‘q.", reply_markup=main_menu())
    text = "🛒 <b>BUYURTMALARIM</b>\n\n"
    for o in rows[-15:]:
        text += f"🆔 #{o['id']} | {o['service']}\n🔢 {o['quantity']} | 💰 {o['price']:,}\n📊 {o['status']}\n\n"
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💵 Hisobim")
def account(message):
    u = get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"💵 <b>Hisobingiz</b>\n\n"
        f"💰 Balans: <b>{u['balance']:,} so‘m</b>\n"
        f"👥 Referallar: <b>{u['referrals']}</b>\n"
        f"🛒 Buyurtmalar: <b>{len(u['orders'])}</b>",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💰 Hisob to‘ldirish")
def add_balance(message):
    bot.send_message(
        message.chat.id,
        f"💰 <b>Hisob to‘ldirish</b>\n\n{data['payment_text']}\n\n"
        "To‘lovdan keyin <b>chek rasmini shu yerga yuboring</b>.",
        reply_markup=main_menu()
    )

@bot.message_handler(content_types=["photo"])
def payment_photo(message):
    if not get_user(message.from_user.id).get("pending_payment"):
        # Chek sifatida qabul qilish
        u = get_user(message.from_user.id)
        u["pending_payment"] = True
        save()
    msg = bot.send_message(message.chat.id, "💰 Chek qabul qilindi. To‘langan summani so‘mda yuboring:")
    bot.register_next_step_handler(msg, payment_amount, message)

def payment_amount(message, original):
    try:
        amount = int(message.text.strip())
    except:
        return bot.send_message(message.chat.id, "❌ Summa raqam bo‘lishi kerak.")
    oid = len(data.get("payments", [])) + 1
    payment = {"id": oid, "user_id": original.from_user.id, "amount": amount, "status": "Kutilmoqda"}
    data.setdefault("payments", []).append(payment)
    get_user(original.from_user.id)["pending_payment"] = False
    save()
    notify_admin_payment(payment)
    bot.send_message(message.chat.id, "✅ Chek adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👥 Referral")
def referral(message):
    u = get_user(message.from_user.id)
    me = bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    bot.send_message(
        message.chat.id,
        f"👥 <b>Referral</b>\n\n🔗 {link}\n\n"
        f"🎁 Bonus: {data['ref_bonus']:,} so‘m\n👥 Takliflar: {u['referrals']}",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text in ["📞 Murojaat", "☎️ Qo‘llab-quvvatlash", "🤝 Hamkorlik"])
def support(message):
    bot.send_message(message.chat.id, f"📞 Administrator: {data['support']}", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "a_back")
def a_back(call):
    if is_admin(call.from_user.id):
        bot.edit_message_text("👑 <b>ADMIN PANEL</b>", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "a_users")
def a_users(call):
    if not is_admin(call.from_user.id): return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"👥 Foydalanuvchilar: <b>{len(data['users'])}</b>", reply_markup=back_admin())

@bot.callback_query_handler(func=lambda c: c.data == "a_orders")
def a_orders(call):
    if not is_admin(call.from_user.id): return
    bot.answer_callback_query(call.id)
    if not data["orders"]:
        return bot.send_message(call.message.chat.id, "📭 Buyurtmalar yo‘q.", reply_markup=back_admin())
    text = "🛒 <b>BUYURTMALAR</b>\n\n"
    m = types.InlineKeyboardMarkup()
    for o in data["orders"][-15:]:
        text += f"#{o['id']} | {o['service']} | {o['quantity']} | {o['price']:,} | {o['status']}\n"
        m.add(types.InlineKeyboardButton(f"#{o['id']} status", callback_data=f"ost:{o['id']}"))
    m.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="a_back"))
    bot.send_message(call.message.chat.id, text, reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ost:"))
def order_status_menu(call):
    if not is_admin(call.from_user.id): return
    oid = int(call.data[4:])
    m = types.InlineKeyboardMarkup()
    for s in ["Kutilmoqda", "Jarayonda", "Bajarildi", "Bekor qilindi"]:
        m.add(types.InlineKeyboardButton(s, callback_data=f"setost:{oid}:{s}"))
    bot.send_message(call.message.chat.id, f"🆔 #{oid} — yangi status:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setost:"))
def set_status(call):
    if not is_admin(call.from_user.id): return
    _, oid, status = call.data.split(":", 2)
    oid = int(oid)
    for o in data["orders"]:
        if o["id"] == oid:
            o["status"] = status
            save()
            try: bot.send_message(o["user_id"], f"📦 <b>Buyurtma #{oid}</b>\n📊 Yangi holat: <b>{status}</b>")
            except: pass
            bot.answer_callback_query(call.id, "Status yangilandi")
            bot.send_message(call.message.chat.id, "✅ Status yangilandi.", reply_markup=back_admin())
            return

@bot.callback_query_handler(func=lambda c: c.data == "a_balance")
def a_balance(call):
    if not is_admin(call.from_user.id): return
    msg = bot.send_message(call.message.chat.id, "👤 Telegram ID yuboring:")
    bot.register_next_step_handler(msg, balance_uid)

def balance_uid(message):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text.strip())
    except: return bot.send_message(message.chat.id, "❌ ID raqam bo‘lishi kerak.")
    if str(uid) not in data["users"]: return bot.send_message(message.chat.id, "❌ Foydalanuvchi topilmadi.")
    msg = bot.send_message(message.chat.id, "💰 Qo‘shiladigan summa:")
    bot.register_next_step_handler(msg, balance_amount, uid)

def balance_amount(message, uid):
    if not is_admin(message.from_user.id): return
    try: amount = int(message.text.strip())
    except: return bot.send_message(message.chat.id, "❌ Summa raqam bo‘lishi kerak.")
    if amount <= 0: return bot.send_message(message.chat.id, "❌ Summa 0 dan katta bo‘lishi kerak.")
    get_user(uid)["balance"] += amount
    save()
    bot.send_message(message.chat.id, "✅ Balans qo‘shildi.", reply_markup=admin_menu())
    try: bot.send_message(uid, f"💰 Balansingiz <b>{amount:,} so‘m</b>ga to‘ldirildi.")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "a_services")
def a_services(call):
    if not is_admin(call.from_user.id): return
    text = "🛍 <b>XIZMATLAR</b>\n\n" + ("\n".join(f"{n}: {p:,}/1000" for n,p in data["services"].items()) or "Yo‘q")
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("➕ Qo‘shish", callback_data="svc_add"))
    m.add(types.InlineKeyboardButton("💵 Narx", callback_data="svc_price"))
    m.add(types.InlineKeyboardButton("🗑 O‘chirish", callback_data="svc_del"))
    m.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="a_back"))
    bot.send_message(call.message.chat.id, text, reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data == "svc_add")
def svc_add(call):
    msg = bot.send_message(call.message.chat.id, "Xizmat nomi:")
    bot.register_next_step_handler(msg, svc_add_name)

def svc_add_name(m):
    msg = bot.send_message(m.chat.id, "1000 dona narxi:")
    bot.register_next_step_handler(msg, svc_add_price, m.text.strip())

def svc_add_price(m, name):
    try: p = int(m.text.strip())
    except: return bot.send_message(m.chat.id, "❌ Narx raqam bo‘lishi kerak.")
    data["services"][name] = p; save()
    bot.send_message(m.chat.id, "✅ Xizmat qo‘shildi.", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "svc_price")
def svc_price(call):
    msg = bot.send_message(call.message.chat.id, "Xizmat nomi:")
    bot.register_next_step_handler(msg, svc_price_name)

def svc_price_name(m):
    if m.text not in data["services"]: return bot.send_message(m.chat.id, "❌ Xizmat topilmadi.")
    msg = bot.send_message(m.chat.id, "Yangi narx:")
    bot.register_next_step_handler(msg, svc_price_value, m.text)

def svc_price_value(m, name):
    try: p = int(m.text.strip())
    except: return bot.send_message(m.chat.id, "❌ Narx raqam bo‘lishi kerak.")
    data["services"][name] = p; save()
    bot.send_message(m.chat.id, "✅ Narx yangilandi.", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "svc_del")
def svc_del(call):
    msg = bot.send_message(call.message.chat.id, "O‘chiriladigan xizmat nomi:")
    bot.register_next_step_handler(msg, svc_del_name)

def svc_del_name(m):
    if m.text not in data["services"]: return bot.send_message(m.chat.id, "❌ Xizmat topilmadi.")
    del data["services"][m.text]; save()
    bot.send_message(m.chat.id, "✅ O‘chirildi.", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "a_channels")
def a_channels(call):
    if not is_admin(call.from_user.id): return
    text = "📢 <b>MAJBURIY OBUNA</b>\n\n" + ("\n".join(data["channels"]) or "Kanallar yo‘q")
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="ch_add"))
    m.add(types.InlineKeyboardButton("🗑 Kanal o‘chirish", callback_data="ch_del"))
    m.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="a_back"))
    bot.send_message(call.message.chat.id, text, reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data == "ch_add")
def ch_add(call):
    msg = bot.send_message(call.message.chat.id, "Kanal username yuboring. Masalan: @mychannel")
    bot.register_next_step_handler(msg, ch_add_save)

def ch_add_save(m):
    ch = m.text.strip()
    if not ch.startswith("@"): ch = "@" + ch
    if ch not in data["channels"]: data["channels"].append(ch)
    save(); bot.send_message(m.chat.id, "✅ Kanal qo‘shildi.", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "ch_del")
def ch_del(call):
    msg = bot.send_message(call.message.chat.id, "O‘chiriladigan kanal username:")
    bot.register_next_step_handler(msg, ch_del_save)

def ch_del_save(m):
    ch = m.text.strip()
    if not ch.startswith("@"): ch = "@" + ch
    if ch in data["channels"]: data["channels"].remove(ch); save()
    bot.send_message(m.chat.id, "✅ Bajarildi.", reply_markup=admin_menu())

def subscribed(uid):
    for ch in data["channels"]:
        try:
            member = bot.get_chat_member(ch, uid)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

@bot.message_handler(content_types=["text"], func=lambda m: bool(data["channels"]) and not subscribed(m.from_user.id) and not is_admin(m.from_user.id))
def force_sub(message):
    m = types.InlineKeyboardMarkup()
    for ch in data["channels"]:
        m.add(types.InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
    m.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="checksub"))
    bot.send_message(message.chat.id, "❗ Avval quyidagi kanallarga obuna bo‘ling:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data == "checksub")
def checksub(call):
    if subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        bot.send_message(call.message.chat.id, "✅ Endi botdan foydalanishingiz mumkin.", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo‘lmagansiz.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "a_payments")
def a_payments(call):
    if not is_admin(call.from_user.id): return
    payments = data.get("payments", [])
    if not payments: return bot.send_message(call.message.chat.id, "📭 Kutilayotgan to‘lovlar yo‘q.", reply_markup=back_admin())
    text = "💳 <b>TO‘LOVLAR</b>\n\n"
    m = types.InlineKeyboardMarkup()
    for p in payments:
        if p["status"] == "Kutilmoqda":
            text += f"#{p['id']} | 👤 {p['user_id']} | 💰 {p['amount']:,}\n"
            m.row(types.InlineKeyboardButton(f"#{p['id']} ✅", callback_data=f"payok:{p['id']}"),
                  types.InlineKeyboardButton("❌", callback_data=f"payno:{p['id']}"))
    m.add(types.InlineKeyboardButton("⬅️ Admin panel", callback_data="a_back"))
    bot.send_message(call.message.chat.id, text or "📭 Kutilayotgan to‘lov yo‘q.", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("payok:"))
        
