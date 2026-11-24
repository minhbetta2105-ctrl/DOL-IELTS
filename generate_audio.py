"""
Script tu dong tao file audio IELTS Listening chat luong cao
Su dung Microsoft Edge Neural TTS (edge-tts) voi 2 giong doc Anh - Anh (British English):
- Giong Nu (Female): en-GB-SoniaNeural
- Giong Nam (Male): en-GB-RyanNeural
"""

import os
import sys
import asyncio
import wave
from pathlib import Path

# Thiet lap Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from receptive.models import Exercise
import edge_tts

# Giong doc chuan Anh - Anh (British English)
VOICE_MALE = "en-GB-RyanNeural"
VOICE_FEMALE = "en-GB-SoniaNeural"

# Phân vai chi tiết cho từng bài tập
EXERCISE_SPEAKER_MAP = {
    # Nhóm 1: 6 bài luyện tập theo chủ đề (Topic Exercises)
    7: {
        "Narrator": VOICE_MALE,
        "Mrs. Davis": VOICE_FEMALE,
        "Alex": VOICE_MALE,
        "default": VOICE_MALE,
    },
    8: {
        "Narrator": VOICE_FEMALE,
        "Officer": VOICE_FEMALE,
        "Customer": VOICE_MALE,
        "default": VOICE_FEMALE,
    },
    9: {
        "Narrator": VOICE_MALE,
        "Librarian": VOICE_FEMALE,
        "default": VOICE_FEMALE,
    },
    10: {
        "Narrator": VOICE_FEMALE,
        "Interviewer": VOICE_FEMALE,
        "Dr. Vance": VOICE_MALE,
        "Dr. Marcus Vance": VOICE_MALE,
        "default": VOICE_MALE,
    },
    11: {
        "Narrator": VOICE_MALE,
        "Lecturer": VOICE_FEMALE,
        "default": VOICE_FEMALE,
    },
    12: {
        "Narrator": VOICE_FEMALE,
        "Speaker": VOICE_MALE,
        "default": VOICE_MALE,
    },
    # Nhóm 2: 3 bài thi thử hoàn chỉnh (Full Mock Tests)
    16: {
        "Speaker A": VOICE_MALE,
        "Speaker B": VOICE_FEMALE,
        "Narrator": VOICE_MALE,
        "default": VOICE_MALE,
    },
    17: {
        "Speaker A": VOICE_MALE,
        "Speaker B": VOICE_FEMALE,
        "Narrator": VOICE_MALE,
        "default": VOICE_MALE,
    },
    18: {
        "Speaker A": VOICE_MALE,
        "Speaker B": VOICE_FEMALE,
        "Narrator": VOICE_MALE,
        "default": VOICE_MALE,
    },
}

# Fallback transcript phong khi can dong bo
FALLBACK_TRANSCRIPTS = {
    7: (
        "Narrator: You will hear a conversation between an international student, Alex, and a university housing officer, Mrs. Davis.\n\n"
        "Mrs. Davis: Good morning, welcome to the Student Accommodation Services. How can I help you today?\n"
        "Alex: Hello! I am an incoming first-year student, and I am looking for a place to stay near campus.\n"
        "Mrs. Davis: Wonderful! For first-year international students, we strongly recommend our University Residence Halls. They are secure, close to lecture theatres, and provide a great community atmosphere.\n"
        "Alex: That sounds ideal. What about the pricing?\n"
        "Mrs. Davis: Standard rooms range from 400 to 500 dollars a month. What is your budget?\n"
        "Alex: My maximum monthly budget is 450 dollars, ideally including utility bills.\n"
        "Mrs. Davis: That fits nicely with our Hall B option. Standard water and heating are included in this package. To secure your reservation, you must submit a scanned copy of your Student ID card before next Friday.\n"
        "Alex: Perfect, I will email the copy this afternoon. Thank you very much!"
    ),
    8: (
        "Narrator: You will hear a customer service representative explaining leisure centre facilities and membership terms.\n\n"
        "Officer: Good afternoon! Welcome to Riverdale Community Sports Centre.\n"
        "Customer: Hi, I would like some information about joining the sports centre.\n"
        "Officer: Certainly! Our facilities include a gym, fitness studios, and an Olympic-sized swimming pool. On weekdays, the swimming pool opens early at 6:00 AM for morning lap swimmers.\n"
        "Customer: That is great for my schedule. How much is the membership?\n"
        "Officer: A standard adult membership is 250 pounds, but if you have a valid student card, an annual student pass is discounted to only 180 pounds per year.\n"
        "Customer: Excellent. Are fitness classes included?\n"
        "Officer: Most classes like yoga and aerobics are drop-in, but our indoor cycling spin class requires advance booking at least 24 hours ahead due to limited bikes.\n"
        "Customer: Understood. What about the changing room lockers and indoor court shoes?\n"
        "Officer: Lockers use a returnable one-pound coin deposit, so you get your money back. And please remember that in the badminton courts, members must wear clean sports shoes with non-marking rubber soles."
    ),
    9: (
        "Narrator: Welcome to the University Central Library Orientation Tour. Please listen carefully as we guide you through our research facilities.\n\n"
        "Librarian: Good afternoon, everyone! On the Ground Floor, you will find our main circulation desk, self-service borrowing machines, and the general computer lab with high-speed printing.\n"
        "Moving up to the Second Floor, we host our main book collection and collaborative group study rooms.\n"
        "However, if you require absolute quiet for concentration, please head up to the Third Floor. Level 3 is reserved strictly for silent research and individual study pods.\n"
        "Regarding borrowing allowances: undergraduate students may borrow up to 10 items, whereas postgraduate researchers are entitled to borrow up to 15 books simultaneously for a duration of four weeks.\n"
        "Finally, please note that our interlibrary loan service with partner institutions across the country is completely free of charge for all enrolled students.\n"
        "Thank you, and happy researching!"
    ),
    10: (
        "Narrator: You will hear a radio interview with Dr. Marcus Vance, a municipal urban transport planner.\n\n"
        "Interviewer: Dr. Vance, your team recently published an evaluation of the city's green mobility policy. What were the most noticeable results?\n"
        "Dr. Vance: The headline outcome was that two years after introducing the inner-city congestion charge, passenger vehicle traffic in the central district dropped by 24 percent.\n"
        "Interviewer: That is a substantial decrease. What is replacing those private car trips?\n"
        "Dr. Vance: Primarily public transit and cycling. To support this, the city council has committed to electrifying our entire municipal bus fleet by the year 2030.\n"
        "Interviewer: And how do commuters navigate between different transit modes?\n"
        "Dr. Vance: We constructed new multimodal transit interchanges. These hubs provide seamless, sheltered connections between trams, city buses, and secured bicycle parking. Furthermore, commuters no longer need paper tickets; our universal contactless payment system allows tapping with any smartphone or debit card."
    ),
    11: (
        "Narrator: You will hear part of a lecture on marine ecology and environmental change.\n\n"
        "Lecturer: Good morning, students. Today we examine the delicate symbiotic relationship that forms the backbone of coral reef ecosystems.\n"
        "Reef-building corals rely heavily on microscopic photosynthetic algae called zooxanthellae living within their tissues.\n"
        "Under normal conditions, these algae supply up to 90 percent of the coral host's nutritional energy requirements through photosynthesis.\n"
        "However, this partnership is highly vulnerable to thermal anomalies. When sea surface temperatures rise even one or two degrees Celsius above historical summer averages, the coral experiences thermal stress.\n"
        "In response, the coral expels the zooxanthellae. Because coral tissue is naturally translucent, shedding the pigmented algae exposes the stark white calcium carbonate skeleton beneath—a process known as coral bleaching.\n"
        "Crucially, bleaching is not an instantaneous death sentence. If ambient water temperatures return to baseline within several weeks, bleached corals can reabsorb symbiotic microalgae and make a full recovery."
    ),
    12: (
        "Narrator: You will hear an archaeologist delivering a keynote presentation on modern remote sensing techniques.\n\n"
        "Speaker: Good morning, colleagues. Over the past decade, aerial LiDAR—which stands for Light Detection and Ranging—has utterly transformed Mesoamerican archaeology.\n"
        "Historically, ancient structures beneath thick rainforest canopies required arduous ground expeditions. Airborne LiDAR overcomes this by firing hundreds of thousands of laser pulses per second from an aircraft. While the majority bounce off the foliage, enough photons filter through gaps in the leaves to measure ground topography.\n"
        "Specialized computer algorithms then strip away the vegetation returns to generate a digital bare-earth terrain model.\n"
        "When we applied this in northern Guatemala, the findings overturned decades of scholarly assumptions. Instead of isolated jungle settlements, LiDAR revealed massive interconnected urban networks. Most impressively, we discovered vast networks of terraced agricultural hillsides and sophisticated irrigation canals, proving that ancient populations sustained complex farming at an unprecedented scale."
    ),
}

# Cau hinh file xuat cho 9 bai
OUTPUT_FILES = {
    7: {"mp3": "audio_exercise_1.mp3", "wav": "audio_exercise_1.wav"},
    8: {"mp3": "audio_exercise_2.mp3", "wav": "audio_exercise_2.wav"},
    9: {"mp3": "audio_exercise_3.mp3", "wav": "audio_exercise_3.wav"},
    10: {"mp3": "audio_exercise_4.mp3", "wav": "audio_exercise_4.wav"},
    11: {"mp3": "audio_exercise_5.mp3", "wav": "audio_exercise_5.wav"},
    12: {"mp3": "audio_exercise_6.mp3", "wav": "audio_exercise_6.wav"},
    16: {"mp3": "mock_listening_01.mp3"},
    17: {"mp3": "mock_listening_02.mp3"},
    18: {"mp3": "mock_listening_03.mp3"},
}


def parse_turns(ex_id, transcript):
    """Phân vai và trích xuất các lượt thoại (turns) từ transcript."""
    mapping = EXERCISE_SPEAKER_MAP[ex_id]
    turns = []
    lines = [line.strip() for line in transcript.split("\n") if line.strip()]
    current_voice = mapping.get("default", VOICE_MALE)

    for line in lines:
        matched = False
        for speaker_name, voice in mapping.items():
            if speaker_name == "default":
                continue
            prefix = speaker_name + ":"
            if line.startswith(prefix):
                content = line[len(prefix):].strip()
                turns.append((voice, content))
                current_voice = voice
                matched = True
                break
        if not matched:
            turns.append((current_voice, line))

    # Nối các lượt thoại liên tiếp của cùng một nhân vật
    merged = []
    for voice, text in turns:
        if merged and merged[-1][0] == voice:
            merged[-1] = (voice, merged[-1][1] + "\n\n" + text)
        else:
            merged.append((voice, text))
    return merged


async def synthesize_turn(text, voice, max_retries=5):
    """Sinh am thanh cho mot luot thoai qua edge-tts voi co che thu lai."""
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


def convert_mp3_to_wav(mp3_path, wav_path):
    """Chuyen doi MP3 sang WAV de tuong thich tuyet doi."""
    try:
        import miniaudio
        decoded = miniaudio.decode_file(str(mp3_path))
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(decoded.nchannels)
            wf.setsampwidth(decoded.sample_width)
            wf.setframerate(decoded.sample_rate)
            wf.writeframes(decoded.samples)
        return True
    except Exception as e:
        print(f"      [Canh bao] Chuyen doi WAV bang miniaudio khong thanh cong: {e}")
        with open(mp3_path, "rb") as f_in, open(wav_path, "wb") as f_out:
            f_out.write(f_in.read())
        return False


async def generate_exercise_audio(ex_id, title, transcript, media_dir, force=False):
    """Sinh toan bo turns va ghep noi thanh file hoan chinh."""
    file_info = OUTPUT_FILES[ex_id]
    mp3_file = media_dir / file_info["mp3"]
    wav_file = media_dir / file_info["wav"] if "wav" in file_info else None

    # Kiem tra neu file da duoc tao hop le va khong co co force
    if not force and mp3_file.exists() and mp3_file.stat().st_size > 0:
        # Neu la mock 03 (chua tao moi) thi tiep tuc tao
        if ex_id == 18 and mp3_file.stat().st_size > 5000000:
            pass  # Day la file cu, can sinh lai
        elif wav_file is None or (wav_file.exists() and wav_file.stat().st_size > 0):
            print(f"\n[OK] Bai {ex_id}: {title} da co audio hop le, bo qua ({mp3_file.name}).")
            return

    print(f"\n[+] Dang tao audio cho Bai {ex_id}: {title}...")
    turns = parse_turns(ex_id, transcript)
    print(f"    - So luot thoai (turns): {len(turns)}")

    audio_segments = []
    for idx, (voice, text) in enumerate(turns, 1):
        voice_short = "Ryan (Male)" if "Ryan" in voice else "Sonia (Female)"
        first_words = text[:45].replace("\n", " ")
        print(f"      Turn {idx:02d}/{len(turns):02d} [{voice_short}]: {first_words}...")
        audio_data = await synthesize_turn(text, voice)
        audio_segments.append(audio_data)

    complete_mp3 = b"".join(audio_segments)
    with open(mp3_file, "wb") as f:
        f.write(complete_mp3)
    print(f"    -> Da luu MP3: {mp3_file.name} ({len(complete_mp3):,} bytes)")

    if "wav" in file_info:
        wav_file = media_dir / file_info["wav"]
        convert_mp3_to_wav(mp3_file, wav_file)
        wav_size = wav_file.stat().st_size
        print(f"    -> Da luu WAV: {wav_file.name} ({wav_size:,} bytes)")



def main():
    media_dir = BASE_DIR / "media" / "listening"
    media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Chuan bi du lieu tu Database ben ngoai asyncio
    print("==========================================================")
    print(" BƯỚC 1: ĐỌC DỮ LIỆU & ĐỒNG BỘ TRANSCRIPT TỪ DATABASE")
    print("==========================================================")
    exercises_data = []
    for ex_id in [7, 8, 9, 10, 11, 12, 16, 17, 18]:
        try:
            ex = Exercise.objects.get(id=ex_id)
            transcript = ex.transcript.strip() if ex.transcript else ""
            if not transcript and ex_id in FALLBACK_TRANSCRIPTS:
                transcript = FALLBACK_TRANSCRIPTS[ex_id]
                ex.transcript = transcript
                ex.save(update_fields=["transcript"])
                print(f"[OK] Da dong bo fallback transcript cho bai {ex_id}")
            exercises_data.append({
                "id": ex.id,
                "title": ex.title,
                "transcript": transcript,
            })
            print(f"[OK] Lay du lieu Bai {ex_id}: {ex.title} ({len(transcript)} ky tu)")
        except Exercise.DoesNotExist:
            print(f"[Canh bao] Khong tim thay Exercise ID {ex_id} trong database!")

    # 2. Sinh audio bang edge-tts qua asyncio.run()
    print("\n==========================================================")
    print(" BƯỚC 2: SINH AUDIO QUA EDGE-TTS (BRITISH ENGLISH)")
    print("==========================================================")
    force_mode = "--force" in sys.argv
    async def run_all():
        for item in exercises_data:
            await generate_exercise_audio(item["id"], item["title"], item["transcript"], media_dir, force=force_mode)

    asyncio.run(run_all())

    # 3. Cap nhat Django ORM (Thuc hien ngoai asyncio de tranh loi SynchronousOnlyOperation)
    print("\n==========================================================")
    print(" BƯỚC 3: CẬP NHẬT TRƯỜNG AUDIO_FILE TRONG DATABASE")
    print("==========================================================")
    for ex_id, file_info in OUTPUT_FILES.items():
        try:
            ex = Exercise.objects.get(id=ex_id)
            new_audio_file = f"listening/{file_info['mp3']}"
            ex.audio_file = new_audio_file
            ex.save(update_fields=["audio_file"])
            print(f"[OK] Exercise ID {ex_id} ({ex.title}) -> audio_file: {new_audio_file}")
        except Exercise.DoesNotExist:
            print(f"[Loi] Khong tim thay Exercise {ex_id} de cap nhat database!")

    print("\n==========================================================")
    print(" HOÀN TẤT NÂNG CẤP TOÀN BỘ 9 FILE AUDIO LISTENING!")
    print("==========================================================")


if __name__ == "__main__":
    main()
