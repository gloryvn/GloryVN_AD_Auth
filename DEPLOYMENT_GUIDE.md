# 🚀 HƯỚNG DẪN DEPLOY LÊN RENDER

## 📋 TỔNG QUAN

Bot Telegram sẽ chạy trên Render với:
- **Web Service** (không phải background worker)
- **Webhook mode** (thay vì polling)
- **Gunicorn** + **Flask** để nhận webhook
- **Free tier** của Render (đủ dùng)

---

## 📁 FILES ĐÃ TẠO

### 1. **Procfile** - Lệnh khởi động
```
web: gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT wsgi:app
```

### 2. **wsgi.py** - Entry point cho Gunicorn
- Khởi tạo bots
- Setup webhooks
- Import Flask app

### 3. **app.py** - Flask application
- Health check endpoints
- Webhook endpoints cho 2 bots
- Auto-setup webhooks

### 4. **runtime.txt** - Python version
```
python-3.11.7
```

### 5. **render.yaml** - Render configuration (optional)
- Auto-deploy config
- Environment variables

### 6. **.gitignore** - Ignore sensitive files
- .env
- *.db
- __pycache__

---

## 🔧 SETUP RENDER

### Bước 1: Tạo Git Repository

```bash
# Trong thư mục Auth/
git init
git add .
git commit -m "Initial commit - GloryVN Bot"

# Push lên GitHub (tạo repo trước)
git remote add origin https://github.com/your-username/gloryvn-bot.git
git branch -M main
git push -u origin main
```

### Bước 2: Tạo Web Service trên Render

1. Đăng nhập [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect GitHub repository
4. Chọn repo `gloryvn-bot`
5. Cấu hình:

```
Name:              gloryvn-bot
Environment:       Python 3
Branch:            main
Build Command:     pip install -r requirements.txt
Start Command:     gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT wsgi:app
Instance Type:     Free
```

### Bước 3: Thêm Environment Variables

Vào **Environment** tab, thêm các biến sau:

```bash
# Bot Tokens
CUSTOMER_BOT_TOKEN=<your_customer_bot_token>
ADMIN_BOT_TOKEN=<your_admin_bot_token>

# Admin
ADMIN_CHAT_ID=<your_telegram_chat_id>

# VietQR
VIETQR_ACCOUNT=<your_momo_phone>
VIETQR_BANK=MOMO
VIETQR_TEMPLATE=compact

# Supabase
SUPABASE_URL=<your_supabase_url>
SUPABASE_KEY=<your_supabase_key>

# QUAN TRỌNG: Webhook URL
WEBHOOK_URL=https://your-app-name.onrender.com
```

**Lưu ý:** `WEBHOOK_URL` phải là URL của app trên Render (sẽ có sau khi deploy lần đầu)

### Bước 4: Deploy

1. Click **"Create Web Service"**
2. Đợi build & deploy (3-5 phút)
3. Sau khi deploy xong, lấy URL: `https://your-app-name.onrender.com`

### Bước 5: Cập nhật WEBHOOK_URL

1. Copy URL app từ Render
2. Vào **Environment** → Edit `WEBHOOK_URL`
3. Paste URL: `https://your-app-name.onrender.com`
4. Save changes → Render sẽ auto-redeploy

### Bước 6: Kiểm tra Webhooks

Vào browser, truy cập:
```
https://your-app-name.onrender.com/health
```

Kết quả:
```json
{"status": "healthy"}
```

---

## 🧪 TESTING

### 1. Health Check
```bash
curl https://your-app-name.onrender.com/health
```

### 2. Test Bot
- Mở Telegram
- Gửi `/start` cho bot
- Nếu nhận được phản hồi → **THÀNH CÔNG! 🎉**

### 3. Kiểm tra Logs
Trên Render dashboard:
- Click vào service
- Tab **"Logs"**
- Xem real-time logs

Expected logs:
```
Database initialized.
Customer bot handlers registered.
Admin bot handlers registered.
Customer bot webhook set to: https://...
Admin bot webhook set to: https://...
```

---

## 🔍 TROUBLESHOOTING

### Issue 1: Bot không phản hồi

**Kiểm tra:**
```bash
# 1. Check webhook status
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

**Expected:**
```json
{
  "url": "https://your-app-name.onrender.com/...",
  "has_custom_certificate": false,
  "pending_update_count": 0
}
```

**Sửa:**
- Đảm bảo `WEBHOOK_URL` đúng
- Redeploy app

### Issue 2: App sleep (Free tier)

**Vấn đề:** Render free tier sleep sau 15 phút không hoạt động

**Giải pháp 1:** Dùng cron job (UptimeRobot)
```
https://uptimerobot.com
- Add monitor
- Type: HTTP(s)
- URL: https://your-app-name.onrender.com/health
- Interval: 5 minutes
```

**Giải pháp 2:** Tự ping từ script
```python
# ping_self.py
import requests
import time

URL = "https://your-app-name.onrender.com/health"

while True:
    try:
        requests.get(URL)
        print("Pinged successfully")
    except:
        pass
    time.sleep(300)  # 5 minutes
```

### Issue 3: Database không tồn tại

**Vấn đề:** SQLite database bị mất sau mỗi deploy

**Giải pháp:** Dùng Render Disk
1. Vào service settings
2. Tab **"Disks"**
3. Add disk:
   - Name: `data`
   - Mount Path: `/opt/render/project/src/data`
4. Update `database.py`:
```python
DB_PATH = "/opt/render/project/src/data/orders.db"
```

### Issue 4: Logs không hiện

**Kiểm tra:**
```python
# Đảm bảo logging được config đúng
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
```

---

## 🔒 BẢO MẬT

### 1. Ẩn Bot Tokens trong URL

✅ **ĐÃ LÀM**: Webhook URL dùng token làm secret path
```
https://your-app.com/<BOT_TOKEN>
```

→ Chỉ Telegram biết URL này

### 2. HTTPS Required

✅ **ĐÃ CÓ**: Render tự động có SSL certificate
→ Webhook phải dùng HTTPS

### 3. Environment Variables

✅ **ĐÃ LÀM**: Tất cả secrets trong env vars
→ Không commit tokens vào Git

### 4. Validate Requests

⚠️ **CẦN THÊM**: Verify request từ Telegram
```python
# TODO: Add signature validation
# https://core.telegram.org/bots/api#setwebhook
```

---

## 📊 MONITORING

### 1. Render Dashboard
- **Metrics**: CPU, Memory, Network
- **Logs**: Real-time streaming
- **Events**: Deploy history

### 2. Telegram Bot API
```bash
# Check webhook info
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Get updates (for debugging)
curl https://api.telegram.org/bot<TOKEN>/getUpdates
```

### 3. Custom Monitoring (Optional)

Thêm vào `app.py`:
```python
from datetime import datetime

stats = {
    "total_requests": 0,
    "last_request": None,
    "start_time": datetime.now()
}

@app.route("/stats")
def get_stats():
    return {
        "total_requests": stats["total_requests"],
        "last_request": stats["last_request"],
        "uptime": (datetime.now() - stats["start_time"]).total_seconds()
    }
```

---

## 💰 PRICING

### Free Tier Limitations:
- ✅ 750 hours/month (enough for 1 app)
- ✅ Auto-sleep after 15 min inactivity
- ✅ 512 MB RAM
- ⚠️ Cold start: ~30s khi wake up

### Paid Tier Benefits ($7/month):
- ✅ No sleep
- ✅ 512 MB → 2 GB RAM
- ✅ Faster cold starts
- ✅ Custom domains

**Khuyến nghị:** Start với Free, upgrade nếu cần

---

## 🔄 CI/CD

### Auto-deploy khi push code:

1. **GitHub Integration** (Recommended)
   - Render tự động deploy khi push lên `main`
   - Không cần config gì thêm

2. **Manual Deploy**
   - Vào Render dashboard
   - Click **"Manual Deploy"** → **"Deploy latest commit"**

3. **Deploy Hooks**
```bash
# Deploy từ CLI
curl -X POST https://api.render.com/deploy/srv-xxxxx?key=xxxxx
```

---

## 📝 CHECKLIST DEPLOY

### Pre-deployment:
- [ ] Code đã test local
- [ ] Git repo đã tạo
- [ ] Tất cả env variables đã có
- [ ] Database migration (nếu cần)

### Deployment:
- [ ] Service đã tạo trên Render
- [ ] Build thành công
- [ ] Env vars đã set
- [ ] `WEBHOOK_URL` đã cập nhật

### Post-deployment:
- [ ] Health check OK
- [ ] Webhooks đã setup
- [ ] Bot phản hồi trong Telegram
- [ ] Logs không có error
- [ ] Setup monitoring (UptimeRobot)

---

## 🆘 SUPPORT

### Render Support:
- Docs: https://render.com/docs
- Community: https://community.render.com
- Status: https://status.render.com

### Telegram Bot API:
- Docs: https://core.telegram.org/bots/api
- Webhooks: https://core.telegram.org/bots/webhooks

### Issues?
1. Check Render logs
2. Check webhook info
3. Test locally first
4. Contact: @admin

---

## 🚀 QUICK START

```bash
# 1. Clone & setup
git clone <your-repo>
cd gloryvn-bot

# 2. Test locally
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py

# 3. Push to GitHub
git add .
git commit -m "Ready for deploy"
git push origin main

# 4. Deploy trên Render (theo steps trên)

# 5. Done! 🎉
```

**Bot của bạn giờ đang chạy 24/7 trên cloud! ☁️**
