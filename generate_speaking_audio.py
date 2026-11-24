"""
Script tu dong tao file audio bai mau IELTS Speaking (SpeakingSupport)
Su dung Microsoft Edge Neural TTS (edge-tts) voi 2 giong doc Anh - Anh (British English):
- Giong Nu (Female): en-GB-SoniaNeural (cac bai 1, 3, 5, 7, 9)
- Giong Nam (Male): en-GB-RyanNeural (cac bai 2, 4, 6, 8)
"""

import os
import sys
import asyncio
from pathlib import Path

# Thiet lap Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from speaking.models import SpeakingSupport
import edge_tts

# Voice constants
VOICE_FEMALE = "en-GB-SoniaNeural"
VOICE_MALE = "en-GB-RyanNeural"


def get_voice_for_exercise(ex_id):
    """Dan xen giong doc nu va nam giua cac bai luyen."""
    if ex_id % 2 != 0:
        return VOICE_FEMALE, "Sonia (Female)"
    return VOICE_MALE, "Ryan (Male)"


async def synthesize_text(text, voice, max_retries=5):
    """Sinh audio bang edge-tts voi co che tu dong thu lai khi loi mang."""
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            if chunks:
                return b"".join(chunks)
            raise ValueError("No audio chunks received")
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = (attempt + 1) * 2.0
            print(f"        [Retry {attempt + 1}/{max_retries}] Loi: {e}. Cho {wait_time}s...")
            await asyncio.sleep(wait_time)


async def generate_all_samples(items, output_dir):
    """Sinh am thanh cho toan bo cac bai mau IELTS Speaking."""
    for item in items:
        ex_id = item["ex_id"]
        title = item["title"]
        text = item["text"]
        voice = item["voice"]
        voice_label = item["voice_label"]
        file_name = item["file_name"]
        output_path = output_dir / file_name

        print(f"\n[+] Dang tao audio bai mau cho Exercise {ex_id}: {title}")
        print(f"    - Giong doc: {voice_label} ({voice})")
        print(f"    - File dich: {file_name}")

        audio_bytes = await synthesize_text(text, voice)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        print(f"    -> [OK] Da luu: {file_name} ({len(audio_bytes):,} bytes)")


def main():
    media_dir = BASE_DIR / "media" / "speaking_samples"
    media_dir.mkdir(parents=True, exist_ok=True)

    print("==========================================================")
    print(" BƯỚC 1: ĐỌC DỮ LIỆU BÀI MẪU TỪ SPEAKINGSUPPORT (ORM)")
    print("==========================================================")
    items_to_generate = []
    supports_to_update = []

    for ex_id in range(1, 10):
        try:
            support = SpeakingSupport.objects.select_related("exercise").get(exercise_id=ex_id)
            sample_answer = support.sample_answer.strip() if support.sample_answer else ""
            if not sample_answer:
                print(f"[Canh bao] Exercise {ex_id} khong co noi dung sample_answer!")
                continue

            voice, voice_label = get_voice_for_exercise(ex_id)
            file_name = f"practice_sample_{ex_id:02d}.mp3"

            items_to_generate.append({
                "ex_id": ex_id,
                "title": support.exercise.title,
                "text": sample_answer,
                "voice": voice,
                "voice_label": voice_label,
                "file_name": file_name,
            })
            supports_to_update.append((support, f"speaking_samples/{file_name}"))
            print(f"[OK] Lay du lieu Ex {ex_id}: {support.exercise.title} ({len(sample_answer)} ky tu) - {voice_label}")
        except SpeakingSupport.DoesNotExist:
            print(f"[Canh bao] Khong tim thay SpeakingSupport cho exercise_id = {ex_id}")

    print("\n==========================================================")
    print(" BƯỚC 2: SINH AUDIO QUA EDGE-TTS (BRITISH ENGLISH)")
    print("==========================================================")
    asyncio.run(generate_all_samples(items_to_generate, media_dir))

    print("\n==========================================================")
    print(" BƯỚC 3: CẬP NHẬT TRƯỜNG SAMPLE_AUDIO_FILE TRONG DATABASE")
    print("==========================================================")
    for support, rel_path in supports_to_update:
        support.sample_audio_file = rel_path
        support.save(update_fields=["sample_audio_file"])
        print(f"[OK] Exercise {support.exercise_id} ({support.exercise.title}) -> sample_audio_file: {rel_path}")

    print("\n==========================================================")
    print(" HOÀN TẤT NÂNG CẤP TOÀN BỘ 9 FILE AUDIO SPEAKING SAMPLES!")
    print("==========================================================")


if __name__ == "__main__":
    main()
