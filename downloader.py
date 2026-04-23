import yt_dlp
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Folder where audio files are temporarily saved
DOWNLOAD_DIR = "downloads"

# Load ffmpeg path from .env — falls back to system PATH if not set
FFMPEG_PATH = os.getenv("FFMPEG_PATH", None)


def ensure_download_dir():
    """Create downloads folder if it doesn't exist."""
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)


def detect_platform(url: str) -> str:
    """Detect which social media platform the URL is from."""
    url_lower = url.lower()

    if "tiktok.com" in url_lower:
        return "TikTok"
    elif "instagram.com" in url_lower:
        return "Instagram"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "Twitter/X"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "Facebook"
    else:
        return "Unknown"


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name)[:80]


def download_audio(url: str) -> dict:
    """
    Download audio from a social media URL.
    Returns a dict with file path, platform, creator, and title.
    """
    ensure_download_dir()
    platform = detect_platform(url)

    print(f"⬇️  Detected platform: {platform}")
    print(f"⬇️  Downloading audio from: {url}")

    # yt-dlp options — extract audio only, save as mp3
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(uploader)s_%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "postprocessor_args": ["-c:a", "libmp3lame"],
        "prefer_ffmpeg": True,
    }

    # Only set ffmpeg_location if explicitly provided in .env
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Get metadata
            creator = info.get("uploader") or info.get("channel") or "Unknown"
            title = info.get("title") or "Unknown Title"
            video_id = info.get("id") or "unknown"

            # Build the expected output filename
            safe_creator = sanitize_filename(creator)
            filename = f"{safe_creator}_{video_id}.mp3"
            filepath = os.path.join(DOWNLOAD_DIR, filename)

            # Sometimes yt-dlp uses a slightly different name — find the file
            if not os.path.exists(filepath):
                mp3_files = sorted(
                    Path(DOWNLOAD_DIR).glob("*.mp3"),
                    key=os.path.getmtime,
                    reverse=True
                )
                if mp3_files:
                    filepath = str(mp3_files[0])
                else:
                    raise FileNotFoundError("Audio file not found after download.")

            file_size = os.path.getsize(filepath)
            print(f"✅ Audio downloaded: {filepath} ({round(file_size / 1024 / 1024, 2)} MB)")

            return {
                "success": True,
                "filepath": filepath,
                "platform": platform,
                "creator": creator,
                "title": title,
                "video_id": video_id,
                "url": url
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"❌ Download failed: {error_msg}")

        if "Private" in error_msg or "private" in error_msg:
            reason = "Video is private."
        elif "removed" in error_msg or "deleted" in error_msg:
            reason = "Video has been removed."
        elif "age" in error_msg:
            reason = "Video is age-restricted."
        elif "copyright" in error_msg:
            reason = "Video blocked due to copyright."
        else:
            reason = error_msg

        return {
            "success": False,
            "error": reason,
            "platform": platform,
            "url": url
        }

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {
            "success": False,
            "error": str(e),
            "platform": platform,
            "url": url
        }


def cleanup_audio(filepath: str):
    """Delete the audio file after transcription to save disk space."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️  Cleaned up: {filepath}")
    except Exception as e:
        print(f"⚠️  Could not delete file {filepath}: {e}")


# Test the downloader directly
if __name__ == "__main__":
    test_url = input("Enter a video URL to test: ").strip()
    result = download_audio(test_url)

    if result["success"]:
        print("\n✅ Download successful:")
        print(f"   Platform : {result['platform']}")
        print(f"   Creator  : {result['creator']}")
        print(f"   Title    : {result['title']}")
        print(f"   File     : {result['filepath']}")

        cleanup = input("\nDelete test file? (y/n): ").strip().lower()
        if cleanup == "y":
            cleanup_audio(result["filepath"])
    else:
        print(f"\n❌ Download failed: {result['error']}")
