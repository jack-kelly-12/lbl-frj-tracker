import logging
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT

logger = logging.getLogger(__name__)


def send_email_with_pdf(pdf_path: str, recipient_emails: list[str]):
    if not SENDER_PASSWORD:
        logger.error("SENDER_PASSWORD not set. Cannot send email.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(recipient_emails)
    msg['Subject'] = f"Daily Longball Labs Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText("Please find attached the Daily Longball Labs Report. Contact Jack Kelly with any questions.", 'plain'))

    with open(pdf_path, "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="pdf")
    attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_path))
    msg.attach(attach)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {', '.join(recipient_emails)}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
