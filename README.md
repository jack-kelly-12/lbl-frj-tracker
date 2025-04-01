# Longball Labs Daily Report Generator

This repository contains an automated script that generates daily baseball analytics reports using Statcast data and sends them via email.

## How It Works

The script fetches Statcast data, analyzes it for specific metrics like "Front Row Joes" and "Action Items", and generates a PDF report that is automatically sent to specified recipients.

## GitHub Actions Setup

This project is configured to run automatically via GitHub Actions on a daily schedule.

### Required Repository Secrets

You'll need to set up the following secrets in your GitHub repository:

1. **Email Configuration:**

   - `SENDER_EMAIL`: The email address used to send reports
   - `SENDER_PASSWORD`: Password or app password for the sender email
   - `RECIPIENT_EMAILS`: Comma-separated list of email recipients (e.g., "user1@example.com,user2@example.com")
   - `SMTP_SERVER`: (Optional) SMTP server address (defaults to "smtp.gmail.com")
   - `SMTP_PORT`: (Optional) SMTP port (defaults to "587")
   - `SEND_EMAIL`: (Optional) Set to "true" to enable email sending (defaults to "true")

2. **Data Configuration:**
   - `LABELED_PLAYERS`: (Optional) Comma-separated list of MLB player IDs considered as clients
   - `URL_FANGRAPHS`: (Optional) URL for scraping wOBA weights

### Setting Up Secrets

1. Go to your repository on GitHub
2. Click on "Settings" > "Secrets and variables" > "Actions"
3. Click "New repository secret"
4. Add each secret with its name and value
5. Save each secret

### Manual Trigger

You can manually trigger the workflow:

1. Go to the "Actions" tab in your repository
2. Select the "Daily Longball Labs Report" workflow
3. Click "Run workflow"

## Local Development

### Environment Variables

For local development, you can create a `.env` file with the following variables:

```
# Email Configuration
SENDER_EMAIL=your-email@example.com
SENDER_PASSWORD=your-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
RECIPIENT_EMAILS=recipient1@example.com,recipient2@example.com
SEND_EMAIL=true

# Data Configuration
LABELED_PLAYERS=596142,621439,669261,583871,666135,607054,571745,543877,456781
URL_FANGRAPHS=https://www.fangraphs.com/guts.aspx?type=cn

# Paths
DATA_DIR=./data
OUTPUT_DIR=./output
LOGO_PATH=./assets/longball-labs.png
```

### Running Locally

1. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Run the script:
   ```
   python script.py
   ```

## Customizing the Report

You can customize the report by modifying the following parts of the script:

- `get_action_items()` and `get_frjs()` functions to change the criteria for identifying these events
- `create_daily_report()` to modify the PDF layout and styling
- `create_definitions_page()` to update the definitions of terms used in the report

## Troubleshooting

If the GitHub Actions workflow fails:

1. Check the workflow run logs in the "Actions" tab
2. Verify that all required secrets are correctly set
3. Ensure the Python dependencies are correctly specified in requirements.txt
4. Check if the Statcast API is returning data as expected
