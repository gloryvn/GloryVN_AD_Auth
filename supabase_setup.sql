-- ============================================================
-- SUPABASE SETUP SCRIPT - License Key System
-- Tất cả thời gian được lưu theo múi giờ +7 (Asia/Ho_Chi_Minh)
-- ============================================================

-- 1. Create the license_keys table
CREATE TABLE IF NOT EXISTS license_keys (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  key TEXT UNIQUE NOT NULL,
  hwid TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh'),
  expires_at TIMESTAMP,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  last_login TIMESTAMP,
  device_name TEXT NOT NULL DEFAULT '',
  duration_hours INTEGER NOT NULL DEFAULT 0
);

-- 1b. Migration for existing databases (chạy 1 lần nếu đã có bảng cũ)
-- ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS duration_hours INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE license_keys ALTER COLUMN expires_at DROP NOT NULL;

-- 2. Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_license_keys_key ON license_keys(key);
CREATE INDEX IF NOT EXISTS idx_license_keys_hwid ON license_keys(hwid);

-- 3. Enable Row Level Security
ALTER TABLE license_keys ENABLE ROW LEVEL SECURITY;

-- 4. Restrict anon key: only allow calling the validate_key function
--    Direct SELECT/UPDATE are blocked — anon cannot read or modify license_keys directly
DROP POLICY IF EXISTS "Allow anon select" ON license_keys;
DROP POLICY IF EXISTS "Allow anon update" ON license_keys;

-- Allow anon to ONLY call validate_key(), no direct table access
-- (validate_key is SECURITY DEFINER so it bypasses RLS internally)

-- 5. Create the validate_key function (REST API endpoint)
DROP FUNCTION IF EXISTS validate_key(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS validate_key(TEXT, TEXT);
CREATE FUNCTION validate_key(p_key TEXT, p_hwid TEXT, p_device_name TEXT DEFAULT '')
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_record license_keys%ROWTYPE;
  v_now TIMESTAMP := NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh';
  v_expires_at TIMESTAMP;
  v_message TEXT;
BEGIN
  -- Look up the key
  SELECT * INTO v_record FROM license_keys WHERE key = p_key;

  -- Check if key exists
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'message', 'Invalid key');
  END IF;

  -- Check if key is active
  IF NOT v_record.is_active THEN
    RETURN json_build_object('success', false, 'message', 'Key has been deactivated');
  END IF;

  -- Kiểm tra expiry (chỉ khi expires_at đã được set)
  IF v_record.expires_at IS NOT NULL AND v_record.expires_at < v_now THEN
    UPDATE license_keys SET is_active = false WHERE id = v_record.id;
    RETURN json_build_object(
      'success', false,
      'message', 'Key has expired',
      'duration_hours', v_record.duration_hours
    );
  END IF;

  -- HWID logic
  IF v_record.hwid = '' OR v_record.hwid IS NULL THEN
    -- First login: tính expires_at từ duration_hours
    IF v_record.duration_hours > 0 THEN
      v_expires_at := v_now + (v_record.duration_hours * INTERVAL '1 hour');
      v_message := 'Key activated – ' || v_record.duration_hours || 'h license started';
    ELSIF v_record.expires_at IS NOT NULL THEN
      -- Legacy key: giữ nguyên expires_at cố định
      v_expires_at := v_record.expires_at;
      v_message := 'Key activated and bound to this device';
    ELSE
      RETURN json_build_object(
        'success', false,
        'message', 'Key has no duration set. Contact admin.'
      );
    END IF;

    -- Bind HWID + set expires_at
    UPDATE license_keys
    SET hwid = p_hwid,
        expires_at = v_expires_at,
        last_login = v_now,
        device_name = p_device_name
    WHERE id = v_record.id;

    RETURN json_build_object(
      'success', true,
      'message', v_message,
      'expires_at', v_expires_at,
      'duration_hours', v_record.duration_hours,
      'key', p_key
    );
  ELSIF v_record.hwid = p_hwid THEN
    -- Same device: allow login
    UPDATE license_keys SET last_login = v_now WHERE id = v_record.id;

    -- Tính thời gian còn lại để gửi về client
    v_expires_at := v_record.expires_at;

    RETURN json_build_object(
      'success', true,
      'message', 'Login successful',
      'expires_at', v_expires_at,
      'duration_hours', v_record.duration_hours,
      'key', p_key
    );
  ELSE
    -- HWID mismatch
    RETURN json_build_object(
      'success', false,
      'message', 'Key is already bound to another device. HWID mismatch.',
      'duration_hours', v_record.duration_hours
    );
  END IF;
END;
$$;

-- 6. Grant execute permission to anon role (required for REST API calls)
GRANT EXECUTE ON FUNCTION validate_key TO anon;
GRANT EXECUTE ON FUNCTION validate_key TO authenticated;
GRANT EXECUTE ON FUNCTION validate_key TO public;

-- ============================================================
-- HOW TO ADD KEYS (chạy trong SQL Editor):
-- Thời gian được tính từ lần login đầu tiên (khi HWID được bind)
-- ============================================================
-- Key 30 ngày (720 giờ):
-- INSERT INTO license_keys (key, duration_hours)
-- VALUES ('KEY-EXAMPLE-001', 720);
--
-- Key 72 giờ:
-- INSERT INTO license_keys (key, duration_hours)
-- VALUES ('KEY-EXAMPLE-002', 72);
--
-- Key 7 ngày (168 giờ):
-- INSERT INTO license_keys (key, duration_hours)
-- VALUES ('KEY-EXAMPLE-003', 168);
--
-- Key 24 giờ:
-- INSERT INTO license_keys (key, duration_hours)
-- VALUES ('KEY-EXAMPLE-004', 24);
--
-- ============================================================
-- MIGRATION: Key cũ đã có expires_at cố định
-- ============================================================
-- UPDATE license_keys
-- SET duration_hours = EXTRACT(EPOCH FROM (expires_at - created_at)) / 3600
-- WHERE duration_hours = 0 AND expires_at IS NOT NULL;

-- ============================================================
-- MIGRATION: Thêm created_by để biết key do ai tạo
-- ============================================================
ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS created_by BIGINT NOT NULL DEFAULT 0;
UPDATE license_keys SET created_by = 0 WHERE created_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_license_keys_created_by ON license_keys(created_by);

-- ============================================================
