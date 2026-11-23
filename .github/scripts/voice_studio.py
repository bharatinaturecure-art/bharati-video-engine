import os
import sys
import re
import subprocess
import asyncio
import edge_tts

# Bharati Studio Voice Engine - High-Retention Clean Voice Architecture
DEFAULT_VOICE = "hi-IN-SwaraNeural"

def humanize_script_for_speech(text: str) -> str:
    """
    Cleans text and uses natural Hindi punctuation to inject human breathing pauses,
    rhythm, and curiosity inflections WITHOUT ANY XML or SSML tags.
    """
    # 1. Strictly strip ANY XML/HTML/SSML tags if present
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # 2. Conversational Hindi pause markers using pure punctuation
    clean = clean.replace("नमस्ते दोस्तों!", "नमस्ते दोस्तों! ... ")
    clean = clean.replace("नमस्ते!", "नमस्ते! ... ")
    clean = clean.replace("रुकिए!", "रुकिए! ... ")
    clean = clean.replace(" लेकिन ", "... लेकिन ")
    clean = clean.replace(" पर ", "... पर ")
    clean = clean.replace(" क्योंकि ", ", क्योंकि ")
    clean = clean.replace(" ध्यान रहे ", "... ध्यान रहे, ")
    clean = clean.replace(" सबसे पहले ", "सबसे पहले... ")
    clean = clean.replace(" दूसरा नियम ", "... दूसरा नियम, ")
    clean = clean.replace(" तीसरा नियम ", "... तीसरा नियम, ")
    clean = clean.replace("याद रखिए,", "... याद रखिए, ")
    clean = clean.replace("सच कहूँ तो,", "... सच कहूँ तो, ")
    clean = clean.replace("आइए जानते हैं", "... आइए जानते हैं... ")

    # 3. Enhance sentence boundaries with natural pauses
    clean = re.sub(r'([।!?])', r'\1 ... ', clean)
    clean = re.sub(r'([,;])', r'\1 ', clean)
    clean = re.sub(r'\.{4,}', '...', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    return clean

async def generate_raw_voice(text: str, voice_name: str = DEFAULT_VOICE, raw_output_path: str = "temp.mp3", rate: str = "+6%", pitch: str = "+1Hz"):
    """
    Generates high-definition neural voice with calibrated speed and pitch.
    """
    processed_text = humanize_script_for_speech(text)
    communicate = edge_tts.Communicate(
        text=processed_text,
        voice=voice_name,
        rate=rate,
        pitch=pitch
    )
    await communicate.save(raw_output_path)

def master_audio_studio_quality(raw_input_path: str, mastered_output_path: str, ffmpeg_exe: str = "ffmpeg"):
    """
    Studio Audio Mastering Chain:
    1. High-Pass Filter (90Hz): Strips mic thumps and room rumble.
    2. Warmth EQ: +2.0dB boost at 260Hz for rich vocal presence.
    3. Silk & Air EQ: +2.8dB presence boost at 3800Hz for crisp consonants.
    4. Broadcast Compressor: Smooths peaks and brings up delicate whispers.
    5. Soft Limiter (-1dB ceiling): Clean, distortion-free output.
    """
    audio_filter = (
        "highpass=f=90,"
        "equalizer=f=260:t=q:w=1.2:g=2.0,"
        "equalizer=f=3800:t=q:w=1.0:g=2.8,"
        "acompressor=threshold=-19dB:ratio=3.5:attack=10:release=80:makeup=2.5dB,"
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

def build_elevenlabs_quality_audio(text: str, output_path: str, voice_type: str = "healer_female", ffmpeg_exe: str = "ffmpeg") -> str:
    raw_temp = output_path.replace(".mp3", "_raw.mp3")
    asyncio.run(generate_raw_voice(text, DEFAULT_VOICE, raw_temp, rate="+6%", pitch="+1Hz"))
    master_audio_studio_quality(raw_temp, output_path, ffmpeg_exe)
    if os.path.exists(raw_temp):
        os.remove(raw_temp)
    return output_path
