-- ============================================================
-- BOT TABLES - Chạy trong Supabase SQL Editor
-- ============================================================

-- Admins (thêm trực tiếp bằng tay)
CREATE TABLE IF NOT EXISTS bot_admins (
  telegram_id BIGINT PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')
);

-- Sellers
CREATE TABLE IF NOT EXISTS bot_sellers (
  telegram_id BIGINT PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')
);

-- Payment requests
CREATE TABLE IF NOT EXISTS payment_requests (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  telegram_id BIGINT NOT NULL,
  telegram_username TEXT NOT NULL DEFAULT '',
  license_key TEXT NOT NULL,
  duration_hours INTEGER NOT NULL,
  amount BIGINT NOT NULL,
  payos_order_code TEXT UNIQUE NOT NULL,
  checkout_url TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh'),
  paid_at TIMESTAMP
);

-- Xoá cột name khỏi license_keys (chạy 1 lần nếu đã thêm trước đó)
ALTER TABLE license_keys DROP COLUMN IF EXISTS name;

-- Xoá bảng key_prices nếu còn
DROP TABLE IF EXISTS key_prices;
