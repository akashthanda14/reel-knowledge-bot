"""
One-time script to add required fields to your Notion database.
Run this once after sharing the database with your integration.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def setup_database():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"

    # First check connection
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 401:
        print("ERROR: Notion token is invalid or the database is not shared with your integration.")
        print()
        print("Fix steps:")
        print("  1. Go to notion.so/my-integrations and confirm your integration exists.")
        print("  2. Open your Notion database → click '...' menu → Connections → Add connection → select your integration.")
        print("  3. Re-run this script.")
        return
    if response.status_code == 404:
        print("ERROR: Database not found. Check NOTION_DATABASE_ID in .env.")
        return
    if response.status_code != 200:
        print(f"ERROR: {response.status_code} — {response.text}")
        return

    db = response.json()
    existing = list(db.get("properties", {}).keys())
    title_parts = db.get("title", [])
    title = "".join(part.get("plain_text", "") for part in title_parts).strip() if isinstance(title_parts, list) else ""
    print(f"Connected to database: {title or DATABASE_ID}")
    print(f"Existing fields: {existing}")

    # Add missing fields
    new_props = {}
    if "Topic" not in existing:
        new_props["Topic"] = {"rich_text": {}}
    if "Subtopic" not in existing:
        new_props["Subtopic"] = {"rich_text": {}}

    if not new_props:
        print("All required fields already exist. Nothing to do.")
        return

    print(f"Adding fields: {list(new_props.keys())}")
    patch = requests.patch(url, headers=HEADERS, json={"properties": new_props})
    if patch.status_code == 200:
        print("Done! Notion database is ready.")
    else:
        print(f"ERROR adding fields: {patch.status_code} — {patch.text}")


if __name__ == "__main__":
    setup_database()
