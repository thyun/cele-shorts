import json
import subprocess


def source_dimensions(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    if not streams or not streams[0].get("width") or not streams[0].get("height"):
        raise ValueError(f"영상 크기를 확인할 수 없습니다: {path}")
    return streams[0]["width"], streams[0]["height"]


def segment_crop(short, index, source_size=None):
    crops = short.get("segment_crops")
    override = crops[index] if crops is not None else {}
    source_size = source_size or (16, 9)
    aspect = source_size[0] / source_size[1]
    square_width = min(1.0, 1 / aspect)
    square_height = min(1.0, aspect)
    square_top = (1 - square_height) / 2
    has_crop_override = "crop_width" in short or "crop_height" in short
    return (
        override.get("width", short.get("crop_width", square_width)),
        override.get("height", short.get("crop_height", square_height)),
        override.get("top", 0.0 if has_crop_override else square_top),
    )


def validate_crops(short):
    for key, default in (("crop_width", 0.4), ("crop_height", 0.75)):
        value = short.get(key, default)
        if not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise ValueError(f"{short['id']}: {key}는 0보다 크고 1 이하여야 합니다")
    if "segment_crops" in short:
        crops = short["segment_crops"]
        if not isinstance(crops, list) or len(crops) != len(short["segments"]):
            raise ValueError(f"{short['id']}: segment_crops는 영상 구간별 목록이어야 합니다")
        for crop in crops:
            if not isinstance(crop, dict) or set(crop) - {"width", "height", "top"}:
                raise ValueError(f"{short['id']}: 잘못된 구간 크롭 설정")
    for index in range(len(short["segments"])):
        width, height, top = segment_crop(short, index)
        if (not all(isinstance(value, (int, float)) for value in (width, height, top))
                or not (0 < width <= 1 and 0 < height <= 1 and 0 <= top <= 1 - height)):
            raise ValueError(f"{short['id']}: 구간 크롭이 원본 범위를 벗어납니다")
