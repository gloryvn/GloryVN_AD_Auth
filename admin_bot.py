import logging
import random
import string
import requests
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import CUSTOMER_BOT_TOKEN, ADMIN_CHAT_ID, KEY_TYPES, VIETQR_ACCOUNT
from database import (
    get_order, update_order, create_order,
    supabase_insert_key, supabase_query_keys,
    supabase_delete_key, supabase_reset_hwid,
    supabase_get_key, supabase_toggle_key,
    supabase_count_keys,
    is_seller, add_seller, remove_seller, list_sellers,
)
from key_gen import generate_key
from payment import download_qr_image

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _is_admin(uid):
    return uid == ADMIN_CHAT_ID


def _can_access(uid):
    return _is_admin(uid) or is_seller(uid)


def _fmt_price(vnd):
    s = f"{vnd:,}".replace(",", ".")
    return f"{s}đ"


def _fmt_key(k):
    act = "✅" if k.get("is_active") else "❌"
    hw = k.get("hwid", "") or "—"
    return (f"`{k['key']}` – {k.get('duration_hours', 0)}h "
            f"– {act} – HWID: {hw} – {k.get('created_at', '')[:10]}")


def _page_buttons(page, total, prefix):
    kb = []
    if page > 0:
        kb.append({"text": "⬅ Trước", "callback_data": f"{prefix}_page_{page - 1}"})
    if (page + 1) * PAGE_SIZE < total:
        kb.append({"text": "Sau ➡", "callback_data": f"{prefix}_page_{page + 1}"})
    return {"inline_keyboard": [kb]} if kb else None


# ---------------------------------------------------------------------------
# /start – Admin → menu, Seller → mua key
# ---------------------------------------------------------------------------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if _is_admin(uid):
        await update.message.reply_text(
            "🔐 *Admin Bot – GloryVN 247 Store*\n\n"
            "*/addseller* `<chat_id>` – Thêm seller\n"
            "*/removeseller* `<chat_id>` – Xoá seller\n"
            "*/sellers* – Danh sách seller\n"
            "*/createkey* `<hours>` `[custom_id]` – Tạo key thủ công\n"
            "*/keyinfo* `<key>` – Chi tiết key\n"
            "*/mykeys* – Key do bạn tạo\n"
            "*/deletekey* `<key>` – Xoá key\n"
            "*/resethwid* `<key>` – Reset HWID\n"
            "*/togglekey* `<key>` – Bật/tắt key\n"
            "*/stats* – Thống kê key",
            parse_mode="Markdown"
        )
        return

    if not is_seller(uid):
        await update.message.reply_text("❌ Bạn không có quyền truy cập bot.")
        return

    ctx.user_data.clear()
    await _show_menu(update.message)


async def _show_menu(msg):
    # 8 buttons in 2 columns: random | custom
    kb = []
    for kid in ("1_day", "1_week", "1_month", "forever"):
        name, hours, p_r, p_c = KEY_TYPES[kid]
        row = [
            InlineKeyboardButton(f"🎲 {name} {_fmt_price(p_r)}", callback_data=f"buy_{kid}_r"),
            InlineKeyboardButton(f"✏️ {name} {_fmt_price(p_c)}", callback_data=f"buy_{kid}_c"),
        ]
        kb.append(row)
    await msg.reply_text(
        "👋 *Chào mừng bạn đến với GloryVN 247 Store!*\n\n"
        "Chọn gói key bên dưới để tạo QR thanh toán:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ---------------------------------------------------------------------------
# Seller flow – chọn → tạo QR ngay
# ---------------------------------------------------------------------------

async def buy_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    logger.info("Seller buy_key called: uid=%s, data=%s", uid, q.data)
    
    if _is_admin(uid) or not is_seller(uid):
        logger.warning("User %s is admin or not seller", uid)
        return

    # Parse callback data: "buy_1_day_r" hoặc "buy_forever_c"
    # Format: buy_{key_id}_{mode}
    data = q.data.replace("buy_", "")  # "1_day_r" hoặc "forever_c"
    
    # Lấy mode (r/c) - ký tự cuối
    mode = data[-1]  # "r" hoặc "c"
    
    # Lấy key_id - bỏ mode và dấu _ cuối
    kid = data[:-2]  # "1_day" hoặc "forever"
    
    logger.info("Parsed: kid=%s, mode=%s", kid, mode)

    if kid not in KEY_TYPES:
        logger.error("Invalid key_id: %s (available: %s)", kid, list(KEY_TYPES.keys()))
        await q.edit_message_text(f"❌ Lỗi: Key ID không hợp lệ ({kid})")
        return

    name, hours, p_r, p_c = KEY_TYPES[kid]
    price = p_r if mode == "r" else p_c
    label = "Key ngẫu nhiên" if mode == "r" else "Key tùy chỉnh"

    logger.info("Processing key: kid=%s, mode=%s, price=%s", kid, mode, price)

    # Lưu thông tin tạm thời
    ctx.user_data["sel_kid"] = kid
    ctx.user_data["sel_name_base"] = name
    ctx.user_data["sel_hours"] = hours
    ctx.user_data["sel_price"] = price
    ctx.user_data["sel_mode"] = mode
    ctx.user_data["sel_label"] = label

    # Nếu là key NGẪU NHIÊN → tạo QR ngay
    if mode == "r":
        logger.info("Random key selected, creating QR immediately")
        try:
            await _seller_create_payment_qr(update, ctx, None)
        except Exception as e:
            logger.error("Error creating QR: %s", e, exc_info=True)
            await q.edit_message_text(f"❌ Lỗi: {str(e)}")
    # Nếu là key TÙY CHỈNH → hỏi tên key trước
    else:
        logger.info("Custom key selected, asking for name")
        ctx.user_data["sel_waiting_custom"] = True
        try:
            await q.edit_message_text(
                "✏️ *Nhập tên key tùy chỉnh của bạn:*\n\n"
                "📝 Tối đa 12 ký tự, chỉ chữ và số (A-Z, 0-9)\n"
                "💡 Ví dụ: MYKEY123, SHOP2024, ABC\n\n"
                "⚠️ Gửi tin nhắn để nhập hoặc /cancel để hủy.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Error editing message: %s", e, exc_info=True)
            await ctx.bot.send_message(
                chat_id=q.message.chat_id,
                text="✏️ *Nhập tên key tùy chỉnh của bạn:*\n\n"
                     "📝 Tối đa 12 ký tự, chỉ chữ và số (A-Z, 0-9)\n"
                     "💡 Ví dụ: MYKEY123, SHOP2024, ABC\n\n"
                     "⚠️ Gửi tin nhắn để nhập hoặc /cancel để hủy.",
                parse_mode="Markdown"
            )


async def seller_receive_custom_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Seller nhận tên key tùy chỉnh"""
    uid = update.effective_user.id
    if _is_admin(uid) or not is_seller(uid):
        return

    # Kiểm tra xem có đang chờ input không
    if not ctx.user_data.get("sel_waiting_custom"):
        return

    custom_name = update.message.text.strip().upper()

    # Validate tên key
    if not custom_name:
        await update.message.reply_text("❌ Tên key không được để trống. Vui lòng nhập lại:")
        return

    if len(custom_name) > 12:
        await update.message.reply_text("❌ Tên key tối đa 12 ký tự. Vui lòng nhập lại:")
        return

    if not custom_name.isalnum():
        await update.message.reply_text("❌ Tên key chỉ được chứa chữ cái và số. Vui lòng nhập lại:")
        return

    # Lưu tên custom
    ctx.user_data["sel_custom_name"] = custom_name
    ctx.user_data["sel_waiting_custom"] = False

    # Hiện bảng xác nhận
    kid = ctx.user_data["sel_kid"]
    name = ctx.user_data["sel_name_base"]
    price = ctx.user_data["sel_price"]
    hours = ctx.user_data["sel_hours"]
    label = ctx.user_data["sel_label"]

    duration_str = "Vĩnh Viễn" if hours == -1 else f"{name} ({hours}h)"

    confirm_text = (
        f"📋 *XÁC NHẬN THÔNG TIN ĐƠN HÀNG*\n\n"
        f"📦 Gói: {duration_str}\n"
        f"🏷️ Loại: {label}\n"
        f"✏️ Tên key: `{custom_name}`\n"
        f"💰 Số tiền: {_fmt_price(price)}\n\n"
        f"⚠️ Vui lòng kiểm tra kỹ trước khi xác nhận!"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận", callback_data="sel_confirm_custom")],
        [InlineKeyboardButton("❌ Hủy", callback_data="selcancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirm_text, parse_mode="Markdown", reply_markup=reply_markup)


async def seller_confirm_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Seller xác nhận custom key và tạo QR"""
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    if _is_admin(uid) or not is_seller(uid):
        return

    custom_name = ctx.user_data.get("sel_custom_name")
    if not custom_name:
        await q.edit_message_text("❌ Phiên làm việc đã hết hạn. /start lại.")
        return

    # Tạo QR thanh toán với custom name
    await _seller_create_payment_qr(update, ctx, custom_name)


async def _seller_create_payment_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE, custom_name=None):
    """Tạo QR thanh toán cho seller"""
    logger.info("_seller_create_payment_qr called: custom_name=%s", custom_name)
    
    if update.callback_query:
        q = update.callback_query
        chat_id = q.message.chat_id
        # Phản hồi ngay để tránh timeout
        try:
            await q.edit_message_text("🔄 Đang tạo mã QR, vui lòng chờ...")
            logger.info("Edited message to show loading")
        except Exception as e:
            logger.error("Error editing message: %s", e, exc_info=True)
    else:
        chat_id = update.message.chat_id

    kid = ctx.user_data.get("sel_kid")
    name = ctx.user_data.get("sel_name_base")
    hours = ctx.user_data.get("sel_hours")
    price = ctx.user_data.get("sel_price")
    label = ctx.user_data.get("sel_label")
    
    logger.info("Order info: kid=%s, name=%s, hours=%s, price=%s", kid, name, hours, price)

    if not all([kid, name is not None, hours is not None, price]):
        logger.error("Missing user_data: %s", ctx.user_data)
        await ctx.bot.send_message(chat_id=chat_id, text="❌ Lỗi: Thiếu thông tin. Vui lòng /start lại.")
        return

    order_info = "GLORYVN_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    ctx.user_data["sel_order_info"] = order_info

    # Tạo label hiển thị
    if custom_name:
        full_label = f"{name} - {label} - {custom_name}"
        ctx.user_data["sel_custom_name"] = custom_name
    else:
        full_label = f"{name} - {label}"
        ctx.user_data["sel_custom_name"] = None

    duration_str = "Vĩnh Viễn" if hours == -1 else f"{name} ({hours}h)"

    caption = (
        f"📋 *Thông tin đơn hàng*\n\n"
        f"🆔 Mã đơn: `{order_info}`\n"
        f"📦 Gói: {duration_str}\n"
        f"🏷️ Loại: {label}\n"
    )
    if custom_name:
        caption += f"✏️ Tên key: `{custom_name}`\n"
    caption += (
        f"💰 Số tiền: {_fmt_price(price)}\n\n"
        f"💳 Quét mã QR bên dưới để thanh toán,\n"
        f"hoặc chuyển khoản đến:\n"
        f"🏦 *Ngân hàng:* MOMO\n"
        f"📱 *Số TK:* `{VIETQR_ACCOUNT}`\n"
        f"💰 *Số tiền:* {_fmt_price(price)}\n"
        f"📝 *Nội dung:* `{order_info}`\n\n"
        f"⚠️ Sau khi thanh toán, bấm nút bên dưới!"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Tôi đã thanh toán", callback_data="selpaid")],
        [InlineKeyboardButton("❌ Hủy", callback_data="selcancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Tải QR trong background
    logger.info("Downloading QR image...")
    qr_data = download_qr_image(price, order_info)
    logger.info("QR download result: %s", "success" if qr_data else "failed")

    try:
        if qr_data:
            logger.info("Sending photo with QR")
            await ctx.bot.send_photo(
                chat_id=chat_id,
                photo=BytesIO(qr_data),
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            logger.info("Photo sent successfully")
        else:
            # Nếu không load được QR, gửi text với hướng dẫn
            logger.warning("QR not available, sending text instead")
            text = caption + "\n\n⚠️ *Không thể tải mã QR, vui lòng chuyển khoản thủ công theo thông tin trên.*"
            await ctx.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
            logger.info("Text message sent successfully")
    except Exception as e:
        logger.error("Error sending message: %s", e, exc_info=True)
        await ctx.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi khi gửi tin nhắn: {str(e)}")


async def seller_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    if _is_admin(uid) or not is_seller(uid):
        return

    ud = ctx.user_data
    order_info = ud.get("sel_order_info")
    kid = ud.get("sel_kid")
    if not order_info or not kid:
        await q.edit_message_text("❌ Phiên làm việc đã hết hạn. /start lại.")
        return

    name, hours, p_r, p_c = KEY_TYPES[kid]
    price = ud["sel_price"]
    label = ud.get("sel_label", "Key ngẫu nhiên")
    custom_name = ud.get("sel_custom_name")
    uname = update.effective_user.username or "N/A"

    # Tạo key_name đầy đủ
    if custom_name:
        key_name = f"{name} - {label} - {custom_name}"
    else:
        key_name = f"{name} - {label}"

    order_id = create_order(uid, uname, kid, key_name, hours, price, order_info, custom_name)

    await q.edit_message_caption(
        caption=(
            f"✅ Đã ghi nhận yêu cầu!\n\n"
            f"📋 Mã đơn: `{order_info}`\n"
            f"📦 Gói: {key_name}\n"
            f"💰 Số tiền: {_fmt_price(price)}\n\n"
            f"⏳ Đang chờ admin xác nhận...\n"
            f"Bạn sẽ nhận được key sau khi admin duyệt."
        ),
        parse_mode="Markdown",
        reply_markup=None
    )

    text = (
        f"🔔 *ĐƠN HÀNG MỚI TỪ SELLER!*\n\n"
        f"🆔 Mã đơn: `{order_info}`\n"
        f"👤 Seller: @{uname} (ID: `{uid}`)\n"
        f"📦 Gói: {key_name}\n"
    )
    if custom_name:
        text += f"✏️ Tên key: `{custom_name}`\n"
    text += (
        f"💰 Tiền: {_fmt_price(price)}\n\n"
        f"Kiểm tra và xác nhận:"
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Xác nhận", "callback_data": f"confirm_{order_id}"},
                {"text": "❌ Hủy", "callback_data": f"cancel_{order_id}"}
            ]
        ]
    }
    try:
        requests.post(
            f"https://api.telegram.org/bot{ctx.bot.token}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard},
            timeout=10
        )
    except Exception as e:
        logger.error("notify admin failed: %s", e)


async def seller_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    try:
        await q.edit_message_caption(caption="❌ Đã hủy đơn hàng.", reply_markup=None)
    except Exception:
        try:
            await q.edit_message_text("❌ Đã hủy đơn hàng.")
        except Exception:
            await q.message.reply_text("❌ Đã hủy đơn hàng.")


# ---------------------------------------------------------------------------
# Admin commands
# ---------------------------------------------------------------------------

async def add_seller_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(uid):
        return
    try:
        target = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Cú pháp: /addseller <chat_id>")
        return
    add_seller(target, update.effective_user.username or "")
    await update.message.reply_text(f"✅ Đã thêm seller `{target}`.", parse_mode="Markdown")


async def remove_seller_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(uid):
        return
    try:
        target = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Cú pháp: /removeseller <chat_id>")
        return
    remove_seller(target)
    await update.message.reply_text(f"✅ Đã xoá seller `{target}`.", parse_mode="Markdown")


async def list_sellers_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(uid):
        return
    rows = list_sellers()
    if not rows:
        await update.message.reply_text("📋 Chưa có seller nào.")
        return
    lines = ["📋 *Danh sách seller:*"]
    for cid, uname, added in rows:
        lines.append(f"👤 `{cid}` – @{uname or 'N/A'} – {added[:10]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# order confirm / cancel (admin)
# ---------------------------------------------------------------------------

def _insert_key_to_supabase(key, hours, created_by):
    if supabase_insert_key(key, hours, created_by):
        logger.info("Inserted key %s into Supabase (created_by=%s)", key, created_by)
    else:
        logger.warning("Failed to insert key %s into Supabase", key)


async def confirm_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    if not _is_admin(uid):
        await q.edit_message_text("❌ Bạn không phải admin.")
        return

    order_id = int(q.data.replace("confirm_", ""))
    order = get_order(order_id)
    if not order:
        await q.edit_message_text("❌ Không tìm thấy đơn hàng.")
        return
    if order["status"] != "pending":
        await q.edit_message_text(f"❌ Đã xử lý (trạng thái: {order['status']}).")
        return

    # Trích xuất custom_key_name từ order_info (nếu có)
    order_info_parts = order["order_info"].split("|")
    order_info_code = order_info_parts[0]
    custom_key_name = order_info_parts[1] if len(order_info_parts) > 1 else None

    # Tạo key với custom name nếu có
    license_key = generate_key(order_id, order["hours"], custom_key_name)
    update_order(order_id, "confirmed", license_key)
    _insert_key_to_supabase(license_key, order["hours"], 0)

    _notify_customer(order["customer_chat_id"], license_key, order["key_name"])

    confirm_text = (
        f"✅ *Đã xác nhận đơn hàng #{order_id}*\n\n"
        f"👤 KH: @{order['customer_username']}\n"
        f"📦 Gói: {order['key_name']}\n"
    )
    if custom_key_name:
        confirm_text += f"✏️ Tên key: `{custom_key_name}`\n"
    confirm_text += (
        f"🔑 Key: `{license_key}`\n"
        f"📨 Đã gửi key cho khách hàng."
    )

    await q.edit_message_text(text=confirm_text, parse_mode="Markdown")


async def cancel_order_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    if not _is_admin(uid):
        await q.edit_message_text("❌ Bạn không phải admin.")
        return

    order_id = int(q.data.replace("cancel_", ""))
    order = get_order(order_id)
    if not order:
        await q.edit_message_text("❌ Không tìm thấy đơn hàng.")
        return
    if order["status"] != "pending":
        await q.edit_message_text(f"❌ Đã xử lý (trạng thái: {order['status']}).")
        return

    update_order(order_id, "cancelled")
    _notify_customer_cancelled(order["customer_chat_id"])
    await q.edit_message_text(
        text=f"❌ *Đã hủy đơn hàng #{order_id}*\n👤 KH: @{order['customer_username']}",
        parse_mode="Markdown"
    )


# ---------------------------------------------------------------------------
# custom key creation (admin / seller via command)
# ---------------------------------------------------------------------------

async def create_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền tạo key.")
        return

    try:
        hours = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Cú pháp: /createkey <hours> [custom_id]\n"
            "VD: `/createkey 720` – key 30 ngày\n"
            "VD: `/createkey -1` – vĩnh viễn\n"
            "VD: `/createkey 24 ABC123` – key 24h với custom ID",
            parse_mode="Markdown"
        )
        return

    if hours <= 0 and hours != -1:
        await update.message.reply_text("hours phải > 0 hoặc -1 (vĩnh viễn).")
        return

    custom_id = ctx.args[1].upper() if len(ctx.args) > 1 else None
    if custom_id and (len(custom_id) > 12 or not custom_id.isalnum()):
        await update.message.reply_text("custom_id tối đa 12 ký tự, chỉ chữ và số.")
        return

    dummy_id = random.randint(10000, 99999)
    license_key = generate_key(dummy_id, hours, custom_id)

    created_by = uid if not _is_admin(uid) else 0
    _insert_key_to_supabase(license_key, hours, created_by)

    lines = [f"✅ *Key đã được tạo!*\n🔑 `{license_key}`"]
    lines.append(f"⏳ Thời hạn: {'Vĩnh viễn' if hours == -1 else f'{hours}h'}")
    lines.append(f"👤 Người tạo: {'Admin' if _is_admin(uid) else f'Seller `{uid}`'}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# query keys
# ---------------------------------------------------------------------------

async def my_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    created_by = 0 if _is_admin(uid) else uid
    page = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 0
    keys = supabase_query_keys(created_by=created_by, limit=PAGE_SIZE, offset=page * PAGE_SIZE)

    if not keys:
        await update.message.reply_text("📭 Không có key nào.")
        return

    lines = [f"📋 *Key của bạn (trang {page + 1}):*"]
    for k in keys:
        lines.append(_fmt_key(k))

    kb = _page_buttons(page, len(keys), f"mykeys_{created_by}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=kb)


async def key_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    try:
        key_val = ctx.args[0]
    except IndexError:
        await update.message.reply_text("Cú pháp: /keyinfo <key>")
        return

    k = supabase_get_key(key_val)
    if not k:
        await update.message.reply_text(f"❌ Không tìm thấy key `{key_val}`.", parse_mode="Markdown")
        return

    expires = k.get("expires_at", "") or "—"
    last_login = k.get("last_login", "") or "—"
    if expires != "—":
        expires = expires[:19]
    if last_login != "—":
        last_login = last_login[:19]

    await update.message.reply_text(
        f"📋 *Chi tiết key:*\n"
        f"🔑 Key: `{k['key']}`\n"
        f"⏳ Duration: {k.get('duration_hours', 0)}h\n"
        f"✅ Active: {'Có' if k.get('is_active') else 'Không'}\n"
        f"📅 Hết hạn: {expires}\n"
        f"💻 HWID: `{k.get('hwid', '—')}`\n"
        f"📱 Device: `{k.get('device_name', '—')}`\n"
        f"🕐 Lần cuối: {last_login}\n"
        f"👤 Tạo bởi: `{k.get('created_by', 0)}`\n"
        f"📅 Tạo lúc: {k.get('created_at', '—')[:19]}",
        parse_mode="Markdown"
    )


# ---------------------------------------------------------------------------
# delete / reset HWID / toggle
# ---------------------------------------------------------------------------

async def delete_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    try:
        key_val = ctx.args[0]
    except IndexError:
        await update.message.reply_text("Cú pháp: /deletekey <key>")
        return

    k = supabase_get_key(key_val)
    if not k:
        await update.message.reply_text(f"❌ Không tìm thấy key `{key_val}`.", parse_mode="Markdown")
        return

    creator = k.get("created_by", 0)
    if not _is_admin(uid) and creator != uid:
        await update.message.reply_text("❌ Bạn chỉ có thể xoá key do mình tạo.")
        return

    ok = supabase_delete_key(key_val, created_by=None if _is_admin(uid) else uid)
    if ok:
        await update.message.reply_text(f"✅ Đã xoá key `{key_val}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không thể xoá key.")


async def reset_hwid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    try:
        key_val = ctx.args[0]
    except IndexError:
        await update.message.reply_text("Cú pháp: /resethwid <key>")
        return

    k = supabase_get_key(key_val)
    if not k:
        await update.message.reply_text(f"❌ Không tìm thấy key `{key_val}`.", parse_mode="Markdown")
        return

    creator = k.get("created_by", 0)
    if not _is_admin(uid) and creator != uid:
        await update.message.reply_text("❌ Bạn chỉ có thể reset HWID key do mình tạo.")
        return

    ok = supabase_reset_hwid(key_val, created_by=None if _is_admin(uid) else uid)
    if ok:
        await update.message.reply_text(f"✅ Đã reset HWID cho key `{key_val}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không thể reset HWID.")


async def toggle_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    try:
        key_val = ctx.args[0]
    except IndexError:
        await update.message.reply_text("Cú pháp: /togglekey <key>")
        return

    k = supabase_get_key(key_val)
    if not k:
        await update.message.reply_text(f"❌ Không tìm thấy key `{key_val}`.", parse_mode="Markdown")
        return

    creator = k.get("created_by", 0)
    if not _is_admin(uid) and creator != uid:
        await update.message.reply_text("❌ Bạn chỉ có thể bật/tắt key do mình tạo.")
        return

    new_active = not k.get("is_active", True)
    ok = supabase_toggle_key(key_val, new_active, created_by=None if _is_admin(uid) else uid)
    if ok:
        status = "bật" if new_active else "tắt"
        await update.message.reply_text(f"✅ Đã {status} key `{key_val}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không thể thay đổi trạng thái key.")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _can_access(uid):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    if _is_admin(uid):
        total = supabase_count_keys()
        mine = supabase_count_keys(created_by=0)
        sellers_total = 0
        for s in list_sellers():
            sellers_total += supabase_count_keys(created_by=s[0])
        await update.message.reply_text(
            f"📊 *Thống kê key:*\n"
            f"📌 Tổng số: {total}\n"
            f"🛡️ Admin tạo: {mine}\n"
            f"👤 Seller tạo: {sellers_total}",
            parse_mode="Markdown"
        )
    else:
        mine = supabase_count_keys(created_by=uid)
        await update.message.reply_text(
            f"📊 *Thống kê key của bạn:*\n📌 Tổng số: {mine}",
            parse_mode="Markdown"
        )


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------

async def page_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    data = q.data
    parts = data.split("_")

    if parts[0] == "mykeys":
        created_by = int(parts[1])
        if not _is_admin(uid) and uid != created_by:
            return
        page = int(parts[-1])
        keys = supabase_query_keys(created_by=created_by, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
        lines = [f"📋 *Key của bạn (trang {page + 1}):*"] + [_fmt_key(k) for k in keys]
        kb = _page_buttons(page, len(keys), f"mykeys_{created_by}")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=kb)


# ---------------------------------------------------------------------------
# cross-bot notify
# ---------------------------------------------------------------------------

def _notify_customer(chat_id, license_key, key_name):
    text = (
        "🎉 *ĐƠN HÀNG ĐÃ ĐƯỢC XÁC NHẬN!*\n\n"
        f"📦 Gói: {key_name}\n"
        f"🔑 *Key của bạn:*\n`{license_key}`\n\n"
        "📝 Copy key trên và nhập vào phần mềm AotForms.\n"
        "💡 Liên hệ admin nếu cần hỗ trợ."
    )
    url = f"https://api.telegram.org/bot{CUSTOMER_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        logger.error("notify_customer failed: %s", e)


def _notify_customer_cancelled(chat_id):
    text = "❌ Đơn hàng của bạn đã bị hủy. Vui lòng liên hệ admin để biết thêm chi tiết."
    url = f"https://api.telegram.org/bot{CUSTOMER_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error("notify_customer_cancelled failed: %s", e)


async def cancel_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Hủy bất kỳ thao tác nào đang chờ"""
    ctx.user_data.clear()
    await update.message.reply_text("❌ Đã hủy. Gửi /start để bắt đầu lại.")


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Seller management (admin)
    app.add_handler(CommandHandler("addseller", add_seller_cmd))
    app.add_handler(CommandHandler("removeseller", remove_seller_cmd))
    app.add_handler(CommandHandler("sellers", list_sellers_cmd))

    # Key management (admin / seller)
    app.add_handler(CommandHandler("createkey", create_key))
    app.add_handler(CommandHandler("mykeys", my_keys))
    app.add_handler(CommandHandler("keyinfo", key_info))
    app.add_handler(CommandHandler("deletekey", delete_key))
    app.add_handler(CommandHandler("resethwid", reset_hwid))
    app.add_handler(CommandHandler("togglekey", toggle_key))
    app.add_handler(CommandHandler("stats", stats))

    # Seller buy-flow
    app.add_handler(CallbackQueryHandler(buy_key, pattern=r"^buy_"))
    app.add_handler(CallbackQueryHandler(seller_confirm_custom, pattern=r"^sel_confirm_custom$"))
    app.add_handler(CallbackQueryHandler(seller_paid, pattern=r"^selpaid$"))
    app.add_handler(CallbackQueryHandler(seller_cancel, pattern=r"^selcancel$"))

    # Order confirm/cancel (admin callback)
    app.add_handler(CallbackQueryHandler(confirm_order, pattern=r"^confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_order_cmd, pattern=r"^cancel_\d+$"))

    # Pagination
    app.add_handler(CallbackQueryHandler(page_callback, pattern=r"^mykeys_\d+_page_\d+$"))

    # MessageHandler để nhận tên key custom từ seller - đặt cuối cùng
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, seller_receive_custom_name))
