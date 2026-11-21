"""걷기/뛰기 판정용 사진(D-83 (4)): 구간 가운데 연속 6걸음의 디딤 시작 프레임과 2프레임 뒤를 잘라 시행마다 한 줄로 붙인다.

사용(저장소 맨 위에서): python -I tools/video/gait_tiles.py <판독 출력 폴더> <그림 출력 폴더>
앞발이 닿은 순간에 뒷발이 땅에 있으면 두 발이 함께 닿은 프레임이 있는 것(걷기), 뒷발이 이미 떠 있으면 그 앞에 두 발이 다 뜬 프레임이 있는 것(뛰기)이다.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FPS = 60000 / 1001
O, G = Path(sys.argv[1]), Path(sys.argv[2])
G.mkdir(parents=True, exist_ok=True)
rows = [r for r in csv.DictReader(open("data/exp2_trials.csv", encoding="utf-8-sig")) if r["ratio_pct"] != "J"]
CW, CH, Z = 96, 96, 1.5
for person in ("A", "B"):
    strips = []
    for r in [x for x in rows if x["runner"] == person]:
        stem = r["video_file"].replace(".MOV", "")
        j = json.loads((O / f"{stem}.json").read_text(encoding="utf-8"))
        ST = np.loadtxt(O / f"{stem}_stances.csv", delimiter=",", skiprows=1)
        t_in, t_out = j["t_in_app_s"], j["t_out_app_s"]
        e0, e1 = j["edge"]
        mid = (t_in + t_out) / 2
        ins = np.flatnonzero((ST[:, 0] >= t_in) & (ST[:, 0] < t_out))
        c = ins[np.argsort(np.abs(ST[ins, 0] - mid))[:6]]
        c = np.arange(c.min(), c.min() + 6) if c.max() - c.min() == 5 else np.sort(c)  # 이어진 6걸음
        strip = Image.new("RGB", (int(CW * Z) * 12 + 150, int(CH * Z)))
        d = ImageDraw.Draw(strip)
        d.text((4, 4), f"{r['trial_id']}\n{r['bpm_played'] or 'silent'} BPM\n{stem}", fill=(255, 255, 0))
        for n, i in enumerate(c):
            s = ST[i]
            for m, dt in enumerate((0, 2 / FPS)):
                x0 = int(np.clip(s[2] - CW / 2, 0, 1920 - CW)) // 2 * 2
                y0 = (int(e0 + e1 * s[2]) - CH + 20) // 2 * 2
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s[0] + dt:.4f}", "-i", f"data/raw/data-vid/{stem}.MOV", "-vf",
                                      f"crop={CW}:{CH}:{x0}:{y0}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     capture_output=True).stdout
                if len(raw) < CW * CH * 3:
                    continue
                im = Image.fromarray(np.frombuffer(raw, np.uint8).reshape(CH, CW, 3)).resize((int(CW * Z), int(CH * Z)), Image.LANCZOS)
                dd = ImageDraw.Draw(im)
                dd.text((2, 1), f"{s[0]:.2f}{'*' if s[4] else ''}{'+2' if m else ''}", fill=(255, 255, 0))
                strip.paste(im, (150 + (2 * n + m) * int(CW * Z), 0))
        strips.append(strip)
    half = (len(strips) + 1) // 2
    for part, sel in enumerate((strips[:half], strips[half:]), 1):
        sheet = Image.new("RGB", (sel[0].width, sel[0].height * len(sel)))
        for k, st in enumerate(sel):
            sheet.paste(st, (0, st.height * k))
        sheet.save(G / f"gait_{person}_{part}.jpg", quality=88)
        print(person, part, sheet.size)
