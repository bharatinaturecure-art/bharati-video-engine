import os
import sys
import re
import subprocess
import asyncio
import edge_tts

# Bharati Studio Voice Engine - ElevenLabs Quality Architecture
VOICES = {
    "doctor_male": "hi-IN-MadhurNeural",       # Deep, warm, authoritative doctor
    "healer_female": "hi-IN-SwaraNeural",     # Gentle, empathetic, clear female
    "bilingual_male": "en-IN-PrabhatNeural",  # Modern Indian English/Hinglish
    "bilingual_female": "en-IN-NeerjaNeural"  # Professional Indian English
}

def humanize_script_for_speech(text: str) -> str:
    clean = re.sub(r'\s+', ' ', text).strip()
    clean = clean.replace(" लेकिन ", "... लेकिन ")
    clean = clean.replace(" पर ", "... पर ")
    clean = clean.replace(" क्योंकि ", ", क्योंकि ")
    clean = clean.replace(" ध्यान रहे ", "... ध्यान रहे, ")
    clean = clean.replace(" सबसे पहले ", "सबसे पहले... ")
    clean = clean.replace(" दूसरा नियम ", "... दूसरा नियम, ")
    clean = clean.replace(" तीसरा नियम ", "... तीसरा नियम, ")
    clean = re.sub(r'([।!?])', r'\1 ... ', clean)
    clean = re.sub(r'([,;])', r'\1 ', clean)
    clean = re.sub(r'\.{4,}', '...', clean)
    return clean

async def generate_raw_voice(text: str, voice_key: str, raw_output_path: str, rate: str = "-4%", pitch: str = "+0Hz"):
    voice = VOICES.get(voice_key, VOICES["doctor_male"])
    processed_text = humanize_script_for_speech(text)
    communicate = edge_tts.Communicate(
        text=processed_text,
        voice=voice,
        rate=rate,
        pitch=pitch
    )
    await communicate.save(raw_output_path)

def master_audio_studio_quality(raw_input_path: str, mastered_output_path: str, ffmpeg_exe: str = "ffmpeg"):
    audio_filter = (
        "highpass=f=80,"
        "equalizer=f=250:t=q:w=1.2:g=1.8,"
        "equalizer=f=3500:t=q:w=1.0:g=2.2,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=8:release=80:makeup=2.5dB,"
        "alimiter=limit=-1dB"
    )
    cmd = [
        ffmpeg_exe, "-y",
        "-i", raw_input_path,
        "-af", audio_filter,
        "-c:a", "libmp3lame", "-b:a", "256k",
        mastered_output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def build_elevenlabs_quality_audio(text: str, output_path: str, voice_type: str = "doctor_male", ffmpeg_exe: str = "ffmpeg") -> str:
    raw_temp = output_path.replace(".mp3", "_raw.mp3")
    asyncio.run(generate_raw_voice(text, voice_type, raw_temp))
    master_audio_studio_quality(raw_temp, output_path, ffmpeg_exe)
    if os.path.exists(raw_temp):
        os.remove(raw_temp)
    return output_path
