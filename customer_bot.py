import logging
import random
import string
import requests
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import KEY_TYPES, VIETQR_ACCOUNT, CUSTOMER_BOT_TOKEN, ADMIN_BOT_TOKEN, ADMIN_CHAT_ID
from database import is_seller, create_order
from payment import download_qr_image

logger = logging.getLogger(__name__)


def _fmt_price(vnd):
    s = f"{vnd:,}".replace(",", ".")
    return f"{s}đ"


def _build_menu():
    """Menu chính với UI đẹp và có description"""
    kb = [
        [InlineKeyboardButton("⚡ 1 Ngày - Dùng thử", callback_data="package_1_day")],
        [InlineKeyboardButton("🔥 1 Tuần - Phổ biến nhất", callback_data="package_1_week")],
        [InlineKeyboardButton("💎 1 Tháng - Tiết kiệm", callback_data="package_1_month")],
        [InlineKeyboardButton("👑 Vĩnh Viễn - Premium", callback_data="package_forever")]
    ]
    return InlineKeyboardMarkup(kb)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.first_name or update.effective_user.username or "bạn"
    
    if not is_seller(uid):
        await update.message.reply_text(
            "❌ *QUYỀN TRUY CẬP BỊ TỪ CHỐI*\n\n"
            "Bạn chưa được cấp quyền sử dụng bot.\n"
            "📞 Vui lòng liên hệ admin để được cấp quyền.\n\n"
            "👉 Liên hệ: @admin",
            parse_mode="Markdown"
        )
        return
    
    ctx.user_data.clear()
    
    welcome_text = (
        "╔════════════════════════════╗\n"
        "║  🎯 *GLORYVN 247 STORE*   ║\n"
        "╚════════════════════════════╝\n\n"
        f"Xin chào *{uname}*! 👋\n\n"
        "📦 *Chọn gói key bạn muốn mua:*\n\n"
        "💡 *Tip:* Gói 1 Tháng tiết kiệm 20%!"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=_build_menu()
    )


async def select_package(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bước 1: Chọn gói → Hiện 2 loại key với UI đẹp"""
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    if not is_seller(uid):
        return

    kid = q.data.replace("package_", "")
    logger.info("select_package: uid=%s, kid=%s", uid, kid)
    
    if kid not in KEY_TYPES:
        await q.edit_message_text(f"❌ Gói không hợp lệ: {kid}")
        return
    
    name, hours, p_r, p_c = KEY_TYPES[kid]
    
    # Lưu thông tin
    ctx.user_data["selected_package"] = kid
    ctx.user_data["package_name"] = name
    ctx.user_data["package_hours"] = hours
    
    # Icon cho từng gói
    package_icons = {
        "1_day": "⚡",
        "1_week": "🔥",
        "1_month": "💎",
        "forever": "👑"
    }
    icon = package_icons.get(kid, "📦")
    
    duration_display = f"{name}" if hours != -1 else "Vĩnh Viễn"
    
    text = (
        f"╔════════════════════════════╗\n"
        f"║  {icon} *GÓI: {duration_display.upper()}*\n"
        f"╚════════════════════════════╝\n\n"
        f"🎯 *Chọn loại key:*"
    )
    
    # Button với mô tả chi tiết hơn
    keyboard = [
        [InlineKeyboardButton(
            f"🎲 Key ngẫu nhiên - {_fmt_price(p_r)}", 
            callback_data=f"type_{kid}_r"
        )],
        [InlineKeyboardButton(
            f"✏️ Key tùy chỉnh - {_fmt_price(p_c)} (+{_fmt_price(p_c - p_r)})", 
            callback_data=f"type_{kid}_c"
        )],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="back_to_menu")]
    ]
    
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def select_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bước 2: Chọn loại → Hỏi số lượng với UI hướng dẫn chi tiết"""
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    if not is_seller(uid):
        return
    
    data = q.data.replace("type_", "")
    mode = data[-1]
    kid = data[:-2]
    
    logger.info("select_type: uid=%s, kid=%s, mode=%s", uid, kid, mode)
    
    if kid not in KEY_TYPES:
        await q.edit_message_text(f"❌ Gói không hợp lệ")
        return
    
    name, hours, p_r, p_c = KEY_TYPES[kid]
    price = p_r if mode == "r" else p_c
    label = "🎲 Ngẫu nhiên" if mode == "r" else "✏️ Tùy chỉnh"
    
    # Lưu thông tin
    ctx.user_data["key_type"] = mode
    ctx.user_data["key_label"] = label
    ctx.user_data["key_price"] = price
    ctx.user_data["waiting_for_quantity"] = True
    
    # Icon package
    package_icons = {"1_day": "⚡", "1_week": "🔥", "1_month": "💎", "forever": "👑"}
    icon = package_icons.get(kid, "📦")
    
    text = (
        f"╔════════════════════════════╗\n"
        f"║  {icon} *{name.upper()}* • {label}\n"
        f"╚════════════════════════════╝\n\n"
        f"🔢 *Bạn cần bao nhiêu key?*\n\n"
        f"┌───────────────────────┐\n"
        f"│  💰 Đơn giá:  {_fmt_price(price)}/key\n"
        f"│  📊 Giới hạn: 1 - 100 key\n"
        f"└───────────────────────┘\n\n"
        f"💬 Vui lòng nhập *SỐ LƯỢNG KEY*\n"
        f"   _(Ví dụ: 1, 5, 10, 50)_\n\n"
        f"⚡ *Tip:* Mua nhiều = Giao dịch ít = Nhanh hơn!"
    )
    
    msg = await q.edit_message_text(text, parse_mode="Markdown")
    ctx.user_data["quantity_message_id"] = msg.message_id
    ctx.user_data["last_action_time"] = __import__('time').time()


async def receive_quantity(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bước 3: Nhận số lượng → Hiện bảng xác nhận"""
    uid = update.effective_user.id
    if not is_seller(uid):
        return
    
    if not ctx.user_data.get("waiting_for_quantity"):
        return
    
    try:
        quantity = int(update.message.text.strip())
        if quantity <= 0:
            await update.message.reply_text("❌ Số lượng phải lớn hơn 0. Vui lòng nhập lại:")
            return
        if quantity > 100:
            await update.message.reply_text("❌ Số lượng tối đa 100 key. Vui lòng nhập lại:")
            return
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ (VD: 5):")
        return
    
    # Xóa tin nhắn user
    try:
        await update.message.delete()
    except Exception:
        pass
    
    ctx.user_data["quantity"] = quantity
    ctx.user_data["waiting_for_quantity"] = False
    
    # Lấy thông tin
    kid = ctx.user_data.get("selected_package")
    name = ctx.user_data.get("package_name")
    hours = ctx.user_data.get("package_hours")
    mode = ctx.user_data.get("key_type")
    label = ctx.user_data.get("key_label")
    price = ctx.user_data.get("key_price")
    
    total = price * quantity
    duration_str = "Vĩnh Viễn" if hours == -1 else f"{name}"
    
    # Nếu là CUSTOM và số lượng > 1 → Hỏi danh sách tên
    if mode == "c" and quantity > 1:
        ctx.user_data["waiting_for_custom_names"] = True
        text = (
            f"📦 *Gói: {duration_str}*\n"
            f"🏷️ *Loại: {label}*\n"
            f"📦 *Số lượng: {quantity} key*\n\n"
            f"✏️ Vui lòng nhập *{quantity} tên key*, mỗi tên một dòng:\n"
            f"_(Tối đa 12 ký tự/tên, chỉ chữ và số)_\n\n"
            f"*Ví dụ:*\n"
            f"`KEY001`\n"
            f"`KEY002`\n"
            f"`KEY003`"
        )
        msg_id = ctx.user_data.get("quantity_message_id")
        try:
            await ctx.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception:
            msg = await update.effective_chat.send_message(text, parse_mode="Markdown")
            ctx.user_data["quantity_message_id"] = msg.message_id
        return
    
    # Nếu CUSTOM và số lượng = 1 → Hỏi 1 tên
    if mode == "c" and quantity == 1:
        ctx.user_data["waiting_for_custom_name"] = True
        text = (
            f"📦 *Gói: {duration_str}*\n"
            f"🏷️ *Loại: {label}*\n\n"
            f"✏️ Vui lòng nhập *tên key*:\n"
            f"_(Tối đa 12 ký tự, chỉ chữ và số)_"
        )
        msg_id = ctx.user_data.get("quantity_message_id")
        try:
            await ctx.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception:
            msg = await update.effective_chat.send_message(text, parse_mode="Markdown")
            ctx.user_data["quantity_message_id"] = msg.message_id
        return
    
    # RANDOM key → Hiện bảng xác nhận ngay
    await show_confirmation(update, ctx, None)


async def show_confirmation(update: Update, ctx: ContextTypes.DEFAULT_TYPE, custom_names=None):
    """Hiện bảng xác nhận cuối cùng trước khi tạo QR"""
    kid = ctx.user_data.get("selected_package")
    name = ctx.user_data.get("package_name")
    hours = ctx.user_data.get("package_hours")
    label = ctx.user_data.get("key_label")
    price = ctx.user_data.get("key_price")
    quantity = ctx.user_data.get("quantity")
    
    total = price * quantity
    duration_str = "Vĩnh Viễn" if hours == -1 else name
    
    text = (
        f"📋 *XÁC NHẬN THÔNG TIN ĐƠN HÀNG*\n\n"
        f"📦 Gói: {duration_str}\n"
        f"🏷️ Loại: {label}\n"
        f"📦 Số lượng: *{quantity} key*\n"
        f"💰 Đơn giá: {_fmt_price(price)}\n"
        f"💵 *Tổng tiền: {_fmt_price(total)}*\n"
    )
    
    if custom_names:
        ctx.user_data["custom_names"] = custom_names
        text += f"\n✏️ *Tên key:*\n"
        for cn in custom_names[:5]:  # Hiện tối đa 5 tên
            text += f"  • `{cn}`\n"
        if len(custom_names) > 5:
            text += f"  _... và {len(custom_names) - 5} tên khác_\n"
    
    text += f"\n⚠️ *Vui lòng kiểm tra kỹ trước khi xác nhận!*"
    
    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận & Tạo QR", callback_data="confirm_order")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_order")]
    ]
    
    msg_id = ctx.user_data.get("quantity_message_id")
    if msg_id:
        try:
            await ctx.bot.edit_message_text(
                chat_id=update.effective_chat.id if hasattr(update, 'effective_chat') else update.callback_query.message.chat_id,
                message_id=msg_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        except Exception as e:
            logger.error("Cannot edit message: %s", e)
    
    # Fallback
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        msg = await update.effective_chat.send_message(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        ctx.user_data["quantity_message_id"] = msg.message_id
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    logger.info("buy_key called: uid=%s, data=%s", uid, q.data)
    
    if not is_seller(uid):
        logger.warning("User %s is not a seller", uid)
        await q.edit_message_text("❌ Bạn chưa được cấp quyền sử dụng bot.")
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
    ctx.user_data["key_id"] = kid
    ctx.user_data["key_name_base"] = name
    ctx.user_data["hours"] = hours
    ctx.user_data["price"] = price
    ctx.user_data["mode"] = mode
    ctx.user_data["label"] = label

    # Nếu là key NGẪU NHIÊN → tạo QR ngay
    if mode == "r":
        logger.info("Random key selected, creating QR immediately")
        try:
            await _create_payment_qr(update, ctx, None)
        except Exception as e:
            logger.error("Error creating QR: %s", e, exc_info=True)
            await q.edit_message_text(f"❌ Lỗi: {str(e)}")
    # Nếu là key TÙY CHỈNH → hỏi tên key trước
    else:
        logger.info("Custom key selected, asking for name")
        ctx.user_data["waiting_for_custom_name"] = True
        try:
            msg = await q.edit_message_text(
                "✏️ *Nhập tên key tùy chỉnh của bạn:*\n\n"
                "📝 Tối đa 12 ký tự, chỉ chữ và số (A-Z, 0-9)\n"
                "💡 Ví dụ: MYKEY123, SHOP2024, ABC\n\n"
                "⚠️ Gửi tin nhắn để nhập hoặc /cancel để hủy.",
                parse_mode="Markdown"
            )
            # Lưu message_id để edit sau
            ctx.user_data["input_message_id"] = msg.message_id
        except Exception as e:
            logger.error("Error editing message: %s", e, exc_info=True)
            msg = await ctx.bot.send_message(
                chat_id=q.message.chat_id,
                text="✏️ *Nhập tên key tùy chỉnh của bạn:*\n\n"
                     "📝 Tối đa 12 ký tự, chỉ chữ và số (A-Z, 0-9)\n"
                     "💡 Ví dụ: MYKEY123, SHOP2024, ABC\n\n"
                     "⚠️ Gửi tin nhắn để nhập hoặc /cancel để hủy.",
                parse_mode="Markdown"
            )
            ctx.user_data["input_message_id"] = msg.message_id


async def receive_custom_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Nhận tên key tùy chỉnh (1 key hoặc nhiều key)"""
    uid = update.effective_user.id
    if not is_seller(uid):
        return

    # Nhận 1 tên (quantity = 1)
    if ctx.user_data.get("waiting_for_custom_name"):
        custom_name = update.message.text.strip().upper()
        
        if not custom_name:
            await update.message.reply_text("❌ Tên key không được để trống. Vui lòng nhập lại:")
            return
        if len(custom_name) > 12:
            await update.message.reply_text("❌ Tên key tối đa 12 ký tự. Vui lòng nhập lại:")
            return
        if not custom_name.isalnum():
            await update.message.reply_text("❌ Tên key chỉ được chứa chữ cái và số. Vui lòng nhập lại:")
            return
        
        try:
            await update.message.delete()
        except Exception:
            pass
        
        ctx.user_data["waiting_for_custom_name"] = False
        await show_confirmation(update, ctx, [custom_name])
        return
    
    # Nhận nhiều tên (quantity > 1)
    if ctx.user_data.get("waiting_for_custom_names"):
        text = update.message.text.strip()
        names = [n.strip().upper() for n in text.split("\n") if n.strip()]
        
        quantity = ctx.user_data.get("quantity", 1)
        
        # Validate số lượng
        if len(names) != quantity:
            await update.message.reply_text(
                f"❌ Bạn cần nhập đúng {quantity} tên key (hiện tại: {len(names)}).\n"
                f"Vui lòng nhập lại, mỗi tên một dòng:"
            )
            return
        
        # Validate từng tên
        errors = []
        for i, name in enumerate(names, 1):
            if not name:
                errors.append(f"Dòng {i}: Trống")
            elif len(name) > 12:
                errors.append(f"Dòng {i}: Quá 12 ký tự ({name})")
            elif not name.isalnum():
                errors.append(f"Dòng {i}: Chỉ được chữ và số ({name})")
        
        if errors:
            await update.message.reply_text(
                f"❌ Có lỗi trong danh sách tên:\n" + "\n".join(errors) + "\n\nVui lòng nhập lại:"
            )
            return
        
        # Kiểm tra trùng
        if len(names) != len(set(names)):
            await update.message.reply_text("❌ Các tên key không được trùng nhau. Vui lòng nhập lại:")
            return
        
        try:
            await update.message.delete()
        except Exception:
            pass
        
        ctx.user_data["waiting_for_custom_names"] = False
        await show_confirmation(update, ctx, names)
        return


async def receive_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Router: Xử lý input text (số lượng hoặc tên key)"""
    uid = update.effective_user.id
    
    # CRITICAL: Check quyền trước khi xử lý
    if not is_seller(uid):
        logger.warning("Unauthorized user %s tried to input", uid)
        return
    
    # Check session timeout (5 phút)
    last_action = ctx.user_data.get("last_action_time", 0)
    import time
    if last_action and (time.time() - last_action > 300):
        ctx.user_data.clear()
        await update.message.reply_text(
            "⏱️ Phiên làm việc đã hết hạn (5 phút).\n"
            "Vui lòng gửi /start để bắt đầu lại."
        )
        return
    
    # Update last action time
    ctx.user_data["last_action_time"] = time.time()
    
    if ctx.user_data.get("waiting_for_quantity"):
        await receive_quantity(update, ctx)
    elif ctx.user_data.get("waiting_for_custom_name") or ctx.user_data.get("waiting_for_custom_names"):
        await receive_custom_name(update, ctx)


async def confirm_order_and_create_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Xác nhận đơn hàng → Tạo QR thanh toán"""
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    if not is_seller(uid):
        return
    
    # Lấy thông tin
    kid = ctx.user_data.get("selected_package")
    name = ctx.user_data.get("package_name")
    hours = ctx.user_data.get("package_hours")
    mode = ctx.user_data.get("key_type")
    label = ctx.user_data.get("key_label")
    price = ctx.user_data.get("key_price")
    quantity = ctx.user_data.get("quantity", 1)
    custom_names = ctx.user_data.get("custom_names")
    
    if not all([kid, name is not None, hours is not None, mode, price, quantity]):
        await q.edit_message_text("❌ Thiếu thông tin. Vui lòng /start lại.")
        return
    
    total = price * quantity
    
    await q.edit_message_text("🔄 Đang tạo mã QR thanh toán, vui lòng chờ...")
    
    # Tạo order info với 12 ký tự (tăng độ bảo mật)
    order_info = "GLORYVN_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
    
    # Lưu vào user_data để dùng sau
    ctx.user_data["order_info"] = order_info
    ctx.user_data["total_price"] = total
    
    duration_str = "Vĩnh Viễn" if hours == -1 else f"{name}"
    
    caption = (
        f"📋 *THÔNG TIN ĐƠN HÀNG*\n\n"
        f"🆔 Mã đơn: `{order_info}`\n"
        f"📦 Gói: {duration_str}\n"
        f"🏷️ Loại: {label}\n"
        f"📦 Số lượng: *{quantity} key*\n"
        f"💰 Đơn giá: {_fmt_price(price)}\n"
        f"💵 *Tổng tiền: {_fmt_price(total)}*\n\n"
    )
    
    if custom_names:
        caption += f"✏️ *Tên key:*\n"
        for cn in custom_names[:3]:
            caption += f"  • `{cn}`\n"
        if len(custom_names) > 3:
            caption += f"  _... và {len(custom_names) - 3} tên khác_\n"
        caption += "\n"
    
    caption += (
        f"💳 *HƯỚNG DẪN THANH TOÁN:*\n"
        f"🏦 Ngân hàng: *MOMO*\n"
        f"📱 Số TK: `{VIETQR_ACCOUNT}`\n"
        f"💰 Số tiền: *{_fmt_price(total)}*\n"
        f"📝 Nội dung: `{order_info}`\n\n"
        f"⚠️ Sau khi thanh toán, bấm nút bên dưới!"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Tôi đã thanh toán", callback_data="paid")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Download QR
    logger.info("Downloading QR for order %s, amount %s", order_info, total)
    qr_data = download_qr_image(total, order_info)
    
    chat_id = q.message.chat_id
    
    try:
        if qr_data:
            await ctx.bot.send_photo(
                chat_id=chat_id,
                photo=BytesIO(qr_data),
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=caption + "\n\n⚠️ *Không thể tải QR, vui lòng chuyển khoản thủ công.*",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error("Error sending QR: %s", e, exc_info=True)
        await ctx.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {str(e)}")


async def back_to_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quay lại menu chính"""
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    await q.edit_message_text(
        "👋 *Chào mừng bạn đến với GloryVN 247 Store!*\n\n"
        "📦 Vui lòng chọn gói key bạn muốn mua:",
        parse_mode="Markdown",
        reply_markup=_build_menu()
    )


async def _create_payment_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE, custom_name=None):
    """Tạo QR thanh toán (dùng chung cho cả random và custom key)"""
    logger.info("_create_payment_qr called: custom_name=%s", custom_name)
    
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

    kid = ctx.user_data.get("key_id")
    name = ctx.user_data.get("key_name_base")
    hours = ctx.user_data.get("hours")
    price = ctx.user_data.get("price")
    label = ctx.user_data.get("label")
    
    logger.info("Order info: kid=%s, name=%s, hours=%s, price=%s", kid, name, hours, price)

    if not all([kid, name is not None, hours is not None, price]):
        logger.error("Missing user_data: %s", ctx.user_data)
        await ctx.bot.send_message(chat_id=chat_id, text="❌ Lỗi: Thiếu thông tin. Vui lòng /start lại.")
        return

    order_info = "GLORYVN_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    ctx.user_data["order_info"] = order_info

    # Tạo key_name hiển thị
    if custom_name:
        key_name = f"{name} - {label} - {custom_name}"
        ctx.user_data["custom_key_name"] = custom_name
    else:
        key_name = f"{name} - {label}"
        ctx.user_data["custom_key_name"] = None

    ctx.user_data["key_name"] = key_name

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
        [InlineKeyboardButton("✅ Tôi đã thanh toán", callback_data="paid")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_order")]
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
            # Nếu không load được QR, gửi text với hướng dẫn chuyển khoản
            logger.warning("QR not available, sending text instead")
            text = caption + "\n\n⚠️ *Không thể tải mã QR, vui lòng chuyển khoản thủ công theo thông tin trên.*"
            await ctx.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
            logger.info("Text message sent successfully")
    except Exception as e:
        logger.error("Error sending message: %s", e, exc_info=True)
        await ctx.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi khi gửi tin nhắn: {str(e)}")


async def paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    ud = ctx.user_data
    order_info = ud.get("order_info")
    if not order_info:
        await q.edit_message_text("❌ Phiên làm việc đã hết hạn. Vui lòng /start lại.")
        return

    uid = update.effective_user.id
    
    # RATE LIMIT: Check cooldown (10 giây giữa 2 lần bấm)
    import time
    last_paid_time = ud.get("last_paid_time", 0)
    if time.time() - last_paid_time < 10:
        await q.answer("⏱️ Vui lòng chờ 10 giây trước khi bấm lại.", show_alert=True)
        return
    
    ud["last_paid_time"] = time.time()

    kid = ud.get("selected_package")
    name = ud.get("package_name")
    hours = ud.get("package_hours")
    label = ud.get("key_label")
    price = ud.get("key_price")
    quantity = ud.get("quantity", 1)
    total = ud.get("total_price")
    custom_names = ud.get("custom_names")
    
    uname = update.effective_user.username or "N/A"

    # Tạo key_name để lưu
    key_name = f"{name} - {label} - x{quantity}"
    
    # Lưu order vào database (lưu với giá tổng)
    order_id = create_order(uid, uname, kid, key_name, hours, total, order_info, custom_names)

    await q.edit_message_caption(
        caption=(
            f"✅ *Đã ghi nhận yêu cầu!*\n\n"
            f"📋 Mã đơn: `{order_info}`\n"
            f"📦 Gói: {name}\n"
            f"🏷️ Loại: {label}\n"
            f"📦 Số lượng: *{quantity} key*\n"
            f"💵 Tổng tiền: {_fmt_price(total)}\n\n"
            f"⏳ *Đang chờ admin xác nhận...*\n"
            f"Bạn sẽ nhận được key sau khi admin duyệt."
        ),
        parse_mode="Markdown",
        reply_markup=None
    )

    _notify_admin(order_id, uid, uname, key_name, _fmt_price(total), order_info, quantity, custom_names)


def _notify_admin(order_id, customer_chat_id, customer_username, key_name, price, order_info, quantity, custom_names=None):
    text = (
        f"🔔 *ĐƠN HÀNG MỚI!*\n\n"
        f"🆔 Mã đơn: `{order_info}`\n"
        f"👤 KH: @{customer_username} (ID: `{customer_chat_id}`)\n"
        f"📦 Gói: {key_name}\n"
        f"📦 Số lượng: *{quantity} key*\n"
    )
    if custom_names:
        text += f"✏️ *Tên key:*\n"
        for cn in custom_names[:5]:
            text += f"  • `{cn}`\n"
        if len(custom_names) > 5:
            text += f"  _... và {len(custom_names) - 5} tên khác_\n"
    text += (
        f"💰 Tiền: {price}\n\n"
        f"Kiểm tra và xác nhận thanh toán:"
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Xác nhận", "callback_data": f"confirm_{order_id}"},
                {"text": "❌ Hủy", "callback_data": f"cancel_{order_id}"}
            ]
        ]
    }
    url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }, timeout=10)
    except Exception as e:
        logger.error("notify_admin failed: %s", e)


async def cancel_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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


async def cancel_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Hủy bất kỳ thao tác nào đang chờ"""
    ctx.user_data.clear()
    await update.message.reply_text("❌ Đã hủy. Gửi /start để bắt đầu lại.")


def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # Luồng mới
    app.add_handler(CallbackQueryHandler(select_package, pattern=r"^package_"))
    app.add_handler(CallbackQueryHandler(select_type, pattern=r"^type_"))
    app.add_handler(CallbackQueryHandler(confirm_order_and_create_qr, pattern=r"^confirm_order$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern=r"^back_to_menu$"))
    
    # Common
    app.add_handler(CallbackQueryHandler(paid, pattern=r"^paid$"))
    app.add_handler(CallbackQueryHandler(cancel_order, pattern=r"^cancel_order$"))
    
    # MessageHandler để nhận số lượng và tên key - đặt cuối cùng
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_input))
