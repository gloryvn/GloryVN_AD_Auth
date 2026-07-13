import logging
import threading

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


def run_bot(token, register_fn, name):
    logger.info("Starting %s ...", name)
    app = ApplicationBuilder().token(token).build()
    register_fn(app)
    logger.info("%s is polling ...", name)
    app.run_polling()


def main():
    init_db()
    logger.info("Database initialized.")

    t1 = threading.Thread(
        target=run_bot,
        args=(CUSTOMER_BOT_TOKEN, customer_bot.register_handlers, "CustomerBot"),
        daemon=True
    )
    t2 = threading.Thread(
        target=run_bot,
        args=(ADMIN_BOT_TOKEN, admin_bot.register_handlers, "AdminBot"),
        daemon=True
    )

    t1.start()
    t2.start()

    logger.info("Both bots are running. Press Ctrl+C to stop.")
    try:
        t1.join()
        t2.join()
    except KeyboardInterrupt:
        logger.info("Shutting down ...")


if __name__ == "__main__":
    main()
