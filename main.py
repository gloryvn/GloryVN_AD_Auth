import asyncio
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import ApplicationBuilder

from config import CUSTOMER_BOT_TOKEN, ADMIN_BOT_TOKEN
from database import init_db
import customer_bot
import admin_bot

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", 10000))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health server listening on port %d", PORT)
    server.serve_forever()


async def run_bot(token, register_fn, name):
    logger.info("Starting %s ...", name)
    app = ApplicationBuilder().token(token).build()
    register_fn(app)
    logger.info("%s is polling ...", name)
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()


async def main():
    init_db()
    logger.info("Database initialized.")

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_health_server)

    logger.info("Both bots are running. Press Ctrl+C to stop.")
    await asyncio.gather(
        run_bot(CUSTOMER_BOT_TOKEN, customer_bot.register_handlers, "CustomerBot"),
        run_bot(ADMIN_BOT_TOKEN, admin_bot.register_handlers, "AdminBot"),
    )


if __name__ == "__main__":
    asyncio.run(main())
