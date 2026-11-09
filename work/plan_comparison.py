from copy import deepcopy
from plan_hooks_20s import SHORTS as ORIGINAL, SRC

SHORTS = deepcopy(ORIGINAL)
SHORTS[0]["highlight_color"] = (1.0, 0.84, 0.20)
SHORTS[0]["outro_video"] = "../output/comparison_20261110/assets/cushion_outro.mp4"
SHORTS[1]["highlight_color"] = (1.0, 0.64, 0.75)
SHORTS[1]["title"] = "티파니가 15년째 찾는\n이런 타입의 립밤"
SHORTS[1]["title_highlights"] = ["15년째", "립밤"]
SHORTS[2]["highlight_color"] = (0.50, 0.94, 0.81)
