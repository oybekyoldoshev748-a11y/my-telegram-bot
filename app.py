import os
import json
import time
import threading
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# TELEGRAM SMM BOT - ONE FILE / RENDER READY
# No external Python package is required.
# Render Start Command can be: python app.py
#
# Environment variables:
# BOT_TOKEN = Telegram bot token
# ADMIN_ID  = your Telegram numeric ID
#
# Optional:
# PORT      = Render port (default 10000)
# SMM_API_URL = generic SMM API endpoint
# SMM_API_KEY = generic SMM API key
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
PORT = int(os.getenv("PORT", "10000"))
DATA_FILE = "bot_data.json"

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable is missing.")
if not ADMIN_ID:
    print("WARNING: ADMIN_ID environment variable is missing.")

try:
    ADMIN_ID_INT = int(ADMIN_ID)
except Exception:
    ADMIN_ID_INT = 0

API = "https://api.telegram.org/bot" + BOT_TOKEN

DEFAULT_SERVICES = {
    "👤 Obunachi": 1000,
    "❤️ Like": 1500,
    "👁 Ko'rish": 500,
    "💬 Komment": 3000,
    "📈 Kanal reklama": 10000,
}

data_lock = threading.RLock()

def default_data():
    return {
        "users": {},
        "orders": [],
        "services": DEFAULT_SERVICES.copy(),
        "settings": {
            "channel": "",
            "channel_url": "",
            "support": "",
            "payment_text": "💳 To'lov uchun admin bilan bog'laning.",
            "admin_note": "",
            "welcome": "👋 Xush kelibsiz!\n\nKerakli xizmatni tanlang.",
            "smm_api_url": os.getenv("SMM_API_URL", ""),
            "smm_api_key": os.getenv("SMM_API_KEY", ""),
        },
        "next_order_id": 1,
        "banned": [],
        "pending_checks": {},
    }

def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        base = default_data()
        for k, v in base.items():
            if k not in d:
                d[k] = v
        return d
    except Exception as e:
        print("DATA LOAD ERROR:", e)
        return default_data()

db = load_data()

def save():
    with data_lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)

def tg(method, params=None):
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN missing"}
    params = params or {}
    encoded = urllib.parse.urlencode(params).encode()
    try:
        req = urllib.request.Request(API + "/" + method, data=encoded)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("Telegram API ERROR:", method, e)
        return {"ok": False, "description": str(e)}

def send(chat_id, text, keyboard=None, parse_mode="HTML"):
    p = {"chat_id": chat_id, "text": text}
    if parse_mode:
        p["parse_mode"] = parse_mode
    if keyboard:
        p["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return tg("sendMessage", p)

def edit(chat_id, message_id, text, keyboard=None):
    p = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        p["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return tg("editMessageText", p)

def answer(callback_id, text=""):
    return tg("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

def is_admin(uid):
    return int(uid) == ADMIN_ID_INT and ADMIN_ID_INT != 0

def user(uid, name=""):
    uid = str(uid)
    with data_lock:
        if uid not in db["users"]:
            db["users"][uid] = {
                "id": int(uid),
                "name": name or "",
                "balance": 0,
                "orders": 0,
                "ref": None,
                "refs": 0,
                "joined": int(time.time()),
            }
            save()
        elif name:
            db["users"][uid]["name"] = name
            save()
        return db["users"][uid]

def kb(rows):
    return {"inline_keyboard": rows}

def main_menu(uid):
    rows = [
        [{"text": "🛍 Xizmatlar", "callback_data": "services"},
         {"text": "💰 Balans", "callback_data": "balance"}],
        [{"text": "🛒 Buyurtmalarim", "callback_data": "my_orders"},
         {"text": "💳 Balans to'ldirish", "callback_data": "deposit"}],
        [{"text": "👥 Referal", "callback_data": "referral"},
         {"text": "📞 Yordam", "callback_data": "support"}],
    ]
    if is_admin(uid):
        rows.append([{"text": "👑 ADMIN PANEL", "callback_data": "admin"}])
    return kb(rows)

def admin_menu():
    return kb([
        [{"text": "📊 Statistika", "callback_data": "a_stats"},
         {"text": "🛒 Buyurtmalar", "callback_data": "a_orders"}],
        [{"text": "💰 Balans qo'shish", "callback_data": "a_balance"},
         {"text": "🛍 Xizmatlar", "callback_data": "a_services"}],
        [{"text": "💵 Narxlar", "callback_data": "a_prices"},
         {"text": "📣 Reklama", "callback_data": "a_broadcast"}],
        [{"text": "📢 Majburiy obuna", "callback_data": "a_channel"},
         {"text": "⚙️ Sozlamalar", "callback_data": "a_settings"}],
        [{"text": "🔌 SMM API", "callback_data": "a_smm"},
         {"text": "📥 Cheklar", "callback_data": "a_checks"}],
        [{"text": "🏠 Bosh menyu", "callback_data": "home"}],
    ])

def back_admin():
    return kb([[{"text": "⬅️ Admin panel", "callback_data": "admin"}]])

def esc(s):
    s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def subscription_ok(uid):
    channel = db["settings"].get("channel", "").strip()
    if not channel:
        return True
    r = tg("getChatMember", {"chat_id": channel, "user_id": uid})
    if not r.get("ok"):
        return True
    status = r.get("result", {}).get("status", "")
    return status in ("creator", "administrator", "member")

def subscription_prompt(uid):
    channel = db["settings"].get("channel", "")
    url = db["settings"].get("channel_url", "") or ("https://t.me/" + channel.lstrip("@"))
    return kb([
        [{"text": "📢 Kanalga o'tish", "url": url}],
        [{"text": "✅ Tekshirish", "callback_data": "check_sub"}],
    ])

def show_home(chat_id, uid):
    u = user(uid)
    text = db["settings"].get("welcome", "👋 Xush kelibsiz!")
    text += f"\n\n💰 Balans: <b>{u['balance']:,} so'm</b>"
    send(chat_id, text, main_menu(uid))

def services_text():
    if not db["services"]:
        return "🛍 <b>XIZMATLAR</b>\n\nHozircha xizmatlar yo'q."
    return "🛍 <b>XIZMATLAR</b>\n\n" + "\n\n".join(
        f"🔹 <b>{esc(n)}</b>\n💰 {p:,} so'm / 1000" for n, p in db["services"].items()
    )

def services_menu():
    rows = []
    for name in db["services"]:
        rows.append([{"text": name, "callback_data": "svc:" + name}])
    rows.append([{"text": "⬅️ Bosh menyu", "callback_data": "home"}])
    return kb(rows)

def ask_order(chat_id, uid, service):
    price = db["services"].get(service)
    if price is None:
        return
    send(chat_id,
         f"🛍 <b>{esc(service)}</b>\n\n"
         f"💰 Narx: <b>{price:,} so'm / 1000</b>\n\n"
         "Buyurtma miqdorini yuboring.\n"
         "Masalan: <b>1000</b>",
         kb([[{"text": "❌ Bekor qilish", "callback_data": "home"}]]))
    pending[uid] = {"type": "quantity", "service": service}

pending = {}

def create_order(uid, chat_id, quantity):
    state = pending.get(uid)
    if not state or state.get("type") != "quantity":
        return
    service = state["service"]
    price_per_1000 = int(db["services"][service])
    try:
        quantity = int(quantity)
    except Exception:
        send(chat_id, "❌ Miqdor faqat raqam bo'lishi kerak.")
        return
    if quantity < 1 or quantity > 10000000:
        send(chat_id, "❌ Miqdor noto'g'ri.")
        return
    total = max(1, int((price_per_1000 * quantity + 999) // 1000))
    u = user(uid)
    if u["balance"] < total:
        send(chat_id,
             f"❌ Balansingiz yetarli emas.\n\n"
             f"💰 Kerak: <b>{total:,} so'm</b>\n"
             f"💵 Balans: <b>{u['balance']:,} so'm</b>\n\n"
             "Avval balansni to'ldiring.",
             main_menu(uid))
        pending.pop(uid, None)
        return
    order_id = db["next_order_id"]
    db["next_order_id"] += 1
    u["balance"] -= total
    u["orders"] += 1
    order = {
        "id": order_id,
        "user_id": int(uid),
        "service": service,
        "quantity": quantity,
        "price": total,
        "status": "⏳ Kutilmoqda",
        "created": int(time.time()),
        "smm_id": None,
    }
    db["orders"].append(order)
    save()
    pending.pop(uid, None)
    send(chat_id,
         f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
         f"🆔 ID: <code>#{order_id}</code>\n"
         f"🛍 {esc(service)}\n"
         f"🔢 {quantity:,}\n"
         f"💰 {total:,} so'm\n"
         f"📊 {order['status']}",
         main_menu(uid))
    if db["settings"].get("smm_api_url"):
        result = smm_add(order)
        if result:
            send(chat_id, f"🚀 SMM tizimiga yuborildi.\n🆔 SMM ID: <code>{esc(result)}</code>")

def smm_add(order):
    url = db["settings"].get("smm_api_url", "").strip()
    key = db["settings"].get("smm_api_key", "").strip()
    if not url or not key:
        return None
    # Generic SMM API: action=add, service, link, quantity.
    # The link is requested only when the service is configured by provider.
    # For providers requiring a different payload, change this function.
    payload = {
        "key": key,
        "action": "add",
        "service": str(order.get("service_id", "")),
        "quantity": str(order["quantity"]),
    }
    try:
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(payload).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            obj = json.loads(r.read().decode())
        if "order" in obj:
            order["smm_id"] = obj["order"]
            order["status"] = "🚀 Jarayonda"
            save()
            return str(obj["order"])
    except Exception as e:
        print("SMM API ERROR:", e)
    return None

def stats():
    total_balance = sum(int(x.get("balance", 0)) for x in db["users"].values())
    done = sum(1 for x in db["orders"] if "Bajar" in x.get("status", ""))
    return (
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(db['users'])}</b>\n"
        f"🛒 Buyurtmalar: <b>{len(db['orders'])}</b>\n"
        f"✅ Bajarilgan: <b>{done}</b>\n"
        f"💰 Jami balans: <b>{total_balance:,} so'm</b>\n"
        f"🧾 Cheklar: <b>{len(db['pending_checks'])}</b>"
    )

def admin_orders_text():
    if not db["orders"]:
        return "📭 Buyurtmalar yo'q."
    text = "🛒 <b>SO'NGGI BUYURTMALAR</b>\n\n"
    for o in db["orders"][-15:][::-1]:
        text += (
            f"🆔 #{o['id']} | 👤 <code>{o['user_id']}</code>\n"
            f"🛍 {esc(o['service'])}\n"
            f"🔢 {o['quantity']:,} | 💰 {o['price']:,} so'm\n"
            f"📊 {esc(o['status'])}\n\n"
        )
    return text

def my_orders(uid):
    arr = [x for x in db["orders"] if int(x["user_id"]) == int(uid)]
    if not arr:
        return "🛒 Sizda hali buyurtmalar yo'q."
    text = "🛒 <b>BUYURTMALARIM</b>\n\n"
    for o in arr[-10:][::-1]:
        text += (
            f"🆔 #{o['id']} — {esc(o['service'])}\n"
            f"🔢 {o['quantity']:,} | 💰 {o['price']:,} so'm\n"
            f"📊 {esc(o['status'])}\n\n"
        )
    return text

def referral(uid):
    u = user(uid)
    bot_username = ""
    r = tg("getMe")
    if r.get("ok"):
        bot_username = r["result"]["username"]
    link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else f"ref_{uid}"
    return (
        "👥 <b>REFERAL TIZIMI</b>\n\n"
        f"👤 Taklif qilganlaringiz: <b>{u['refs']}</b>\n\n"
        f"🔗 Sizning havolangiz:\n<code>{link}</code>\n\n"
        "Do'stingiz shu havola orqali kirsa, referalingiz hisoblanadi."
    )

def handle_start(msg):
    uid = int(msg["from"]["id"])
    chat_id = msg["chat"]["id"]
    name = msg["from"].get("first_name", "")
    u = user(uid, name)
    args = (msg.get("text") or "").split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref = int(args[1][4:])
            if ref != uid and not u.get("ref") and str(ref) in db["users"]:
                u["ref"] = ref
                db["users"][str(ref)]["refs"] += 1
                save()
        except Exception:
            pass
    if uid in db["banned"]:
        send(chat_id, "🚫 Siz bloklangansiz.")
        return
    if not subscription_ok(uid):
        send(chat_id, "📢 <b>Botdan foydalanish uchun kanalga obuna bo'ling.</b>",
             subscription_prompt(uid))
        return
    show_home(chat_id, uid)

def handle_message(msg):
    uid = int(msg["from"]["id"])
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    user(uid, msg["from"].get("first_name", ""))
    if uid in db["banned"]:
        return
    if text.startswith("/start"):
        handle_start(msg)
        return
    if text == "/admin":
        if is_admin(uid):
            send(chat_id, "👑 <b>ADMIN PANEL</b>", admin_menu())
        return
    state = pending.get(uid)
    if state:
        typ = state.get("type")
        if typ == "quantity":
            create_order(uid, chat_id, text)
            return
        if typ == "balance_user" and is_admin(uid):
            try:
                target = int(text)
            except Exception:
                send(chat_id, "❌ Telegram ID faqat raqam bo'lishi kerak.")
                return
            if str(target) not in db["users"]:
                send(chat_id, "❌ Foydalanuvchi topilmadi.")
                return
            pending[uid] = {"type": "balance_amount", "target": target}
            send(chat_id, "💵 Qancha balans qo'shamiz?\nMasalan: 10000")
            return
        if typ == "balance_amount" and is_admin(uid):
            try:
                amount = int(text)
            except Exception:
                send(chat_id, "❌ Summa raqam bo'lishi kerak.")
                return
            if amount <= 0:
                send(chat_id, "❌ Summa 0 dan katta bo'lsin.")
                return
            target = str(state["target"])
            db["users"][target]["balance"] += amount
            save()
            send(chat_id, f"✅ <b>Balans qo'shildi</b>\n\n👤 {target}\n➕ {amount:,} so'm\n💰 Yangi balans: {db['users'][target]['balance']:,} so'm", admin_menu())
            try:
                send(int(target), f"💰 Balansingiz to'ldirildi!\n➕ <b>{amount:,} so'm</b>\n💵 Balans: <b>{db['users'][target]['balance']:,} so'm</b>")
            except Exception:
                pass
            pending.pop(uid, None)
            return
        if typ == "broadcast" and is_admin(uid):
            pending.pop(uid, None)
            count = 0
            for k in list(db["users"]):
                try:
                    r = send(int(k), text)
                    if r.get("ok"):
                        count += 1
                except Exception:
                    pass
                time.sleep(0.03)
            send(chat_id, f"📣 Reklama yuborildi.\n✅ Yetkazildi: <b>{count}</b>", admin_menu())
            return
        if typ == "channel" and is_admin(uid):
            db["settings"]["channel"] = text
            db["settings"]["channel_url"] = "https://t.me/" + text.lstrip("@")
            save()
            pending.pop(uid, None)
            send(chat_id, f"✅ Majburiy kanal saqlandi: <code>{esc(text)}</code>", admin_menu())
            return
        if typ == "service_add" and is_admin(uid):
            parts = text.split("|", 1)
            if len(parts) != 2:
                send(chat_id, "Format: Xizmat nomi | narx")
                return
            try:
                price = int(parts[1].strip())
            except Exception:
                send(chat_id, "❌ Narx raqam bo'lishi kerak.")
                return
            db["services"][parts[0].strip()] = price
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ Xizmat qo'shildi.", admin_menu())
            return
        if typ == "price" and is_admin(uid):
            parts = text.split("|", 1)
            if len(parts) != 2 or parts[0] not in db["services"]:
                send(chat_id, "Format: Xizmat nomi | yangi narx")
                return
            try:
                price = int(parts[1].strip())
            except Exception:
                send(chat_id, "❌ Narx raqam bo'lishi kerak.")
                return
            db["services"][parts[0]] = price
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ Narx o'zgartirildi.", admin_menu())
            return
        if typ == "support" and is_admin(uid):
            db["settings"]["support"] = text
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ Yordam kontakti saqlandi.", admin_menu())
            return
        if typ == "payment" and is_admin(uid):
            db["settings"]["payment_text"] = text
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ To'lov matni saqlandi.", admin_menu())
            return
        if typ == "smm_url" and is_admin(uid):
            db["settings"]["smm_api_url"] = text
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ SMM API URL saqlandi.", admin_menu())
            return
        if typ == "smm_key" and is_admin(uid):
            db["settings"]["smm_api_key"] = text
            save()
            pending.pop(uid, None)
            send(chat_id, "✅ SMM API KEY saqlandi.", admin_menu())
            return
        if typ == "status" and is_admin(uid):
            parts = text.split("|", 1)
            if len(parts) == 2:
                try:
                    oid = int(parts[0].strip())
                    for o in db["orders"]:
                        if o["id"] == oid:
                            o["status"] = parts[1].strip()
                            save()
                            send(chat_id, f"✅ #{oid} statusi o'zgartirildi.", admin_menu())
                            try:
                                send(o["user_id"], f"📦 <b>Buyurtma #{oid}</b>\n📊 Yangi status: <b>{esc(o['status'])}</b>")
                            except Exception:
                                pass
                            break
                    else:
                        send(chat_id, "❌ Buyurtma topilmadi.")
                except Exception:
                    send(chat_id, "Format: ID | status")
            pending.pop(uid, None)
            return

    if text:
        send(chat_id, "👇 Menyudan foydalaning.", main_menu(uid))

def handle_callback(c):
    uid = int(c["from"]["id"])
    chat_id = c["message"]["chat"]["id"]
    mid = c["message"]["message_id"]
    action = c.get("data", "")
    answer(c["id"])
    user(uid, c["from"].get("first_name", ""))

    if action == "check_sub":
        if subscription_ok(uid):
            answer(c["id"], "✅ Obuna tasdiqlandi!")
            show_home(chat_id, uid)
        else:
            answer(c["id"], "❌ Hali obuna bo'lmagansiz.")
        return

    if action == "home":
        show_home(chat_id, uid)
        return

    if action == "services":
        edit(chat_id, mid, services_text(), services_menu())
        return

    if action.startswith("svc:"):
        service = action[4:]
        if service in db["services"]:
            ask_order(chat_id, uid, service)
