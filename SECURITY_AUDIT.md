# 🔒 BÁO CÁO KIỂM TRA BẢO MẬT VÀ LUỒNG HOẠT ĐỘNG

## ❌ CÁC VẤN ĐỀ NGHIÊM TRỌNG PHÁT HIỆN

### 1. **DUPLICATE FUNCTION - CODE BỊ TRÙNG LẶP**

```python
# File customer_bot.py có 2 hàm start() TRÙNG NHAU (dòng 33 và 44)
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # ... code 1 ...

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):  # ← TRÙNG!
    # ... code 2 ...
```

**Hậu quả:**
- Python sẽ chỉ dùng hàm thứ 2
- Hàm thứ 1 bị ignore hoàn toàn
- Code lộn xộn, khó maintain

**Giải pháp:**
- ✅ Xóa 1 trong 2 hàm trùng lặp
- ✅ Chỉ giữ lại hàm ở dòng 44

---

### 2. **HÀM LEGACY CHƯA XÓA**

```python
async def _create_payment_qr(...)  # ← Hàm CŨ, không còn dùng
```

**Vấn đề:**
- Hàm này từ luồng cũ (1 key duy nhất)
- Luồng mới dùng `confirm_order_and_create_qr()`
- Hàm cũ vẫn còn trong code → gây nhầm lẫn

**Giải pháp:**
- ✅ Xóa hàm `_create_payment_qr()` và `buy_key()` (đã không dùng)

---

### 3. **THIẾU KIỂM TRA QUYỀN TRONG `receive_input()`**

```python
async def receive_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Router: Xử lý input text (số lượng hoặc tên key)"""
    if ctx.user_data.get("waiting_for_quantity"):
        await receive_quantity(update, ctx)
    elif ctx.user_data.get("waiting_for_custom_name") or ...):
        await receive_custom_name(update, ctx)
```

**Vấn đề:**
- Không check `is_seller()` ở function chính
- Nếu attacker spam message text → function vẫn chạy
- Phụ thuộc vào check bên trong `receive_quantity()`

**Giải pháp:**
- ✅ Thêm check `is_seller()` ngay đầu `receive_input()`

---

### 4. **RACE CONDITION - USER_DATA CONFLICT**

```python
# User A và User B cùng dùng bot:
ctx.user_data["quantity"] = 5      # User A
ctx.user_data["quantity"] = 10     # User B → GHI ĐÈ!
```

**Vấn đề:**
- `user_data` là PER-USER nên OK
- Nhưng nếu 1 user dùng 2 device khác nhau:
  - Device 1: Chọn gói 1 Tuần
  - Device 2: Chọn gói 1 Tháng
  - → Data bị conflict!

**Giải pháp:**
- ✅ Thêm warning nếu phát hiện session cũ đang active
- ✅ Auto clear old session khi /start mới

---

### 5. **INPUT VALIDATION CHƯA ĐẦY ĐỦ**

#### 5.1. **Số lượng key**
```python
if quantity > 100:  # ✅ Có check max
    return
```
**OK - Đã có validation**

#### 5.2. **Tên key custom**
```python
if len(custom_name) > 12:  # ✅ Check length
if not custom_name.isalnum():  # ✅ Check alphanumeric
```
**OK - Đã có validation**

#### 5.3. **THIẾU: Check XSS/Injection trong markdown**
```python
# Nếu user nhập: `<script>alert('xss')</script>` 
# Telegram markdown có thể bị lợi dụng
```

**Vấn đề:**
- Telegram hỗ trợ Markdown → có thể inject
- User nhập tên key chứa ký tự đặc biệt của Markdown: `*`, `_`, `` ` ``, `[`, `]`

**Giải pháp:**
- ✅ Escape markdown characters trước khi display
- ✅ Hoặc dùng `parse_mode=None` khi hiện user input

---

### 6. **ADMIN NOTIFICATION - KHÔNG CÓ RATE LIMIT**

```python
def _notify_admin(...):
    requests.post(url, json={...}, timeout=10)
```

**Vấn đề:**
- Nếu attacker spam "Tôi đã thanh toán" → Admin bị spam notification
- Không có cooldown giữa các lần bấm

**Giải pháp:**
- ✅ Thêm rate limit: 1 user chỉ được tạo tối đa 5 đơn/phút
- ✅ Thêm cooldown: Phải chờ 10s giữa 2 lần bấm "Đã thanh toán"

---

### 7. **ORDER INFO - MÃ ĐƠN DỄ ĐOÁN**

```python
order_info = "GLORYVN_" + "".join(random.choices(
    string.ascii_uppercase + string.digits, k=8
))
# → GLORYVN_ABC12345 (8 ký tự random)
```

**Phân tích:**
- Tổ hợp: (26+10)^8 = 2.8 trillion
- Với brute force 1000 req/s → 32 năm mới thử hết
- **Tương đối an toàn** nhưng có thể tốt hơn

**Cải thiện:**
- ✅ Tăng lên 12 ký tự: `k=12`
- ✅ Hoặc dùng UUID: `uuid.uuid4().hex[:12].upper()`

---

### 8. **DATABASE - LƯU JSON TRONG TEXT FIELD**

```python
# database.py
full_order_info = f"{order_info}|{json.dumps(custom_names)}"
# → "GLORYVN_ABC|[\"KEY1\",\"KEY2\"]"
```

**Vấn đề:**
- Dùng `|` để phân tách → Nếu user nhập tên có `|` sao?
- Parse dễ lỗi nếu format thay đổi
- Khó query trong database

**Giải pháp:**
- ✅ Thêm table riêng `order_keys`:
  ```sql
  CREATE TABLE order_keys (
      id INTEGER PRIMARY KEY,
      order_id INTEGER,
      key_name TEXT,
      FOREIGN KEY (order_id) REFERENCES orders(id)
  )
  ```

---

### 9. **TIMEOUT - QR DOWNLOAD BLOCKING**

```python
qr_data = download_qr_image(total, order_info)  # Timeout 5s
```

**Vấn đề:**
- Nếu VietQR API chậm → Bot chờ 5s
- Trong lúc đó user không thể tương tác

**Hiện trạng:**
- ✅ Đã có timeout = 5s (OK)
- ✅ Đã có fallback nếu QR fail

**Cải thiện thêm:**
- ✅ Dùng async HTTP client (aiohttp) thay vì requests
- ✅ Show progress: "Đang tải QR... (1/5s)"

---

### 10. **SESSION TIMEOUT - USER_DATA KHÔNG HẾT HẠN**

```python
ctx.user_data["waiting_for_quantity"] = True
# → Nếu user không nhập gì, state này tồn tại MÃI MÃI
```

**Vấn đề:**
- User data không tự động clear
- Nếu user bỏ dở → lần sau vào có thể nhầm lẫn state

**Giải pháp:**
- ✅ Thêm timestamp cho mỗi action
- ✅ Check timeout 5 phút:
  ```python
  if time.time() - ctx.user_data.get("last_action", 0) > 300:
      ctx.user_data.clear()
      await update.message.reply_text("Phiên đã hết hạn. Vui lòng /start lại.")
      return
  ```

---

## ✅ NHỮNG ĐIỂM TỐT ĐÃ LÀM ĐÚNG

### 1. **Authorization Check**
```python
if not is_seller(uid):
    return
```
✅ Có check quyền ở hầu hết functions

### 2. **Input Validation**
```python
if quantity <= 0 or quantity > 100:
    return
if len(custom_name) > 12:
    return
if not custom_name.isalnum():
    return
```
✅ Validate số lượng, length, format

### 3. **SQL Injection Prevention**
```python
c.execute("INSERT INTO orders ... VALUES (?, ?, ?)", (val1, val2, val3))
```
✅ Dùng parameterized queries (không dùng string concat)

### 4. **Clear Sensitive Data**
```python
ctx.user_data.clear()  # Khi /start hoặc cancel
```
✅ Clear user data khi kết thúc

### 5. **Logging**
```python
logger.info("select_package: uid=%s, kid=%s", uid, kid)
logger.error("Error: %s", e, exc_info=True)
```
✅ Log đầy đủ để audit

### 6. **Error Handling**
```python
try:
    await update.message.delete()
except Exception:
    pass  # Fail gracefully
```
✅ Try/catch để tránh crash

---

## 🔧 CHECKLIST SỬA LỖI ƯU TIÊN

### Priority 1 - CRITICAL (Phải sửa ngay)
- [ ] **Xóa hàm `start()` trùng lặp** (dòng 33)
- [ ] **Xóa hàm legacy** (`_create_payment_qr`, `buy_key`)
- [ ] **Thêm auth check trong `receive_input()`**
- [ ] **Thêm rate limit cho "Đã thanh toán"**

### Priority 2 - HIGH (Nên sửa sớm)
- [ ] **Tăng độ dài order_info** lên 12 ký tự
- [ ] **Escape markdown trong user input**
- [ ] **Thêm session timeout 5 phút**
- [ ] **Tách table `order_keys` riêng**

### Priority 3 - MEDIUM (Cải thiện)
- [ ] **Dùng aiohttp thay vì requests** (async)
- [ ] **Thêm warning nếu multi-session**
- [ ] **Thêm CAPTCHA nếu spam detection**

### Priority 4 - LOW (Nice to have)
- [ ] **Thêm audit log** cho mọi action
- [ ] **Monitor VietQR API uptime**
- [ ] **Thêm retry logic cho QR download**

---

## 🎯 LUỒNG HOẠT ĐỘNG - ĐÁNH GIÁ

### ✅ **Điểm mạnh:**
1. Phân tầng rõ ràng: Gói → Loại → Số lượng → Xác nhận
2. Validation đầy đủ ở mỗi bước
3. UX tốt: Edit message thay vì spam
4. Nhiều bước xác nhận → giảm lỗi

### ⚠️ **Điểm yếu:**
1. Code có hàm trùng lặp → dễ nhầm lẫn
2. Thiếu rate limit → dễ bị spam
3. Session không timeout → data lẫn lộn
4. Lưu JSON trong text field → khó query

### 🎯 **Tổng điểm: 7/10**
- Bảo mật cơ bản: ✅ Đạt
- Validation: ✅ Đạt
- Error handling: ✅ Đạt
- Code quality: ⚠️ Cần cải thiện
- Performance: ✅ Đạt
- Rate limiting: ❌ Thiếu
- Session management: ⚠️ Cần cải thiện

---

## 📝 HÀNH ĐỘNG ĐỀ XUẤT

### Ngay lập tức:
```bash
# 1. Backup code hiện tại
cp customer_bot.py customer_bot.py.backup

# 2. Sửa lỗi critical
# - Xóa hàm trùng
# - Xóa hàm legacy
# - Thêm auth check
# - Thêm rate limit

# 3. Test kỹ lưỡng
python main.py
```

### Tuần tới:
- Refactor database schema (tách table order_keys)
- Implement session timeout
- Add monitoring/alerting

### Tháng tới:
- Add CAPTCHA nếu phát hiện abuse
- Implement comprehensive audit log
- Performance optimization

---

## 🛡️ KẾT LUẬN

**Hệ thống hiện tại:**
- ✅ Bảo mật CƠ BẢN đạt yêu cầu
- ⚠️ Có một số lỗi code cần sửa NGAY
- ⚠️ Thiếu rate limiting và session management
- ✅ Luồng logic rõ ràng, dễ hiểu

**Rủi ro chính:**
1. **Code trùng lặp** → Có thể gây bug khó debug
2. **Thiếu rate limit** → Dễ bị spam/abuse
3. **Session không expire** → Data lẫn lộn giữa các lần dùng

**Khuyến nghị:**
- Sửa lỗi Priority 1 TRƯỚC KHI deploy production
- Implement rate limiting trong vòng 1 tuần
- Monitor logs để phát hiện abuse sớm

**An toàn deploy? → ⚠️ CÓ, nhưng cần sửa lỗi Priority 1 trước**
