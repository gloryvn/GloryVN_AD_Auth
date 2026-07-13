import sqlite3
import threading
import requests
from datetime import datetime

from config import DATABASE_PATH, SUPABASE_URL, SUPABASE_SERVICE_KEY

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Supabase REST API helpers
# ---------------------------------------------------------------------------

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    _SUPABASE_BASE = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
    _SUPABASE_HEADERS = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
else:
    _SUPABASE_BASE = None
    _SUPABASE_HEADERS = None


def _supabase_req(method, table, params=None, json_data=None):
    if not _SUPABASE_BASE:
        return None
    url = f"{_SUPABASE_BASE}/{table}"
    try:
        resp = requests.request(
            method, url, headers=_SUPABASE_HEADERS,
            params=params, json=json_data, timeout=15
        )
        if method == "GET":
            return resp.json() if resp.status_code == 200 else []
        return resp
    except requests.RequestException:
        return None


def supabase_insert_key(key, duration_hours, created_by=0):
    return _supabase_req("POST", "license_keys", json_data={
        "key": key,
        "duration_hours": duration_hours,
        "created_by": created_by,
        "is_active": True,
    })


def supabase_query_keys(created_by=None, search=None, limit=50, offset=0):
    params = {"order": "created_at.desc", "limit": limit, "offset": offset}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    if search:
        params["key"] = f"like.%{search}%"
    result = _supabase_req("GET", "license_keys", params=params)
    return result if isinstance(result, list) else []


def supabase_delete_key(key, created_by=None):
    params = {"key": f"eq.{key}"}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    resp = _supabase_req("DELETE", "license_keys", params=params)
    return resp is not None and resp.status_code in (200, 204)


def supabase_reset_hwid(key, created_by=None):
    params = {"key": f"eq.{key}"}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    resp = _supabase_req("PATCH", "license_keys", params=params, json_data={"hwid": ""})
    return resp is not None and resp.status_code in (200, 204)


def supabase_get_key(key):
    params = {"key": f"eq.{key}", "limit": "1"}
    result = _supabase_req("GET", "license_keys", params=params)
    if isinstance(result, list) and len(result) > 0:
        return result[0]
    return None


def supabase_toggle_key(key, is_active, created_by=None):
    params = {"key": f"eq.{key}"}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    resp = _supabase_req("PATCH", "license_keys", params=params, json_data={"is_active": is_active})
    return resp is not None and resp.status_code in (200, 204)


def supabase_extend_key(key, add_hours, created_by=None):
    k = supabase_get_key(key)
    if not k:
        return False
    current = k.get("duration_hours", 0)
    new_hours = current + add_hours
    if new_hours < 0:
        new_hours = 0
    params = {"key": f"eq.{key}"}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    resp = _supabase_req("PATCH", "license_keys", params=params, json_data={"duration_hours": new_hours})
    return resp is not None and resp.status_code in (200, 204)


def supabase_count_keys(created_by=None):
    params = {"select": "id", "limit": "0"}
    if created_by is not None:
        params["created_by"] = f"eq.{created_by}"
    resp = _supabase_req("GET", "license_keys", params=params)
    if isinstance(resp, list):
        return len(resp)
    return 0


# ---------------------------------------------------------------------------
# Local SQLite – orders + sellers
# ---------------------------------------------------------------------------

def _get_conn():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_chat_id INTEGER NOT NULL,
                customer_username TEXT DEFAULT '',
                key_type TEXT NOT NULL,
                key_name TEXT NOT NULL,
                hours INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                order_info TEXT NOT NULL,
                license_key TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sellers (
                chat_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                added_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()


# -- sellers -----------------------------------------------------------------

def is_seller(chat_id):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT 1 FROM sellers WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        conn.close()
        return row is not None


def add_seller(chat_id, username=""):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "INSERT OR REPLACE INTO sellers (chat_id, username, added_at) VALUES (?, ?, ?)",
            (chat_id, username, now))
        conn.commit()
        conn.close()


def remove_seller(chat_id):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM sellers WHERE chat_id=?", (chat_id,))
        conn.commit()
        conn.close()


def list_sellers():
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT chat_id, username, added_at FROM sellers ORDER BY added_at DESC")
        rows = c.fetchall()
        conn.close()
        return rows


# -- orders -------------------------------------------------------------------

def create_order(customer_chat_id, customer_username, key_type, key_name, hours, amount, order_info, custom_names=None):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        now = datetime.now().isoformat()
        # Thêm custom_names vào order_info nếu có (JSON string)
        full_order_info = order_info
        if custom_names:
            import json
            full_order_info = f"{order_info}|{json.dumps(custom_names)}"
        c.execute("""
            INSERT INTO orders
            (customer_chat_id, customer_username, key_type, key_name, hours, amount, order_info, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (customer_chat_id, customer_username, key_type, key_name, hours, amount, full_order_info, now, now))
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        return order_id


def update_order(order_id, status, license_key=None):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        now = datetime.now().isoformat()
        if license_key:
            c.execute("UPDATE orders SET status=?, license_key=?, updated_at=? WHERE id=?",
                      (status, license_key, now, order_id))
        else:
            c.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?",
                      (status, now, order_id))
        conn.commit()
        conn.close()


def get_order(order_id):
    with _lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = c.fetchone()
        conn.close()
        if row:
            cols = ["id", "customer_chat_id", "customer_username", "key_type", "key_name",
                    "hours", "amount", "status", "order_info", "license_key", "created_at", "updated_at"]
            return dict(zip(cols, row))
        return None
