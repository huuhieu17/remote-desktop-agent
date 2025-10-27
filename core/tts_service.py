import requests
import tempfile
import os
from playsound import playsound  # pip install playsound==1.2.2

CUSTOM_TTS_BASE_URL = "https://tts.imsteve.dev"
CUSTOM_TTS_API_KEY = "YOUR_API_KEY_HERE"

def clean_ssml_tags(text):
    import re
    return re.sub(r"<[^>]+>", "", text)

def synthesize_and_play(text_content, voice_gender="FEMALE"):
    payload = {
        "input": clean_ssml_tags(text_content),
        "voice": "vi-VN-HoaiMyNeural" if voice_gender.upper() == "FEMALE" else "vi-VN-NamMinhNeural",
        "response_format": "mp3"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CUSTOM_TTS_API_KEY}"
    }

    try:
        response = requests.post(
            f"{CUSTOM_TTS_BASE_URL}/v1/audio/speech",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        playsound(tmp_path)
        os.remove(tmp_path)

    except Exception as e:
        print(f"❌ Lỗi TTS: {e}")
