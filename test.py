import feedparser
import sqlite3
import time
from datetime import datetime, timedelta

# List of feeds to process
FEEDS = [
    "https://www.darkreading.com/rss.xml",
    "https://www.cisa.gov/news.xml",
    "https://www.bleepingcomputer.com/feed/"
]

DB_FILE = "feeds.db"  # SQLite database file


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
    published_ts = None

    # Use published_parsed if available, else updated_parsed
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_ts = time.mktime(entry.published_parsed)
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        published_ts = time.mktime(entry.updated_parsed)

    # If we can't parse a time, treat as not recent
    if published_ts is None:
        return False

    published_dt = datetime.fromtimestamp(published_ts)
    cutoff = datetime.now() - timedelta(hours=24)
    return published_dt > cutoff


def fetch_and_filter_rss(rss_url, limit=5):
    feed = feedparser.parse(rss_url)
    if feed.bozo:
        print(f"[!] Error parsing RSS feed: {rss_url}")
        return []

    new_entries = []
    for entry in feed.entries:
        if not is_recent(entry):
            # Skip articles older than 24 hours
            continue

        # Use 'guid' if present; otherwise fallback to 'link'
        raw_guid = entry.get("guid") or entry.get("link")
        if not raw_guid:
            # If there's no unique identifier, skip
            continue

        # To ensure uniqueness across multiple feeds,
        # prefix the GUID with the feed URL.
        # Example: "https://www.darkreading.com/rss.xml||<GUID>"
        combined_guid = f"{rss_url}||{raw_guid}"

        # Check if already processed
        if not has_been_processed(combined_guid):
            new_entries.append((combined_guid, entry))
            if len(new_entries) >= limit:
                break

    return new_entries


def main():
    setup_database()

    # For each feed, fetch up to 5 new entries from the last 24 hours
    all_new_entries = []

    for feed_url in FEEDS:
        # Returns a list of (combined_guid, entry) tuples
        entries = fetch_and_filter_rss(feed_url, limit=5)
        all_new_entries.extend(entries)

    if not all_new_entries:
        print("No new articles from the last 24 hours.")
        return

    # Process the newly found entries
    for idx, (combined_guid, entry) in enumerate(all_new_entries, start=1):
        title = entry.get("title", "No title")
        link = entry.get("link", "No link")

        # Print or send to Discord, etc.
        print(f"\n--- New Article {idx} ---")
        print(f"Feed:   {combined_guid.split('||')[0]}")
        print(f"Title:  {title}")
        print(f"Link:   {link}")

        # If you need images
        if hasattr(entry, "media_content"):
            media_url = entry.media_content[0].get("url")
            if media_url:
                print(f"Media: {media_url}")
        elif hasattr(entry, "media_thumbnail"):
            thumb_url = entry.media_thumbnail[0].get("url")
            if thumb_url:
                print(f"Thumbnail: {thumb_url}")

        # Mark as processed so we don't send it again
        mark_as_processed(combined_guid)


if __name__ == "__main__":
    main()
