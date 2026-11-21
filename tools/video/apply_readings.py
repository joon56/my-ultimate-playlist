"""판독 결과(collect.py의 표)를 기록지와 판독 내역 표에 넣는다(D-83). 사용(저장소 맨 위에서): python -I tools/video/apply_readings.py <판독 출력 폴더>/collected.csv

- data/video_exp2.csv: 시행마다 화면상 통과 시각, d·k, t30, 걸음 수, 걷기/뛰기 판정과 근거(새로 쓴다)
- data/exp2_trials.csv: t30_s, steps_N, gait_video, direction을 채우고 notes에 판독 메모를 붙인다
"""
import csv
import sys
from pathlib import Path

D_M, CAM_M = 0.9, 15.0          # 걷는 줄과 물병 줄의 간격, 카메라에서 물병 줄까지(m). k = 1 − D_M ÷ CAM_M
GAIT = {  # 메인 영상 가운데 6걸음의 디딤 시작 프레임: 뒷발이 땅에 있으면 walk, 이미 떠 있으면 run, 가를 수 없으면 빈칸
    "A": {"S": "walk", "100": "walk", "120": "walk", "135": "walk", "150": "walk", "165": "", "180": "run"},
    "B": {"S": "walk", "100": "walk", "120": "walk", "135": "walk", "150": "walk", "165": "", "180": "run", "195": "run"},
}
NOTE = {
    "165": "걷기/뛰기 판정 불가: 앞발 착지와 뒷발 이탈이 같은 프레임(±1)이라 60 fps로 가를 수 없음",
}
EXTRA = {
    "E2_B_165_2": "영상 걸음 수 ±1–2 불확실(간격이 불규칙한 디딤 1개)",
    "E2_B_180_1": "영상 걸음 수 ±1–2 불확실(간격이 불규칙한 디딤 4개)",
    "E2_B_195_2": "35 m 쪽 통과 시각은 디딤 줄을 늘려 읽음(출발 직후 디딤이 흐림), 5걸음 채움, 영상 걸음 수 ±2 불확실",
}
src = Path(sys.argv[1])
read = {r["trial_id"]: r for r in csv.DictReader(open(src, encoding="utf-8"))}
k = round(1 - D_M / CAM_M, 3)
sheet_p = Path("data/exp2_trials.csv")
rows = list(csv.DictReader(open(sheet_p, encoding="utf-8-sig", newline="")))
cols = list(rows[0].keys())
out = []
for r in rows:
    v = read.get(r["trial_id"])
    if v is None:
        continue
    assert abs(float(v["k"]) - k) < 1e-9, (v["k"], k)
    gait = GAIT[r["runner"]][r["ratio_pct"]]
    notes = [x for x in (NOTE.get(r["ratio_pct"]), EXTRA.get(r["trial_id"])) if x]
    r["t30_s"], r["steps_N"], r["gait_video"], r["direction"] = v["t30_s"], v["steps_N"], gait, v["direction"]
    for n in notes:
        if n not in r["notes"]:
            r["notes"] = ". ".join(x for x in (r["notes"].rstrip("."), n) if x)
    out.append(dict(trial_id=r["trial_id"], video_file=v["video_file"], direction=v["direction"], signal=v["mode"],
                    t_in_app_s=v["t_in_app_s"], t_out_app_s=v["t_out_app_s"], dt_app_s=v["dt_app_s"], d_m=D_M, k=k, t30_s=v["t30_s"],
                    steps_N=v["steps_N"], n_filled=v["n_filled"], n_irregular=v["n_irregular"],
                    cadence_interval_spm=v["cadence_interval_spm"], gait=gait,
                    gait_basis="메인 60 fps, 가운데 6걸음의 디딤 시작 프레임", flags=v["flags"], reader="vread3(2026-11-22)",
                    notes="; ".join(notes)))
with open(sheet_p, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
with open("data/video_exp2.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(out)
print(f"exp2_trials.csv: {len(out)}줄 채움 | video_exp2.csv: {len(out)}줄 | k = {k}")
