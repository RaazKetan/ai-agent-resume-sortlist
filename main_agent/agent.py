import os
import io
import asyncio
from typing import Dict, Any
import re

# --- Google Cloud & API Imports ---
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# --- PDF Processing ---
import PyPDF2

# --- Agent Development Kit (ADK) Imports ---
from google.adk.agents import Agent
from google.adk.tools import FunctionTool


# --- 1. Authentication Helpers ---
def get_sheet_values_from_link(sheet_url: str, range_name: str = "A:H"):
    """
    Given a Google Sheet link, extracts its spreadsheet ID and fetches rows.
    By default, reads columns A–H (schema of your form).
    """
    # Extract spreadsheetId from the URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        raise ValueError("Invalid Google Sheet link provided.")
    spreadsheet_id = match.group(1)

    creds, _ = google.auth.default()
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    # ✅ don't hardcode "Sheet1!" → just request A:H from the first sheet
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
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
    """Returns a Drive API service object using ADC."""
    creds, _ = google.auth.default()
    service = build('drive', 'v3', credentials=creds)
    return service


# --- 2. Tool Functions ---

def read_pdf_content(file_id: str) -> Dict[str, Any]:
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
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        return {"status": "success", "text_content": text}
    except HttpError as e:
        return {"status": "error", "error_message": f"An API error occurred: {e}"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


# --- 3. Wrap as Tools ---

sheet_tool = FunctionTool(func=get_sheet_values_from_link)
pdf_tool = FunctionTool(func=read_pdf_content)


# --- 4. Define the Agent ---

root_agent = Agent(
    name="resume_shortlist_agent",
    model="gemini-2.5-pro",
    description="Shortlists strong candidates from resumes (PDFs linked in a Google Sheet) for specific roles.",
    instruction="""
    You are an intelligent recruitment assistant.
    Your task is to shortlist candidates from a Google Sheet and their linked resumes.
    
    The Google Sheet contains the following columns:
    - Timestamp
    - Full Name
    - Email Address
    - Phone Number
    - Upload your updated resume (Drive Link)
    - Achievements worth mentioning (in bullet points)
    - Role Interested in
    - Why Google should hire you (in 3rd person, max 150 words)

    Workflow:
    1. Use the `get_sheet_values_from_link` tool with the sheet link provided by the user.
    2. For each row:
        - Extract candidate details (name, email, phone, achievements, role).
        - From the resume link column, extract the Google Drive file ID.
        - Use `read_pdf_content` tool to extract resume text.
    3. Filtering rules:
        - Only consider candidates whose "Role Interested in" matches the role mentioned in the user’s query.
        - Resumes should be strong, ideally 1 page, with clear sections on **skills, projects, and achievements**.
        - Use the "Achievements worth mentioning" column in the sheet to further validate candidate strength.
        - Discard candidates with weak or irrelevant achievements or poorly structured resumes.
    4. Output:
        - Provide a **shortlist of strong candidates** in structured format:
            - Full Name
            - Email
            - Role Interested
            - Key Achievements (from sheet + resume)
            - Resume Strength Summary
    5. If no candidate qualifies, clearly say "No strong candidates found matching the role."

    Always prioritize clarity, conciseness, and relevance in your evaluation.
    """,
    tools=[sheet_tool, pdf_tool]
)
