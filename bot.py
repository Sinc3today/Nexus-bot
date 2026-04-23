import discord
import os
import asyncio
from dotenv import load_dotenv
from downloader import download_audio, cleanup_audio
from transcriber import transcribe_audio
from analyzer import analyze_transcript, format_discord_report
from sheets import save_to_sheets
from database import init_db, save_video, url_exists

load_dotenv()

# Initialize database on startup
init_db()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Map category names to Discord channel IDs — loaded from .env
CATEGORY_CHANNEL_MAP = {
    "Stock Market":                 int(os.getenv("CH_STOCK_MARKET",          0)),
    "Economics":                    int(os.getenv("CH_ECONOMICS",             0)),
    "World News":                   int(os.getenv("CH_WORLD_NEWS",            0)),
    "AI News & Projects":           int(os.getenv("CH_AI_NEWS",               0)),
    "Business & Entrepreneurship":  int(os.getenv("CH_BUSINESS",             0)),
    "Side Hustles":                 int(os.getenv("CH_SIDE_HUSTLES",          0)),
    "Trading Strategies":           int(os.getenv("CH_TRADING_STRATEGIES",    0)),
    "Philosophy & Self Reflection": int(os.getenv("CH_PHILOSOPHY",           0)),
    "Science & Technology":         int(os.getenv("CH_SCIENCE_TECH",          0)),
    "Uncategorized":                int(os.getenv("CH_UNCATEGORIZED",         0)),
}

NEXUS_CONTROL_ID = int(os.getenv("CH_NEXUS_CONTROL", 0))
NEXUS_LOGS_ID    = int(os.getenv("CH_NEXUS_LOGS",    0))

# Valid URL patterns for supported platforms
SUPPORTED_DOMAINS = [
    "tiktok.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "facebook.com",
    "fb.watch"
]


def is_valid_url(text: str) -> bool:
    """Check if message contains a supported social media URL."""
    return any(domain in text.lower() for domain in SUPPORTED_DOMAINS)


async def send_long_message(channel, text: str):
    """Send a message, splitting into chunks under 1900 chars at newline boundaries."""
    if len(text) <= 1900:
        await channel.send(text)
        return

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 1900:
            if current:
                chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())

    for chunk in chunks:
        if chunk:
            await channel.send(chunk)


async def get_category_channels(guild, categories: list) -> list:
    """Find Discord channels matching the video's categories."""
    channels = []
    for category in categories:
        channel_id = CATEGORY_CHANNEL_MAP.get(category, CATEGORY_CHANNEL_MAP.get("Uncategorized", 0))
        channel = guild.get_channel(channel_id)
        if channel and channel not in channels:
            channels.append(channel)
    if not channels:
        fallback = guild.get_channel(CATEGORY_CHANNEL_MAP.get("Uncategorized", 0))
        if fallback:
            channels.append(fallback)
    return channels


async def post_to_logs(guild, message: str):
    """Post a status message to the nexus-logs channel."""
    logs_channel = guild.get_channel(NEXUS_LOGS_ID)
    if logs_channel:
        await logs_channel.send(message)


async def process_video(url: str, guild, control_channel, force: bool = False):
    """
    Full pipeline: download → transcribe → analyze → save → post to Discord.
    All blocking API calls run in thread executor to keep Discord heartbeat alive.
    """
    # Check for duplicate
    existing = url_exists(url)
    if existing and not force:
        await control_channel.send(
            f"⚠️ **Already processed!**\n"
            f"This URL was processed on `{existing['processed_at'][:10]}`\n"
            f"Category: `{existing['primary_category']}` | "
            f"Sentiment: `{existing['sentiment']}` | "
            f"Misinfo Score: `{existing['misinformation_score']}`\n\n"
            f"Add `!force` to the URL to reprocess it."
        )
        return

    await post_to_logs(guild, f"⚙️ Processing started: {url}")
    loop = asyncio.get_event_loop()

    # Step 1 — Download (blocking — run in executor)
    await control_channel.send("⬇️ Downloading audio...")
    download_result = await loop.run_in_executor(
        None, lambda: download_audio(url)
    )

    if not download_result["success"]:
        error_msg = f"❌ Download failed: {download_result['error']}"
        await control_channel.send(error_msg)
        await post_to_logs(guild, error_msg)
        return

    filepath = download_result["filepath"]
    platform = download_result["platform"]
    creator  = download_result["creator"]
    title    = download_result["title"]

    await control_channel.send(f"✅ Downloaded from {platform} by {creator}")

    # Step 2 — Transcribe (blocking — run in executor)
    await control_channel.send("🎙️ Transcribing audio...")
    transcribe_result = await loop.run_in_executor(
        None, lambda: transcribe_audio(filepath)
    )

    if not transcribe_result["success"]:
        error_msg = f"❌ Transcription failed: {transcribe_result['error']}"
        await control_channel.send(error_msg)
        await post_to_logs(guild, error_msg)
        cleanup_audio(filepath)
        return

    transcript = transcribe_result["transcript"]
    await control_channel.send(f"✅ Transcribed — {transcribe_result['word_count']} words")

    # Step 3 — Analyze (blocking — run in executor)
    await control_channel.send("🤖 Analyzing with Claude AI...")
    analysis = await loop.run_in_executor(
        None, lambda: analyze_transcript(transcript, creator=creator, platform=platform)
    )

    if not analysis.get("success"):
        error_msg = f"❌ Analysis failed: {analysis.get('error')}"
        await control_channel.send(error_msg)
        await post_to_logs(guild, error_msg)
        cleanup_audio(filepath)
        return

    categories = analysis.get("categories", ["Uncategorized"])
    await control_channel.send(f"✅ Analysis complete — Categories: {', '.join(categories)}")

    # Step 4 — Save to database
    meta = {"url": url, "platform": platform, "creator": creator, "title": title}
    video_data = {**analysis, **meta, "transcript": transcript}
    db_id = save_video(video_data)
    await post_to_logs(guild, f"💾 Saved to database — ID: {db_id}")

    # Step 5 — Save to Google Sheets (blocking — run in executor)
    sheets_success = await loop.run_in_executor(
        None, lambda: save_to_sheets(analysis, meta)
    )
    if sheets_success:
        await post_to_logs(guild, f"📊 Saved to Google Sheets")

    # Step 6 — Format and post report to category channels
    report = format_discord_report(analysis, meta)
    category_channels = await get_category_channels(guild, categories)

    for channel in category_channels:
        await send_long_message(channel, report)

    await control_channel.send(
        f"✅ **Done!** Report posted to: {', '.join([f'#{c.name}' for c in category_channels])}"
    )
    await post_to_logs(guild, f"✅ Pipeline complete for: {url}")

    # Cleanup audio file
    cleanup_audio(filepath)


@client.event
async def on_ready():
    print(f"✅ Nexus bot is online as {client.user}")
    print(f"   Connected to {len(client.guilds)} server(s)")
    for guild in client.guilds:
        print(f"   → {guild.name}")


@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Allow !clean command in any channel
    if message.content.strip() == "!clean":
        await control_channel_cleanup(message)
        return

    # All other commands only work in nexus-control
    if message.channel.id != NEXUS_CONTROL_ID:
        return

    content = message.content.strip()

    # Handle !stats command
    if content == "!stats":
        from database import get_stats
        stats = get_stats()
        stats_msg = (
            f"📊 **Nexus Database Stats**\n"
            f"Total videos processed: **{stats['total_videos']}**\n"
            f"Avg misinformation score: **{stats['avg_misinformation_score']}**\n\n"
            f"**By Category:**\n"
        )
        for cat, count in stats.get("by_category", {}).items():
            stats_msg += f"  • {cat}: {count}\n"
        await message.channel.send(stats_msg)
        return

    # Handle !help command
    if content == "!help":
        help_msg = (
            "**🎯 Nexus Commands**\n\n"
            "Paste any social media URL → full intelligence report\n\n"
            "**Supported platforms:**\n"
            "TikTok, Instagram, YouTube, Twitter/X, Facebook\n\n"
            "**Commands:**\n"
            "`!stats` — database statistics\n"
            "`!help` — show this message\n\n"
            "**Force reprocess a duplicate:**\n"
            "Paste the URL followed by `!force`\n"
            "Example: `https://tiktok.com/... !force`"
        )
        await message.channel.send(help_msg)
        return

    # Handle !recategorize command
    if content.startswith("!recategorize"):
        parts = content.split()
        if len(parts) >= 3:
            video_id = parts[1]
            new_category = " ".join(parts[2:]).strip('"')
            await message.channel.send(
                f"📝 Recategorize for ID `{video_id}` to `{new_category}` noted.\n"
                f"Manual DB update — full recategorize coming in a future update."
            )
        else:
            await message.channel.send(
                "Usage: `!recategorize [video_id] \"Category Name\"`"
            )
        return

    # Handle !clean command — deletes all messages in current channel
    if content == "!clean":
        await control_channel_cleanup(message)
        return

    # Process video URL — support !force flag to reprocess duplicates
    if is_valid_url(content):
        force = "!force" in content
        url = content.replace("!force", "").strip()
        if force:
            await message.channel.send("🔄 Force reprocess enabled — bypassing duplicate check...")
        else:
            await message.channel.send("🎯 URL detected — starting Nexus pipeline...")
        await process_video(url, message.guild, message.channel, force=force)
    else:
        await message.channel.send(
            "⚠️ No supported URL detected.\n"
            "Paste a TikTok, Instagram, YouTube, Twitter/X, or Facebook URL.\n"
            "Type `!help` for commands."
        )


async def control_channel_cleanup(message):
    """Delete all messages in the channel where !clean was called."""
    await message.channel.send("🧹 Cleaning up messages...")
    await asyncio.sleep(1)
    deleted = await message.channel.purge(limit=500)
    confirm = await message.channel.send(f"✅ Deleted {len(deleted)} messages.")
    await asyncio.sleep(3)
    await confirm.delete()


# Run the bot
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in .env file")
    else:
        print("🚀 Starting Nexus bot...")
        client.run(token)
