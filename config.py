import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

CUSTOMER_BOT_TOKEN = os.getenv("CUSTOMER_BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not CUSTOMER_BOT_TOKEN or not ADMIN_BOT_TOKEN or not ADMIN_CHAT_ID:
    raise ValueError("Missing required environment variables. Check .env file")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "orders.db")

# id -> (display_name, hours, price_random, price_custom)
KEY_TYPES = {
    "1_day":    ("1 Ngày",    24,  17500, 20000),
    "1_week":   ("1 Tuần",   168, 84000, 96000),
    "1_month":  ("1 Tháng",  720, 245000, 280000),
    "forever":  ("Vĩnh Viễn", -1, 875000, 1000000),
}

VIETQR_BANK = "momo"
VIETQR_ACCOUNT = "PSP2615213800000100"
VIETQR_TEMPLATE = "qr_only"
