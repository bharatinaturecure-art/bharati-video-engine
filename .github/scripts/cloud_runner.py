import os
import sys
import json
import time
import subprocess
import requests
import urllib.request
from voice_studio import build_elevenlabs_quality_audio

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.getenv("CHAT_ID", "8387155304")
INSFORGE_HOST = os.getenv("INSFORGE_HOST", "https://i8vqipie.ap-southeast.insforge.app")
INSFORGE_KEY = os.getenv("INSFORGE_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

def send_telegram(text: str, chat_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram send error:", e)

def send_telegram_video(video_url: str, caption: str, chat_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    payload = json.dumps({
        "chat_id": chat_id,
        "video": video_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram sendVideo error:", e)

def fetch_image_from_query(query: str) -> str:
    try:
        url = "https://serpapi.com/search.json"
        params = {
            "q": query + " high quality photo naturopathy health",
            "tbm": "isch",
            "api_key": SERPAPI_KEY,
            "num": 4
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("images_results", []):
                u = item.get("original")
                if u and u.startswith("http") and not u.endswith(".svg"):
                    return u
    except Exception as e:
        print(f"Error fetching image for '{query}':", e)
    return "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=1080"

def generate_script_and_queries(topic: str, duration_min: int):
    target_words = duration_min * 135
    prompt = f"""You are the chief Naturopathy doctor for Bharati Nature Cure.
Topic: "{topic}"
Target Spoken Duration: {duration_min} minute(s) (~{target_words} words).

Return strict JSON only:
{{
  "title": "Short punchy title under 60 chars with 1 emoji",
  "script_hinglish": "Complete spoken Hinglish script of approx {target_words} words",
  "scene_queries": [
    "search query for scene 1 (problem/symptom)",
    "search query for scene 2 (root cause/diet mistake)",
    "search query for scene 3 (first herbal remedy)",
    "search query for scene 4 (morning routine/water)",
    "search query for scene 5 (healthy diet detox)",
    "search query for scene 6 (happy healthy energetic person)"
  ]
}}"""
    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}
        }).encode("utf-8")
        req = urllib.request.Request(gemini_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            res = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            return res.get("title", topic), res.get("script_hinglish", ""), res.get("scene_queries", [])
    except Exception as e:
        print("Gemini generation error:", e)
        fallback_queries = [
            f"{topic} problem medical pain",
            "unhealthy fast food lifestyle",
            "ayurvedic herbal home remedy seeds",
            "drinking warm water clean detox",
            "green organic healthy vegetables fruits",
            "energetic smiling healthy person in nature"
        ]
        return topic, f"Naturopathy me {topic} ko theek karne ke liye subah gunguna paani piyein aur chemical dawaiyon se bachein. Bharati Nature Cure ko follow karein!", fallback_queries

def main():
    topic = os.getenv("VIDEO_TOPIC", "Acidity & Seene Ki Jalan Ka Permanent Ilaaj")
    try:
        duration_min = int(os.getenv("VIDEO_DURATION_MIN", "1"))
    except Exception:
        duration_min = 1
    chat_id = os.getenv("CHAT_ID", DEFAULT_CHAT_ID)

    work_dir = os.path.abspath("temp_render")
    os.makedirs(work_dir, exist_ok=True)
    
    print(f"=== Starting Cloud Video Render on GitHub Actions ===")
    print(f"Topic: {topic} | Duration: {duration_min} min | Chat: {chat_id}")

    send_telegram(
        f"⚡ *GitHub Actions Cloud Runner Activated!* ⚡\n\n"
        f"📌 *Topic:* {topic}\n"
        f"⏱️ *Duration:* {duration_min} Minute\n"
        f"🚀 100% Free Cloud Runner is rendering your video with HD stock visuals and Ken Burns motion...",
        chat_id
    )

    # 1. Script & Visual Queries
    title, script, queries = generate_script_and_queries(topic, duration_min)
    print("Title:", title)
    print("Queries:", queries)

    # 2. Studio Mastered Voiceover (ElevenLabs Quality)
    audio_file = os.path.join(work_dir, "voice.mp3")
    build_elevenlabs_quality_audio(script, audio_file, voice_type="doctor_male")
    print("Studio mastered voiceover created!")

    # Probe duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
        stdout=subprocess.PIPE, text=True
    )
    total_dur = float(probe.stdout.strip() or (duration_min * 60))
    print(f"Total audio duration: {total_dur:.2f}s")

    # 3. Download 6 Visuals
    image_paths = []
    for idx, q in enumerate(queries[:6], start=1):
        img_url = fetch_image_from_query(q)
        img_dest = os.path.join(work_dir, f"scene_{idx}.jpg")
        try:
            r = requests.get(img_url, timeout=15)
            if r.status_code == 200:
                with open(img_dest, "wb") as f:
                    f.write(r.content)
                image_paths.append(img_dest)
                print(f"Downloaded scene {idx}: {img_url[:60]}")
        except Exception as e:
            print(f"Failed to fetch {img_url}: {e}")

    if not image_paths:
        send_telegram("❌ Video rendering failed: Could not fetch visual assets.", chat_id)
        sys.exit(1)

    # 4. Render Video with FFmpeg (Ken Burns Zoompan)
    clip_dur = total_dur / len(image_paths)
    output_mp4 = os.path.join(work_dir, "output.mp4")
    
    segment_files = []
    fps = 30
    frames_per_clip = int(clip_dur * fps)
    
    for idx, img_p in enumerate(image_paths, start=1):
        seg_out = os.path.join(work_dir, f"seg_{idx}.mp4")
        zoom_expr = "min(pzoom+0.0015,1.25)" if idx % 2 == 1 else "max(1.25-0.0015*on,1.0)"
        filter_str = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='{zoom_expr}':d={frames_per_clip}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
            f"setsar=1"
        )
        cmd_seg = [
            "ffmpeg", "-y", "-loop", "1", "-t", f"{clip_dur:.2f}",
            "-i", img_p,
            "-vf", filter_str,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            seg_out
        ]
        subprocess.run(cmd_seg, check=True)
        segment_files.append(seg_out)

    # Concat clips
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    cmd_final = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_mp4
    ]
    subprocess.run(cmd_final, check=True)
    print("FFmpeg rendering complete!")

    # 5. Upload finished MP4 to InsForge Storage
    video_key = f"github_rendered_{int(time.time())}.mp4"
    upload_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{video_key}"
    with open(output_mp4, "rb") as f:
        files = {"file": (video_key, f, "video/mp4")}
        headers = {"Authorization": f"Bearer {INSFORGE_KEY}"}
        up_resp = requests.put(upload_url, files=files, headers=headers, timeout=120)
        print("InsForge Video Upload Status:", up_resp.status_code)

    public_video_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{video_key}"

    # 6. Deliver to Telegram
    caption = (
        f"🌿 *Bharati Nature Cure - 100% Free Cloud Video* 🌿\n\n"
        f"🎬 *Title:* {title}\n"
        f"⏱️ *Duration:* {total_dur:.1f}s (~{duration_min} Min)\n"
        f"📸 *Visuals:* Auto Stock HD Clips + Ken Burns Camera Zoom Motion\n"
        f"🎙️ *Audio:* Natural AI Doctor Narration\n"
        f"✨ *Branding:* @BharatiNatureCure\n\n"
        f"🔗 [Direct Stream / Download]({public_video_url})"
    )
    send_telegram_video(public_video_url, caption, chat_id)
    print("Delivered to Telegram!")

if __name__ == "__main__":
    main()
