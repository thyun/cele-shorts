import importlib
import os
import pycapcut as cc
from pycapcut import trange, tim
plan = importlib.import_module(os.environ.get("SHORTS_PLAN", "plan"))
SHORTS, SRC = plan.SHORTS, plan.SRC

ROOT = os.path.abspath(os.environ.get("SHORTS_DRAFTS", "../output/capcut_drafts"))
os.makedirs(ROOT, exist_ok=True)
SRC_ABS = os.path.abspath(SRC)
CROP_W, CROP_H = 0.4, 0.75
SPEED = float(os.environ.get("SHORTS_SPEED", "1"))
END_FADE = float(os.environ.get("SHORTS_END_FADE", "0"))
if SPEED <= 0:
    raise ValueError("SHORTS_SPEED must be positive")

folder = cc.DraftFolder(ROOT)

for s in SHORTS:
    script = folder.create_draft(s["id"], 1080, 1920, fps=30, allow_replace=False)
    script.add_track(cc.TrackType.video, "main")
    script.add_track(cc.TrackType.text, "title")
    script.add_track(cc.TrackType.text, "caption")

    segs = s["segments"]
    offs, acc = [], 0.0
    for a, b, _ in segs:
        offs.append(acc)
        acc += round((b - a) * 1_000_000 / SPEED) / 1_000_000
    total = acc

    for i, ((a, b, cx), o) in enumerate(zip(segs, offs)):
        x0 = max(0.0, min(1 - CROP_W, cx - CROP_W / 2))
        crop = cc.CropSettings(
            upper_left_x=x0, upper_left_y=0.0,
            upper_right_x=x0 + CROP_W, upper_right_y=0.0,
            lower_left_x=x0, lower_left_y=CROP_H,
            lower_right_x=x0 + CROP_W, lower_right_y=CROP_H,
        )
        mat = cc.VideoMaterial(SRC_ABS, crop_settings=crop)
        seg = cc.VideoSegment(
            mat,
            trange(tim(f"{o}s"), tim(f"{(b-a)/SPEED}s")),
            source_timerange=trange(tim(f"{a}s"), tim(f"{b-a}s")),
            speed=SPEED,
        )
        seg.add_background_filling("blur", 0.75)
        if END_FADE and i == len(segs) - 1:
            seg.add_fade(0, round(END_FADE * 1_000_000))
        script.add_segment(seg, "main")

    def to_out(t):
        for (a, b, _), o in zip(segs, offs):
            if a - 1e-6 <= t <= b + 1e-6:
                return o + (t - a) / SPEED

    title = cc.TextSegment(
        s["title"], trange(tim("0s"), tim(f"{total}s")),
        style=cc.TextStyle(size=9.0, bold=True, color=(1, 1, 1), align=1),
        clip_settings=cc.ClipSettings(transform_y=0.72),
        background=cc.TextBackground(color="#FF3B5C", alpha=0.93, round_radius=0.3, height=0.25, width=0.25),
        border=cc.TextBorder(color=(0, 0, 0), width=30.0),
    )
    script.add_segment(title, "title")

    for a, b, t in s["captions"]:
        oa, ob = to_out(a), to_out(b)
        start_us, end_us = round(oa * 1_000_000), round(ob * 1_000_000)
        cap = cc.TextSegment(
            t, trange(start_us, end_us - start_us),
            style=cc.TextStyle(size=8.0, bold=True, color=(1, 1, 1), align=1),
            clip_settings=cc.ClipSettings(transform_y=-0.62),
            border=cc.TextBorder(color=(0, 0, 0), width=40.0),
        )
        script.add_segment(cap, "caption")

    script.save()
    print("saved", s["id"], f"{total:.1f}s")
