#!/usr/bin/env python3
"""
Reads morning briefing (already in Spanish), extracts news section,
saves to noticias-es/ and sends to Telegram.
"""

import glob
import json
import os
import re
import urllib.request
from pathlib import Path

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8312127798:AAGObENO59ohY_vWAfcYK0-6bNPUEaNXEv4")
TELEGRAM_CHAT_ID = "8295693189"
OUTPUT_DIR = "/opt/proyectos/noticias-ia/noticias-es"
BRIEFING_DIR = "/home/ubuntu/hermes-notes/news"


def find_briefing_file():
    """Find today's morning briefing file."""
    candidates = sorted(glob.glob(f"{BRIEFING_DIR}/briefing-manana-*.md"), reverse=True)
    for f in candidates[:3]:
        text = Path(f).read_text(encoding="utf-8")
        if "Y en noticias de IA" in text:
            return f, text
    return None, None


def extract_news_section(briefing_text):
    """Extract just the news section from briefing and convert to • format."""
    # Find news section start
    match = re.search(r'Y en noticias de IA y tecnologia:(.*?)Eso es todo por hoy\.', briefing_text, re.DOTALL)
    if not match:
        return None
    
    news_section = match.group(1).strip()
    
    # Split by numbered items (Uno., Dos., etc.)
    items = re.split(r'\n(?=Uno\.|Dos\.|Tres\.|Cuatro\.|Cinco\.|Seis\.|Siete\.|Ocho\.|Nueve\.|Diez\.)', news_section)
    
    result = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        
        # Convert "Uno. Title - content" format to "• Title\n  content" format
        lines = item.split('\n')
        first_line = lines[0]
        
        # Remove "Uno. " etc prefix and add •
        first_line = re.sub(r'^(Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez)\.\s+', '• ', first_line)
        
        # Reconstruct
        if lines[1:]:
            result.append(first_line + '\n' + '\n'.join(lines[1:]))
        else:
            result.append(first_line)
    
    return '\n\n'.join(result) if result else None


def send_telegram(text):
    """Send text to Telegram in chunks."""
    chunks = []
    while len(text) > 4000:
        split_at = text.rfind("\n\n", 0, 4000)
        if split_at == -1:
            split_at = 4000
        chunks.append(text[:split_at])
        text = text[split_at:].strip()
    chunks.append(text)

    for chunk in chunks:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass


def main():
    briefing_file, text = find_briefing_file()
    if not briefing_file:
        print("No briefing file found, skipping")
        return

    basename = os.path.basename(briefing_file)
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', basename)
    if not date_match:
        print(f"Could not extract date from {basename}")
        return
    file_date = date_match.group(1)
    print(f"Using briefing: {briefing_file}")

    news_content = extract_news_section(text)
    if not news_content:
        print("No news section found in briefing")
        return

    # Count items
    item_count = len([l for l in news_content.split('\n\n') if l.strip()])
    print(f"Found {item_count} news items")

    # Save Spanish file
    out_path = f"{OUTPUT_DIR}/noticias-es-{file_date}.md"
    Path(out_path).write_text(news_content, encoding="utf-8")
    print(f"Saved: {out_path}")

    # Send to Telegram
    send_telegram(news_content)
    print(f"Sent to Telegram ({item_count} noticias)")


if __name__ == "__main__":
    main()