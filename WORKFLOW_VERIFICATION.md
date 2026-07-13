# 📋 KIỂM TRA LUỒNG HOẠT ĐỘNG - GLORYVN 247 STORE

## ✅ LUỒNG HOÀN CHỈNH ĐÃ ĐƯỢC SỬA

### 🎯 LUỒNG 1: KEY NGẪU NHIÊN (Nhanh - 1 bước)

#### Customer Bot:
1. User gửi `/start` → Kiểm tra quyền seller
2. Hiển thị menu 8 nút (4 gói × 2 loại)
3. **Chọn "🎲 [Gói] [Giá Random]"** → Callback: `buy_{kid}_r`
4. ✅ **TẠO QR NGAY** (gọi `_create_payment_qr()` với `custom_name=None`)
5. Hiện QR + thông tin đơn hàng + nút "Tôi đã thanh toán"
6. Bấm "Tôi đã thanh toán" → Gọi `paid()`
7. Tạo order trong DB → Gửi thông báo Admin
8. Admin nhận thông báo với nút Xác nhận/Hủy

#### Admin Bot (Seller mua key):
1. Seller gửi `/start` → Hiển thị menu tương tự
2. **Chọn "🎲 [Gói] [Giá Random]"** → Callback: `buy_{kid}_r`
3. ✅ **TẠO QR NGAY** (gọi `_seller_create_payment_qr()` với `custom_name=None`)
4. Hiện QR + nút "Tôi đã thanh toán"
5. Bấm "Tôi đã thanh toán" → Gọi `seller_paid()`
6. Tạo order → Thông báo Admin

---

### 🎨 LUỒNG 2: KEY TÙY CHỈNH (3 bước)

#### Customer Bot:
1. User gửi `/start` → Kiểm tra quyền seller
2. Hiển thị menu 8 nút (4 gói × 2 loại)
3. **Chọn "✏️ [Gói] [Giá Custom]"** → Callback: `buy_{kid}_c`
4. ✏️ **BẮT ĐẦU LUỒNG HỎI TÊN KEY**:
   - Lưu state: `user_data["waiting_for_custom_name"] = True`
   - Hiện tin nhắn: "Nhập tên key tùy chỉnh (max 12 ký tự, chỉ A-Z, 0-9)"
5. 📝 **User nhập text** → MessageHandler gọi `receive_custom_name()`
   - Validate: không trống, max 12 ký tự, chỉ alphanumeric
   - Nếu sai → Yêu cầu nhập lại
   - Nếu đúng → Lưu `user_data["custom_key_name"]`
6. 📋 **HIỆN BẢNG XÁC NHẬN**:
   - Gói, Loại, **Tên key**, Giá
   - Nút: "✅ Xác nhận" (callback: `confirm_custom`) | "❌ Hủy"
7. Bấm "Xác nhận" → Gọi `confirm_custom_key()`
8. ✅ **TẠO QR THANH TOÁN** (gọi `_create_payment_qr()` với `custom_name`)
9. Hiện QR + thông tin + nút "Tôi đã thanh toán"
10. Bấm "Tôi đã thanh toán" → Gọi `paid()`
11. Tạo order với `custom_key_name` → Gửi thông báo Admin (có hiển thị tên key)

#### Admin Bot (Seller mua key custom):
1. Seller gửi `/start` → Hiển thị menu
2. **Chọn "✏️ [Gói] [Giá Custom]"** → Callback: `buy_{kid}_c`
3. ✏️ **BẮT ĐẦU LUỒNG HỎI TÊN KEY**:
   - Lưu state: `user_data["sel_waiting_custom"] = True`
   - Hiện tin nhắn hỏi tên key
4. 📝 **Seller nhập text** → MessageHandler gọi `seller_receive_custom_name()`
   - Validate tương tự
   - Lưu `user_data["sel_custom_name"]`
5. 📋 **HIỆN BẢNG XÁC NHẬN** với nút "✅ Xác nhận" (callback: `sel_confirm_custom`)
6. Bấm "Xác nhận" → Gọi `seller_confirm_custom()`
7. ✅ **TẠO QR** (gọi `_seller_create_payment_qr()` với `custom_name`)
8. Hiện QR + nút "Tôi đã thanh toán"
9. Bấm "Tôi đã thanh toán" → Gọi `seller_paid()`
10. Tạo order với `custom_key_name` → Thông báo Admin

---

### 🔐 LUỒNG 3: ADMIN XÁC NHẬN ĐƠN HÀNG

#### Khi Admin nhận thông báo:
1. Thông báo hiển thị:
   - Mã đơn, Customer/Seller ID, Username
   - Gói, **Tên key (nếu là custom)**
   - Giá tiền
   - Nút: "✅ Xác nhận" | "❌ Hủy"

2. **Admin bấm "Xác nhận"** → Callback: `confirm_{order_id}`
   - Gọi `confirm_order()` trong admin_bot
   - Lấy order từ DB
   - **Trích xuất custom_key_name**: `order_info.split("|")[1]` nếu có
   - Gọi `generate_key(order_id, hours, custom_key_name)`
   - Tạo key với custom ID nếu có
   - Lưu vào Supabase
   - Gửi key cho customer qua Customer Bot API

3. **Admin bấm "Hủy"** → Callback: `cancel_{order_id}`
   - Đổi status order thành "cancelled"
   - Thông báo customer đơn bị hủy

---

## 🔍 CÁC ĐIỂM KIỂM TRA QUAN TRỌNG

### ✅ 1. State Management
- [x] `waiting_for_custom_name` (Customer Bot)
- [x] `sel_waiting_custom` (Admin Bot - Seller flow)
- [x] Clear state khi cancel hoặc hoàn thành

### ✅ 2. Data Flow
- [x] `custom_key_name` được lưu trong `user_data`
- [x] `custom_key_name` được truyền vào `create_order()`
- [x] `custom_key_name` được nhúng vào `order_info` dạng: `GLORYVN_XXX|CUSTOMNAME`
- [x] Admin trích xuất `custom_key_name` từ `order_info` khi xác nhận
- [x] `generate_key()` nhận `custom_id` parameter

### ✅ 3. Validation
- [x] Tên key không trống
- [x] Tối đa 12 ký tự
- [x] Chỉ chữ và số (A-Z, 0-9)
- [x] Tự động uppercase

### ✅ 4. UI/UX Flow
- [x] Random key: 1 click → QR (nhanh)
- [x] Custom key: 3 bước (chọn → nhập → xác nhận → QR)
- [x] Bảng xác nhận hiển thị đầy đủ: Gói, Loại, Tên key, Giá
- [x] Có nút Hủy ở mọi bước
- [x] Command `/cancel` để thoát

### ✅ 5. Cross-Bot Communication
- [x] Customer Bot → Admin Bot: Thông báo đơn hàng mới
- [x] Admin Bot → Customer Bot: Gửi key sau khi xác nhận
- [x] Thông báo admin hiển thị tên key custom (nếu có)

### ✅ 6. Database
- [x] `create_order()` hỗ trợ `custom_key_name` parameter
- [x] `order_info` lưu kèm custom name: `CODE|CUSTOMNAME`
- [x] Supabase `license_keys` lưu key đã tạo

### ✅ 7. Error Handling
- [x] Phiên hết hạn → Yêu cầu `/start` lại
- [x] Input không hợp lệ → Yêu cầu nhập lại
- [x] QR không tải được → Hiện thông tin chuyển khoản thủ công
- [x] Try/catch cho `edit_message_caption` và `edit_message_text`

---

## 🎯 CALLBACK DATA MAP

### Customer Bot:
- `buy_{kid}_r` → Random key
- `buy_{kid}_c` → Custom key (bắt đầu luồng hỏi tên)
- `confirm_custom` → Xác nhận tên key custom và tạo QR
- `paid` → Đã thanh toán
- `cancel_order` → Hủy đơn

### Admin Bot (Seller):
- `buy_{kid}_r` → Seller mua random key
- `buy_{kid}_c` → Seller mua custom key
- `sel_confirm_custom` → Seller xác nhận tên key custom
- `selpaid` → Seller đã thanh toán
- `selcancel` → Seller hủy

### Admin Bot (Admin):
- `confirm_{order_id}` → Xác nhận đơn hàng
- `cancel_{order_id}` → Hủy đơn hàng

---

## 🧪 KỊCH BẢN TEST

### Test Case 1: Random Key (Customer)
1. `/start`
2. Chọn "🎲 1 Ngày 17.500đ"
3. Kiểm tra: QR hiện ra ngay, không hỏi tên
4. Bấm "Tôi đã thanh toán"
5. Kiểm tra: Admin nhận thông báo (không có trường "Tên key")

### Test Case 2: Custom Key (Customer)
1. `/start`
2. Chọn "✏️ 1 Tuần 96.000đ"
3. Kiểm tra: Bot hỏi nhập tên key
4. Nhập: "TEST123"
5. Kiểm tra: Hiện bảng xác nhận với tên "TEST123"
6. Bấm "Xác nhận"
7. Kiểm tra: QR hiện ra
8. Bấm "Tôi đã thanh toán"
9. Kiểm tra: Admin nhận thông báo **có trường "Tên key: TEST123"**

### Test Case 3: Custom Key với validation
1. `/start`
2. Chọn custom key
3. Nhập: "abc@#$" → Kiểm tra: Báo lỗi, yêu cầu nhập lại
4. Nhập: "VERYLONGKEYNAME123" → Kiểm tra: Báo lỗi max 12 ký tự
5. Nhập: "ABC123" → Kiểm tra: OK, hiện bảng xác nhận

### Test Case 4: Admin xác nhận custom key
1. Admin nhận thông báo đơn custom key "MYKEY999"
2. Bấm "Xác nhận"
3. Kiểm tra: Key được tạo dạng `GLORYVN-MYKEY999-20261231-XXXX`
4. Kiểm tra: Customer nhận được key

### Test Case 5: Hủy ở các bước
1. Chọn custom key → Nhập tên → Bấm "Hủy" trên bảng xác nhận
2. Kiểm tra: State bị clear, không tạo order
3. Chọn key → Tạo QR → Bấm "Hủy"
4. Kiểm tra: State bị clear
5. Gửi `/cancel` ở bất kỳ bước nào
6. Kiểm tra: State bị clear, yêu cầu `/start` lại

---

## 📊 TRẠNG THÁI HOÀN THÀNH

| Component | Status | Notes |
|-----------|--------|-------|
| Customer Bot - Random Flow | ✅ | 1 bước, tạo QR ngay |
| Customer Bot - Custom Flow | ✅ | 3 bước: chọn → nhập → xác nhận → QR |
| Admin Bot Seller - Random | ✅ | Tương tự customer |
| Admin Bot Seller - Custom | ✅ | Tương tự customer |
| Admin Confirm Order | ✅ | Trích xuất custom_name từ order_info |
| Database Integration | ✅ | Lưu custom_name vào order_info |
| Key Generation | ✅ | Hỗ trợ custom_id parameter |
| Validation | ✅ | Max 12 ký tự, alphanumeric only |
| Error Handling | ✅ | Try/catch, session timeout |
| Cross-Bot Notification | ✅ | Admin nhận thông báo đầy đủ |

---

## 🚀 SẴN SÀNG SỬ DỤNG

Tất cả các luồng đã được kiểm tra và sửa đổi theo đúng yêu cầu:

✅ `/start` → nếu là Seller → chọn thời hạn (1 Ngày / 1 Tuần / 1 Tháng / Vĩnh Viễn)  
✅ Chọn loại: **Key ngẫu nhiên** (giá cũ) hoặc **Key tùy chỉnh** (giá mới)  
✅ Nếu **tùy chỉnh** → bot hỏi nhập tên key → nhập → hiện bảng xác nhận giá + tên + nút Xác nhận/Hủy  
✅ Xác nhận → tạo QR thanh toán → nút "Tôi đã thanh toán"  
✅ Bấm "Tôi đã thanh toán" → gửi thông báo cho Admin kèm nút Xác nhận/Hủy  

**Luồng hoạt động mượt mà, đầy đủ, và nhất quán! 🎉**
