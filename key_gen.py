import hashlib
from datetime import datetime, timedelta

SECRET_KEY = "AotForms-Secret-Key-2024"

def generate_key(order_id, hours, custom_id=None):
    raw = f"{order_id}-{datetime.now().timestamp()}-{SECRET_KEY}"
    unique_id = custom_id or hashlib.md5(raw.encode()).hexdigest()[:8].upper()

    if hours == -1:
        expiry = "99991231"
    else:
        exp_date = datetime.now() + timedelta(hours=hours)
        expiry = exp_date.strftime("%Y%m%d")

    key_body = f"GLORYVN-{unique_id}-{expiry}"
    sig_input = f"{key_body}-{SECRET_KEY}"
    signature = hashlib.sha256(sig_input.encode()).hexdigest()[:4].upper()

    return f"{key_body}-{signature}"
