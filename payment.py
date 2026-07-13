import requests
from config import VIETQR_BANK, VIETQR_ACCOUNT, VIETQR_TEMPLATE

def generate_qr_url(amount, info):
    return (f"https://img.vietqr.io/image/"
            f"{VIETQR_BANK}-{VIETQR_ACCOUNT}-{VIETQR_TEMPLATE}.png"
            f"?amount={amount}&addInfo={info}")

def download_qr_image(amount, info):
    """Download QR image với timeout ngắn để tránh lag"""
    url = generate_qr_url(amount, info)
    try:
        # Giảm timeout xuống 5s để tránh lag
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.content
    except requests.RequestException:
        pass
    return None
