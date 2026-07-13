"""
Flask app để chạy Telegram bot với webhook mode trên Render
"""
import logging
import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder

from config import CUSTOMER_BOT_TOKEN, ADMIN_BOT_TOKEN
from database import init_db
import customer_bot
import admin_bot

# Setup logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Webhook URL (sẽ được set từ env variable)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # VD: https://your-app.onrender.com

# Initialize bots
customer_app = None
admin_app = None
webhooks_initialized = False

def init_bots():
    """Initialize both bots"""
    global customer_app, admin_app
    
    if customer_app is not None:
        return
    
    # Init database
    init_db()
    logger.info("Database initialized.")
    
    # Customer bot
    customer_app = ApplicationBuilder().token(CUSTOMER_BOT_TOKEN).build()
    customer_bot.register_handlers(customer_app)
    
    # IMPORTANT: Initialize bot
    asyncio.run(customer_app.initialize())
    logger.info("Customer bot initialized and handlers registered.")
    
    # Admin bot
    admin_app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    admin_bot.register_handlers(admin_app)
    
    # IMPORTANT: Initialize bot
    asyncio.run(admin_app.initialize())
    logger.info("Admin bot initialized and handlers registered.")

def setup_webhooks():
    """Set up webhooks for both bots"""
    global webhooks_initialized
    
    if webhooks_initialized:
        return
    
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL not set! Cannot setup webhooks.")
        return
    
    async def _setup():
        # Customer bot webhook
        customer_webhook_url = f"{WEBHOOK_URL}/{CUSTOMER_BOT_TOKEN}"
        await customer_app.bot.set_webhook(customer_webhook_url)
        logger.info(f"Customer bot webhook set to: {customer_webhook_url}")
        
        # Admin bot webhook
        admin_webhook_url = f"{WEBHOOK_URL}/{ADMIN_BOT_TOKEN}"
        await admin_app.bot.set_webhook(admin_webhook_url)
        logger.info(f"Admin bot webhook set to: {admin_webhook_url}")
    
    try:
        asyncio.run(_setup())
        webhooks_initialized = True
    except Exception as e:
        logger.error(f"Error setting up webhooks: {e}")

@app.route("/")
def index():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "GloryVN 247 Bot",
        "version": "2.0",
        "webhooks_active": webhooks_initialized
    }

@app.route("/health")
def health():
    """Health check for Render"""
    return {"status": "healthy", "bots_ready": customer_app is not None}, 200

@app.route(f"/{CUSTOMER_BOT_TOKEN}", methods=["POST"])
def customer_webhook():
    """Webhook endpoint for customer bot"""
    try:
        if customer_app is None:
            init_bots()
            setup_webhooks()
        
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, customer_app.bot)
        
        # Process update in background
        asyncio.run(customer_app.process_update(update))
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing customer bot update: {e}", exc_info=True)
        return "Error", 500

@app.route(f"/{ADMIN_BOT_TOKEN}", methods=["POST"])
def admin_webhook():
    """Webhook endpoint for admin bot"""
    try:
        if admin_app is None:
            init_bots()
            setup_webhooks()
        
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, admin_app.bot)
        
        # Process update in background
        asyncio.run(admin_app.process_update(update))
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing admin bot update: {e}", exc_info=True)
        return "Error", 500

# Initialize on startup
init_bots()
setup_webhooks()

if __name__ == "__main__":
    # For local testing
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
