-- ============================================================
-- MIGRATION: Thêm created_by để biết key do ai tạo
-- Chạy 1 lần trong Supabase SQL Editor
-- ============================================================

ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS created_by BIGINT NOT NULL DEFAULT 0;
UPDATE license_keys SET created_by = 0 WHERE created_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_license_keys_created_by ON license_keys(created_by);

-- ============================================================
