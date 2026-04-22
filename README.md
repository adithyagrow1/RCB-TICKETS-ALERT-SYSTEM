# RCB Ticket Monitor 🏏

Automatically monitors the RCB ticket booking page and sends you an instant
alert the moment tickets go on sale — via WhatsApp, SMS, Email, or Telegram.

---

## How it works

1. A scheduler wakes up every 2 minutes (configurable)
2. It fetches the booking page HTML (using Playwright for JS-rendered pages)
3. Claude AI reads the page and decides if tickets are actually on sale
4. If tickets just went live → fires all your configured alerts instantly
5. Saves state so you only get ONE alert per sale window (no spam)

---

## Setup (5 minutes)

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure your .env

```bash
cp .env.example .env
# Open .env and fill in your keys
```

**Required:**
- `ANTHROPIC_API_KEY` — get from https://console.anthropic.com

**Pick at least one notification channel:**

| Channel  | What you need |
|----------|--------------|
| WhatsApp | Free Twilio account + sandbox setup |
| SMS      | Twilio account + a purchased phone number |
| Email    | Gmail + App Password |
| Telegram | BotFather bot token + your chat ID |

### 3. Run it

```bash
python rcb_monitor.py
```

Leave it running in a terminal, or deploy it to a server / Raspberry Pi.

---

## Notification channel setup

### WhatsApp (easiest free option)
1. Sign up at https://www.twilio.com (free trial)
2. Go to Messaging → Try it Out → Send a WhatsApp Message
3. Follow the sandbox setup (send a WhatsApp message to activate)
4. Copy your Account SID and Auth Token into `.env`

### Telegram (simplest to set up)
1. Open Telegram → search for `@BotFather` → `/newbot`
2. Copy the bot token into `.env`
3. Start a chat with your new bot
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Copy your `chat_id` from the response into `.env`

### Email (Gmail)
1. Go to https://myaccount.google.com/apppasswords
2. Generate an App Password for "Mail"
3. Use that password (not your Gmail password) in `.env`

---

## Changing the page to monitor

Edit `TARGET_URL` in `.env` to point to whichever booking page you want:

```
# BookMyShow (most common for IPL)
TARGET_URL=https://www.bookmyshow.com/sports/royal-challengers-bengaluru

# Paytm Insider
TARGET_URL=https://insider.in/sports/cricket

# RCB official site
TARGET_URL=https://www.royalchallengers.com/tickets
```

---

## Running 24/7 (Linux/Mac)

Use `nohup` to keep it running after you close the terminal:

```bash
nohup python rcb_monitor.py > rcb.log 2>&1 &
```

Or use `screen`:
```bash
screen -S rcb
python rcb_monitor.py
# Press Ctrl+A then D to detach
```

Or deploy free to a cloud VM (AWS EC2 free tier, Google Cloud, Railway, etc.)

---

## State file

The monitor saves `rcb_state.json` with the last known status:
```json
{
  "tickets_available": false,
  "last_checked": "2026-04-21T14:30:00",
  "alert_sent": false
}
```

Delete this file to reset the alert state.
