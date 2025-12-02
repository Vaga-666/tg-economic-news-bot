import os
import json
import asyncio
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────
TOKEN = os.getenv("TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
if not TOKEN or not CHAT_ID:
    raise RuntimeError("Fill TOKEN and CHAT_ID in .env (no quotes)")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)
log = logging.getLogger("news-bot")

SITES = [
    "https://www.bbc.com/news/business",
    "https://www.cnbc.com/world/",
    "https://www.reuters.com/markets/",
    "https://www.bloomberg.com/markets",
    "https://www.ft.com/stream/4d2a6a4c-fd57-40d2-b619-4bc8ef235632",
]
SEND_LIMIT_PER_ROUND = 5           # сколько новостей слать за цикл
ROUND_INTERVAL_SEC = 300           # пауза между циклами (5 минут)
REQ_TIMEOUT_SEC = 15               # таймаут http-запроса
CACHE_FILE = Path("sent_urls.json")

HDRS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ── Cache helpers ──────────────────────────────
def load_cache() -> set:
    if CACHE_FILE.exists():
        try:
            return set(json.loads(CACHE_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()

def save_cache(cache: set) -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps(list(cache), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning(f"Cache save error: {e}")

# ── Scraping (requests + bs4) ─────────────────
def parse_site_requests(url: str) -> list[dict]:
    out: list[dict] = []
    try:
        r = requests.get(url, headers=HDRS, timeout=REQ_TIMEOUT_SEC)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # На большинстве из этих сайтов заголовки лежат в h1/h2/h3 > a
        for a in soup.select("h1 a, h2 a, h3 a"):
            title = (a.get_text(strip=True) or "")[:300]
            href = (a.get("href") or "").strip()
            if not title or not href:
                continue
            out.append({"title": title, "link": urljoin(url, href)})

    except Exception as e:
        log.warning(f"[requests] {url}: {e}")
    return out

async def scrape_all_sites() -> list[dict]:
    all_news: list[dict] = []
    for site in SITES:
        all_news.extend(parse_site_requests(site))
        await asyncio.sleep(0.5)  # мягкий троттлинг
    return all_news

# ── Bot logic ──────────────────────────────────
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    text = (
        "👋 Hello!\n\n"
        "I am a bot that delivers the latest *economic news* directly to Telegram.\n"
        "Every few minutes I will collect fresh headlines from sources like BBC, Reuters, Bloomberg, and others, "
        "and send them here.\n\n"
        "Stay tuned 📈📊"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

    # запускаем фоновую задачу рассылки (одну на процесс)
    if not getattr(dp, "_news_task", None):
        dp._news_task = asyncio.create_task(news_loop())

async def send_batch(news: list[dict], cache: set) -> int:
    sent = 0
    for art in news:
        if sent >= SEND_LIMIT_PER_ROUND:
            break
        link = art["link"]
        if link in cache:
            continue
        text = f"{art['title']}\n{link}"
        try:
            await bot.send_message(chat_id=CHAT_ID, text=text)
            sent += 1
            cache.add(link)
            await asyncio.sleep(1.0)  # не спамим быстро
        except Exception as e:
            log.warning(f"Send error: {e}")
            await asyncio.sleep(2.0)
    return sent

async def news_loop():
    cache = load_cache()
    while True:
        news = await scrape_all_sites()

        # дедуп в рамках раунда
        uniq, seen = [], set()
        for n in news:
            key = (n["title"], n["link"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(n)

        sent = await send_batch(uniq, cache)
        if sent == 0:
            try:
                await bot.send_message(chat_id=CHAT_ID, text="No fresh news right now.")
            except Exception as e:
                log.warning(f"Notify error: {e}")

        save_cache(cache)
        await asyncio.sleep(ROUND_INTERVAL_SEC)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")
