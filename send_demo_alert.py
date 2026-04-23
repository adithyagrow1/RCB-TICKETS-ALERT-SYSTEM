"""
RCB Demo Alert Sender
=====================
Sends a fake "tickets live" notification to Telegram
with yesterday's 4:00 PM timestamp — perfect for a LinkedIn demo screenshot.

Usage:
    python send_demo_alert.py
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8543257717:AAE_kdST6wlNcdZsd6o6Q6Y3PriIVLUTYss")

TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "6496519631")

# Yesterday at 4:00 PM

yesterday = datetime.now() - timedelta(days=1)
alert_time = yesterday.replace(hour=16, minute=0, second=0, microsecond=0)
formatted_time = alert_time.strftime("%d %b %Y, %I:%M %p")  # e.g. 22 Apr 2026, 04:00 PM

message = f"""🚨 *RCB TICKETS ARE LIVE\!* 🏏

📅 *Match:* Royal Challengers Bengaluru vs Punjab Kings
🏟️ *Venue:* M\. Chinnaswamy Stadium, Bengaluru
🕓 *Detected at:* {formatted_time}

🎟️ [Buy now → RCB TICKETS](https://shop.royalchallengers.com/ticket)

⚡ *Monitored by RCB Ticket Alert Bot*
_Powered by Claude AI • Auto\-detected ticket availability_"""

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise SystemExit("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file.")

    print(f"Sending demo alert with timestamp: {formatted_time}")
    result = send_telegram(message)

    if result.get("ok"):
        print("✅ Demo alert sent successfully! Check your Telegram.")
    else:
        print("❌ Something went wrong:", result)
