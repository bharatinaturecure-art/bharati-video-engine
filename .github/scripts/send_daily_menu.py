import os
import json
import urllib.request

BOT_TOKEN = os.getenv("BOT_TOKEN", "9106881636:AAHWxgYkYdH4BPbsjPH1RT1poeS-SZ0psqs")
CHAT_ID = os.getenv("CHAT_ID", "8387155304")

text = """🌅 *सुप्रभात! Bharati Nature Cure Foundation, Lucknow* 🌿

📋 *आज के टॉप 5 दैनिक प्राकृतिक चिकित्सा (Naturopathy) टॉपिक्स:*

1️⃣ *Acidity & Seene Ki Jalan Ka Permanent Ilaaj*
2️⃣ *Fatty Liver & Uric Acid Flush Karne Ka Desi Tarika*
3️⃣ *Saalon Purani Kabz (Constipation) & Aanton Ki Safai*
4️⃣ *High BP & Blood Purifier Ke 3 Naturopathy Niyam*
5️⃣ *Subah Khali Pet Usha Paan & Weight Loss Detox Water*

👉 *आज आपको कौन सा वीडियो बनवाना है?*
बस नीचे दिए गए बटन पर टैप करें या नंबर (*1*, *2*, *3*) लिखकर रिप्लाई करें!
⏱️ *फॉर्मेट गाइड:*
• 1 min या कुछ न लिखें = *9:16 YouTube Shorts*
• 2 min या 3 min लिखें = *16:9 Landscape Full HD*

🌐 *Official Website:* [www.bharatinaturecure.com](https://www.bharatinaturecure.com)"""

reply_markup = {
    "inline_keyboard": [
        [
            {"text": "1️⃣ Acidity Permanent Ilaaj", "callback_data": "order:1"},
            {"text": "2️⃣ Fatty Liver & Uric Acid", "callback_data": "order:2"}
        ],
        [
            {"text": "3️⃣ Kabz & Aanton Ki Safai", "callback_data": "order:3"},
            {"text": "4️⃣ High BP & Blood Purifier", "callback_data": "order:4"}
        ],
        [
            {"text": "5️⃣ Subah Khali Pet Detox Water", "callback_data": "order:5"}
        ],
        [
            {"text": "🌐 Visit Website", "url": "https://www.bharatinaturecure.com"}
        ]
    ]
}

def main():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print("Daily Menu Sent to Telegram! Status:", resp.status)

if __name__ == "__main__":
    main()
