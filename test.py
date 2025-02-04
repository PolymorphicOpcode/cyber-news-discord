import feedparser
import sqlite3
import time
from datetime import datetime, timedelta

DB_FILE = "feeds.db"  # SQLite database file

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
    # Use OR IGNORE in case we ever try to insert a duplicate
    cur.execute("INSERT OR IGNORE INTO processed_articles (guid) VALUES (?)", (guid,))
    conn.commit()
    conn.close()

def is_recent(entry):
    published_ts = None

    # Check published_parsed first, fallback to updated_parsed
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_ts = time.mktime(entry.published_parsed)
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        published_ts = time.mktime(entry.updated_parsed)

    if published_ts is None:
        # If we can't parse a time, treat as not recent (skip)
        return False

    published_dt = datetime.fromtimestamp(published_ts)
    cutoff = datetime.now() - timedelta(hours=24)
    return published_dt > cutoff

def fetch_and_filter_rss(rss_url, limit=5):
    """
    Fetch the RSS feed, return new (unprocessed) entries 
    that are within the last 24 hours, up to 'limit'.
    """
    feed = feedparser.parse(rss_url)
    if feed.bozo:
        print("Error parsing RSS feed. Check the URL or feed validity.")
        return []

    new_entries = []
    for entry in feed.entries:
        if not is_recent(entry):
            # Skip if older than 24 hours
            continue

        # Use 'guid' if present; otherwise fallback to 'link'
        guid = entry.get("guid") or entry.get("link")
        if not guid:
            # If there's no unique identifier at all, skip
            continue

        # Check if already processed
        if not has_been_processed(guid):
            new_entries.append(entry)
            if len(new_entries) >= limit:
                break

    return new_entries

def main():
    # Create the table if it doesn't exist
    setup_database()

    rss_url = "https://www.darkreading.com/rss.xml"
    
    # Fetch new, unseen articles from the last 24 hours (up to 5)
    new_entries = fetch_and_filter_rss(rss_url, limit=5)

    if not new_entries:
        print("No new articles from the last 24 hours.")
        return

    for idx, entry in enumerate(new_entries, start=1):
        title = entry.get("title", "No title")
        link = entry.get("link", "No link")
        guid = entry.get("guid") or link

        # Print or send to Discord, etc.
        print(f"\n--- New Article {idx} ---")
        print(f"Title: {title}")
        print(f"Link:  {link}")

        # Check for media content
        if hasattr(entry, "media_content"):
            media_url = entry.media_content[0].get("url")
            if media_url:
                print(f"Media: {media_url}")
        elif hasattr(entry, "media_thumbnail"):
            thumb_url = entry.media_thumbnail[0].get("url")
            if thumb_url:
                print(f"Thumbnail: {thumb_url}")

        # Mark this article as processed
        mark_as_processed(guid)

if __name__ == "__main__":
    main()