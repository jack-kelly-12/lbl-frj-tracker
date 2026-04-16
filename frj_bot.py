import logging
import os

from clients import get_client_players
from config import OUTPUT_DIR, RECIPIENT_EMAILS, SEND_EMAIL
from data import get_action_items, get_client_hrs, get_frjs, get_yesterday_data
from mailer import send_email_with_pdf
from report import create_daily_report

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    client_df = get_client_players()
    logger.info(f"Clients:\n{client_df.to_string(index=False)}")
    client_ids = client_df["mlbam_id"].tolist()

    sc = get_yesterday_data()
    if sc.empty:
        logger.error("No data available. Exiting.")
        return

    action_items = get_action_items(sc, client_ids)
    frjs = get_frjs(sc, client_ids)
    client_hrs = get_client_hrs(sc, client_ids)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, 'daily_lbl_report.pdf')

    create_daily_report(action_items, frjs, client_hrs, output_file)
    logger.info(f"PDF created: {output_file}")

    if SEND_EMAIL:
        recipients = [e.strip() for e in RECIPIENT_EMAILS.split(',')]
        send_email_with_pdf(output_file, recipients)
    else:
        logger.info("Email skipped (SEND_EMAIL not set to 'true')")


if __name__ == "__main__":
    main()
