import json, subprocess, sys
from pathlib import Path
from faster_whisper import WhisperModel
WORK = Path(__file__).resolve().parent
MODEL = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
RANGES = [("morning",12,46),("hair1",46,96),("scalp",96,126),("leave",126,186),("ending",186,208)]
out = json.loads((WORK/"transcript.json").read_text()) if (WORK/"transcript.json").exists() else {}
for name, start, end in RANGES:
    if name in out: continue
    audio = WORK / f"{name}.wav"
    if not audio.exists():
        subprocess.run(["ffmpeg","-v","error","-n","-ss",str(start),"-t",str(end-start),"-i",str(WORK/"long.mp4"),"-vn","-ar","16000","-ac","1",str(audio)],check=True)
    segs,_ = MODEL.transcribe(str(audio), language="ko", beam_size=5, word_timestamps=True, condition_on_previous_text=False)
    res=[]
    for s in segs:
        res.append({"start":round(start+s.start,2),"end":round(start+s.end,2),"text":s.text,
                    "words":[[round(start+w.start,2),round(start+w.end,2),w.word] for w in s.words]})
        print(f"{res[-1]['start']:.2f}-{res[-1]['end']:.2f}:{s.text}",flush=True)
    out[name]=res
(WORK/"transcript.json").write_text(json.dumps(out,ensure_ascii=False,indent=1))
