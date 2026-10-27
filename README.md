<p align="center">
<img alt="Background news radar ai agent" src="https://github.com/user-attachments/assets/66b0bbc2-94c0-47a2-989b-6c78def51ebf"/>
</p>

<h1 align="center">
 News Radar AI Agent
</h1>

News Radar is an AI agent that follows international news and turns what it finds into a clear briefing. It uses Gemini to understand the stories, checks headlines and can save the finished report as a new Google Doc.

The agent can read selected articles for extra context and remember which headlines it has seen before. It creates new reports in the Google Drive folder you choose.

## Requirements

- Python 3.12 and a working `pip` installation.
- A Gemini API key for a Google project that is allowed to use the Gemini API.
- A Google OAuth Desktop application client for Google Drive and Google Docs access.

## Installation

From the project root, create and activate a virtual environment, then install the dependencies:

```bash
python3.12 -m venv .venv
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
LANGFUSE_PUBLIC_KEY=YOUR_LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY=YOUR_LANGFUSE_SECRET_KEY
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENVIRONMENT=development
```

### Langfuse Observability

The agent uses Langfuse to record traces of Google ADK runs. Traces help you inspect model calls, tool calls, timing, and errors.

1. Create a Langfuse project and copy its Public Key and Secret Key from the project's API keys settings.
2. Add the Langfuse variables in the `.env` example above. Set `LANGFUSE_BASE_URL` to the URL for your Langfuse region or self-hosted instance.
3. Run the agent with `./run.sh`.
4. Open the project in Langfuse and select **Traces** to review the agent run and its steps.

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
