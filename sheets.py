import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_HEADERS = [
    "Date",
    "Time",
    "Platform",
    "Creator",
    "Primary Category",
    "All Categories",
    "Summary",
    "Sentiment",
    "Sentiment Confidence",
    "Bias Detected",
    "Misinformation Score",
    "Claims Verified",
    "Claims Partly True",
    "Claims Opinion",
    "Claims Total",
    "Topics",
    "Key Points Count",
    "Conclusion",
    "URL"
]


def get_sheet():
    """Authenticate and return the Google Sheet."""
    creds = Credentials.from_service_account_file(
        "google_credentials.json",
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    spreadsheet = client.open_by_key(sheet_id)

    # Use first sheet
    return spreadsheet.sheet1


def setup_headers(sheet):
    """Add headers to the sheet if it's empty."""
    existing = sheet.row_values(1)
    if not existing or existing[0] != "Date":
        sheet.insert_row(SHEET_HEADERS, 1)

        # Format header row
        sheet.format("A1:S1", {
            "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True
            },
            "horizontalAlignment": "CENTER"
        })
        print("✅ Headers added to Google Sheet")


def save_to_sheets(analysis: dict, meta: dict) -> bool:
    """
    Save a processed video record to Google Sheets.
    analysis = output from analyzer.py
    meta = {url, platform, creator, title}
    """
    print("📊 Saving to Google Sheets...")

    try:
        sheet = get_sheet()
        setup_headers(sheet)

        now = datetime.now()
        topics_str = ", ".join(analysis.get("topics", []))
        categories_str = ", ".join(analysis.get("categories", []))

        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%I:%M %p"),
            meta.get("platform", "Unknown"),
            meta.get("creator", "Unknown"),
            analysis.get("primary_category", "Uncategorized"),
            categories_str,
            analysis.get("summary", ""),
            analysis.get("sentiment", ""),
            analysis.get("sentiment_confidence", ""),
            analysis.get("bias_detected", "None"),
            analysis.get("misinformation_score", 0),
            analysis.get("claims_verified", 0),
            analysis.get("claims_partly_true", 0),
            analysis.get("claims_opinion", 0),
            analysis.get("claims_total", 0),
            topics_str,
            len(analysis.get("key_points", [])),
            analysis.get("conclusion", ""),
            meta.get("url", "")
        ]

        sheet.append_row(row)

        # Color code misinformation score
        last_row = len(sheet.get_all_values())
        misinfo = analysis.get("misinformation_score", 0)

        if misinfo < 0.3:
            bg_color = {"red": 0.85, "green": 0.95, "blue": 0.85}  # Green
        elif misinfo < 0.6:
            bg_color = {"red": 1.0, "green": 0.95, "blue": 0.8}    # Yellow
        else:
            bg_color = {"red": 1.0, "green": 0.85, "blue": 0.85}   # Red

        sheet.format(f"A{last_row}:S{last_row}", {
            "backgroundColor": bg_color
        })

        print(f"✅ Saved to Google Sheets — row {last_row}")
        return True

    except Exception as e:
        print(f"❌ Google Sheets save failed: {e}")
        return False


# Test sheets directly
if __name__ == "__main__":
    print("🧪 Testing Google Sheets connection...")

    # Sample data to test with
    test_analysis = {
        "summary": "Test video about S&P 500 options expiry with bullish flow.",
        "key_points": [
            {"point": "Test claim", "verdict": "VERIFIED", "confidence": 0.9, "context": "test", "source_note": "test"}
        ],
        "conclusion": "This is a test entry from Nexus setup.",
        "sentiment": "Bullish",
        "sentiment_confidence": "High",
        "emotional_framing": "Confident",
        "bias_detected": "None",
        "misinformation_score": 0.05,
        "claims_verified": 1,
        "claims_partly_true": 0,
        "claims_opinion": 0,
        "claims_total": 1,
        "categories": ["Stock Market", "Trading Strategies"],
        "primary_category": "Stock Market",
        "topics": ["S&P 500", "options expiry", "delta flow"]
    }

    test_meta = {
        "url": "https://tiktok.com/test",
        "platform": "TikTok",
        "creator": "test_creator",
        "title": "Test Video"
    }

    success = save_to_sheets(test_analysis, test_meta)

    if success:
        print("\n✅ Google Sheets integration working!")
        print("Check your Nexus Intelligence sheet — a test row should be there.")
    else:
        print("\n❌ Google Sheets integration failed — check error above.")
