import json
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel


WORK = Path(__file__).resolve().parent
MODEL = WhisperModel(
    "small", device="cpu", compute_type="int8",
    cpu_threads=4, local_files_only=True,
)
for name, start, end in [("hat", 1490, 1518), ("cream", 1604, 1634)]:
    audio = WORK / f"{name}_source.wav"
    if not audio.exists():
        subprocess.run(
            ["ffmpeg", "-v", "error", "-n", "-ss", str(start), "-t", str(end - start),
             "-i", str(WORK / "long.mp4"), "-vn", "-ar", "16000", "-ac", "1", str(audio)],
            check=True,
        )
    segments, _ = MODEL.transcribe(
        str(audio), language="ko", beam_size=5, word_timestamps=True,
        condition_on_previous_text=False,
    )
    result = []
    for segment in segments:
        item = {
            "start": round(start + segment.start, 3),
            "end": round(start + segment.end, 3),
            "text": segment.text,
            "words": [
                {"start": round(start + word.start, 3),
                 "end": round(start + word.end, 3), "word": word.word}
                for word in segment.words
            ],
        }
        result.append(item)
        print(f"{item['start']:.3f}-{item['end']:.3f}: {item['text']}", flush=True)
    path = WORK / f"{name}_local_transcript.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
