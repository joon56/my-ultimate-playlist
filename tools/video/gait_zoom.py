"""경계 시행의 걷기/뛰기 확인용: 가운데 두 걸음의 디딤 시작 앞뒤 4프레임(60 fps)을 발 주변만 크게 잘라 붙인다.
사용: python -I tools/video/gait_zoom.py <판독 출력 폴더> <그림 파일> <걸음 수> <앞뒤 프레임 수> <trial_id> ..."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FPS = 60000 / 1001
O, out = Path(sys.argv[1]), Path(sys.argv[2])
NS, HF = int(sys.argv[3]), int(sys.argv[4])  # 걸음 수, 앞뒤 프레임 수
tids = sys.argv[5:]
rows = {r["trial_id"]: r for r in csv.DictReader(open("data/exp2_trials.csv", encoding="utf-8-sig"))}
CW, CH, Z = 104, 64, 2.3
strips = []
for tid in tids:
    r = rows[tid]
    stem = r["video_file"].replace(".MOV", "")
    j = json.loads((O / f"{stem}.json").read_text(encoding="utf-8"))
    ST = np.loadtxt(O / f"{stem}_stances.csv", delimiter=",", skiprows=1)
    e0, e1 = j["edge"]
    mid = (j["t_in_app_s"] + j["t_out_app_s"]) / 2
    real = np.flatnonzero(ST[:, 4] == 0)
    i0 = real[np.argmin(np.abs(ST[real, 0] - mid))]
    lo = max(i0 - NS // 2 + (1 if NS % 2 == 0 else 0), 0)
    for i in range(lo, min(lo + NS, len(ST))):
        s = ST[i]
        strip = Image.new("RGB", (int(CW * Z) * (2 * HF + 1), int(CH * Z)))
        for n, df in enumerate(range(-HF, HF + 1)):
            x0 = int(np.clip(s[2] - CW / 2, 0, 1920 - CW)) // 2 * 2
            y0 = (int(e0 + e1 * s[2]) - CH + 16) // 2 * 2
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s[0] + df / FPS:.4f}", "-i", f"data/raw/data-vid/{stem}.MOV", "-vf",
                                  f"crop={CW}:{CH}:{x0}:{y0}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True).stdout
            if len(raw) < CW * CH * 3:
                continue
            im = Image.fromarray(np.frombuffer(raw, np.uint8).reshape(CH, CW, 3)).resize((int(CW * Z), int(CH * Z)), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            d.text((2, 1), (f"{tid} " if n == 0 else "") + f"{df:+d}", fill=(255, 255, 0))
            strip.paste(im, (n * int(CW * Z), 0))
        strips.append(strip)
sheet = Image.new("RGB", (strips[0].width, strips[0].height * len(strips)))
for k, st in enumerate(strips):
    sheet.paste(st, (0, st.height * k))
sheet.save(out, quality=90)
print(sheet.size)
