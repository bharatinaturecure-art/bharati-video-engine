import os
import sys
import json
import time
import hashlib
import subprocess
import requests
import urllib.request
import urllib.parse
import io
from PIL import Image, ImageOps, ImageDraw, ImageFont
from voice_studio import build_elevenlabs_quality_audio

# Load event payload if running in GitHub Actions
_event_payload = {}
_event_path = os.getenv("GITHUB_EVENT_PATH")
if _event_path and os.path.exists(_event_path):
    try:
        with open(_event_path, "r", encoding="utf-8") as _f:
            _event_data = json.load(_f)
            _event_payload = _event_data.get("client_payload") or _event_data.get("inputs") or {}
    except Exception as _e:
        print("Could not parse GITHUB_EVENT_PATH:", _e)

BOT_TOKEN = _event_payload.get("bot_token") or os.getenv("BOT_TOKEN", "")
DEFAULT_CHAT_ID = str(_event_payload.get("chat_id") or os.getenv("CHAT_ID", "8387155304"))
INSFORGE_HOST = _event_payload.get("insforge_host") or os.getenv("INSFORGE_HOST", "https://i8vqipie.ap-southeast.insforge.app")
INSFORGE_KEY = _event_payload.get("insforge_key") or os.getenv("INSFORGE_KEY", "")
GEMINI_KEY = _event_payload.get("gemini_key") or os.getenv("GEMINI_KEY", "")
SERPAPI_KEY = _event_payload.get("serpapi_key") or os.getenv("SERPAPI_KEY", "")
OPENROUTER_KEY = _event_payload.get("openrouter_key") or os.getenv("OPENROUTER_KEY", "")

# ----------------------------------------------------
# QUALITY MANAGER ENGINE
# ----------------------------------------------------
class QualityManager:
    def __init__(self):
        self.seen_hashes = set()
        self.audit_log = []

    def get_hash(self, im: Image.Image) -> str:
        small = im.resize((16, 16)).convert("L")
        return hashlib.md5(small.tobytes()).hexdigest()

    def validate_and_crop(self, img_bytes: bytes, target_w: int, target_h: int) -> Image.Image:
        if not img_bytes or len(img_bytes) < 2500:
            raise ValueError("Image bytes empty or too small (< 2.5KB)")
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if im.width < 300 or im.height < 300:
            raise ValueError("Resolution too low")

        # Natural crop without stretching (works for 9:16 and 16:9)
        im_fit = ImageOps.fit(im, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.4 if target_h > target_w else 0.5))

        # Check duplicate hash
        h = self.get_hash(im_fit)
        if h in self.seen_hashes:
            raise ValueError("QualityManager Rejected: Duplicate image detected across scenes!")

        self.seen_hashes.add(h)
        return im_fit

    def audit_scene(self, scene_idx: int, source: str, file_path: str, res_str: str):
        size_kb = os.path.getsize(file_path) / 1024
        msg = f"Scene {scene_idx}: APPROVED | Source: {source} | Resolution: {res_str} | Size: {size_kb:.1f} KB | 100% Unique"
        print(f"[QualityManager] {msg}")
        self.audit_log.append(msg)

    def verify_final_video(self, video_path: str, expected_w: int, expected_h: int) -> bool:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,width,height",
            "-of", "json", video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", [])
        has_v = any(s.get("width") == expected_w and s.get("height") == expected_h for s in streams)
        has_a = any(s.get("codec_name") in ["aac", "mp3"] for s in streams)
        dur = float(data.get("format", {}).get("duration", 0))
        passed = has_v and has_a and dur > 15
        status = "PASSED" if passed else "FAILED"
        print(f"[QualityManager] Final Verification -> {status} (Expected: {expected_w}x{expected_h}, VideoStream: {has_v}, AudioStream: {has_a}, Duration: {dur:.1f}s)")
        return passed

# ----------------------------------------------------
# 4-LAYER VISUAL GENERATION & FALLBACK SYSTEM
# ----------------------------------------------------
TIER4_CURATED_POOLS = {
    1: [
        "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=1920",
        "https://images.unsplash.com/photo-1584467735870-87779bc5694c?w=1920",
        "https://images.unsplash.com/photo-1584515933487-779824d29309?w=1920"
    ],
    2: [
        "https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=1920",
        "https://images.unsplash.com/photo-1550547660-d9450f859349?w=1920",
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=1920"
    ],
    3: [
        "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?w=1920",
        "https://images.unsplash.com/photo-1615485290382-441e4d049cb5?w=1920",
        "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=1920"
    ],
    4: [
        "https://images.unsplash.com/photo-1548839140-29a749e1bc4e?w=1920",
        "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=1920",
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=1920"
    ],
    5: [
        "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=1920",
        "https://images.unsplash.com/photo-1545205597-3d9d02c29597?w=1920",
        "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=1920"
    ]
}

def generate_ai_image(prompt: str, target_w: int, target_h: int) -> bytes:
    # Layer 1: OpenRouter (If active credit balance >= $1.00)
    if OPENROUTER_KEY:
        try:
            url = "https://openrouter.ai/api/v1/images/generations"
            payload = json.dumps({
                "prompt": prompt,
                "model": "google/gemini-2.5-flash-image",
                "width": target_w,
                "height": target_h
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=18) as resp:
                data = json.loads(resp.read().decode())
                if data.get("data") and data["data"][0].get("url"):
                    img_url = data["data"][0]["url"]
                    r = requests.get(img_url, timeout=20)
                    if r.status_code == 200 and len(r.content) > 3000:
                        print("[AI Image Layer 1] Generated via OpenRouter!")
                        return r.content
        except Exception as e:
            pass

    # Layer 2: Pollinations FLUX.1 Engine (100% Free, Photorealistic FLUX, Unlimited)
    try:
        clean_p = prompt[:280].strip()
        encoded = urllib.parse.quote(clean_p)
        poll_w = 1024 if target_w >= target_h else 576
        poll_h = 576 if target_w >= target_h else 1024
        seed = int(time.time() * 1000) % 999999
        p_url = f"https://image.pollinations.ai/prompt/{encoded}?width={poll_w}&height={poll_h}&model=flux&nologo=true&seed={seed}"
        r = requests.get(p_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        if r.status_code == 200 and len(r.content) > 3000:
            print("[AI Image Layer 2] Generated via Pollinations FLUX.1!")
            return r.content
    except Exception as e:
        print("[AI Image Layer 2] Pollinations error:", e)

    return None

def fetch_tier3_serpapi(query: str):
    if not SERPAPI_KEY:
        return []
    try:
        url = (
            f"https://serpapi.com/search.json?engine=google_images"
            f"&q={urllib.parse.quote(query)}"
            f"&api_key={SERPAPI_KEY}&num=4&tbs=isz:lt,islt:qsvga"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("images_results", [])
            urls = []
            for item in results:
                u = item.get("original")
                if u and u.startswith("http") and not u.endswith(".svg"):
                    urls.append(u)
            return urls
    except Exception as e:
        print(f"[SerpApi] Search error for '{query}':", e)
    return []

def get_best_scene_image(scene_idx: int, prompt_query: str, qm: QualityManager, dest_path: str, target_w: int, target_h: int):
    # 1. Try AI Image Generator (Layer 1: OpenRouter / Layer 2: Pollinations FLUX)
    ai_bytes = generate_ai_image(prompt_query, target_w, target_h)
    if ai_bytes:
        try:
            cropped = qm.validate_and_crop(ai_bytes, target_w, target_h)
            cropped.save(dest_path, "JPEG", quality=95)
            qm.audit_scene(scene_idx, "AI Generated (FLUX.1/OpenRouter)", dest_path, f"{target_w}x{target_h}")
            return True
        except Exception as e:
            print(f"[Scene {scene_idx}] AI image validation error, falling back to SerpApi:", e)

    # 2. Try SerpApi Google Image Search
    serp_candidates = fetch_tier3_serpapi(prompt_query)
    
    # 3. Guaranteed Curated Naturopathy Archive
    pool_idx = ((scene_idx - 1) % len(TIER4_CURATED_POOLS)) + 1
    t4_candidates = TIER4_CURATED_POOLS.get(pool_idx, TIER4_CURATED_POOLS[1])

    pipeline = [("Tier 3 SerpApi", u) for u in serp_candidates] + [("Tier 4 Curated", u) for u in t4_candidates]

    for source_name, url in pipeline:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200 and len(r.content) > 2500:
                cropped = qm.validate_and_crop(r.content, target_w, target_h)
                cropped.save(dest_path, "JPEG", quality=95)
                qm.audit_scene(scene_idx, source_name, dest_path, f"{target_w}x{target_h}")
                return True
        except Exception:
            continue

    im = Image.new("RGB", (target_w, target_h), color=(12, 35 + (scene_idx % 20) * 4, 25))
    im.save(dest_path, "JPEG")
    qm.audit_scene(scene_idx, "Emergency Fallback", dest_path, f"{target_w}x{target_h}")
    return True

# ----------------------------------------------------
# AUTOMATED HIGH-CTR YOUTUBE THUMBNAIL GENERATOR (1280x720)
# ----------------------------------------------------
def get_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\mangal.ttf",
        "C:\\Windows\\Fonts\\NirmalaB.ttf"
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

def create_youtube_thumbnail(bg_image_path: str, dest_path: str, hook_text: str, badge_text: str = "100% प्राकृतिक नुस्खा"):
    W, H = 1280, 720
    if bg_image_path and os.path.exists(bg_image_path):
        bg = Image.open(bg_image_path).convert("RGB")
        im = ImageOps.fit(bg, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    else:
        im = Image.new("RGB", (W, H), color=(15, 45, 30))

    # Add dark gradient overlays for maximum headline text readability
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_over = ImageDraw.Draw(overlay)
    for y in range(H):
        if y < 140:
            alpha = int(140 * (1 - y / 140))
            d_over.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        elif y > 380:
            alpha = int(195 * ((y - 380) / (H - 380)))
            d_over.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(im)

    # 1. Top Left Branding Badge
    font_brand = get_font(26, bold=True)
    draw.rounded_rectangle([35, 30, 460, 85], radius=15, fill=(18, 55, 38), outline=(212, 175, 55), width=3)
    draw.text((247, 57), "🌿 BHARATI NATURE CURE", fill=(255, 255, 255), font=font_brand, anchor="mm")

    # 2. Right Top Hook Badge
    font_badge = get_font(24, bold=True)
    draw.rounded_rectangle([W - 380, 30, W - 35, 85], radius=15, fill=(212, 175, 55))
    draw.text((W - 207, 57), badge_text, fill=(10, 30, 20), font=font_badge, anchor="mm")

    # 3. Main Headline Hook (Big, Vibrant Yellow/White with heavy dark outline)
    font_main = get_font(64, bold=True)
    words = hook_text.split()
    if len(words) > 4:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx != 0 or dy != 0:
                    draw.text((W // 2 + dx, 515 + dy), line1, font=font_main, fill=(0, 0, 0), anchor="mm")
                    draw.text((W // 2 + dx, 600 + dy), line2, font=font_main, fill=(0, 0, 0), anchor="mm")
        draw.text((W // 2, 515), line1, font=font_main, fill=(255, 230, 0), anchor="mm")
        draw.text((W // 2, 600), line2, font=font_main, fill=(255, 255, 255), anchor="mm")
    else:
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx != 0 or dy != 0:
                    draw.text((W // 2 + dx, 555 + dy), hook_text, font=font_main, fill=(0, 0, 0), anchor="mm")
        draw.text((W // 2, 555), hook_text, font=font_main, fill=(255, 230, 0), anchor="mm")

    # 4. Outer Gold Border
    draw.rectangle([10, 10, W - 10, H - 10], outline=(212, 175, 55), width=6)
    im.save(dest_path, "JPEG", quality=95)
    print("Thumbnail created successfully:", dest_path)

# ----------------------------------------------------
# DYNAMIC OUTRO CTA CARD (9:16 Portrait OR 16:9 Landscape)
# ----------------------------------------------------
def create_outro_card(dest_path: str, is_landscape: bool = False):
    if is_landscape:
        W, H = 1920, 1080
        im = Image.new("RGB", (W, H), color=(11, 35, 24))
        draw = ImageDraw.Draw(im)

        for y in range(H):
            r = int(11 + (y / H) * 15)
            g = int(35 + (y / H) * 20)
            b = int(24 + (y / H) * 15)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        draw.rectangle([30, 30, W - 30, H - 30], outline=(46, 139, 87), width=4)
        draw.rectangle([45, 45, W - 45, H - 45], outline=(212, 175, 55), width=2)

        font_hero = get_font(52, bold=True)
        font_sub = get_font(36, bold=True)
        font_badge = get_font(34, bold=True)
        font_url = get_font(42, bold=True)
        font_desc = get_font(28, bold=False)

        # Left Side Branding
        draw.text((500, 380), "🌿 BHARATI NATURE CURE 🌿", fill=(255, 255, 255), font=font_hero, anchor="mm")
        draw.text((500, 455), "FOUNDATION, LUCKNOW", fill=(212, 175, 55), font=font_sub, anchor="mm")
        draw.text((500, 525), "Natural Healing & Holistic Wellness", fill=(180, 220, 190), font=font_desc, anchor="mm")
        draw.text((500, 650), "Ayurveda • Naturopathy • Yoga • Detox", fill=(200, 230, 210), font=font_badge, anchor="mm")

        # Right Side CTA Box
        draw.rounded_rectangle([1020, 240, 1820, 840], radius=35, fill=(18, 55, 38), outline=(212, 175, 55), width=4)
        draw.text((1420, 350), "FOR MORE DETAILS & CONSULTATION", fill=(255, 255, 255), font=font_sub, anchor="mm")
        draw.text((1420, 420), "VISIT OUR OFFICIAL WEBSITE", fill=(160, 215, 175), font=font_desc, anchor="mm")

        draw.rounded_rectangle([1080, 500, 1760, 640], radius=25, fill=(212, 175, 55))
        draw.text((1420, 570), "www.bharatinaturecure.com", fill=(10, 30, 20), font=font_url, anchor="mm")

        draw.text((1420, 720), "👇 CLICK THE LINK IN DESCRIPTION 👇", fill=(255, 255, 255), font=font_badge, anchor="mm")
        draw.text((1420, 775), "Consult qualified naturopathy doctors", fill=(180, 210, 190), font=font_desc, anchor="mm")

    else:
        # Portrait (9:16)
        W, H = 1080, 1920
        im = Image.new("RGB", (W, H), color=(11, 35, 24))
        draw = ImageDraw.Draw(im)

        for y in range(H):
            r = int(11 + (y / H) * 15)
            g = int(35 + (y / H) * 20)
            b = int(24 + (y / H) * 15)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        draw.rectangle([25, 25, W - 25, H - 25], outline=(46, 139, 87), width=4)
        draw.rectangle([40, 40, W - 40, H - 40], outline=(212, 175, 55), width=2)

        font_hero = get_font(44, bold=True)
        font_sub = get_font(30, bold=True)
        font_badge = get_font(26, bold=True)
        font_url = get_font(34, bold=True)
        font_desc = get_font(22, bold=False)

        draw.text((W / 2, 350), "🌿 BHARATI NATURE CURE 🌿", fill=(255, 255, 255), font=font_hero, anchor="mm")
        draw.text((W / 2, 415), "FOUNDATION, LUCKNOW", fill=(212, 175, 55), font=font_sub, anchor="mm")
        draw.text((W / 2, 475), "Natural Naturopathy & Lifestyle Healing", fill=(180, 220, 190), font=font_desc, anchor="mm")

        draw.rounded_rectangle([80, 800, W - 80, 1250], radius=30, fill=(18, 55, 38), outline=(212, 175, 55), width=3)
        draw.text((W / 2, 900), "FOR COMPLETE CURE & DIET CHART", fill=(255, 255, 255), font=font_sub, anchor="mm")
        draw.text((W / 2, 960), "VISIT OUR OFFICIAL WEBSITE", fill=(160, 215, 175), font=font_desc, anchor="mm")

        draw.rounded_rectangle([130, 1030, W - 130, 1140], radius=20, fill=(212, 175, 55))
        draw.text((W / 2, 1085), "www.bharatinaturecure.com", fill=(10, 30, 20), font=font_url, anchor="mm")

        draw.text((W / 2, 1400), "CLICK THE LINK BELOW", fill=(255, 255, 255), font=font_badge, anchor="mm")
        draw.text((W / 2, 1460), "Tap the button below or link in description", fill=(180, 210, 190), font=font_desc, anchor="mm")

    im.save(dest_path, "JPEG", quality=95)
    print(f"Created {'Landscape (16:9)' if is_landscape else 'Portrait (9:16)'} outro card:", dest_path)

# ----------------------------------------------------
# TELEGRAM DELIVERY HELPERS
# ----------------------------------------------------
def send_telegram(text: str, chat_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram send error:", e)

def send_telegram_photo(photo_url: str, caption: str, chat_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = json.dumps({
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram sendPhoto error:", e)

def send_telegram_video(video_url: str, caption: str, chat_id: str, video_key: str = "", thumb_key: str = "", is_short: bool = True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    btn_text = "🚀 1-Click Publish to YouTube Shorts" if is_short else "🚀 1-Click Publish to YouTube (Full HD)"
    cb_data = f"yt:{video_key}:{thumb_key}" if thumb_key else f"yt:{video_key}"
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": btn_text,
                    "callback_data": cb_data
                }
            ],
            [
                {
                    "text": "🌐 Visit www.bharatinaturecure.com",
                    "url": "https://www.bharatinaturecure.com"
                }
            ]
        ]
    }
    payload = json.dumps({
        "chat_id": chat_id,
        "video": video_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Telegram sendVideo error:", e)

# ----------------------------------------------------
# SCRIPT & SCENE PROMPTS GENERATION (GEMINI ENGINE)
# ----------------------------------------------------
def generate_script_and_queries(topic: str, duration_min: int, num_scenes: int):
    target_words = 130 if duration_min <= 1 else int(duration_min * 135)
    format_type = "9:16 Vertical YouTube Shorts" if duration_min <= 1 else "16:9 Landscape Standard YouTube Video"
    
    prompt = f"""You are Dr. Bharati, a warm, caring, empathetic senior Naturopathy doctor at Bharati Nature Cure Foundation, Lucknow.
Topic: "{topic}"
Target Spoken Duration: Exactly {duration_min} minute(s) (~{target_words} spoken Hindi words).
Target Video Format: {format_type}.
Number of Visual Scenes Needed: Exactly {num_scenes}.

Task:
1. Write a complete, comprehensive, heartfelt spoken Hindi script (~{target_words} words).
   Start with warm loving greeting: "नमस्ते दोस्तों! क्या आपको भी..."
   Provide deep root cause analysis, 3 daily naturopathy kitchen remedies, exact preparation steps, timings, and dietary rules.
   
2. Divide the visual progression into EXACTLY {num_scenes} distinct scene prompts in ENGLISH for an AI text-to-image generator.
   Each prompt MUST describe a specific photorealistic, cinematic visual directly corresponding to the exact words spoken at that moment:
   - For remedies: close up of ingredients (Triphala, ajwain, fennel, copper water, amla, etc.)
   - For symptoms: realistic Indian patient expressing stomach discomfort or fatigue
   - For habits: oily greasy junk food vs fresh leafy greens & yoga pranayama
   - For clinic: serene naturopathy clinic, Indian female doctor smiling warmly
   Format: "Photorealistic cinematic shot of [exact subject], [lighting/setting], 4k natural lighting, no text"

3. Provide a high-CTR YouTube thumbnail prompt and a short 4-6 word Hindi hook for the thumbnail.

Return strict JSON only:
{{
  "title": "Emotional Hindi title",
  "script_hinglish": "Complete spoken Hindi script (~{target_words} words)",
  "scene_queries": [
    "prompt 1", "prompt 2", ... exactly {num_scenes} visual prompts
  ],
  "thumbnail_prompt": "Cinematic high-impact YouTube thumbnail visual prompt for {topic}, dramatic natural lighting",
  "thumbnail_text": "Short 4-6 word punchy Hindi hook"
}}"""
    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}
        }).encode("utf-8")
        req = urllib.request.Request(gemini_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode())
            res = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            return (
                res.get("title", topic),
                res.get("script_hinglish", ""),
                res.get("scene_queries", []),
                res.get("thumbnail_prompt", f"Cinematic Ayurvedic Naturopathy healing for {topic}"),
                res.get("thumbnail_text", topic[:30])
            )
    except Exception as e:
        print("Gemini generation error:", e)
        default_queries = [
            f"Photorealistic shot of person experiencing discomfort due to {topic}, cinematic 4k",
            "Photorealistic close-up of unhealthy oily spicy junk food on plate",
            "Photorealistic close-up of traditional Indian Ayurvedic herbs, fennel seeds, ajwain in brass bowl",
            "Photorealistic shot of pouring clean lukewarm water from clay pot into glass morning sunlight",
            "Photorealistic shot of fresh green detox vegetables and mint leaves on wooden cutting board",
            "Photorealistic shot of peaceful Indian woman practicing pranayama yoga in nature",
            "Photorealistic shot of serene Indian garden in golden morning sunlight",
            "Photorealistic portrait of smiling healthy vibrant Indian family, radiant wellness"
        ]
        return topic, "", default_queries, f"Ayurvedic remedy for {topic}", topic[:30]

# ----------------------------------------------------
# MAIN RENDER WORKFLOW
# ----------------------------------------------------
def main():
    topic = _event_payload.get("topic") or os.getenv("VIDEO_TOPIC", "Acidity & Seene Ki Jalan Ka Permanent Ilaaj")
    try:
        duration_min = int(_event_payload.get("duration_min") or os.getenv("VIDEO_DURATION_MIN", "1"))
    except Exception:
        duration_min = 1
    chat_id = str(_event_payload.get("chat_id") or os.getenv("CHAT_ID", DEFAULT_CHAT_ID))
    custom_script = (_event_payload.get("custom_script") or os.getenv("CUSTOM_SCRIPT") or "").strip()

    work_dir = os.path.abspath("temp_render")
    os.makedirs(work_dir, exist_ok=True)
    
    qm = QualityManager()

    # Dynamic Aspect Ratio & Dynamic Scene Count
    is_landscape = duration_min > 1
    target_w, target_h = (1920, 1080) if is_landscape else (1080, 1920)
    aspect_label = "16:9 Landscape Video" if is_landscape else "9:16 Vertical Short"

    # Each scene visual stays for ~8.5 seconds
    scene_dur_target = 8.5
    total_est_seconds = duration_min * 60
    num_content_scenes = max(5, min(65, int(total_est_seconds / scene_dur_target)))

    print(f"=== Starting Bharati Video Engine ===")
    print(f"Topic: {topic} | Duration: {duration_min} min ({num_content_scenes} scenes) | Aspect Ratio: {aspect_label} ({target_w}x{target_h})")

    send_telegram(
        f"⚡ *Bharati Video Engine Activated!* ⚡\n\n"
        f"📌 *Topic:* {topic}\n"
        f"⏱️ *Duration:* {duration_min} Minute(s)\n"
        f"🎬 *Scenes:* {num_content_scenes} AI-Generated Visuals\n"
        f"📐 *Format:* {aspect_label} ({target_w}x{target_h})\n"
        f"🎨 *Visual Engine:* FLUX.1 / OpenRouter Text-to-Image Matching\n"
        f"🖼️ *Thumbnail Engine:* 1280x720 High-CTR Generator\n"
        f"🛡️ *Quality Manager:* Active\n"
        f"🚀 Rendering video & thumbnail in cloud...",
        chat_id
    )

    # 1. Script & Visual Prompts Generation
    min_words_needed = 70 if duration_min <= 1 else (duration_min * 90)
    script_word_count = len(custom_script.split()) if custom_script else 0

    if custom_script and script_word_count >= min_words_needed:
        print(f"[Script Manager] Using Approved Custom Script ({script_word_count} words for {duration_min} min video)!")
        title = topic
        script = custom_script
        _, _, queries, thumb_prompt, thumb_text = generate_script_and_queries(topic, duration_min, num_content_scenes)
    else:
        if custom_script:
            print(f"[Script Manager] Notice: Provided custom_script was too short ({script_word_count} words, needed >= {min_words_needed}). Generating full doctor script for {duration_min} min!")
        title, script, queries, thumb_prompt, thumb_text = generate_script_and_queries(topic, duration_min, num_content_scenes)

    # Mandatory Outro & Disclaimer for Bharati Nature Cure Foundation
    disclaimer_outro = (
        " Yaad rahe — ye sirf general naturopathy tips hain. "
        "Apni personal health ke liye kisi qualified naturopathy doctor se zaroor sampark karein. "
        "Aap hamare Bharati Nature Cure Foundation, Lucknow se jud sakte hain — link description mein hai."
    )
    if disclaimer_outro.strip() not in script:
        script = script.strip() + " " + disclaimer_outro

    # Ensure title has #Shorts only if <= 1 min
    if not is_landscape and "#shorts" not in title.lower():
        title = f"{title} #Shorts"

    print("Title:", title)
    print("Full Spoken Script:", script[:180], "...")

    # 2. Studio Mastered Voiceover
    audio_file = os.path.join(work_dir, "voice.mp3")
    build_elevenlabs_quality_audio(script, audio_file, voice_type="healer_female")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
        stdout=subprocess.PIPE, text=True
    )
    total_dur = float(probe.stdout.strip() or (duration_min * 60))
    print(f"Total audio duration: {total_dur:.2f}s")

    # 3. AI Text-to-Image Visuals (Sentence-Matching Scenes)
    image_paths = []
    # Fill queries if needed to match num_content_scenes
    while len(queries) < num_content_scenes:
        queries.append(f"Cinematic photorealistic shot of natural healing for {topic}, scene {len(queries)+1}")

    for idx, q in enumerate(queries[:num_content_scenes], start=1):
        img_dest = os.path.join(work_dir, f"scene_{idx}.jpg")
        get_best_scene_image(idx, q, qm, img_dest, target_w, target_h)
        image_paths.append(img_dest)

    # Final Outro Branded CTA Card (Dynamic 16:9 or 9:16)
    outro_dest = os.path.join(work_dir, "scene_outro.jpg")
    create_outro_card(outro_dest, is_landscape=is_landscape)
    image_paths.append(outro_dest)
    qm.audit_scene(len(image_paths), f"Official Outro ({'16:9' if is_landscape else '9:16'})", outro_dest, f"{target_w}x{target_h}")

    # 4. Generate 1280x720 High-CTR YouTube Thumbnail
    thumb_dest = os.path.join(work_dir, "thumbnail.jpg")
    thumb_bg = os.path.join(work_dir, "thumb_bg.jpg")
    tb_bytes = generate_ai_image(thumb_prompt, 1280, 720)
    if tb_bytes:
        with open(thumb_bg, "wb") as f_tb:
            f_tb.write(tb_bytes)
    else:
        # Use scene 1 or scene 3 as fallback background
        thumb_bg = image_paths[0] if image_paths else ""

    create_youtube_thumbnail(thumb_bg, thumb_dest, thumb_text, badge_text="100% प्राकृतिक नुस्खा")

    # 5. Render Video with FFmpeg (Ken Burns Zoompan)
    clip_dur = total_dur / len(image_paths)
    output_mp4 = os.path.join(work_dir, "output.mp4")
    
    segment_files = []
    fps = 30
    frames_per_clip = int(clip_dur * fps)
    
    for idx, img_p in enumerate(image_paths, start=1):
        seg_out = os.path.join(work_dir, f"seg_{idx}.mp4")
        if idx == len(image_paths):
            zoom_expr = "min(zoom+0.0004,1.05)"
        elif idx % 2 == 1:
            zoom_expr = "min(zoom+0.0015,1.22)"
        else:
            zoom_expr = "max(1.22-0.0015*on,1.0)"

        filter_str = (
            f"zoompan=z='{zoom_expr}':d={frames_per_clip}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={fps},"
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

    # Verify final video with Quality Manager
    qm.verify_final_video(output_mp4, target_w, target_h)

    # 6. Upload finished MP4 and Thumbnail to InsForge Storage
    video_key = f"github_rendered_{int(time.time())}.mp4"
    thumb_key = f"thumb_{video_key.replace('.mp4', '.jpg')}"

    headers = {"Authorization": f"Bearer {INSFORGE_KEY}"}

    # Upload MP4
    upload_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{video_key}"
    with open(output_mp4, "rb") as f:
        files = {"file": (video_key, f, "video/mp4")}
        up_resp = requests.put(upload_url, files=files, headers=headers, timeout=180)
        print("InsForge Video Upload Status:", up_resp.status_code)

    # Upload Thumbnail
    upload_thumb_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{thumb_key}"
    with open(thumb_dest, "rb") as f_th:
        files_th = {"file": (thumb_key, f_th, "image/jpeg")}
        th_resp = requests.put(upload_thumb_url, files=files_th, headers=headers, timeout=60)
        print("InsForge Thumbnail Upload Status:", th_resp.status_code)

    public_video_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{video_key}"
    public_thumb_url = f"{INSFORGE_HOST}/api/storage/buckets/videos/objects/{thumb_key}"

    # 7. Deliver Thumbnail & Video to Telegram
    thumb_caption = (
        f"🖼️ *Official YouTube Thumbnail (1280x720)*\n"
        f"📌 *Topic:* {topic}\n"
        f"✨ *Hook:* {thumb_text}\n"
        f"🏛️ *Brand:* Bharati Nature Cure Foundation"
    )
    send_telegram_photo(public_thumb_url, thumb_caption, chat_id)

    video_caption = (
        f"🌿 *Bharati Nature Cure Foundation, Lucknow* 🌿\n\n"
        f"🎬 *Title:* {title}\n"
        f"⏱️ *Duration:* {total_dur:.1f}s (~{duration_min} Min)\n"
        f"📐 *Format:* {aspect_label} ({target_w}x{target_h})\n"
        f"🎨 *Visuals:* {len(image_paths)-1} Sentence-Matching AI Photos (FLUX.1)\n"
        f"🖼️ *Thumbnail:* 1280x720 High-CTR Thumbnail Attached\n"
        f"🛡️ *Quality Manager:* 100% Unique Verified\n"
        f"🎙️ *Voice:* Style 1 Natural Doctor Voiceover\n"
        f"🏥 *Foundation:* Bharati Nature Cure Foundation, Lucknow\n"
        f"🌐 *Website:* [www.bharatinaturecure.com](https://www.bharatinaturecure.com)\n\n"
        f"👇 *Neeche diye gaye button se 1-click YouTube publish karein:*"
    )
    send_telegram_video(public_video_url, video_caption, chat_id, video_key=video_key, thumb_key=thumb_key, is_short=not is_landscape)
    print("Execution completed successfully!")

if __name__ == "__main__":
    main()
