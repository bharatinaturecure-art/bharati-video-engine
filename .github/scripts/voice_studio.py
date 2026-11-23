import os
import sys
import re
import subprocess
import asyncio
import edge_tts

# Bharati Studio Voice Engine - ElevenLabs Quality Architecture
VOICES = {
    "healer_female": "hi-IN-SwaraNeural",     # Gentle, empathetic, warm female doctor (Default)
    "doctor_male": "hi-IN-MadhurNeural",       # Deep, warm, authoritative doctor
    "bilingual_female": "en-IN-NeerjaNeural",  # Professional Indian English
    "bilingual_male": "en-IN-PrabhatNeural"    # Modern Indian English/Hinglish
}

def humanize_script_for_speech(text: str) -> str:
    """
    Transforms script with natural conversational pauses, empathetic breathing rhythms,
    and warm pacing so it sounds completely alive and human.
    """
    clean = re.sub(r'\s+', ' ', text).strip()
    
    # Conversational Hindi pause markers
    clean = clean.replace("नमस्ते दोस्तों!", "नमस्ते दोस्तों! ... ")
    clean = clean.replace("नमस्ते!", "नमस्ते! ... ")
    clean = clean.replace(" लेकिन ", "... लेकिन ")
    clean = clean.replace(" पर ", "... पर ")
    clean = clean.replace(" क्योंकि ", ", क्योंकि ")
    clean = clean.replace(" ध्यान रहे ", "... ध्यान रहे, ")
    clean = clean.replace(" सबसे पहले ", "सबसे पहले... ")
    clean = clean.replace(" दूसरा नियम ", "... दूसरा नियम, ")
    clean = clean.replace(" तीसरा नियम ", "... तीसरा नियम, ")
    clean = clean.replace("रुकिए!", "रुकिए! ... ")
    clean = clean.replace("याद रखिए,", "... याद रखिए, ")
    clean = clean.replace("सच कहूँ तो,", "... सच कहूँ तो, ")
    clean = clean.replace("आइए जानते हैं", "... आइए जानते हैं... ")
    
    # Ensure punctuation creates audible breathing space
    clean = re.sub(r'([।!?])', r'\1 ... ', clean)
    clean = re.sub(r'([,;])', r'\1 ', clean)
    clean = re.sub(r'\.{4,}', '...', clean)
    return clean

async def generate_raw_voice(text: str, voice_key: str = "healer_female", raw_output_path: str = "temp.mp3", rate: str = "-2%", pitch: str = "+0Hz"):
    """
    Generates high-definition neural voice with calibrated speed and pitch.
    Default rate is -2% for warm, intimate, caring female doctor pacing.
    """
    voice = VOICES.get(voice_key, VOICES["healer_female"])
    processed_text = humanize_script_for_speech(text)
    communicate = edge_tts.Communicate(
        text=processed_text,
        voice=voice,
        rate=rate,
        pitch=pitch
    )
    await communicate.save(raw_output_path)

def master_audio_studio_quality(raw_input_path: str, mastered_output_path: str, ffmpeg_exe: str = "ffmpeg"):
    """
    Studio Audio Mastering Chain for Warm Female Voice (ElevenLabs Quality):
    1. High-Pass Filter (100Hz): Strips mic thumps and room rumble.
    2. Warmth EQ: +1.5dB boost at 280Hz for soothing chest resonance.
    3. Silk & Air EQ: +2.2dB presence boost at 4200Hz for crisp, intimate consonants.
    4. Broadcast Compressor: Smooths peaks and brings up delicate whispers.
    5. Soft Limiter (-1dB ceiling): Clean, distortion-free output.
    """
    audio_filter = (
        "highpass=f=100,"
        "equalizer=f=280:t=q:w=1.2:g=1.5,"
        "equalizer=f=4200:t=q:w=1.0:g=2.2,"
        "acompressor=threshold=-20dB:ratio=3.0:attack=10:release=90:makeup=2.5dB,"
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
    asyncio.run(generate_raw_voice(text, voice_type, raw_temp))
    master_audio_studio_quality(raw_temp, output_path, ffmpeg_exe)
    if os.path.exists(raw_temp):
        os.remove(raw_temp)
    return output_path
