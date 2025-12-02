# Telegram Economic News Bot (Scraper)

Telegram bot that scrapes fresh business/markets headlines from multiple sources and sends them to a Telegram chat/channel.
It keeps a local cache (`sent_urls.json`) to avoid re-sending the same links.

## Features
- Scrapes headlines from multiple sources
- Sends up to N news per round (anti-spam)
- Deduplication + persistent cache
- Configurable interval and request timeout

## Tech Stack
Python • aiogram • requests • BeautifulSoup • python-dotenv

## Setup
### 1) Create virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

#Install dependencies
pip install -r requirements.txt

Create .env

Copy .env.example to .env and fill:

TOKEN — your Telegram bot token

CHAT_ID — target chat/channel id

# Windows:
copy .env.example .env
# Linux/Mac:
cp .env.example .env

Run
python bot.py

Notes

Do not commit .env or tokens.

Some sources may block scraping or change HTML; selectors may need adjustments.


