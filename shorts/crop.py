def segment_crop(short, index):
    crops = short.get("segment_crops")
    override = crops[index] if crops is not None else {}
    return (
        override.get("width", short.get("crop_width", 0.4)),
        override.get("height", short.get("crop_height", 0.75)),
        override.get("top", 0.0),
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
