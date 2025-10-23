<!-- cspell:words venv asyncio PyPDF2 ADK gcloud shortlist shortlisting -->

# AI-Powered Resume Shortlisting Agent

An agent that automates the initial screening of candidates for a specific job role. It reads applications from Google Sheets, parses resumes from Google Drive, and produces a shortlist of top candidates using LLMs via the Google Agent Development Kit (ADK).

## Overview

- Automates data extraction from a Google Sheet (personal details, achievements, resume link).
- Parses PDF resumes stored in Google Drive.
- Filters candidates by target role and evaluates resume strength and achievements.
- Outputs a structured shortlist with key details and rationale.

## Features

- Google Workspace integration (Sheets and Drive).
- Customizable filtering via prompt instructions.
- Scalable for large application volumes.
- Extensible with additional tools and refined instructions.

## How It Works

1. Read the Google Sheet using the `get_sheet_values_from_link` tool.
2. Iterate each candidate row.
3. Extract the resume Drive link and read text via `read_pdf_content`.
4. Filter by “Role Interested in” matching the user-specified role.
5. Evaluate candidate strength (e.g., concise resume, clear sections, validated achievements).
6. Generate a structured shortlist (name, email, role, key achievements, summary).  
    If no candidates meet criteria, the agent reports none found.

## Getting Started

### Prerequisites

- Python 3.7+
- Google Cloud SDK installed and authenticated
- Application Default Credentials (ADC) for Google Workspace APIs
- Python libraries:
  - google-api-python-client
  - google-auth

### Installation

- Authenticate with Google Cloud:
```bash
gcloud auth application-default login
```

- Install required libraries:
```bash
pip install google-api-python-client google-auth
```
## Usage

Run the agent by executing `main_agent/agent.py` and interacting with `root_agent`. Provide the Google Sheet link and the target role.

```python
# Conceptual example
from main_agent.agent import root_agent
import asyncio

async def main():
     sheet_link = "YOUR_GOOGLE_SHEET_LINK"
     role = "Software Engineer"
     prompt = f"Please shortlist candidates for the role of {role} from the following sheet: {sheet_link}"
     response = await root_agent.send(prompt)
     print(response)

asyncio.run(main())
```

## Customization

- Modify the instruction prompt in `main_agent/agent.py` to adjust filtering logic and evaluation criteria.
- Add tools or refine steps to extend capabilities as needed.