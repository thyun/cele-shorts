import re

HIGHLIGHT_RGB = (1.0, 0.88, 0.2)


def highlight_color(short):
    color = short.get("highlight_color", HIGHLIGHT_RGB)
    if len(color) != 3 or any(not 0 <= component <= 1 for component in color):
        raise ValueError(f"{short['id']}: highlight_color must be three values between 0 and 1")
    return tuple(color)


def title_parts(short):
    title = short["title"]
    lines = title.split("\n")
    if len(lines) != 2 or not all(line.strip() for line in lines):
        raise ValueError(f"{short['id']}: title must contain exactly two nonempty lines")
    keywords = short["title_highlights"]
    if not keywords or any(not word or "\n" in word or word not in title for word in keywords):
        raise ValueError(f"{short['id']}: provide title keywords present on one line")
    if not short["source"].strip() or "\n" in short["source"]:
        raise ValueError(f"{short['id']}: provide a single-line source")
    pattern = re.compile("|".join(re.escape(word) for word in sorted(keywords, key=len, reverse=True)))
    return [(line, [(m.start(), m.end()) for m in pattern.finditer(line)]) for line in lines]


def title_ranges(short):
    lines = title_parts(short)
    ranges = []
    offset = 0
    for line, spans in lines:
        ranges.extend((offset + start, offset + end) for start, end in spans)
        offset += len(line) + 1
    return ranges
