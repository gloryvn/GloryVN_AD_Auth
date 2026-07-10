import os
import threading

os.environ["RENDER_SKIP_BOT"] = "1"


def post_fork(server, worker):
    from app import start_bot_in_background
    start_bot_in_background()
