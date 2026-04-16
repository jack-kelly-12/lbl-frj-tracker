import os
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
RECIPIENT_EMAILS = os.environ.get("RECIPIENT_EMAILS", "")
SEND_EMAIL = os.environ.get("SEND_EMAIL", "false").lower() == "true"
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", ".")
LOGO_PATH = os.environ.get("LOGO_PATH", "longball-labs.png")
