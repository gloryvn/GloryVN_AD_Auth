# 🎯 GloryVN 247 - Telegram Bot Store

Hệ thống bot Telegram bán key tự động với 2 bot:
- **Customer Bot**: Cho khách hàng mua key
- **Admin Bot**: Quản lý seller và xác nhận đơn hàng

## 🚀 Quick Start

### Local Development (Polling Mode)

```bash
# 1. Clone project
git clone <your-repo>
cd Auth

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
cp .env.example .env
# Edit .env với các thông tin của bạn

# 5. Run bot
python main.py
```

### Production Deployment (Webhook Mode)

```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy to production"
git push origin main

# 2. Deploy trên Render
# Xem chi tiết: DEPLOYMENT_GUIDE.md

# 3. Test
curl https://your-app.onrender.com/health
```

## 📁 Project Structure

```
Auth/
├── customer_bot.py          # Customer bot logic
├── admin_bot.py             # Admin bot logic
├── database.py              # SQLite database
├── config.py                # Configuration
├── payment.py               # VietQR integration
├── key_gen.py               # License key generator
├── main.py                  # Polling mode runner
├── app.py                   # Flask app (webhook mode)
├── wsgi.py                  # Gunicorn entry point
├── requirements.txt         # Python dependencies
├── Procfile                 # Render/Heroku config
├── runtime.txt              # Python version
├── render.yaml              # Render configuration
├── .env                     # Environment variables (git ignored)
├── .gitignore               # Git ignore rules
├── orders.db                # SQLite database (git ignored)
│
├── DEPLOYMENT_GUIDE.md      # 🚀 Deploy instructions
├── SECURITY_AUDIT.md        # 🔒 Security report
├── FIXES_APPLIED.md         # ✅ Bug fixes log
├── UI_UX_REDESIGN.md        # 🎨 UI/UX design spec
├── UI_IMPROVEMENTS_DONE.md  # ✨ UI improvements log
├── NEW_WORKFLOW.md          # 📋 New workflow documentation
├── PERFORMANCE_OPTIMIZATION.md  # ⚡ Performance guide
└── README.md                # 📖 This file
```

## 🎨 Features

### Customer Bot
- ✅ Multi-step order flow với validation
- ✅ Random key hoặc Custom key (tự đặt tên)
- ✅ Mua nhiều key cùng lúc (1-100)
- ✅ QR thanh toán tự động (VietQR)
- ✅ Real-time notification khi admin xác nhận
- ✅ Session timeout (5 phút)
- ✅ Rate limiting (10s cooldown)
- ✅ Beautiful UI với emoji & boxes

### Admin Bot
- ✅ Quản lý seller (add/remove/list)
- ✅ Xác nhận/Hủy đơn hàng
- ✅ Tạo key thủ công
- ✅ Xem danh sách key
- ✅ Reset HWID
- ✅ Toggle key status
- ✅ Thống kê (stats)
- ✅ Seller cũng có thể mua key (flow giống customer)

### Security
- ✅ Authorization check ở mọi endpoint
- ✅ Input validation (số lượng, tên key)
- ✅ SQL injection prevention (parameterized queries)
- ✅ Rate limiting (chống spam)
- ✅ Session timeout
- ✅ Secure order ID (12 ký tự random)

## 🔧 Configuration

### Environment Variables

```bash
# Bot Tokens (từ @BotFather)
CUSTOMER_BOT_TOKEN=123456:ABC-DEF...
ADMIN_BOT_TOKEN=789012:GHI-JKL...

# Admin Telegram ID
ADMIN_CHAT_ID=123456789

# VietQR Payment
VIETQR_ACCOUNT=0123456789
VIETQR_BANK=MOMO
VIETQR_TEMPLATE=compact

# Supabase (optional - để sync keys)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_supabase_key

# Webhook (chỉ dùng khi deploy production)
WEBHOOK_URL=https://your-app.onrender.com
```

### Package Pricing (config.py)

```python
KEY_TYPES = {
    "1_day": ("1 Ngày", 24, 17500, 22000),
    "1_week": ("1 Tuần", 168, 84000, 96000),
    "1_month": ("1 Tháng", 720, 312000, 360000),
    "forever": ("Vĩnh Viễn", -1, 900000, 1000000)
}
# Format: (tên, giờ, giá_random, giá_custom)
```

## 🧪 Testing

### Test Locally

```bash
# 1. Run bot
python main.py

# 2. Test trên Telegram
# - Customer Bot: Gửi /start
# - Admin Bot: Gửi /start

# 3. Test workflow
# - Chọn gói → Chọn loại → Nhập số lượng
# - Nhập tên key (nếu custom)
# - Xác nhận → QR hiện
# - Bấm "Đã thanh toán"
# - Admin nhận thông báo → Xác nhận
# - Customer nhận key
```

### Test on Render

```bash
# 1. Check health
curl https://your-app.onrender.com/health

# 2. Check webhook info
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# 3. Test bot trên Telegram như bình thường
```

## 📊 Database Schema

```sql
-- Sellers (có quyền mua key)
CREATE TABLE sellers (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    added_at TEXT
);

-- Orders (đơn hàng)
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_chat_id INTEGER,
    customer_username TEXT,
    key_type TEXT,
    key_name TEXT,
    hours INTEGER,
    amount REAL,
    status TEXT DEFAULT 'pending',
    order_info TEXT UNIQUE,
    license_key TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- License Keys (sync với Supabase)
CREATE TABLE license_keys (
    license_key TEXT PRIMARY KEY,
    duration_hours INTEGER,
    is_active INTEGER DEFAULT 1,
    hwid TEXT,
    created_at TEXT
);
```

## 🛠️ Development

### Adding New Package

```python
# In config.py
KEY_TYPES = {
    # ...existing...
    "3_month": ("3 Tháng", 2160, 800000, 900000),  # New!
}
```

### Adding New Feature

1. **Customer side**: Edit `customer_bot.py`
2. **Admin side**: Edit `admin_bot.py`
3. **Database**: Update `database.py` nếu cần schema mới
4. **Test**: Test local trước, sau đó deploy

### Debugging

```python
# Tăng log level
logging.basicConfig(level=logging.DEBUG)

# Xem tất cả updates
logger.debug(f"Received update: {update}")

# Xem user_data
logger.debug(f"User data: {ctx.user_data}")
```

## 🔒 Security Best Practices

1. **Never commit**:
   - `.env` files
   - Bot tokens
   - Database files
   - API keys

2. **Always validate**:
   - User input (số lượng, tên key)
   - User permissions (is_seller, is_admin)
   - Session state (timeout)

3. **Rate limiting**:
   - 10s cooldown cho "Đã thanh toán"
   - 5 phút session timeout
   - Có thể thêm CAPTCHA nếu cần

4. **Database**:
   - Dùng parameterized queries
   - Backup định kỳ
   - Encrypt sensitive data nếu cần

## 📈 Monitoring

### Logs

```bash
# On Render
- Dashboard → Service → Logs

# Local
- Console output
- Check orders.db với SQLite browser
```

### Metrics

```bash
# Health check
curl https://your-app.onrender.com/health

# Webhook status
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Stats (nếu có endpoint)
curl https://your-app.onrender.com/stats
```

## 🆘 Troubleshooting

### Bot không phản hồi

1. Check logs trên Render
2. Check webhook: `getWebhookInfo`
3. Đảm bảo `WEBHOOK_URL` đúng
4. Redeploy app

### Database mất sau deploy

1. Dùng Render Disk (persistent storage)
2. Hoặc migrate sang PostgreSQL
3. Backup trước mỗi deploy

### App sleep (Free tier)

1. Dùng UptimeRobot để ping /health
2. Hoặc upgrade lên Paid tier ($7/month)

## 📚 Documentation

- [Deployment Guide](./DEPLOYMENT_GUIDE.md) - Chi tiết deploy lên Render
- [Security Audit](./SECURITY_AUDIT.md) - Báo cáo bảo mật
- [UI/UX Design](./UI_UX_REDESIGN.md) - Thiết kế giao diện
- [Workflow](./NEW_WORKFLOW.md) - Luồng hoạt động chi tiết

## 🤝 Contributing

1. Fork repo
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open Pull Request

## 📄 License

Private project - All rights reserved

## 📞 Support

- Telegram: @admin
- Email: support@gloryvn247.com
- Issues: GitHub Issues

---

**Made with ❤️ by GloryVN 247 Team**
