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
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "🌐 Visit www.bharatinaturecure.com",
                        "url": "https://www.bharatinaturecure.com"
                    }
                ]
            ]
        }
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram sendVideo error:", e)

def create_outro_card(dest_path: str):
    from PIL import Image, ImageDraw, ImageFont

    def get_font(size: int, bold: bool = False):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "arialbd.ttf" if bold else "arial.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf"
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    pass
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    W, H = 1080, 1920
    im = Image.new("RGB", (W, H), color=(11, 35, 24))
    draw = ImageDraw.Draw(im)

    # Gradient background
    for y in range(H):
        r = int(11 + (y / H) * 15)
        g = int(35 + (y / H) * 20)
        b = int(24 + (y / H) * 15)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Outer ornamental borders
    draw.rectangle([40, 60, W - 40, H - 60], outline=(46, 139, 87), width=4)
    draw.rectangle([55, 75, W - 55, H - 75], outline=(212, 175, 55), width=2)

    font_hero = get_font(56, bold=True)
    font_sub = get_font(38, bold=True)
    font_badge = get_font(42, bold=True)
    font_url = get_font(48, bold=True)
    font_desc = get_font(32, bold=False)

    # Header Branding
    draw.text((W / 2, 380), "BHARATI NATURE CURE", fill=(255, 255, 255), font=font_hero, anchor="mm")
    draw.text((W / 2, 450), "FOUNDATION, LUCKNOW", fill=(212, 175, 55), font=font_sub, anchor="mm")
    draw.text((W / 2, 510), "Natural Healing & Holistic Wellness", fill=(180, 220, 190), font=font_desc, anchor="mm")

    # Center Call-to-Action Box
    draw.rounded_rectangle([70, 720, W - 70, 1280], radius=35, fill=(18, 55, 38), outline=(212, 175, 55), width=4)
    draw.text((W / 2, 820), "FOR MORE DETAILS & CONSULTATION", fill=(255, 255, 255), font=font_sub, anchor="mm")
    draw.text((W / 2, 890), "VISIT OUR OFFICIAL WEBSITE", fill=(160, 215, 175), font=font_desc, anchor="mm")

    # Golden Button Container
    draw.rounded_rectangle([110, 960, W - 110, 1120], radius=25, fill=(212, 175, 55))
    draw.text((W / 2, 1040), "www.bharatinaturecure.com", fill=(10, 30, 20), font=font_url, anchor="mm")

    # Bottom guidance
    draw.text((W / 2, 1400), "CLICK THE LINK BELOW", fill=(255, 255, 255), font=font_badge, anchor="mm")
    draw.text((W / 2, 1460), "Tap the button below or link in description", fill=(180, 210, 190), font=font_desc, anchor="mm")

    im.save(dest_path, "JPEG", quality=95)
    print("Created branded outro card:", dest_path)

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

Return strict JSON only:
{{
  "title": "Emotional, click-worthy Hindi title with 1 emoji",
  "script_hinglish": "Complete heartfelt spoken Hindi script (~{target_words} words)",
  "scene_queries": [
    "person touching chest acid reflux heartburn discomfort emotional",
    "oily greasy fast food spicy fried meal unhealthy diet",
    "fennel seeds saunf in wooden spoon ayurvedic herbal remedy",
    "pouring clean lukewarm water in glass morning sunlight",
    "fresh green vegetables cucumber mint detox leaves"
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
            "fresh green cucumber mint detox vegetables"
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
        f"🚀 100% Free Cloud Runner is rendering your video with HD stock visuals, Ken Burns motion & Official End Card...",
        chat_id
    )

    # 1. Script & Visual Queries
    title, script, queries = generate_script_and_queries(topic, duration_min)

    # Mandatory Outro & Disclaimer for Bharati Nature Cure Foundation
    disclaimer_outro = (
        " Yaad rahe — ye sirf general naturopathy tips hain. "
        "Apni personal health ke liye kisi qualified naturopathy doctor se zaroor sampark karein. "
        "Aap hamare Bharati Nature Cure Foundation, Lucknow se jud sakte hain — link description mein hai."
    )
    if disclaimer_outro.strip() not in script:
        script = script.strip() + " " + disclaimer_outro

    print("Title:", title)
    print("Full Spoken Script (with Lucknow disclaimer):", script[:200], "...")
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

    # 3. Download, Validate and Natural Aspect-Ratio Crop 5 Visuals + 1 Outro Card
    from PIL import Image, ImageOps
    import io

    FALLBACK_IMAGES = [
        "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=1080",
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=1080",
        "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?w=1080",
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=1080",
        "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1080"
    ]

    image_paths = []
    # 5 content scenes
    for idx, q in enumerate(queries[:5], start=1):
        img_url = fetch_image_from_query(q)
        img_dest = os.path.join(work_dir, f"scene_{idx}.jpg")
        saved = False

        fallback_idx = min(idx - 1, len(FALLBACK_IMAGES) - 1)
        for candidate_url in [img_url, FALLBACK_IMAGES[fallback_idx]]:
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

    # 6th Scene: Dedicated Branded CTA Outro Card (matches the Lucknow outro disclaimer voiceover!)
    outro_dest = os.path.join(work_dir, "scene_outro.jpg")
    create_outro_card(outro_dest)
    image_paths.append(outro_dest)

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
        # For the outro card (last scene), use very subtle gentle zoom so text remains ultra-sharp and readable
        if idx == len(image_paths):
            zoom_expr = "min(zoom+0.0004,1.06)"
        elif idx % 2 == 1:
            zoom_expr = "min(zoom+0.0015,1.25)"
        else:
            zoom_expr = "max(1.25-0.0015*on,1.0)"

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

    # 6. Deliver to Telegram with Clickable Inline Button & Formatted Caption
    caption = (
        f"🌿 *Bharati Nature Cure Foundation, Lucknow* 🌿\n\n"
        f"🎬 *Title:* {title}\n"
        f"⏱️ *Duration:* {total_dur:.1f}s (~{duration_min} Min)\n"
        f"📸 *Visuals:* Auto HD Stock Clips + Ken Burns Camera Zoom Motion\n"
        f"🎙️ *Voice:* Style 1 Natural Hindi (Natural Breathing Rhythm)\n"
        f"🏥 *Foundation:* Bharati Nature Cure Foundation, Lucknow\n"
        f"🌐 *Website:* [www.bharatinaturecure.com](https://www.bharatinaturecure.com)\n\n"
        f"👇 *Neeche diye gaye button par click karke website kholein:*"
    )
    send_telegram_video(public_video_url, caption, chat_id)
    print("Delivered to Telegram with 1-click Website Button!")

if __name__ == "__main__":
    main()
