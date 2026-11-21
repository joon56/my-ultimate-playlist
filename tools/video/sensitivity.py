"""시차 보정 비율 k를 바꿨을 때 가설 3 판정이 달라지는지(D-83 (6)). 저장소의 기록지·결과는 건드리지 않고 임시 폴더에서 돌린다.
사용(저장소 맨 위에서): python -I tools/video/sensitivity.py <판독 출력 폴더> <임시 폴더> <k> [<k> ...]"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from walkmusic.config import load_params
from walkmusic.exp23 import Paths23, run_exp23

V, S = Path(sys.argv[1]), Path(sys.argv[2])
params = load_params("config/params.toml")
for k in sys.argv[3:]:
    subprocess.run([sys.executable, "-I", "-X", "utf8", "tools/video/collect_readings.py", str(V), k], check=True, capture_output=True)
    read = {r["trial_id"]: r for r in csv.DictReader(open(V / "collected.csv", encoding="utf-8"))}
    root = S / f"k{k}"
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    for f in Path("data").glob("*.csv"):
        shutil.copy(f, root / "data" / f.name)
    for name in ("participants.csv", "segments.csv", "prescription.csv"):
        if (Path("results") / name).exists():
            shutil.copy(Path("results") / name, root / "results" / name)
    rows = list(csv.DictReader(open("data/exp2_trials.csv", encoding="utf-8-sig", newline="")))
    for r in rows:
        if r["trial_id"] in read:
            r["t30_s"], r["steps_N"] = read[r["trial_id"]]["t30_s"], read[r["trial_id"]]["steps_N"]
    with open(root / "data" / "exp2_trials.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    try:
        run_exp23(Paths23(root / "data", Path("data/raw").resolve(), root / "results"), params, real=True)
    except ValueError as e:  # 실행 기록(run_info)은 원자료가 data 밖이라 못 쓴다: 표는 그 전에 다 쓰였다
        assert "is not in the subpath" in str(e), e
    h = pd.read_csv(root / "results" / "hypotheses_exp23.csv", dtype=str, keep_default_na=False)
    pc = pd.read_csv(root / "results" / "exp2_pc.csv")
    print(f"k = {k} | PC " + ", ".join(f"{r.runner} {r.pc_field_spm:.1f}" for r in pc.itertuples()))
    for r in h[h["hypothesis"] == "H3"].itertuples():
        print(f"   H3 {r.participant}: supported {r.supported} | {r.note}")
