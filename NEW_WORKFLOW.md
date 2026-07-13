# 🎯 LUỒNG MỚI - NHIỀU BƯỚC XÁC NHẬN & MUA NHIỀU KEY

## 📋 TỔNG QUAN

Luồng mới được thiết kế với nhiều bước xác nhận chi tiết và cho phép mua nhiều key cùng lúc.

---

## 🔄 LUỒNG CHI TIẾT

### **Bước 1: Menu Gói** (Không có giá)
```
/start → Menu 4 nút:
┌─────────────────┐
│  📦 1 Ngày      │
├─────────────────┤
│  📦 1 Tuần      │
├─────────────────┤
│  📦 1 Tháng     │
├─────────────────┤
│  📦 Vĩnh Viễn   │
└─────────────────┘
```

**Lý do không hiện giá:** 
- Menu gọn, dễ nhìn
- Giá chỉ hiện khi chọn loại (random/custom)

---

### **Bước 2: Chọn Loại** (Có giá)
```
User chọn "📦 1 Tuần"
→ Bot hiện 2 loại:

📦 Gói đã chọn: 1 Tuần

Vui lòng chọn loại key:

┌────────────────────────────────────┐
│  🎲 Key ngẫu nhiên - 84.000đ       │
├────────────────────────────────────┤
│  ✏️ Key tùy chỉnh - 96.000đ        │
├────────────────────────────────────┤
│  ⬅️ Quay lại                       │
└────────────────────────────────────┘
```

---

### **Bước 3: Nhập Số Lượng**
```
User chọn "🎲 Key ngẫu nhiên"
→ Bot hỏi:

📦 Gói: 1 Tuần
🏷️ Loại: Key ngẫu nhiên  
💰 Đơn giá: 84.000đ

📝 Vui lòng nhập số lượng key bạn muốn mua:
(Ví dụ: 1, 5, 10)

User nhập: 5
```

**Validation:**
- Phải là số nguyên dương
- Tối thiểu: 1
- Tối đa: 100

---

### **Bước 4A: Nếu Random Key → Xác Nhận**
```
📋 XÁC NHẬN THÔNG TIN ĐƠN HÀNG

📦 Gói: 1 Tuần
🏷️ Loại: Key ngẫu nhiên
📦 Số lượng: 5 key
💰 Đơn giá: 84.000đ
💵 Tổng tiền: 420.000đ

⚠️ Vui lòng kiểm tra kỹ trước khi xác nhận!

┌─────────────────────────┐
│  ✅ Xác nhận & Tạo QR   │
├─────────────────────────┤
│  ❌ Hủy                 │
└─────────────────────────┘
```

---

### **Bước 4B: Nếu Custom Key (1 key) → Hỏi Tên**
```
User chọn "✏️ Key tùy chỉnh"
User nhập số lượng: 1

→ Bot hỏi:

📦 Gói: 1 Tuần
🏷️ Loại: Key tùy chỉnh

✏️ Vui lòng nhập tên key:
(Tối đa 12 ký tự, chỉ chữ và số)

User nhập: MYKEY123
```

**Validation:**
- Không được trống
- Tối đa 12 ký tự
- Chỉ chữ cái (A-Z) và số (0-9)
- Tự động UPPERCASE

---

### **Bước 4C: Nếu Custom Key (Nhiều key) → Hỏi Danh Sách**
```
User chọn "✏️ Key tùy chỉnh"
User nhập số lượng: 3

→ Bot hỏi:

📦 Gói: 1 Tuần
🏷️ Loại: Key tùy chỉnh
📦 Số lượng: 3 key

✏️ Vui lòng nhập 3 tên key, mỗi tên một dòng:
(Tối đa 12 ký tự/tên, chỉ chữ và số)

Ví dụ:
KEY001
KEY002
KEY003

User nhập:
SHOP2024
PROMO01
GIFT999
```

**Validation:**
- Phải đúng số lượng đã nhập (3 tên)
- Mỗi tên tuân thủ quy tắc (12 ký tự, alphanumeric)
- Không được trùng nhau

---

### **Bước 5: Bảng Xác Nhận Cuối**
```
📋 XÁC NHẬN THÔNG TIN ĐƠN HÀNG

📦 Gói: 1 Tuần
🏷️ Loại: Key tùy chỉnh
📦 Số lượng: 3 key
💰 Đơn giá: 96.000đ
💵 Tổng tiền: 288.000đ

✏️ Tên key:
  • SHOP2024
  • PROMO01
  • GIFT999

⚠️ Vui lòng kiểm tra kỹ trước khi xác nhận!

┌─────────────────────────┐
│  ✅ Xác nhận & Tạo QR   │
├─────────────────────────┤
│  ❌ Hủy                 │
└─────────────────────────┘
```

---

### **Bước 6: QR Thanh Toán**
```
User bấm "✅ Xác nhận & Tạo QR"
→ Bot tạo QR:

📋 THÔNG TIN ĐƠN HÀNG

🆔 Mã đơn: GLORYVN_ABC12345
📦 Gói: 1 Tuần
🏷️ Loại: Key tùy chỉnh
📦 Số lượng: 3 key
💰 Đơn giá: 96.000đ
💵 Tổng tiền: 288.000đ

✏️ Tên key:
  • SHOP2024
  • PROMO01
  • GIFT999

💳 HƯỚNG DẪN THANH TOÁN:
🏦 Ngân hàng: MOMO
📱 Số TK: PSP...
💰 Số tiền: 288.000đ
📝 Nội dung: GLORYVN_ABC12345

[QR CODE IMAGE]

⚠️ Sau khi thanh toán, bấm nút bên dưới!

┌─────────────────────────┐
│  ✅ Tôi đã thanh toán   │
├─────────────────────────┤
│  ❌ Hủy                 │
└─────────────────────────┘
```

---

### **Bước 7: Thông Báo Admin**
```
User bấm "✅ Tôi đã thanh toán"
→ Bot gửi tin cho Admin:

🔔 ĐƠN HÀNG MỚI!

🆔 Mã đơn: GLORYVN_ABC12345
👤 KH: @username (ID: 12345)
📦 Gói: 1 Tuần - Key tùy chỉnh - x3
📦 Số lượng: 3 key
✏️ Tên key:
  • SHOP2024
  • PROMO01
  • GIFT999
💰 Tiền: 288.000đ

Kiểm tra và xác nhận thanh toán:

┌────────────────┐
│  ✅ Xác nhận   │  │  ❌ Hủy  │
└────────────────┘
```

---

## 📊 SO SÁNH CŨ/MỚI

| Tính năng | Cũ | Mới |
|-----------|-----|-----|
| **Menu /start** | 8 nút (4 gói × 2 loại) | 4 nút (gọn gàng) ✅ |
| **Hiện giá** | Ngay từ đầu | Sau khi chọn gói ✅ |
| **Số lượng** | Chỉ 1 key | 1-100 key ✅ |
| **Custom nhiều key** | Không | Có ✅ |
| **Xác nhận** | 1 bước | 2-3 bước ✅ |
| **Thông tin đơn** | Cơ bản | Chi tiết ✅ |

---

## 🎯 ƯU ĐIỂM LUỒNG MỚI

### 1. **UI/UX Tốt Hơn**
- Menu gọn, dễ nhìn (4 nút thay vì 8)
- Giá chỉ hiện khi cần thiết
- Phân tầng rõ ràng: Gói → Loại → Số lượng

### 2. **Nhiều Bước Xác Nhận**
- Seller thấy rõ thông tin trước khi thanh toán
- Giảm lỗi do nhầm lẫn
- Tổng tiền được tính sẵn

### 3. **Mua Nhiều Key**
- Hỗ trợ bán buôn (1-100 key)
- Custom nhiều key cùng lúc
- Danh sách tên key rõ ràng

### 4. **Chống Spam**
- Edit message thay vì tạo mới
- Xóa tin nhắn user tự động
- Chat gọn gàng, professional

---

## 🧪 TEST CASES

### Test 1: Random Key - 1 Key
```
1. /start → Chọn "1 Ngày"
2. Chọn "Key ngẫu nhiên"
3. Nhập "1"
4. Kiểm tra bảng xác nhận: 1 key, 17.500đ
5. Xác nhận → QR hiện
✅ PASS
```

### Test 2: Random Key - 10 Key
```
1. /start → Chọn "1 Tuần"
2. Chọn "Key ngẫu nhiên"
3. Nhập "10"
4. Kiểm tra: 10 key, 840.000đ
5. Xác nhận → QR hiện
✅ PASS
```

### Test 3: Custom Key - 1 Key
```
1. /start → Chọn "1 Tháng"
2. Chọn "Key tùy chỉnh"
3. Nhập "1"
4. Nhập tên "MYKEY123"
5. Kiểm tra bảng xác nhận: có tên key
6. Xác nhận → QR hiện
✅ PASS
```

### Test 4: Custom Key - 5 Key
```
1. /start → Chọn "Vĩnh Viễn"
2. Chọn "Key tùy chỉnh"
3. Nhập "5"
4. Nhập 5 tên (mỗi tên 1 dòng)
5. Kiểm tra: 5 tên hiện trong confirm
6. Xác nhận → QR hiện, tổng tiền = 5 × 1.000.000đ
✅ PASS
```

### Test 5: Validation - Số lượng
```
1. Chọn gói và loại
2. Nhập "abc" → Lỗi
3. Nhập "0" → Lỗi
4. Nhập "101" → Lỗi
5. Nhập "5" → OK
✅ PASS
```

### Test 6: Validation - Tên Key
```
1. Chọn custom, số lượng 3
2. Nhập 2 tên → Lỗi (thiếu)
3. Nhập 3 tên, 1 tên quá dài → Lỗi
4. Nhập 3 tên, có ký tự đặc biệt → Lỗi
5. Nhập 3 tên hợp lệ → OK
✅ PASS
```

### Test 7: Quay Lại
```
1. Chọn "1 Tuần"
2. Bấm "⬅️ Quay lại"
3. Kiểm tra: Về menu 4 gói
4. State bị clear
✅ PASS
```

---

## 🔧 KỸ THUẬT

### Callback Data Format
```
package_{kid}     →  Chọn gói: package_1_week
type_{kid}_{mode} →  Chọn loại: type_1_month_c
confirm_order     →  Xác nhận đơn hàng
back_to_menu      →  Quay lại menu
paid              →  Đã thanh toán
cancel_order      →  Hủy đơn
```

### User Data Structure
```python
{
    "selected_package": "1_week",
    "package_name": "1 Tuần",
    "package_hours": 168,
    "key_type": "c",           # "r" hoặc "c"
    "key_label": "Key tùy chỉnh",
    "key_price": 96000,
    "quantity": 5,
    "custom_names": ["KEY1", "KEY2", "KEY3", "KEY4", "KEY5"],
    "total_price": 480000,
    "order_info": "GLORYVN_ABC123",
    "quantity_message_id": 12345,  # Để edit
    "waiting_for_quantity": True/False,
    "waiting_for_custom_name": True/False,
    "waiting_for_custom_names": True/False
}
```

### Database Storage
```python
# order_info format:
"GLORYVN_ABC123|[\"KEY1\", \"KEY2\", \"KEY3\"]"
# ↑ Mã đơn     ↑ JSON danh sách tên (nếu custom)
```

---

## 🚀 HOÀN THÀNH

✅ Menu 4 gói (không có giá)
✅ Chọn gói → Hiện 2 loại kèm giá
✅ Nhập số lượng (1-100)
✅ Custom 1 key: nhập 1 tên
✅ Custom nhiều key: nhập danh sách
✅ Bảng xác nhận chi tiết
✅ Tính tổng tiền tự động
✅ Validation đầy đủ
✅ Edit message (chống spam)
✅ Thông báo admin chi tiết

**Luồng mới hoàn chỉnh, chi tiết, và professional! 🎉**
