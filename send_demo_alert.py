"""
RCB Demo Alert Sender (Fixed)
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8543257717:AAE_kdST6wlNcdZsd6o6Q6Y3PriIVLUTYss")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "@IplRCBticket")

# Yesterday at 4:00 PM
yesterday = datetime.now() - timedelta(days=1)
alert_time = yesterday.replace(hour=16, minute=0, second=0, microsecond=0)
formatted_time = alert_time.strftime("%d %b %Y, %I:%M %p")

message = (
    "🚨 RCB TICKETS ARE LIVE! 🏏\n\n"
    "📅 Match: Royal Challengers Bengaluru vs Punjab Kings\n"
    "🏟 Venue: M. Chinnaswamy Stadium, Bengaluru\n"
    f"🕓 Detected at: {formatted_time}\n\n"
    "🎟 Book Now: https://shop.royalchallengers.com/ticket\n\n"
    "⚡ Monitored by RCB Ticket Alert Bot\n"
    "Powered by Claude AI | Auto-detected ticket availability"
)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
        },
        timeout=10,
    )
    print("Telegram response:", resp.json())
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise SystemExit("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file.")

    print(f"Sending demo alert with timestamp: {formatted_time}")
    result = send_telegram(message)

    if result.get("ok"):
        print("✅ Demo alert sent! Check your Telegram.")
    else:
        print("❌ Something went wrong:", result)