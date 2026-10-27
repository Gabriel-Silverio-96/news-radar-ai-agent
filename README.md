# News Radar AI Agent

News Radar is an AI agent that follows international news and turns what it finds into a clear briefing. It uses Gemini to understand the stories, checks headlines and can save the finished report as a new Google Doc.

The agent can read selected articles for extra context and remember which headlines it has seen before. It creates new reports in the Google Drive folder you choose.

## Requirements

- Python 3 and a working `pip` installation.
- A Gemini API key for a Google project that is allowed to use the Gemini API.
- A Google OAuth Desktop application client for Google Drive and Google Docs access.

## Installation

From the project root, create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root. Do not commit it:

```ini
GOOGLE_GENAI_USE_ENTERPRISE=FALSE
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
GOOGLE_DRIVE_REPORTS_FOLDER_ID=YOUR_DRIVE_FOLDER_ID
```

### Google Drive OAuth

1. In Google Cloud Console, enable the Google Drive API and Google Docs API for the project used by the OAuth client.
2. Configure the OAuth consent screen and add authorized test users if the app is in testing mode.
3. Create an OAuth client ID for a Desktop application.
4. Save the downloaded client JSON in the project root as `credentials.json`.
5. On the first successful Drive save, complete the browser authorization. The application stores the resulting OAuth token in `token.json`.

## Run the full routine

Make the script executable once, then run it from the project root:

```bash
chmod +x run.sh
./run.sh
```
