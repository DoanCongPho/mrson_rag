import time
import unicodedata

from googleapiclient.discovery import build
from google.oauth2 import service_account
from sqlalchemy.dialects.postgresql import insert

from db.models import Document
from db.session import SessionLocal, check_connection
from config import settings


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = "service_account.json"
ROOT_FOLDER_ID = settings.root_folder_id


def get_drive_client():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def list_folder_recursive(drive, folder_id: str):
    """Yield file dict cho mọi file trong folder + subfolder con."""
    page_token = None
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime)",
            pageToken=page_token,
            pageSize=100,
        ).execute()

        for f in resp.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                yield from list_folder_recursive(drive, f["id"])
            else:
                yield f

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def sync_once(session):
    drive = get_drive_client()
    count = 0

    for f in list_folder_recursive(drive, ROOT_FOLDER_ID):
        name = unicodedata.normalize("NFC", f["name"])
        stmt = insert(Document).values(name=name, url=f.get("webViewLink"))
        stmt = stmt.on_conflict_do_update(
            index_elements=[Document.name],
            set_={"url": stmt.excluded.url},
        )
        session.execute(stmt)
        count += 1

    session.commit()
    print(f"[sync] {count} files upserted")


def run_loop(interval_seconds: int):
    session = SessionLocal()
    try:
        while True:
            try:
                sync_once(session)
            except Exception as e:
                print(f"[sync] error: {e}")
            time.sleep(interval_seconds)
    finally:
        session.close()


def main():
    session = SessionLocal()
    check_connection()
    sync_once(session)
    session.close()


if __name__ == "__main__":
    main()
