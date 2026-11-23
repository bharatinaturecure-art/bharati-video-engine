import os
import sys
import re
import subprocess
import asyncio
import edge_tts

# Bharati Studio Voice Engine - Style 1 Natural SSML Swara Architecture
DEFAULT_VOICE = "hi-IN-SwaraNeural"

def text_to_natural_ssml(text: str, voice_name: str = DEFAULT_VOICE, rate: str = "+5%", pitch: str = "+0Hz") -> str:
    """
    Transforms plain Hindi/Hinglish text into rich expressive SSML with
    human breathing pauses, emphatic stress, and dynamic pitch variation.
    """
    clean = re.sub(r'\s+', ' ', text).strip()
    
    # Escape standard XML characters
    clean = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    
    # Natural conversation pause insertions
    clean = clean.replace("नमस्ते दोस्तों!", 'नमस्ते दोस्तों! <break time="280ms"/>')
    clean = clean.replace("नमस्ते!", 'नमस्ते! <break time="250ms"/>')
    clean = clean.replace("रुकिए!", 'रुकिए! <break time="320ms"/>')
    clean = clean.replace(" लेकिन ", ' <break time="200ms"/> लेकिन ')
    clean = clean.replace(" पर ", ' <break time="200ms"/> पर ')
    clean = clean.replace(" क्योंकि ", ', <break time="200ms"/> क्योंकि ')
    clean = clean.replace(" ध्यान रहे ", ' <break time="250ms"/> ध्यान रहे, ')
    clean = clean.replace(" सबसे पहले ", 'सबसे पहले... <break time="250ms"/>')
    clean = clean.replace(" दूसरा नियम ", ' <break time="250ms"/> दूसरा नियम, ')
    clean = clean.replace(" तीसरा नियम ", ' <break time="250ms"/> तीसरा नियम, ')
    clean = clean.replace("याद रखिए,", ' <break time="250ms"/> याद रखिए, ')
    clean = clean.replace("सच कहूँ तो,", ' <break time="250ms"/> सच कहूँ तो, ')
    clean = clean.replace("आइए जानते हैं", ' <break time="250ms"/> आइए जानते हैं... ')
    
    # Natural breath pause at punctuation
    clean = clean.replace("।", '। <break time="280ms"/> ')
    clean = clean.replace("?", '? <break time="320ms"/> ')
    clean = clean.replace("!", '! <break time="280ms"/> ')
    clean = clean.replace(",", ', <break time="180ms"/> ')

    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="hi-IN">
  <voice name="{voice_name}">
    <prosody rate="{rate}" pitch="{pitch}">
      {clean}
    </prosody>
  </voice>
</speak>"""
    return ssml

async def generate_raw_voice(text: str, voice_name: str = DEFAULT_VOICE, raw_output_path: str = "temp.mp3", rate: str = "+5%", pitch: str = "+0Hz"):
    """
    Generates natural human SSML neural voice.
    """
    ssml = text_to_natural_ssml(text, voice_name=voice_name, rate=rate, pitch=pitch)
    communicate = edge_tts.Communicate(
        text=ssml,
        voice=voice_name
    )
    await communicate.save(raw_output_path)

def master_audio_studio_quality(raw_input_path: str, mastered_output_path: str, ffmpeg_exe: str = "ffmpeg"):
    """
    Studio Audio Mastering Chain for Style 1 (ElevenLabs Quality):
    1. High-Pass Filter (90Hz): Strips mic thumps and room rumble.
    2. Warmth EQ: +2.0dB boost at 260Hz for rich vocal warmth.
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
    asyncio.run(generate_raw_voice(text, DEFAULT_VOICE, raw_temp))
    master_audio_studio_quality(raw_temp, output_path, ffmpeg_exe)
    if os.path.exists(raw_temp):
        os.remove(raw_temp)
    return output_path
