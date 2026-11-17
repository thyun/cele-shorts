import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shorts"))
from cli import validate_visual_options
from crop import segment_crop


class VisualOptionsTests(unittest.TestCase):
    def test_editorial_position(self):
        short = {"id": "test", "segments": [[10, 15, 0.5]]}
        for position in ("top", "bottom"):
            validate_visual_options(short | {"editorial_position": position})
        with self.assertRaises(ValueError):
            validate_visual_options(short | {"editorial_position": "middle"})

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

    def test_segment_crops_override_only_selected_geometry(self):
        short = {
            "id": "test", "segments": [[10, 15, 0.5], [20, 25, 0.5]],
            "crop_width": 0.45, "crop_height": 0.8,
            "segment_crops": [{}, {"width": 0.4, "height": 0.7, "top": 0.1}],
        }
        validate_visual_options(short)
        self.assertEqual(segment_crop(short, 0), (0.45, 0.8, 0))
        self.assertEqual(segment_crop(short, 1), (0.4, 0.7, 0.1))

    def test_segment_crops_reject_wrong_count_and_out_of_bounds(self):
        short = {"id": "test", "segments": [[10, 15, 0.5]]}
        for crops in (None, [], [{}, {}], [None], [{"left": 0.2}],
                      [{"width": 0}], [{"height": 0.8, "top": 0.3}],
                      [{"top": -0.1}], [{"top": float("nan")}],
                      [{"height": float("nan")}], [{"width": "wide"}]):
            with self.subTest(crops=crops), self.assertRaises(ValueError):
                validate_visual_options(short | {"segment_crops": crops})

    def test_note_must_fit_one_selected_segment(self):
        for note in ([12, 21, "구간을 넘는 해설"], [10, 10, "빈 구간"],
                     [9, 12, "범위 밖"], [10, 12, " "], [10, 12, "두\n줄"]):
            with self.subTest(note=note), self.assertRaises(ValueError):
                validate_visual_options({
                    "id": "test", "segments": [[10, 15, 0.5], [20, 25, 0.5]],
                    "editorial_notes": [note],
                })

    def test_visual_labels_require_visible_positions_and_one_segment(self):
        short = {"id": "test", "segments": [[10, 15, 0.5], [20, 25, 0.5]]}
        validate_visual_options(short | {"visual_labels": [[10, 15, "filter", 0.5, 0.5]]})
        for label in ([10, 15, "filter", -0.1, 0.5], [10, 15, "filter", 0.5, float("nan")],
                      [14, 21, "filter", 0.5, 0.5], [10, 15, " ", 0.5, 0.5]):
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_visual_options(short | {"visual_labels": [label]})


if __name__ == "__main__":
    unittest.main()
