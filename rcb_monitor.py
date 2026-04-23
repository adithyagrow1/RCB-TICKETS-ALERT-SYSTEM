"""
RCB Ticket Monitor
==================
Monitors the RCB ticket booking page and sends an instant alert
(WhatsApp / Email / Telegram) the moment tickets go live.

Setup:
  pip install requests playwright apscheduler anthropic twilio python-dotenv
  playwright install chromium
"""

import os
import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from anthropic import Anthropic

# ── Optional: Twilio for WhatsApp/SMS ────────────────────────────────────────
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# ── Optional: Playwright for JS-heavy pages ───────────────────────────────────
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (edit these or put them in a .env file)
# ─────────────────────────────────────────────────────────────────────────────

# The page to watch – BookMyShow / RCB official / Paytm Insider, etc.
TARGET_URL = os.getenv(
    "TARGET_URL",
    "https://shop.royalchallengers.com/ticket"
)

# How often to check (seconds). 120 = every 2 minutes
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Twilio (WhatsApp / SMS) – leave blank to skip
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_WHATSAPP = os.getenv("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886")  # Twilio sandbox
YOUR_WHATSAPP_NUMBER = os.getenv("YOUR_WHATSAPP_NUMBER", "whatsapp:+91XXXXXXXXXX")
YOUR_PHONE_NUMBER    = os.getenv("YOUR_PHONE_NUMBER", "+91XXXXXXXXXX")
TWILIO_FROM_SMS      = os.getenv("TWILIO_FROM_SMS", "")

# Email – leave blank to skip
EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))

# Telegram – leave blank to skip
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# State file – tracks last known ticket status to avoid duplicate alerts
STATE_FILE = Path(os.getenv("STATE_FILE", "rcb_state.json"))

# ─────────────────────────────────────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"tickets_available": False, "last_checked": None, "alert_sent": False}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

# ─────────────────────────────────────────────────────────────────────────────
# PAGE FETCHING
# ─────────────────────────────────────────────────────────────────────────────

def fetch_page_html(url: str) -> str:
    """
    Tries Playwright first (handles JavaScript-rendered pages like BMS).
    Falls back to a plain requests GET if Playwright isn't installed.
    """
    if PLAYWRIGHT_AVAILABLE:
        log.info("Fetching page with Playwright (JS rendering)…")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page.goto(url, wait_until="networkidle", timeout=30_000)
            html = page.content()
            browser.close()
        return html
    else:
        log.info("Fetching page with requests (static HTML)…")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.text

# ─────────────────────────────────────────────────────────────────────────────
# AI ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze_page_with_claude(html: str) -> dict:
    """
    Sends the page HTML to Claude and asks it to determine whether
    RCB tickets are currently available for purchase.

    Returns:
        {
            "tickets_available": bool,
            "confidence": "high" | "medium" | "low",
            "reason": str,
            "match_info": str   # e.g. match name / date if found
        }
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Truncate HTML to avoid hitting token limits – first 15k chars usually
    # contain all the booking buttons and status text
    truncated_html = html[:15_000]

    prompt = f"""You are analyzing an HTML page from a cricket ticket booking website.
Your job is to determine whether RCB (Royal Challengers Bengaluru) IPL tickets 
are currently available for purchase RIGHT NOW.

Look for:
- "Book Now", "Buy Tickets", "Book Tickets" buttons that are ACTIVE (not greyed out)
- Ticket prices listed with a purchase option
- "Available" status next to match listings
- Any open sale window

Do NOT count:
- "Notify Me" buttons (tickets not yet on sale)
- "Sold Out" messages
- Upcoming / waitlist pages
- Disabled or greyed-out buy buttons

Respond ONLY with valid JSON in this exact format:
{{
  "tickets_available": true or false,
  "confidence": "high" or "medium" or "low",
  "reason": "one sentence explanation",
  "match_info": "match name and date if found, else empty string"
}}

HTML to analyze:
{truncated_html}
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    result = json.loads(raw)
    log.info(
        "Claude analysis → available=%s  confidence=%s  reason=%s",
        result.get("tickets_available"),
        result.get("confidence"),
        result.get("reason"),
    )
    return result

# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION CHANNELS
# ─────────────────────────────────────────────────────────────────────────────

def build_message(analysis: dict) -> str:
    match_info = analysis.get("match_info") or "RCB match"
    return (
        f"🚨 RCB TICKETS ARE LIVE! 🏏\n\n"
        f"Match: {match_info}\n"
        f"Book now → {TARGET_URL}\n\n"
        f"Hurry – they sell out fast! 🔥"
    )

def send_whatsapp(message: str):
    if not (TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and YOUR_WHATSAPP_NUMBER):
        log.warning("WhatsApp not configured, skipping.")
        return
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_WHATSAPP,
            to=YOUR_WHATSAPP_NUMBER,
        )
        log.info("WhatsApp sent! SID: %s", msg.sid)
    except Exception as e:
        log.error("WhatsApp failed: %s", e)

def send_sms(message: str):
    if not (TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_FROM_SMS and YOUR_PHONE_NUMBER):
        log.warning("SMS not configured, skipping.")
        return
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_SMS,
            to=YOUR_PHONE_NUMBER,
        )
        log.info("SMS sent! SID: %s", msg.sid)
    except Exception as e:
        log.error("SMS failed: %s", e)

def send_email(message: str):
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER):
        log.warning("Email not configured, skipping.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 RCB Tickets Are LIVE – Book Now!"
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        log.info("Email sent to %s", EMAIL_RECEIVER)
    except Exception as e:
        log.error("Email failed: %s", e)

def send_telegram(message: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        log.warning("Telegram not configured, skipping.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Telegram message sent!")
    except Exception as e:
        log.error("Telegram failed: %s", e)

def fire_all_alerts(analysis: dict):
    message = build_message(analysis)
    log.info("🚨 Firing all alerts!")
    send_whatsapp(message)
    send_sms(message)
    send_email(message)
    send_telegram(message)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHECK LOOP
# ─────────────────────────────────────────────────────────────────────────────

def check_tickets():
    log.info("─" * 60)
    log.info("Checking tickets at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    state = load_state()

    try:
        html    = fetch_page_html(TARGET_URL)
        analysis = analyze_page_with_claude(html)
    except Exception as e:
        log.error("Check failed: %s", e)
        return

    tickets_now = analysis.get("tickets_available", False)
    was_available = state.get("tickets_available", False)
    alert_already_sent = state.get("alert_sent", False)

    state["last_checked"] = datetime.now().isoformat()
    state["tickets_available"] = tickets_now
    state["last_analysis"] = analysis

    # Only alert on the FIRST detection (state change: False → True)
    if tickets_now and not was_available and not alert_already_sent:
        log.info("🎉 TICKETS JUST WENT LIVE!")
        fire_all_alerts(analysis)
        state["alert_sent"] = True
        state["alert_time"] = datetime.now().isoformat()

    elif tickets_now and alert_already_sent:
        log.info("Tickets still live – alert already sent, not repeating.")

    elif not tickets_now:
        log.info("No tickets available yet. Will check again in %ds.", CHECK_INTERVAL_SECONDS)
        # Reset alert flag so we catch the next sale window
        state["alert_sent"] = False

    save_state(state)

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ERROR: Set ANTHROPIC_API_KEY in your .env file.")

    log.info("RCB Ticket Monitor started.")
    log.info("Watching: %s", TARGET_URL)
    log.info("Check interval: %d seconds", CHECK_INTERVAL_SECONDS)

    # Run once immediately, then on schedule
    check_tickets()

    scheduler = BlockingScheduler()
    scheduler.add_job(check_tickets, "interval", seconds=CHECK_INTERVAL_SECONDS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Monitor stopped.")
