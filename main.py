import os
import discord
import feedparser
from dotenv import load_dotenv
from discord.ext import tasks

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
RSS_FEED_URL = os.getenv("RSS_FEED_URL")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")

    # Start the periodic RSS fetching task once the bot is ready.
    if not periodic_rss_fetch.is_running():
        periodic_rss_fetch.start()

@client.event
async def on_message(message):
    # Avoid responding to the bot's own messages
    if message.author == client.user:
        return

    # Manual command to fetch RSS immediately
    if message.content.startswith('/fetchRSS'):
        await fetch_and_send_rss(message.channel)


@tasks.loop(minutes=30)
async def periodic_rss_fetch():
    """
    Task that automatically runs every 30 minutes.
    It will fetch the RSS feed and post the results to a specific channel.
    """
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Could not find channel with ID {CHANNEL_ID}. Task will not run.")
        return

    await fetch_and_send_rss(channel)

async def fetch_and_send_rss(channel):
    """
    Fetches the RSS feed and sends each item to the given channel.
    """
    if not RSS_FEED_URL:
        await channel.send("No RSS_FEED_URL is set in .env. Cannot fetch feed.")
        return

    feed = feedparser.parse(RSS_FEED_URL)
    if feed.bozo:
        await channel.send("Failed to parse RSS feed. Check the URL or feed validity.")
        return

    # Send the feed's title
    feed_title = feed.feed.get("title", "Untitled Feed")
    await channel.send(f"**Fetching RSS Feed**: {feed_title}")

    # Limit to the first 5 items
    for entry in feed.entries[:5]:
        title = entry.get("title", "No Title")
        link = entry.get("link", "No Link")
        description = entry.get("description", "No Description")

        message_content = f"**Title**: {title}\n**Link**: {link}\n{description}"
        await channel.send(message_content)

    await channel.send("**Done fetching RSS feed.**")

client.run(TOKEN)