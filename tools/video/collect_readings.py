"""판독 결과(vread2 출력)를 시행 표로 모은다. 사용(저장소 맨 위에서): python -I tools/video/collect_readings.py <판독 출력 폴더> [k]

k = 1 − d ÷ D (D-83 (2)). 실제 통과 구간은 화면상 구간을 양쪽으로 Δt_app × (1 − k) ÷ k의 절반씩 넓힌 것이다.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

O = Path(sys.argv[1])
K = float(sys.argv[2]) if len(sys.argv) > 2 else 0.940
rows = list(csv.DictReader(open("data/exp2_trials.csv", encoding="utf-8-sig")))
out = []
print(f"k = {K}")
print("trial        video    dir  mode    dt_app   t30    v     N  fill irr  cad_NT  cad_iv  overlap med [min,max] n   stance  dA   dB   flags")
for r in rows:
    if r["ratio_pct"] == "J":
        continue
    stem = r["video_file"].replace(".MOV", "")
    f = O / f"{stem}.json"
    if not f.exists():
        print(f"{r['trial_id']:<12} {stem:<8} NO RESULT")
        continue
    j = json.loads(f.read_text(encoding="utf-8"))
    if "dt_app_s" not in j:
        print(f"{r['trial_id']:<12} {stem:<8} FAILED {j['flags']}")
        continue
    ST = np.loadtxt(O / f"{stem}_stances.csv", delimiter=",", skiprows=1)  # t_contact, t_off, x, pixels, filled, sole
    t_in, t_out, dt = j["t_in_app_s"], j["t_out_app_s"], j["dt_app_s"]
    ext = dt * (1 - K) / K / 2
    a, b = t_in - ext, t_out + ext
    ins = (ST[:, 0] >= a) & (ST[:, 0] < b)
    n = int(ins.sum())
    t30 = dt / K
    tc = ST[ins, 0]
    cad_iv = 60 * (n - 1) / (tc.max() - tc.min()) if n > 2 else float("nan")
    ov, sd = [], []
    idx = np.flatnonzero((ST[:, 0] >= t_in) & (ST[:, 0] < t_out))
    for i in idx[:-1]:
        if ST[i, 4] == 0 and ST[i + 1, 4] == 0 and np.isfinite(ST[i, 1]):
            ov.append(ST[i, 1] - ST[i + 1, 0])
            sd.append(ST[i, 1] - ST[i, 0])
    ov, sd = np.array(ov), np.array(sd)
    edge_ok = (ST[:, 0].min() <= a) and (ST[:, 0].max() >= b - 0.001)
    g = lambda k: j.get(k) if j.get(k) is not None else float("nan")
    flags = list(j["flags"]) + ([] if edge_ok else ["window_beyond_stances"])
    row = dict(trial_id=r["trial_id"], video_file=r["video_file"], direction=j["direction"], mode=j["mode"], t_in_app_s=round(t_in, 3),
               t_out_app_s=round(t_out, 3), dt_app_s=round(dt, 3), k=K, t30_s=round(t30, 2), steps_N=n, n_filled=int(ST[ins, 4].sum()),
               n_irregular=len(j["irregular_at_s"]), cadence_N_over_t=round(n / t30 * 60, 1), cadence_interval_spm=round(cad_iv, 1),
               overlap_median_s=round(float(np.median(ov)), 3) if len(ov) else "", overlap_min_s=round(float(ov.min()), 3) if len(ov) else "",
               overlap_max_s=round(float(ov.max()), 3) if len(ov) else "", overlap_n=len(ov),
               stance_median_s=round(float(np.median(sd)), 3) if len(sd) else "",
               delta_px_at_A=round(g("delta_px_at_A"), 2), delta_px_at_B=round(g("delta_px_at_B"), 2), flags=";".join(flags))
    out.append(row)
    om = f"{np.median(ov):6.3f} [{ov.min():6.3f},{ov.max():6.3f}] {len(ov):2d}" if len(ov) else "   -"
    print(f"{r['trial_id']:<12} {stem:<8} {j['direction']}({r['direction']}) {j['mode']:<6} {dt:7.3f} {t30:6.2f} {30 / t30:5.2f} {n:4d} {row['n_filled']:3d} {row['n_irregular']:3d} "
          f"{row['cadence_N_over_t']:7.1f} {cad_iv:7.1f}  {om}  {np.median(sd) if len(sd) else float('nan'):5.3f} {g('delta_px_at_A'):4.1f} {g('delta_px_at_B'):4.1f}  {flags}")
if out:
    with open(O / "collected.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
