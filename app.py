import os
import time
import logging
import threading
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from supabase import create_client, Client
from payos import PayOS
from payos.types import CreatePaymentLinkRequest

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.error import TelegramError

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", 5000))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
payOS = PayOS(
    client_id=PAYOS_CLIENT_ID,
    api_key=PAYOS_API_KEY,
    checksum_key=PAYOS_CHECKSUM_KEY
)

TZ = timezone(timedelta(hours=7))
_bot_instance = None
flask_app = Flask(__name__)


async def get_role(telegram_id: int) -> str:
    if supabase.table("bot_admins").select("*").eq("telegram_id", telegram_id).execute().data:
        return "admin"
    if supabase.table("bot_sellers").select("*").eq("telegram_id", telegram_id).execute().data:
        return "seller"
    return "user"


def insert_license_key(key: str, duration_hours: int) -> bool:
    data = {
        "key": key,
        "hwid": "",
        "duration_hours": duration_hours,
        "is_active": True,
        "device_name": "",
        "created_at": datetime.now(TZ).isoformat()
    }
    return len(supabase.table("license_keys").insert(data).execute().data) > 0


def get_key(key: str):
    result = supabase.table("license_keys").select("*").eq("key", key).limit(1).execute()
    return result.data[0] if result.data else None


def create_payment_record(telegram_id: int, username: str, license_key: str,
                          duration_hours: int, amount: int, order_code: int,
                          checkout_url: str = "") -> bool:
    data = {
        "telegram_id": telegram_id,
        "telegram_username": username,
        "license_key": license_key,
        "duration_hours": duration_hours,
        "amount": amount,
        "payos_order_code": str(order_code),
        "checkout_url": checkout_url,
        "status": "pending",
        "created_at": datetime.now(TZ).isoformat()
    }
    return len(supabase.table("payment_requests").insert(data).execute().data) > 0


def update_payment_status(order_code: int, status: str):
    supabase.table("payment_requests").update({
        "status": status,
        "paid_at": datetime.now(TZ).isoformat()
    }).eq("payos_order_code", str(order_code)).execute()


def get_payment_by_order(order_code: int):
    result = supabase.table("payment_requests").select("*").eq("payos_order_code", str(order_code)).execute()
    return result.data[0] if result.data else None


def get_pending_payment(telegram_id: int):
    result = supabase.table("payment_requests").select("*").eq("telegram_id", telegram_id).eq("status", "pending").limit(1).execute()
    return result.data[0] if result.data else None


def ensure_tables():
    for table in ["bot_admins", "bot_sellers", "payment_requests"]:
        try:
            supabase.table(table).select("*").limit(1).execute()
        except Exception:
            logger.warning(f"Table '{table}' chưa tồn tại. Chạy setup.sql trước.")


def fmt_time(seconds: int) -> str:
    parts = []
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    if d: parts.append(f"{d} ngày")
    if h: parts.append(f"{h} giờ")
    if m: parts.append(f"{m} phút")
    return " ".join(parts) if parts else "0 phút"


def duration_label(h: int) -> str:
    if h >= 720 and h % 720 == 0: return f"{h // 720} tháng"
    if h >= 168 and h % 168 == 0: return f"{h // 168} tuần"
    if h >= 24 and h % 24 == 0: return f"{h // 24} ngày"
    return f"{h} giờ"


# ─── Handlers ─────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.full_name
    role = await get_role(uid)

    if role == "admin":
        text = (
            f"\U0001f44b *Xin chào Admin {name}!*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\U0001f511 `/newkey <key> <giờ>`\nTạo key miễn phí\n\n"
            f"\U0001f50d `/check <key>`\nTra cứu thông tin key\n\n"
            f"\U0001f504 `/resethwid <key>`\nReset HWID (giữ nguyên thời gian)"
        )
    elif role == "seller":
        text = (
            f"\U0001f44b *Xin chào Seller {name}!*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\U0001f4b5 `/newkey <key> <giờ>`\nTạo key (thanh toán PayOS)\n\n"
            f"\U0001f50d `/check <key>`\nTra cứu thông tin key\n\n"
            f"\U0001f464 `/me`\nThông tin tài khoản"
        )
    else:
        text = (
            f"\U0001f44b *Xin chào {name}!*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\u26a0 Bạn chưa được phân quyền sử dụng bot.\n\n"
            f"Vui lòng liên hệ admin để được cấp quyền."
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.full_name
    uname = update.effective_user.username
    role = await get_role(uid)
    role_map = {"admin": "Admin", "seller": "Seller", "user": "Người dùng"}
    await update.message.reply_text(
        f"\U0001f464 *Thông tin tài khoản*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\u2022 **ID:** `{uid}`\n"
        f"\u2022 **Tên:** {name}\n"
        f"\u2022 **Username:** @{uname if uname else 'Không có'}\n"
        f"\u2022 **Vai trò:** {role_map[role]}",
        parse_mode="Markdown"
    )


async def newkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role = await get_role(uid)

    if role == "user":
        await update.message.reply_text("\u26a0 Bạn chưa được phân quyền sử dụng bot.")
        return

    if len(context.args) < 2 or not context.args[1].isdigit():
        await update.message.reply_text(
            "\u26a0 *Cú pháp không đúng*\n\n"
            "Sử dụng: `/newkey <key> <số_giờ>`\n"
            "Ví dụ: `/newkey GloryVN-142564 24`",
            parse_mode="Markdown"
        )
        return

    key = context.args[0]
    duration = int(context.args[1])

    if duration <= 0:
        await update.message.reply_text("\u26a0 Số giờ không hợp lệ.")
        return

    if get_key(key):
        await update.message.reply_text(
            f"\u26a0 Key `{key}` đã tồn tại trong hệ thống.",
            parse_mode="Markdown"
        )
        return

    if role == "admin":
        if insert_license_key(key, duration):
            await update.message.reply_text(
                f"\U0001f389 *Tạo key thành công!*\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"\U0001f511 **Key:** `{key}`\n"
                f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
                f"\U0001f7e2 **Trạng thái:** \u23f3 Chưa kích hoạt",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("\u274c *Thất bại*\nKhông thể tạo key. Vui lòng thử lại.", parse_mode="Markdown")

    elif role == "seller":
        pending = get_pending_payment(uid)
        if pending:
            oc = pending["payos_order_code"]
            keyboard = [
                [InlineKeyboardButton("\U0001f4b5 Thanh toán ngay", url=pending["checkout_url"])],
                [InlineKeyboardButton("\U0001f504 Kiểm tra", callback_data=f"check_{oc}"),
                 InlineKeyboardButton("\u274c Huỷ đơn", callback_data=f"cancel_{oc}")]
            ]
            await update.message.reply_text(
                f"\u26a0 *Đơn hàng cũ chưa hoàn tất!*\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                f"Bạn còn *1 đơn chưa thanh toán:*\n\n"
                f"\U0001f511 **Key:** `{pending['license_key']}`\n"
                f"\U0001f4b0 **Phí duy trì:** `{pending['amount']:,} VND`\n"
                f"\U0001f4c6 **Mã đơn:** `{oc}`\n\n"
                f"\U0001f446 Vui lòng thanh toán hoặc huỷ đơn này trước khi tạo đơn mới.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        username = update.effective_user.username or f"user_{uid}"
        fee = duration * 700
        order_code = int(time.time())

        msg = await update.message.reply_text(
            f"\U0001f4b3 *Đang tạo link thanh toán...*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f511 **Key:** `{key}`\n"
            f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
            f"\U0001f4b0 **Phí duy trì:** `{fee:,} VND`\n"
            f"\U0001f4c6 **Mã đơn:** `{order_code}`",
            parse_mode="Markdown"
        )

        try:
            payment_request = CreatePaymentLinkRequest(
                order_code=order_code,
                amount=fee,
                description=f"{key} {duration}h - {username}",
                cancel_url=f"{WEBHOOK_URL}/cancel" if WEBHOOK_URL else "https://t.me/PlaceholderCancel",
                return_url=f"{WEBHOOK_URL}/success" if WEBHOOK_URL else "https://t.me/PlaceholderSuccess"
            )
            payment_link = payOS.payment_requests.create(payment_request)
            create_payment_record(uid, username, key, duration, fee, order_code, payment_link.checkout_url)

            keyboard = [
                [InlineKeyboardButton("\U0001f4b5 Thanh toán ngay", url=payment_link.checkout_url)],
                [InlineKeyboardButton("\U0001f504 Kiểm tra", callback_data=f"check_{order_code}")]
            ]
            await msg.edit_text(
                f"\U0001f4b3 *Link thanh toán đã sẵn sàng!*\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                f"\U0001f511 **Key:** `{key}`\n"
                f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
                f"\U0001f4b0 **Phí duy trì:** `{fee:,} VND`\n"
                f"\U0001f4c6 **Mã đơn:** `{order_code}`\n\n"
                f"\u26a0 Đây là phí duy trì server key.\n\n"
                f"\U0001f447 Nhấn nút bên dưới để thanh toán:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Lỗi tạo payment link: {e}")
            await msg.edit_text(f"\u274c *Lỗi tạo link thanh toán:*\n`{e}`", parse_mode="Markdown")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "\u26a0 *Cú pháp không đúng*\n\n"
            "Sử dụng: `/check <key>`\n"
            "Ví dụ: `/check GloryVN-142564`",
            parse_mode="Markdown"
        )
        return

    key = context.args[0]
    record = get_key(key)

    if not record:
        await update.message.reply_text(
            f"\U0001f50d *Không tìm thấy key*\n\n"
            f"Key `{key}` không tồn tại trong hệ thống.",
            parse_mode="Markdown"
        )
        return

    now = datetime.now(TZ)
    hwid = record.get("hwid", "") or ""
    expires_at = record.get("expires_at")
    duration = record["duration_hours"]
    created = record.get("created_at", "")

    if hwid and expires_at:
        expires = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at
        remaining = expires - now
        if remaining.total_seconds() > 0:
            status = f"\U0001f7e2 Đã kích hoạt"
            extra = f"\u23f1 **Còn lại:** {fmt_time(int(remaining.total_seconds()))}"
        else:
            status = f"\U0001f534 Đã hết hạn"
            extra = f"\u274c Key đã hết hiệu lực"
    elif hwid:
        status = f"\U0001f7e2 Đã kích hoạt"
        extra = f"\U0001f504 Key vĩnh viễn"
    else:
        status = f"\U0001f7e1 Chưa kích hoạt"
        extra = f"\u23f3 Chờ người dùng kích hoạt"

    await update.message.reply_text(
        f"\U0001f50d *Thông tin key*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f511 **Key:** `{key}`\n"
        f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
        f"\U0001f5d3 **Tạo lúc:** `{created[:19] if created else 'N/A'}`\n"
        f"\U0001f7e1 **Trạng thái:** {status}\n"
        f"{extra}",
        parse_mode="Markdown"
    )


async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_code = int(query.data.split("_")[1])
    record = get_payment_by_order(order_code)

    if not record:
        await query.edit_message_text("\u274c Không tìm thấy đơn hàng.")
        return

    if record["status"] == "pending":
        try:
            payment_info = payOS.payment_requests.get(order_code)
            payos_status = getattr(payment_info, 'status', None)
            logger.info(f"PayOS check {order_code}: status={payos_status}")

            if payos_status == "PAID":
                key = record["license_key"]
                duration = record["duration_hours"]

                if insert_license_key(key, duration):
                    update_payment_status(order_code, "completed")
                    await query.edit_message_text(
                        f"\U0001f389 *Thanh toán thành công!*\n"
                        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                        f"\U0001f511 **Key:** `{key}`\n"
                        f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
                        f"\U0001f4c6 **Mã đơn:** `{order_code}`",
                        parse_mode="Markdown"
                    )
                    return
        except Exception as e:
            logger.warning(f"Lỗi check PayOS {order_code}: {e}")

    status_map = {
        "pending": "\u23f3 Đang chờ thanh toán",
        "completed": "\u2705 Đã thanh toán",
        "cancelled": "\u274c Đã huỷ",
    }
    color_map = {
        "pending": "\U0001f7e1",
        "completed": "\U0001f7e2",
        "cancelled": "\U0001f534",
    }
    s = record["status"]
    lines = [
        f"\U0001f4c6 *Trạng thái đơn hàng*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f4c6 **Mã đơn:** `{order_code}`\n"
        f"\U0001f511 **Key:** `{record['license_key']}`\n"
        f"\U0001f4b0 **Phí duy trì:** `{record['amount']:,} VND`\n"
        f"{color_map.get(s, '')} **Trạng thái:** {status_map.get(s, s)}"
    ]
    if s == "completed":
        lines.append(f"\U0001f511 **Key:** `{record['license_key']}`")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")


async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_code = int(query.data.split("_")[1])
    record = get_payment_by_order(order_code)

    if not record:
        await query.edit_message_text("\u274c Không tìm thấy đơn hàng.")
        return
    if record["status"] != "pending":
        await query.edit_message_text(f"\u26a0 Đơn hàng đã {record['status']}, không thể huỷ.")
        return
    if record["telegram_id"] != query.from_user.id:
        await query.edit_message_text("\u26a0 Đây không phải đơn hàng của bạn.")
        return

    update_payment_status(order_code, "cancelled")
    await query.edit_message_text(
        f"\u274c *Đã huỷ đơn hàng*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f4c6 **Mã đơn:** `{order_code}`\n"
        f"\U0001f511 **Key:** `{record['license_key']}`\n\n"
        f"\U0001f446 Bạn có thể dùng `/newkey` để tạo đơn mới.",
        parse_mode="Markdown"
    )


async def resethwid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await get_role(uid) == "admin":
        await update.message.reply_text("\u26a0 Bạn không có quyền thực hiện thao tác này.")
        return

    if not context.args:
        await update.message.reply_text(
            "\u26a0 *Cú pháp không đúng*\n\n"
            "Sử dụng: `/resethwid <key>`\n"
            "Ví dụ: `/resethwid GloryVN-142564`",
            parse_mode="Markdown"
        )
        return

    key = context.args[0]
    record = get_key(key)

    if not record:
        await update.message.reply_text(f"\u274c Key `{key}` không tồn tại.", parse_mode="Markdown")
        return

    supabase.table("license_keys").update({
        "hwid": "",
        "device_name": "",
    }).eq("key", key).execute()

    await update.message.reply_text(
        f"\U0001f504 *Reset HWID thành công!*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f511 **Key:** `{key}`\n"
        f"\U0001f7e2 **Trạng thái:** \u23f3 Chờ kích hoạt lại\n\n"
        f"\u2705 Người dùng có thể kích hoạt key trên thiết bị mới.",
        parse_mode="Markdown"
    )


def send_telegram(chat_id: int, text: str):
    if _bot_instance:
        try:
            _bot_instance.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except TelegramError as e:
            logger.error(f"Lỗi gửi tin nhắn {chat_id}: {e}")


def process_paid_order(order_code: int) -> str | None:
    record = get_payment_by_order(order_code)
    if not record or record["status"] == "completed":
        return None

    key = record["license_key"]
    duration = record["duration_hours"]
    uid = record["telegram_id"]

    if insert_license_key(key, duration):
        update_payment_status(order_code, "completed")
        send_telegram(uid,
            f"\U0001f389 *Thanh toán thành công!*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f511 **Key:** `{key}`\n"
            f"\u23f1 **Thời hạn:** `{duration_label(duration)} ({duration}h)`\n"
            f"\U0001f4c6 **Mã đơn:** `{order_code}`"
        )
        logger.info(f"Đã xử lý đơn {order_code} -> key {key}")
        return key
    return None


@flask_app.route("/payos-webhook", methods=["POST"])
def payos_webhook():
    try:
        data = payOS.webhooks.verify(request.data)
        order_code = data.order_code
        code = getattr(data, 'code', '')
        logger.info(f"Webhook: order_code={order_code}, code={code}")

        record = get_payment_by_order(order_code)
        if not record:
            return jsonify({"message": "Not found"}), 404
        if record["status"] == "completed":
            return jsonify({"message": "OK"}), 200

        if code == "00":
            process_paid_order(order_code)

        return jsonify({"message": "OK"}), 200
    except Exception as e:
        logger.error(f"Webhook lỗi: {e}")
        return jsonify({"message": "Invalid"}), 400


def _get_oc():
    return request.args.get("orderCode") or request.args.get("order_code")


@flask_app.route("/success")
def payment_success():
    oc = _get_oc()
    if not oc:
        return "<h2>Thiếu mã đơn hàng</h2>", 400

    order_code = int(oc)
    try:
        info = payOS.payment_requests.get(order_code)
        payos_status = getattr(info, 'status', None)
    except Exception:
        payos_status = None

    record = get_payment_by_order(order_code)
    if not record:
        return f"<h2>Không tìm thấy đơn hàng {oc}</h2>"

    if (payos_status == "PAID" or payos_status == "COMPLETED") and record["status"] == "pending":
        key = process_paid_order(order_code)
        status_text = "Thành công"
        msg = f"Key: <b>{key}</b>" if key else "Lỗi tạo key, liên hệ admin."
    elif record["status"] == "completed":
        status_text = "Thành công"
        msg = f"Key: <b>{record['license_key']}</b>"
    elif record["status"] == "cancelled":
        status_text = "Đã huỷ"
        msg = "Đơn hàng đã bị huỷ."
    else:
        status_name = payos_status or "Đang chờ"
        return f"""<html><head><meta charset="utf-8"><title>Kết quả thanh toán</title>
<style>body{{font-family:sans-serif;text-align:center;padding:40px}}
h2{{color:#ffc107}}</style></head><body>
<h2>⏳ Giao dịch đang xử lý</h2>
<p>Mã đơn: <b>{oc}</b></p>
<p>Trạng thái PayOS: {status_name}</p>
<p>Vui lòng quay lại Telegram và nhấn nút <b>Kiểm tra</b>.</p>
<p><a href="https://t.me/GloryVN_Ad_Bot">Quay lại Telegram</a></p>
</body></html>"""

    return f"""<html><head><meta charset="utf-8"><title>Kết quả thanh toán</title>
<style>body{{font-family:sans-serif;text-align:center;padding:40px}}
h2{{color:#333}}.ok{{color:#28a745}}.ko{{color:#dc3545}}</style></head>
<body>
<h2 class="{'ok' if status_text == 'Thành công' else 'ko'}">
{'✅' if status_text == 'Thành công' else '❌'} {status_text}</h2>
<p>Mã đơn: <b>{oc}</b></p>
<p>{msg}</p>
<p><a href="https://t.me/GloryVN_Ad_Bot">Quay lại Telegram</a></p>
</body></html>"""


@flask_app.route("/cancel")
def payment_cancel():
    oc = _get_oc()
    order_code = int(oc) if oc else None

    if order_code:
        update_payment_status(order_code, "cancelled")
        record = get_payment_by_order(order_code)
        if record:
            send_telegram(record["telegram_id"],
                f"\u274c *Đơn hàng đã bị huỷ*\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"\U0001f4c6 **Mã đơn:** `{oc}`\n"
                f"\U0001f511 **Key:** `{record['license_key']}`"
            )

    return f"""<html><head><meta charset="utf-8"><title>Đã huỷ</title>
<style>body{{font-family:sans-serif;text-align:center;padding:40px;color:#666}}
h2{{color:#dc3545}}</style></head>
<body>
<h2>❌ Đã huỷ thanh toán</h2>
<p>Mã đơn: <b>{oc}</b></p>
<p>Bạn có thể tạo đơn mới qua Telegram.</p>
<p><a href="https://t.me/GloryVN_Ad_Bot">Quay lại Telegram</a></p>
</body></html>"""


def start_bot():
    global _bot_instance
    ensure_tables()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    _bot_instance = application

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("me", me))
    application.add_handler(CommandHandler("newkey", newkey))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("resethwid", resethwid))
    application.add_handler(CallbackQueryHandler(check_payment, pattern=r"^check_"))
    application.add_handler(CallbackQueryHandler(cancel_payment, pattern=r"^cancel_"))

    logger.info("Bot Telegram đã sẵn sàng (polling)")
    application.run_polling()


# Gunicorn sẽ dùng 'app' để chạy Flask
app = flask_app

# Khi deploy (gunicorn import), tự động chạy bot polling trong thread nền
if not os.getenv("RENDER_SKIP_BOT", ""):
    logger.info("Khởi động bot Telegram trong thread nền...")
    threading.Thread(target=start_bot, daemon=True).start()

# Chạy trực tiếp (python app.py)
if __name__ == "__main__":
    if WEBHOOK_URL:
        threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT, debug=False), daemon=True).start()
    start_bot()
