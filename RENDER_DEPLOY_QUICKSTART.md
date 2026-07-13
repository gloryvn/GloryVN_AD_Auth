# ⚡ RENDER DEPLOY - QUICKSTART

## 🚀 Deploy trong 10 phút

### Step 1: Chuẩn bị GitHub (2 phút)

```bash
cd "c:\Users\dphat\Desktop\GVN\_Source UI VIP\AotForms\Auth"

# Initialize git
git init
git add .
git commit -m "Initial commit - Ready for deploy"

# Create GitHub repo (trên web: github.com/new)
# Sau đó:
git remote add origin https://github.com/YOUR_USERNAME/gloryvn-bot.git
git branch -M main
git push -u origin main
```

### Step 2: Tạo Web Service trên Render (3 phút)

1. Đăng nhập [render.com](https://render.com)
2. Click **New +** → **Web Service**
3. **Connect repository** → Chọn `gloryvn-bot`
4. Cấu hình:

```yaml
Name:           gloryvn-bot
Environment:    Python 3
Region:         Singapore (hoặc gần nhất)
Branch:         main
Build Command:  pip install -r requirements.txt
Start Command:  gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT wsgi:app
Instance Type:  Free
```

5. Click **Create Web Service**

### Step 3: Thêm Environment Variables (3 phút)

Trong Render dashboard, vào **Environment** tab:

```bash
CUSTOMER_BOT_TOKEN     = 123456:ABC-DEF...        # Từ @BotFather
ADMIN_BOT_TOKEN        = 789012:GHI-JKL...        # Từ @BotFather
ADMIN_CHAT_ID          = 123456789                # Từ @userinfobot
VIETQR_ACCOUNT         = 0123456789               # SĐT MOMO
VIETQR_BANK            = MOMO
VIETQR_TEMPLATE        = compact
SUPABASE_URL           = https://xxx.supabase.co  # Optional
SUPABASE_KEY           = your_key                 # Optional
WEBHOOK_URL            = https://gloryvn-bot.onrender.com  # Thay bằng URL của bạn
```

**⚠️ Lưu ý:** `WEBHOOK_URL` phải là URL thực của app sau khi deploy!

### Step 4: Deploy & Verify (2 phút)

1. **Đợi build & deploy** (3-5 phút)
2. **Lấy URL** từ Render dashboard (VD: `https://gloryvn-bot.onrender.com`)
3. **Cập nhật WEBHOOK_URL**:
   - Vào Environment → Edit `WEBHOOK_URL`
   - Paste URL vừa lấy
   - Save → Auto redeploy

4. **Test:**
```bash
# Health check
curl https://gloryvn-bot.onrender.com/health
# → {"status": "healthy", "bots_ready": true}

# Webhook info
curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
```

5. **Test bot trên Telegram:**
   - Gửi `/start` cho bot
   - Nếu nhận phản hồi → **THÀNH CÔNG! 🎉**

---

## 🔧 Troubleshooting Nhanh

### Bot không phản hồi?

```bash
# 1. Check logs trên Render
Dashboard → Logs → Xem có error không

# 2. Check webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# 3. Verify WEBHOOK_URL đúng
# Phải match với URL của app trên Render
```

### App sleep sau 15 phút?

**Giải pháp:** Dùng [UptimeRobot](https://uptimerobot.com) (free)
1. Đăng ký UptimeRobot
2. Add monitor:
   - Type: HTTP(s)
   - URL: `https://gloryvn-bot.onrender.com/health`
   - Interval: 5 minutes
3. Done! App sẽ không bao giờ sleep

### Database bị mất sau deploy?

**Giải pháp:** Add Render Disk
1. Dashboard → Service → **Disks** tab
2. Click **Add Disk**:
   - Name: `data`
   - Mount Path: `/opt/render/project/src/data`
   - Size: 1 GB
3. Update `database.py`:
```python
DB_PATH = os.getenv("DB_PATH", "/opt/render/project/src/data/orders.db")
```
4. Redeploy

---

## ✅ Checklist

### Pre-deploy:
- [ ] Code đã test local (`python main.py`)
- [ ] Bot tokens đã có
- [ ] Admin chat ID đã có
- [ ] VietQR account đã setup
- [ ] GitHub repo đã tạo

### Deploy:
- [ ] Render service đã tạo
- [ ] Build thành công (xanh)
- [ ] Environment variables đã set đủ
- [ ] WEBHOOK_URL đã cập nhật đúng

### Post-deploy:
- [ ] `/health` trả về healthy
- [ ] Webhook info có URL đúng
- [ ] Bot phản hồi `/start` trên Telegram
- [ ] Logs không có error
- [ ] UptimeRobot đã setup (optional)

---

## 🎯 Commands Tham Khảo

```bash
# Health check
curl https://your-app.onrender.com/health

# Check webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Delete webhook (nếu cần reset)
curl https://api.telegram.org/bot<TOKEN>/deleteWebhook

# Set webhook manually (nếu cần)
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d "url=https://your-app.onrender.com/<TOKEN>"

# Get bot info
curl https://api.telegram.org/bot<TOKEN>/getMe

# Test local
python main.py

# Check Python version
python --version
```

---

## 📱 Support

**Telegram:** @admin
**Logs:** Render Dashboard → Logs
**Docs:** [Full Guide](./DEPLOYMENT_GUIDE.md)

---

**Bot của bạn giờ đã live 24/7! 🚀**
