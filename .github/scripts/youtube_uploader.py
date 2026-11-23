import os
import sys
import json
import urllib.request
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_ID = os.getenv("YT_CLIENT_ID") or os.getenv("PAYLOAD_CLIENT_ID") or ""
CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET") or os.getenv("PAYLOAD_CLIENT_SECRET") or ""
REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN") or os.getenv("PAYLOAD_REFRESH_TOKEN") or ""
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("PAYLOAD_BOT_TOKEN") or ""
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("PAYLOAD_CHAT_ID") or "8387155304"

def send_telegram(text: str, chat_id: str, reply_markup: dict = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram send error:", e)

def upload_video_to_youtube(video_path: str, title: str, description: str, tags: list):
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:95],
            "description": description,
            "tags": tags,
            "categoryId": "26" # Howto & Style
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=1024*1024*5, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response.get("id")
    print(f"Video uploaded successfully! ID: {video_id}")
    return video_id

def main():
    video_url = os.getenv("VIDEO_URL") or os.getenv("PAYLOAD_VIDEO_URL") or os.getenv("INPUT_VIDEO_URL") or ""
    title = os.getenv("VIDEO_TITLE") or os.getenv("PAYLOAD_TITLE") or os.getenv("INPUT_TITLE") or "Acidity & Seene Ki Jalan Ka Permanent Ilaaj #Shorts"
    chat_id = os.getenv("CHAT_ID") or os.getenv("PAYLOAD_CHAT_ID") or CHAT_ID

    if not video_url:
        print("Error: No VIDEO_URL provided.")
        send_telegram("❌ YouTube Publish Failed: No video URL received.", chat_id)
        sys.exit(1)

    print(f"=== Starting YouTube Shorts One-Click Publish ===")
    print(f"Video URL: {video_url}")
    print(f"Title: {title}")

    send_telegram(
        f"⏳ *Publishing to YouTube Shorts...*\n\n"
        f"🎬 *Title:* {title}\n"
        f"📺 *Channel:* Bharati Nature Cure Foundation\n"
        f"🚀 Uploading in background via YouTube Data API v3...",
        chat_id
    )

    # 1. Download video
    local_video = "upload_target.mp4"
    r = requests.get(video_url, stream=True, timeout=60)
    with open(local_video, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    print("Downloaded video. File size:", os.path.getsize(local_video))

    # 2. Formulate metadata
    clean_title = title if "#shorts" in title.lower() else f"{title} #Shorts #HealthTips"
    description = (
        f"🌿 Bharati Nature Cure Foundation, Lucknow 🌿\n\n"
        f"{title}\n\n"
        f"🩺 Natural Naturopathy & Lifestyle Healing Tips.\n\n"
        f"🏥 Foundation: Bharati Nature Cure Foundation, Lucknow\n"
        f"🌐 Official Website: https://www.bharatinaturecure.com\n\n"
        f"⚠️ Disclaimer: Yeh video keval general awareness aur naturopathy education ke liye hai. "
        f"Apni personal health ke liye qualified naturopathy doctor se zaroor consult karein.\n\n"
        f"#shorts #naturopathy #bharatinaturecure #lucknow #health #ayurveda #wellness"
    )
    tags = [
        "naturopathy",
        "bharati nature cure",
        "lucknow",
        "health tips",
        "ayurveda",
        "acidity",
        "healthy lifestyle",
        "shorts"
    ]

    # 3. Upload to YouTube
    video_id = upload_video_to_youtube(local_video, clean_title, description, tags)
    yt_url = f"https://youtube.com/shorts/{video_id}"

    # 4. Notify Telegram with Watch button
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "📺 Watch on YouTube Shorts",
                    "url": yt_url
                }
            ],
            [
                {
                    "text": "🌐 Visit Website",
                    "url": "https://www.bharatinaturecure.com"
                }
            ]
        ]
    }

    send_telegram(
        f"🎉 *Successfully Published to YouTube Shorts!* 🎉\n\n"
        f"🎬 *Title:* {clean_title}\n"
        f"📺 *Channel:* Bharati Nature Cure Foundation\n"
        f"🔗 *Shorts Link:* [Open Shorts]({yt_url})\n\n"
        f"✨ *100% Automated 1-Click Publishing Completed!*",
        chat_id,
        reply_markup=reply_markup
    )
    print("Telegram notification sent with YouTube button!")

if __name__ == "__main__":
    main()
