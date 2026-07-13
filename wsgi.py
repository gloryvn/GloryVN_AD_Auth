"""
WSGI entry point for Gunicorn
"""
from app import app

# Note: Bots are initialized when app module is imported
# Webhooks are setup automatically on first request

if __name__ == "__main__":
    app.run()
