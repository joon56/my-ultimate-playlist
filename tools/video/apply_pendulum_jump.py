"""점프·진자 영상 판독 결과를 data/video_checks.csv와 data/video_markers.csv에 넣는다(D-84).

사용(저장소 맨 위에서): python -I tools/video/apply_pendulum_jump.py <판독 출력 폴더> [무릎 올림 비율, 기본 0.25]
입력: <출력 폴더>/<영상 이름>_jumps.json(jump_read.py), swing_results.json(swing_read.py), knee_results_<비율>.json(knee_read.py)
시행과 영상은 기록지(exp2_trials.csv의 J 줄, exp3_swings.csv)의 video_file로 잇는다.
이 도구가 쓴 줄(measurer가 아래 MEASURER인 줄)만 새로 쓰고, 사람이 넣은 다른 줄은 그대로 둔다.
"""
import csv
import json
import sys
from pathlib import Path

MEASURER = "Claude Code(tools/video)"
CHECK_COLS = ["trial_id", "kind", "event_no", "video_file", "fps", "frames", "value_s", "measurer", "notes"]
MARK_COLS = ["trial_id", "event", "event_no", "video_file", "frame_no", "hip_x", "hip_y", "knee_x", "knee_y", "ankle_x", "ankle_y",
             "measurer", "notes"]


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))


def write(path: Path, cols: list[str], rows: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    out = Path(sys.argv[1])
    ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    data = Path("data")
    jump_trials = {r["video_file"]: r for r in read(data / "exp2_trials.csv") if r.get("ratio_pct") == "J" and r.get("video_file")}
    swing_trials = {r["video_file"]: r for r in read(data / "exp3_swings.csv") if r.get("video_file")}
    checks, marks = [], []
    for vf, tr in sorted(jump_trials.items()):
        f = out / f"{Path(vf).stem}_jumps.json"
        if not f.exists():
            continue
        pf = out / f"{Path(vf).stem}_pairing.json"  # 센서가 센 점프와 짝지은 번호(D-87). 없으면 영상의 순서 그대로
        pairing = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else None
        for j in json.loads(f.read_text(encoding="utf-8"))["jumps"]:
            no, extra = j["jump_no"], ""
            if pairing:
                if str(no) in pairing.get("unread", {}) or str(no) not in pairing["pairs"]:
                    continue  # 짝이 없거나 읽지 못한 영상 점프는 줄을 만들지 않고 note에만 남긴다
                extra = f" 영상의 {no}번째 점프. {pairing.get('note', '')}".rstrip()
                no = pairing["pairs"][str(no)]
            checks.append(dict(trial_id=tr["trial_id"], kind="jump_flight", event_no=no, video_file=vf, fps=tr.get("video_fps", ""),
                               frames="", value_s=f"{j['flight_s']:.3f}", measurer=MEASURER,
                               notes=f"영상 시각 이륙 {j['takeoff_s']:.3f} s, 착지 {j['landing_s']:.3f} s(신발 아래 끝 높이의 꺾이는 점, D-84). "
                                     f"프레임 간격이 고르지 않아 프레임 수 대신 시각 차를 적음{extra}"))
    sw = {r["stem"]: r for r in json.loads((out / "swing_results.json").read_text(encoding="utf-8"))} if (out / "swing_results.json").exists() else {}
    for vf, tr in sorted(swing_trials.items(), key=lambda kv: kv[1]["trial_id"]):
        r = sw.get(Path(vf).stem)
        if not r:
            continue
        n = (r["max"]["n_extremes"], r["min"]["n_extremes"])
        if r["swing10_s"] is None:
            print(f"{tr['trial_id']}: 영상의 이어진 흔들림 끝점이 {n[0]}/{n[1]}개라 swing_10을 내지 않음")
            continue
        part = ", ".join(f"{name} {r[key]['swing10_s']:.3f} s(끝점 {r[key]['used'][0] + 1}–{r[key]['used'][1] + 1}번째)"
                         for key, name in (("max", "한쪽 끝"), ("min", "반대쪽 끝")) if r[key]["swing10_s"] is not None)
        checks.append(dict(trial_id=tr["trial_id"], kind="swing_10", event_no=1, video_file=vf, fps=tr.get("video_fps", ""), frames="",
                           value_s=f"{r['swing10_s']:.3f}", measurer=MEASURER,
                           notes=f"노랑 테이프 위치의 끝점 사이 시간(D-84): {part}{'의 평균' if ', ' in part else ''}. "
                                 f"영상의 이어진 흔들림 끝점 {n[0]}/{n[1]}개"))
    kf = out / f"knee_results_{ratio:.2f}.json"
    kn = json.loads(kf.read_text(encoding="utf-8")) if kf.exists() else {}
    for vf, tr in sorted(swing_trials.items(), key=lambda kv: kv[1]["trial_id"]):
        k = kn.get(Path(vf).stem)
        if not k or tr.get("knee") != "bent":
            continue
        for r in k["rows"]:
            marks.append(dict(trial_id=tr["trial_id"], event="pendulum_bent", event_no=r["event_no"], video_file=vf, frame_no=r["frame_no"],
                              hip_x=f"{r['hip'][0]:.1f}", hip_y=f"{r['hip'][1]:.1f}", knee_x=f"{r['knee'][0]:.1f}", knee_y=f"{r['knee'][1]:.1f}",
                              ankle_x=f"{r['ankle'][0]:.1f}", ankle_y=f"{r['ankle'][1]:.1f}", measurer=MEASURER,
                              notes=f"t = {r['t']:.2f} s. hip = 빨강 테이프 높이에서 {k['info']['drop_px']:.0f} px 내린 점(좌우는 무릎 호에 맞춤), "
                                    f"knee = 파랑 테이프 중심({r['blue'][0]:.0f}, {r['blue'][1]:.0f})에서 정강이 축으로 "
                                    f"{k['info']['delta_px']:.0f} px 올린 점, ankle = 노랑 테이프 중심(D-84)"))
    keep_c = [r for r in read(data / "video_checks.csv") if r.get("measurer") != MEASURER]
    keep_m = [r for r in read(data / "video_markers.csv") if r.get("measurer") != MEASURER]
    write(data / "video_checks.csv", CHECK_COLS, keep_c + checks)
    write(data / "video_markers.csv", MARK_COLS, keep_m + marks)
    print(f"video_checks.csv: 그대로 둔 줄 {len(keep_c)}, 쓴 줄 {len(checks)} | video_markers.csv: 그대로 둔 줄 {len(keep_m)}, 쓴 줄 {len(marks)}")


if __name__ == "__main__":
    main()
