import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORK = Path(__file__).resolve().parent
SOURCE = WORK.parents[1] / "2026-11-10/sooyoung/long.mp4"
FRAMES = WORK / "source_frames"
FRAMES.mkdir(exist_ok=True)
FONT = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 22)
GROUPS = {
    "hat": [1476, 1480, 1487, 1493, 1498, 1502, 1505, 1508, 1510, 1513],
    "cream": [1603, 1606, 1609, 1612, 1616, 1621, 1625, 1628, 1631, 1634],
    "lip": [1863, 1867, 1871, 1876, 1880, 1884, 1888, 1893, 1897, 1903, 1908, 1913],
}
for name, times in GROUPS.items():
    sheet = Image.new("RGB", (1920, ((len(times) + 2) // 3) * 390), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, timestamp in enumerate(times):
        frame = FRAMES / f"{name}_{timestamp}.jpg"
        if not frame.exists():
            subprocess.run(
                ["ffmpeg", "-v", "error", "-n", "-ss", str(timestamp), "-i",
                 str(SOURCE), "-frames:v", "1", "-q:v", "2", str(frame)],
                check=True,
            )
        with Image.open(frame) as image:
            image = image.resize((640, 360))
            x, y = index % 3 * 640, index // 3 * 390
            sheet.paste(image, (x, y))
            draw.text((x + 10, y + 361), f"{timestamp // 60:02d}:{timestamp % 60:02d}", font=FONT)
    sheet.save(FRAMES / f"{name}_sheet.jpg")
print(json.dumps({"source": str(SOURCE), "sheets": list(GROUPS)}, indent=2))
