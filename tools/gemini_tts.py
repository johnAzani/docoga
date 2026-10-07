#!/usr/bin/env python3
"""
Gemini TTS bridge.

Usage:
  python3 tools/gemini_tts.py --voice Charon --instruction "Speak with authority" \
      --text "Your caution fee is refundable." --out renders/vo-line1.wav

  python3 tools/gemini_tts.py --voice Kore --text "Two minutes. That's all." \
      --out renders/vo-line2.mp3 --model gemini-2.5-flash-preview-tts

Voices: Charon, Kore, Puck, Aoede, Fenrir, Leda, Zephyr, etc.
"""
import argparse, base64, json, sys, time, wave, urllib.request, subprocess, os

API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

def get_key():
    env_path = "/home/user/docoga/.worker-secrets.env"
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    # fallback: environment variable
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    sys.exit("no GEMINI_API_KEY found in .worker-secrets.env or environment")


def main():
    p = argparse.ArgumentParser(description="Gemini TTS bridge")
    p.add_argument("--model", default=None)
    p.add_argument("--voice", default="Charon")
    p.add_argument("--instruction", default="")
    p.add_argument("--text", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    model = a.model or os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    prompt = (a.instruction.strip() + " " if a.instruction.strip() else "") + a.text

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": a.voice
                    }
                }
            }
        }
    }

    req = urllib.request.Request(
        API.format(model),
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": get_key()
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")

    try:
        inline = resp["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(inline["data"])
    except (KeyError, IndexError):
        sys.exit("Unexpected response: " + json.dumps(resp)[:400])

    rate = 24000
    mime = inline.get("mimeType", "")
    if "rate=" in mime:
        rate = int(mime.split("rate=")[1])

    wav = a.out.rsplit(".", 1)[0] + ".wav"
    os.makedirs(os.path.dirname(wav) or ".", exist_ok=True)

    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)

    if not a.out.endswith(".wav"):
        FF = "/home/user/docoga/tools/bin/ffmpeg"
        if not os.path.exists(FF):
            try:
                FF = subprocess.run(
                    ["python3", "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True
                ).stdout.strip()
            except Exception:
                FF = "ffmpeg"

        subprocess.run(
            [FF, "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k",
             "-write_xing", "1", a.out],
            capture_output=True
        )
        os.remove(wav)

    print(f"OK {a.voice}: {len(pcm) // (2 * rate)}s -> {a.out}")


if __name__ == "__main__":
    main()