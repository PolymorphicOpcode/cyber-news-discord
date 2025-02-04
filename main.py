import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv

import feedparser
import sqlite3
import time
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# List of feeds to process
FEEDS = [
    "https://www.darkreading.com/rss.xml",
    "https://www.cisa.gov/news.xml",
    "https://www.bleepingcomputer.com/feed/"
]

DB_FILE = "feeds.db"  # SQLite database file

intents = discord.Intents.none()
client = discord.Client(intents=intents)

# ------------------- Database Functions -------------------
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_articles (
            guid TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def has_been_processed(guid):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM processed_articles WHERE guid = ?", (guid,))
    row = cur.fetchone()
    conn.close()
    return (row is not None)

def mark_as_processed(guid):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO processed_articles (guid) VALUES (?)", (guid,))
    conn.commit()
    conn.close()

# ------------------- Helper Functions -------------------
def is_recent(entry):
    """
    Checks if the article was published (or updated) within the last 24 hours.
    If no publication date is found, returns False.
    """
    published_ts = None

    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_ts = time.mktime(entry.published_parsed)
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        published_ts = time.mktime(entry.updated_parsed)

    if published_ts is None:
        return False

    published_dt = datetime.fromtimestamp(published_ts)
    cutoff = datetime.now() - timedelta(hours=24)
    return published_dt > cutoff

def fetch_and_filter_rss(rss_url, limit=5):
    """
    Fetches up to 'limit' unprocessed articles from the given feed,
    if they are published in the last 24 hours.
    """
    feed = feedparser.parse(rss_url)
    if feed.bozo:
        print(f"[!] Error parsing RSS feed: {rss_url}")
        return []

    new_entries = []
    for entry in feed.entries:
        # Skip if older than 24 hours
        if not is_recent(entry):
            continue

        # Use 'guid' if present; otherwise fallback to 'link'
        raw_guid = entry.get("guid") or entry.get("link")
        if not raw_guid:
            continue

        # Combine feed URL + GUID to ensure uniqueness across multiple feeds
        combined_guid = f"{rss_url}||{raw_guid}"

        if not has_been_processed(combined_guid):
            new_entries.append((combined_guid, entry))
            if len(new_entries) >= limit:
                break

    return new_entries

async def check_feeds_and_send(channel):
    setup_database()

    all_new_entries = []
    for feed_url in FEEDS:
        entries = fetch_and_filter_rss(feed_url, limit=5)
        all_new_entries.extend(entries)

    if not all_new_entries:
        print("No new articles from the last 24 hours.")
        return

    for idx, (combined_guid, entry) in enumerate(all_new_entries, start=1):
        title = entry.get("title", "No title")
        link = entry.get("link", "No link")
        description = entry.get("description", "No description")
        feed_source = combined_guid.split("||")[0]

        # Check for the word "porn" (case-insensitive) in the title
        if "porn" in title.lower():
            print(f"[!] Skipping article with 'porn' in title: {title}")
            # Mark as processed to avoid repeated checks
            mark_as_processed(combined_guid)
            continue

        # Build an embed
        embed = discord.Embed(
            title=title,
            description=description,
            url=link,
            color=0x3498db
        )
        # If you want to set an image or thumbnail, do so here:
        # embed.set_image(url=media_url)

        # Send to Discord
        await channel.send(embed=embed)

        # Mark this article as processed
        mark_as_processed(combined_guid)

# ------------------- Discord Bot Events -------------------
CHANNEL = None

@client.event
async def on_ready():
    global CHANNEL
    print(f"Logged in as {client.user}")

    CHANNEL = await client.fetch_channel(CHANNEL_ID)
    print(f"Fetched channel: {CHANNEL.name}")

    # Start the hourly RSS fetch task (or every minute for testing)
    if not fetch_feeds.is_running():
        fetch_feeds.start()

# ------------------- Discord Tasks -------------------
@tasks.loop(hours=24)  # change to .loop(hours=1) for hourly in production
async def fetch_feeds():
    global CHANNEL
    if CHANNEL is None:
        print(f"[!] Could not find channel with ID {CHANNEL_ID}.")
        return

    await check_feeds_and_send(CHANNEL)

client.run(TOKEN)