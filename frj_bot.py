import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Dict
import logging
from datetime import datetime, timedelta
from pybaseball import playerid_reverse_lookup, statcast
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get environment variables with defaults
URL_FANGRAPHS = "https://www.fangraphs.com/guts.aspx?type=cn"
# Convert string of comma-separated IDs to list of integers
LABELED_PLAYERS_STR = "607054,621439,596142,669261,571745,543877,456781,593871,596115,664034,680777,621043,664056"
LABELED_PLAYERS = [int(player_id.strip())
                   for player_id in LABELED_PLAYERS_STR.split(',')]

COLUMNS = ['batter_name', 'playId', 'batter',
           'launch_speed', 'launch_angle', 'events']

# Email configuration
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "jackkelly12902@gmail.com")
SENDER_PASSWORD = os.environ.get(
    "SENDER_PASSWORD", "")  # Empty default for security
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
RECIPIENT_EMAILS_STR = os.environ.get(
    "RECIPIENT_EMAILS", "keenan@lblbaseball.com")
RECIPIENT_EMAILS = [email.strip() for email in RECIPIENT_EMAILS_STR.split(',')]

# Longball Labs green color
LBL_GREEN = colors.Color(0, 0.5, 0, 1)
LIGHT_GREEN = colors.Color(0.9, 1, 0.9)
TODAY = datetime.today().strftime('%Y-%m-%d')


def get_play_by_play(game_id):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/playByPlay"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data for game {game_id}")
        return None


def send_email_with_pdf(pdf_path, recipient_emails):
    # Check if password is provided
    if not SENDER_PASSWORD:
        logger.error(
            "SENDER_PASSWORD environment variable not set. Cannot send email.")
        return

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(recipient_emails)
    msg['Subject'] = f"Daily Longball Labs Report - {datetime.now().strftime('%Y-%m-%d')}"
    body = "Please find attached the Daily Longball Labs Report. Please contact Jack Kelly with any questions or concerns."
    msg.attach(MIMEText(body, 'plain'))

    with open(pdf_path, "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="pdf")
    attach.add_header('Content-Disposition', 'attachment',
                      filename=os.path.basename(pdf_path))
    msg.attach(attach)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        logger.info(
            f"Email sent successfully to {', '.join(recipient_emails)}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def extract_play_ids(play_by_play, game):
    play_ids = []
    for play in play_by_play.get('allPlays', []):
        about = play.get('about', {})
        matchup = play.get('matchup', {})
        for event in play.get('playEvents', []):
            if event.get('isPitch') and 'playId' in event:
                play_ids.append({
                    'playId': event['playId'],
                    'pitch_number': event.get('pitchNumber'),
                    'game_pk': int(game),
                    'batter': matchup.get('batter', {}).get('id'),
                    'pitcher': matchup.get('pitcher', {}).get('id'),
                    'inning': about.get('inning'),
                    'inning_topbot': about.get('halfInning'),
                    'at_bat_number': about.get('atBatIndex', 0) + 1
                })
    return play_ids


def process_games(games):
    all_play_ids = []
    for game in games:
        play_by_play = get_play_by_play(game)
        if play_by_play:
            all_play_ids.extend(extract_play_ids(play_by_play, game))
    df = pd.DataFrame(all_play_ids)
    return df


def get_yesterday_data() -> pd.DataFrame:
    sc = get_statcast()
    sc = sc[sc.description == 'hit_into_play']
    sc['game_date'] = pd.to_datetime(sc['game_date'])
    sc['launch_speed_adj'] = sc['launch_speed'] + 2
    sc['video'] = sc['playId'].apply(
        lambda x: f'https://baseballsavant.mlb.com/sporty-videos?playId={x}')

    player_names = get_player_names(sc['batter'].unique())
    sc['batter_name'] = sc['batter'].map(player_names)
    return sc


def get_statcast():
    try:
        sc = statcast()

        sc['game_date'] = pd.to_datetime(sc['game_date']).dt.date
        games = sc['game_pk'].unique()
        api = process_games(games)
        api['inning_topbot'] = api['inning_topbot'].replace(
            {'top': 'Top', 'bottom': 'Bot'})
        sc_w_playid = pd.merge(sc, api, how='left', on=[
            'game_pk', 'inning', 'inning_topbot', 'pitch_number', 'at_bat_number', 'batter', 'pitcher'
        ])

        logger.info("Statcast data updated successfully.")
    except Exception as e:
        logger.error(f"Error fetching or processing new data: {e}")

    return sc_w_playid.drop_duplicates()


def get_player_names(player_ids):
    try:
        player_info = playerid_reverse_lookup(player_ids)
        return dict(zip(player_info['key_mlbam'], player_info['name_first'] + ' ' + player_info['name_last']))
    except Exception as e:
        logger.error(f"Failed to lookup player names: {e}")
        return {}


def scrape_woba_weights(url: str = URL_FANGRAPHS) -> Dict[str, float]:
    """Scrape wOBA weights from Fangraphs."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'rgMasterTable'})
        if not table:
            raise ValueError("Could not find the table with wOBA weights")

        row_2024 = next((cells for row in table.find_all('tr')
                         if (cells := row.find_all('td')) and cells[0].text.strip() == '2024'), None)
        if not row_2024:
            raise ValueError("No data found for the 2024 season")

        return {
            'single': float(row_2024[5].text.strip()),
            'double': float(row_2024[6].text.strip()),
            'triple': float(row_2024[7].text.strip()),
            'home_run': float(row_2024[8].text.strip()),
            'field_out': 0,
            'walk': float(row_2024[3].text.strip()),
            'hbp': float(row_2024[4].text.strip())
        }
    except requests.RequestException as e:
        logger.error(f"Failed to fetch wOBA weights: {e}")
        raise


def get_frjs(sc: pd.DataFrame) -> pd.DataFrame:
    df = sc[sc['events'].isin(['home_run'])]
    left_or_right = df[(df['hit_location'] == 7) | (df['hit_location'] == 9)]
    left_or_right = left_or_right[left_or_right['hit_distance_sc'] <= 350]
    center = df[(df['hit_location'] == 8)]
    center = center[center['hit_distance_sc'] <= 380]
    result = pd.concat([left_or_right, center])
    result = result[result['batter'].isin(LABELED_PLAYERS) |
                    ((result['inning_topbot'] == 'Top') & (result['away_team'] == 'SD')) |
                    ((result['inning_topbot'] == 'Bot') & (result['home_team'] == 'SD'))]
    return result[COLUMNS]


def get_action_items(sc: pd.DataFrame) -> pd.DataFrame:
    df = sc[sc['events'].isin(['single', 'double', 'triple', 'field_out',
                              'sacrifice_fly', 'sac_fly_double_play', 'field_error'])]
    left_or_right = df[(df['hit_location'] == 7) | (df['hit_location'] == 9)]
    left_or_right = left_or_right[left_or_right['hit_distance_sc'] >= 365]
    center = df[(df['hit_location'] == 8)]
    center = center[center['hit_distance_sc'] >= 380]
    result = pd.concat([left_or_right, center])
    result = result[~(result['batter'].isin(LABELED_PLAYERS) |
                      ((result['inning_topbot'] == 'Top') & (result['away_team'] == 'SD')) |
                      ((result['inning_topbot'] == 'Bot') & (result['home_team'] == 'SD')))]
    return result[COLUMNS]


def create_definitions_page():
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='DefinitionsTitle',
        parent=styles['Title'],
        textColor=LBL_GREEN,
        fontSize=18,
        alignment=1,
        spaceAfter=12
    )
    elements.append(Paragraph("Definitions", title_style))
    elements.append(Spacer(1, 0.25*inch))
    definition_style = ParagraphStyle(
        name='Definition',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=12
    )
    definitions = [
        ("Action Item", "Per Keenan's Statcast query, a non-client hit batted ball to LF/RF where not a home run and >= 365 or non-client hit batted ball to CF where not a home run and >= 380."),
        ("Front Row Joe", "Similar to action item, for clients only. Home runs to LF/RF where <= 350 distance or to CF >= 380 distance.")
    ]
    for term, definition in definitions:
        elements.append(
            Paragraph(f"<b>{term}:</b> {definition}", definition_style))
    elements.append(PageBreak())
    return elements


def create_styled_table(df: pd.DataFrame, title: str):
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='Title',
        parent=styles['Title'],
        textColor=LBL_GREEN,
        fontSize=16,
        spaceAfter=12
    )
    elements.append(Paragraph(title, title_style))

    # Create hyperlinks for playId
    df['playId'] = df['playId'].apply(
        lambda x: f'<link href="https://baseballsavant.mlb.com/sporty-videos?playId={x}">Link</link>')

    # Round numeric columns
    numeric_columns = ['launch_speed', 'launch_angle']
    df[numeric_columns] = df[numeric_columns].round(1)

    # Convert DataFrame to a list of lists
    data = [df.columns.tolist()] + [
        [Paragraph(str(cell), styles['Normal']) if isinstance(
            cell, str) else cell for cell in row]
        for row in df.values.tolist()
    ]

    # Create the table
    t = Table(data, repeatRows=1)

    # Add style
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LBL_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, LBL_GREEN),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GREEN])
    ])
    t.setStyle(style)
    elements.append(t)
    elements.append(Spacer(1, 0.5*inch))
    return elements


def create_daily_report(action_items: pd.DataFrame, frjs: pd.DataFrame, output_filename: str):
    doc = SimpleDocTemplate(output_filename, pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []

    # Check if logo exists, use default path or environment variable
    logo_path = os.environ.get("LOGO_PATH", "longball-labs.png")
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=1*inch, height=1*inch))
        elements.append(Spacer(1, 0.25*inch))
    else:
        logger.warning(
            f"Logo not found at {logo_path}, skipping logo in report")

    # Add report title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        textColor=LBL_GREEN,
        fontSize=24,
        alignment=1,
        spaceAfter=12
    )
    elements.append(Paragraph("Daily Longball Labs Report", title_style))

    # Add date range
    data_date_str = os.environ.get("DATA_DATE", "")
    if data_date_str:
        start_date = data_date_str
    else:
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    date_range = f"From {start_date}"
    date_style = ParagraphStyle(
        name='DateRange',
        parent=styles['Normal'],
        alignment=1,
        fontSize=10,
        textColor=colors.darkgray,
        spaceAfter=24
    )
    elements.append(Paragraph(date_range, date_style))

    # Add definitions page
    elements.extend(create_definitions_page())

    # Add tables
    elements.extend(create_styled_table(
        action_items, "Action Items (non-clients)"))
    elements.extend(create_styled_table(
        frjs, "FRJs (clients)"))

    # Build the PDF
    doc.build(elements)


def main():
    # Check if running in GitHub Actions
    is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if is_github_actions:
        logger.info("Running in GitHub Actions environment")

    # Get data
    sc = get_statcast()
    if sc.empty:
        logger.error("No data available. Exiting.")
        return

    # Get action items and FRJs
    action_items = get_action_items(sc)
    frjs = get_frjs(sc)

    # Output directory - use environment variable if set
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'daily_lbl_report.pdf')
    create_daily_report(action_items, frjs, output_file)
    logger.info(f"PDF created successfully: {output_file}")

    # Send email if requested
    if os.environ.get("SEND_EMAIL", "false").lower() == "true":
        send_email_with_pdf(output_file, RECIPIENT_EMAILS)
    else:
        logger.info("Email sending skipped (SEND_EMAIL not set to 'true')")


if __name__ == "__main__":
    main()
