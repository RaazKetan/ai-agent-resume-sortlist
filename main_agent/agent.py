import io
import re
import asyncio
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2

# --- ADK imports ---
from google.adk.agents import Agent
from google.adk.tools import FunctionTool


# --- 1. Authentication Helpers ---
def get_sheet_values_from_link(sheet_url: str, range_name: str = "A:H"):
    """
    Given a Google Sheet link, extracts its spreadsheet ID and fetches rows.
    By default, reads columns A–H.
    """
    # Extract spreadsheetId from the URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        raise ValueError("Invalid Google Sheet link provided.")
    spreadsheet_id = match.group(1)

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    service = build("sheets", "v4", credentials=creds)

    # ✅ Get the first sheet/tab name dynamically
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_name = metadata["sheets"][0]["properties"]["title"]

    # If caller already provided a sheet-qualified range (contains '!'), use it as-is
    if "!" in range_name:
        final_range = range_name
    else:
        final_range = f"{sheet_name}!{range_name}"

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=final_range
    ).execute()

    return result.get("values", [])


def extract_drive_id(url: str) -> str:
    """Extracts the Google Drive file ID from a shared link."""
    patterns = [
        r"/d/([a-zA-Z0-9_-]+)",   # matches /d/<id>/
        r"id=([a-zA-Z0-9_-]+)"    # matches id=<id>
    ]
    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)
    return None


def get_drive_service():
    """Returns a Drive API service object using ADC (gcloud auth login)."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build('drive', 'v3', credentials=creds)


# --- 2. PDF Reader Tool ---
def read_pdf_content(file_id: str):
    """
    Reads the text content of a single PDF file from Google Drive using its file ID.
    Returns extracted text.
    """
    print(f"--- Tool: Calling read_pdf_content for file_id: {file_id} ---")
    try:
        drive_service = get_drive_service()
        request = drive_service.files().get_media(fileId=file_id)
        file_handle = io.BytesIO()
        downloader = MediaIoBaseDownload(file_handle, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_handle.seek(0)
        reader = PyPDF2.PdfReader(file_handle)
        text = "".join([page.extract_text() or "" for page in reader.pages])

        return {"status": "success", "text_content": text}
    except HttpError as e:
        # 🚨 Instead of blocking, just return a skip marker
        return {"status": "skip", "error_message": f"Cannot access file {file_id}: {e}"}
    except Exception as e:
        return {"status": "skip", "error_message": str(e)}


# --- 3. Register Tools ---
sheet_tool = FunctionTool(func=get_sheet_values_from_link)
pdf_tool = FunctionTool(func=read_pdf_content)


# --- 4. Define the Agent ---
root_agent = Agent(
    name="resume_shortlist_agent",
    model="gemini-2.5-pro",
    description="Shortlists strong candidates from resumes (PDFs linked in a Google Sheet).",
   instruction="""
You are a recruitment assistant.
Task: shortlist candidates from a Google Sheet and their linked resumes.

Rules:
1. Use `get_sheet_values_from_link` to read rows.
2. For each row:
   - Extract candidate details.
   - From the resume link column, extract Drive file ID.
   - Use `read_pdf_content` to extract resume text.
   - ⚠️ If the resume is not accessible, SKIP that candidate and continue.
3. Apply filtering rules:
   - Only consider candidates matching the role the user asks for.
   - Prefer resumes with clear **skills, projects, achievements**.
   - Cross-check achievements from the sheet.
4. Output a shortlist with:
   - Full Name
   - Email
   - Role Interested
   - Key Achievements
   - Resume Strength Summary
   - (If skipped, mark candidate as "Resume inaccessible")
""",
    tools=[sheet_tool, pdf_tool]
)

