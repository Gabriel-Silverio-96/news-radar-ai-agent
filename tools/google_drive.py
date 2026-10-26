"""Google Docs report storage using a local desktop OAuth client."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_REPORT_LENGTH = 30_000
REPORTS_FOLDER_ID = "1ws4QxogqmwfljJHBAOVTeg5INe1gAD-Y"
REPORT_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def _get_credentials() -> Credentials:
    """Load or create the user's local OAuth credentials."""
    client_file = Path(
        os.getenv("GOOGLE_OAUTH_CLIENT_FILE", str(PROJECT_ROOT / "credentials.json"))
    ).expanduser()
    token_file = Path(
        os.getenv("GOOGLE_OAUTH_TOKEN_FILE", str(PROJECT_ROOT / "token.json"))
    ).expanduser()

    if not client_file.is_file():
        raise FileNotFoundError(
            f"OAuth client file not found: {client_file}. "
            "Download a Desktop app OAuth client JSON and save it as credentials.json."
        )

    credentials = None
    if token_file.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        credentials = flow.run_local_server(port=0, access_type="offline")

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    try:
        token_file.chmod(0o600)
    except OSError:
        pass
    return credentials


def save_news_report(report_text: str) -> dict[str, Any]:
    """Create a new Google Doc in the configured reports folder.

    Args:
        report_text: Plain-text report content to write to the document.
    Returns:
        The created document ID and URL, or a structured error.
    """
    report_text = report_text.strip()
    if not report_text:
        return {"status": "error", "message": "report_text cannot be empty."}
    if len(report_text) > MAX_REPORT_LENGTH:
        return {
            "status": "error",
            "message": f"report_text must be {MAX_REPORT_LENGTH} characters or fewer.",
        }

    timestamp = datetime.now(REPORT_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")
    title = f"Top news {timestamp}"

    try:
        credentials = _get_credentials()
        drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        docs_service = build("docs", "v1", credentials=credentials, cache_discovery=False)

        metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [REPORTS_FOLDER_ID],
        }
        document = (
            drive_service.files()
            .create(body=metadata, fields="id,name,webViewLink")
            .execute()
        )
        document_id = document["id"]

        try:
            docs_service.documents().batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {"insertText": {"location": {"index": 1}, "text": report_text}}
                    ]
                },
            ).execute()
        except Exception as error:
            return {
                "status": "partial",
                "document_id": document_id,
                "title": document.get("name", title),
                "url": document.get(
                    "webViewLink", f"https://docs.google.com/document/d/{document_id}/edit"
                ),
                "message": f"The document was created, but its content could not be written: {error}",
            }

        return {
            "status": "success",
            "document_id": document_id,
            "title": document.get("name", title),
            "url": document.get(
                "webViewLink", f"https://docs.google.com/document/d/{document_id}/edit"
            ),
        }
    except FileNotFoundError as error:
        return {"status": "error", "message": str(error)}
    except HttpError as error:
        return {
            "status": "error",
            "message": f"Google Workspace API request failed: {error.reason or error}",
        }
    except Exception as error:
        return {
            "status": "error",
            "message": f"Could not create the Google Docs report: {error}",
        }
