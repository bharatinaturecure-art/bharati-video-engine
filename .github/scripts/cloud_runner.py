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
    prompt = f"""You are Dr. Bharati, a warm, caring, empathetic senior Naturopathy doctor and wellness guide at Bharati Nature Cure.
Topic: "{topic}"
Target Duration: Exactly {duration_min} minute(s) (~{target_words} spoken words).
Speaker Persona: A wise, loving, authoritative Indian female doctor talking warmly to her patients like a caring elder sister or family doctor.

Script Writing Guidelines:
1. Deep Human Conversational Emotion:
   - Start with an affectionate, relatable opening acknowledging real pain:
     "नमस्ते दोस्तों! क्या आपके साथ भी ऐसा होता है कि खाना खाते ही सीने में आग जैसी तेज जलन होने लगती है? और आप तुरंत राहत पाने के लिए हर बार एंटासिड की गोलियां खा लेते हैं? रुकिए! गोलियां सिर्फ समस्या को दबाती हैं, जड़ से खत्म नहीं करतीं..."
   - Use warm emotional phrasing, gentle rhetorical questions, reassuring advice, and practical kitchen naturopathy steps.
   - End with heartfelt warmth and blessings: "अपने शरीर को थोड़ा समय और प्यार दीजिए, यह खुद ठीक होना जानता है। ऐसे ही सच्चे और सरल स्वास्थ्य सुझावों के लिए भारती नेचर क्योर से जुड़े रहिए।"
2. Scene Visual Queries:
   - Must be natural, aesthetically pleasing vertical/portrait (9:16) stock photo concepts:
     Scene 1: person touching chest acid reflux heartburn discomfort emotional
     Scene 2: oily greasy fast food spicy fried meal unhealthy diet
     Scene 3: fennel seeds saunf in wooden spoon ayurvedic herbal remedy
     Scene 4: pouring clean lukewarm water in glass morning sunlight
     Scene 5: fresh green vegetables cucumber mint detox leaves
     Scene 6: vibrant happy smiling peaceful healthy person in morning nature

Return strict JSON only:
{{
  "title": "Emotional, click-worthy Hindi title with 1 emoji",
  "script_hinglish": "Complete heartfelt spoken Hindi script (~{target_words} words)",
  "scene_queries": [
    "person touching chest acid reflux heartburn discomfort emotional",
    "oily greasy fast food spicy fried meal unhealthy diet",
    "fennel seeds saunf in wooden spoon ayurvedic herbal remedy",
    "pouring clean lukewarm water in glass morning sunlight",
    "fresh green vegetables cucumber mint detox leaves",
    "vibrant happy smiling peaceful healthy person in morning nature"
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
            f"{topic} person in discomfort pain emotional",
            "unhealthy oily spicy fast food meal",
            "ayurvedic fennel seeds herbal remedy spoon",
            "drinking warm clean water morning sunlight",
            "fresh green cucumber mint detox vegetables",
            "happy smiling healthy person in beautiful nature"
        ]
        return topic, f"नमस्ते दोस्तों! {topic} को जड़ से खत्म करने के लिए रोज़ सुबह खाली पेट एक गिलास गुनगुना पानी और सौंफ का काढ़ा पिएं। अपने शरीर का ख्याल रखें और भारती नेचर क्योर से जुड़े रहें!", fallback_queries

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

    # 2. Studio Mastered Voiceover (Warm Hindi Lady Doctor)
    audio_file = os.path.join(work_dir, "voice.mp3")
    build_elevenlabs_quality_audio(script, audio_file, voice_type="healer_female")
    print("Warm Hindi Lady Doctor voiceover created!")

    # Probe duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
        stdout=subprocess.PIPE, text=True
    )
    total_dur = float(probe.stdout.strip() or (duration_min * 60))
    print(f"Total audio duration: {total_dur:.2f}s")

    # 3. Download, Validate and Natural Aspect-Ratio Crop 6 Visuals
    from PIL import Image, ImageOps
    import io

    FALLBACK_IMAGES = [
        "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=1080",
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=1080",
        "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?w=1080",
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=1080",
        "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1080",
        "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=1080"
    ]

    image_paths = []
    for idx, q in enumerate(queries[:6], start=1):
        img_url = fetch_image_from_query(q)
        img_dest = os.path.join(work_dir, f"scene_{idx}.jpg")
        saved = False

        for candidate_url in [img_url, FALLBACK_IMAGES[idx - 1]]:
            if not candidate_url:
                continue
            try:
                r = requests.get(candidate_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                if r.status_code == 200 and len(r.content) > 2000:
                    im = Image.open(io.BytesIO(r.content)).convert("RGB")
                    # Preserve 100% natural proportions: Center-crop to 9:16 (1080x1920) without ANY stretching!
                    im = ImageOps.fit(im, (1080, 1920), method=Image.Resampling.LANCZOS, centering=(0.5, 0.4))
                    im.save(img_dest, "JPEG", quality=95)
                    image_paths.append(img_dest)
                    print(f"Validated and natural-cropped scene {idx} from: {candidate_url[:60]}")
                    saved = True
                    break
            except Exception as e:
                print(f"Candidate image failed for scene {idx}: {e}")

        if not saved:
            im = Image.new("RGB", (1080, 1920), color=(20, 60, 40))
            im.save(img_dest, "JPEG")
            image_paths.append(img_dest)

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
        zoom_expr = "min(zoom+0.0015,1.25)" if idx % 2 == 1 else "max(1.25-0.0015*on,1.0)"
        filter_str = (
            f"zoompan=z='{zoom_expr}':d={frames_per_clip}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
            f"setsar=1"
        )
        cmd_seg = [
            "ffmpeg", "-y",
            "-i", img_p,
            "-vf", filter_str,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", f"{clip_dur:.2f}",
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
