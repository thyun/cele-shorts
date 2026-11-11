import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shorts"))
from cli import validate_visual_options


class VisualOptionsTests(unittest.TestCase):
    def test_existing_plan_and_valid_options(self):
        short = {"id": "test", "segments": [[10, 15, 0.5], [20, 25, 0.5]]}
        validate_visual_options(short)
        validate_visual_options(short | {
            "crop_width": 0.8, "editorial_notes": [[10, 15, "내 용도부터 확인"]],
        })
        validate_visual_options(short | {"crop_width": 0.5625, "crop_height": 1.0})

    def test_invalid_crop_height(self):
        for height in (0, -0.1, 1.1, "full", float("nan")):
            with self.subTest(height=height), self.assertRaises(ValueError):
                validate_visual_options({
                    "id": "test", "segments": [[10, 15, 0.5]], "crop_height": height,
                })

    def test_invalid_crop_width(self):
        for width in (0, -0.1, 1.1, "wide", float("nan")):
            with self.subTest(width=width), self.assertRaises(ValueError):
                validate_visual_options({
                    "id": "test", "segments": [[10, 15, 0.5]], "crop_width": width,
                })

    def test_note_must_fit_one_selected_segment(self):
        for note in ([12, 21, "구간을 넘는 해설"], [10, 10, "빈 구간"],
                     [9, 12, "범위 밖"], [10, 12, " "], [10, 12, "두\n줄"]):
            with self.subTest(note=note), self.assertRaises(ValueError):
                validate_visual_options({
                    "id": "test", "segments": [[10, 15, 0.5], [20, 25, 0.5]],
                    "editorial_notes": [note],
                })


if __name__ == "__main__":
    unittest.main()
