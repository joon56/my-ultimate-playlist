"""품질 검사 Q01–Q15와 관문 G1 (QA_CHECKLIST, SPEC §7).

결과: <results>/qa_summary.csv(회차×검사), <results>/qa/<walk_id>.json(상세), 관문은 <results>/gate_G1.csv,
zip 연결 제안은 <results>/zip_links.csv(D-27).
코드는 FAIL이어도 파일을 지우거나 분석에서 빼지 않는다. 좌표 값과 기기 이름은 어디에도 쓰지 않는다.
합성 데이터는 results_synthetic/에만 쓴다.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from walkmusic.config import ROOT, Params, load_params
from walkmusic.io_sensorlogger import Recording, interval_stats, read_zip
from walkmusic.links import expected_walk_id, fill_walk_ids, find_zip, sheet_time, write_zip_links
from walkmusic.orientation import angle_deg, median_direction
from walkmusic.steps import StepResult, analyze_recording, cadence_summary
from walkmusic.units import Units, UnitsError

R_EARTH = 6371008.8
WORST = {"PASS": 0, "NA": 0, "INFO": 1, "WARN": 2, "FAIL": 3}
REQUIRED = {"E1": ("Accelerometer", "Location"), "T": ("Accelerometer", "Location"),  # T는 E1과 같게(K-28)
            "E2": ("Accelerometer",), "E3": ("Gyroscope",)}


@dataclass
class Check:
    """검사 한 줄 (qa_summary.csv)."""

    walk_id: str
    check_id: str
    status: str
    value: str = ""
    threshold: str = ""
    note: str = ""


@dataclass
class Paths:
    """입력·출력 위치. 합성 데이터는 results_synthetic/ 아래에 따로 둔다."""

    raw: Path
    manifest: Path
    assignment: Path
    music: Path
    participants: Path
    sections: Path
    results: Path

    @classmethod
    def real(cls) -> Paths:
        d = ROOT / "data"
        return cls(d / "raw", d / "manifest.csv", d / "assignment.csv", d / "music_bpm.csv", d / "participants.csv",
                   d / "private" / "sections.csv", ROOT / "results")

    @classmethod
    def synthetic(cls) -> Paths:
        s = ROOT / "results_synthetic"
        d = s / "data"
        return cls(d / "raw", d / "manifest.csv", ROOT / "data" / "assignment.csv", d / "music_bpm.csv",
                   d / "participants.csv", d / "private" / "sections.csv", s)


@dataclass
class Walk:
    """회차 하나의 분석 결과."""

    walk_id: str
    row: dict
    zip_path: Path
    rec: Recording | None = None
    units: Units | None = None
    units_error: str = ""
    steps: StepResult | None = None
    u_dir: np.ndarray | None = None
    error: str = ""
    extra: dict = field(default_factory=dict)


def read_table(path: Path) -> pd.DataFrame:
    """CSV를 문자열 표로 읽는다(없으면 빈 표). 구글 시트의 BOM도 받는다."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def experiment_of(row: dict) -> str:
    e = row.get("experiment", "").strip().upper()
    return "T" if e == "TEST" else e


def analyze_walk(row: dict, paths: Paths, params: Params) -> Walk:
    """manifest 한 줄 → zip 읽기, 단위 판별, 걸음 검출."""
    w = Walk(row["walk_id"], row, find_zip(paths.raw, row))
    if not w.zip_path.exists():
        w.error = f"zip 없음: {w.zip_path.name}"
        return w
    w.rec = read_zip(w.zip_path, params)
    try:
        w.units, w.steps = analyze_recording(w.rec, params)
    except UnitsError as e:
        w.units_error = str(e)
        return w
    if w.rec.has("Gravity") and np.isfinite(w.steps.t_depart):
        tg = w.rec.t("Gravity")
        sel = (tg >= w.steps.t_depart) & (tg <= w.steps.t_arrive)
        if sel.sum() > 10:
            w.u_dir = median_direction(w.rec.xyz("Gravity")[sel])
    return w


def _hand_window(row: dict) -> tuple[float, float] | None:
    m = re.search(r"start=(\d+):(\d{2})\s+end=(\d+):(\d{2})", row.get("hand_step_note", ""))
    if not m:
        return None
    a, b, c, d = map(int, m.groups())
    return a * 60 + b, c * 60 + d


def _hav(lat1, lon1, lat2, lon2):
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(h))


def _section_gps_m(w: Walk, sec: pd.DataFrame, radius: float) -> float | None:
    """측정 구간 시작·끝 웨이포인트에 가장 가까이 지난 두 점 사이의 GPS 경로 길이(m). 좌표는 계산에만 쓴다."""
    loc = w.rec.sensors["Location"]
    t = loc["t_s"].to_numpy(float)
    sel = (t >= w.steps.t_depart) & (t <= w.steps.t_arrive)
    lat, lon = np.radians(loc["latitude"].to_numpy(float))[sel], np.radians(loc["longitude"].to_numpy(float))[sel]
    if len(lat) < 3:
        return None
    pts = sec.sort_values("seq", key=lambda s: s.astype(int))
    plat, plon = np.radians(pts["lat"].astype(float).to_numpy()), np.radians(pts["lon"].astype(float).to_numpy())
    d0, d1 = _hav(lat, lon, plat[0], plon[0]), _hav(lat, lon, plat[-1], plon[-1])
    i0, i1 = int(np.argmin(d0)), int(np.argmin(d1))
    if d0[i0] > radius or d1[i1] > radius:
        return None
    a, b = sorted((i0, i1))
    return float(np.sum(_hav(lat[a:b], lon[a:b], lat[a + 1:b + 1], lon[a + 1:b + 1])))


def check_walk(w: Walk, tables: dict[str, pd.DataFrame], params: Params) -> list[Check]:
    """회차 하나의 Q01–Q13 (Q14·Q15와 회차 사이 Q09 비교는 run_checks에서)."""
    exp, wid, row = experiment_of(w.row), w.walk_id, w.row
    out: list[Check] = []
    add = lambda cid, st, value="", thr="", note="": out.append(Check(wid, cid, st, str(value), str(thr), note))  # noqa: E731
    if w.rec is None:
        add("Q01", "FAIL", note=w.error)
        return out
    rec = w.rec
    # Q01 필수 파일
    req = REQUIRED.get(exp, ("Accelerometer",))
    miss = [n for n in req if not rec.has(n)]
    soft = [n for n in ("Gravity", "Gyroscope") if not rec.has(n)] + ([] if rec.meta else ["Metadata"])
    info = [] if rec.has("Pedometer") else ["Pedometer 없음"]
    others = [f"그 밖: {', '.join(rec.unknown)}"] if rec.unknown else []
    empties = [f"빈 파일: {', '.join(rec.empty)}"] if rec.empty else []
    st = "FAIL" if miss else "WARN" if soft else "INFO" if info else "PASS"
    add("Q01", st, ", ".join(f[:-4] for f in sorted(rec.files) if f.endswith(".csv")), ", ".join(req),
        "; ".join([f"필수 없음: {', '.join(miss)}"] * bool(miss) + [f"없음: {', '.join(soft)}"] * bool(soft)
                  + info + others + empties))
    if not rec.has("Accelerometer"):
        return out
    # Q02 샘플링
    s = interval_stats(rec.t("Accelerometer"), params["qa.gap_warn_s"], params["qa.gap_fail_s"])
    fs, setting = s["fs_hz"], rec.meta.get("sampleRateMs", "").split("|")[0]
    note = "" if fs >= params["qa.target_fs_hz"] else (
        f"INFO: 목표 {params['qa.target_fs_hz']:.0f} Hz보다 낮음"
        f"(설정 {setting or '?'} ms, 실제 {s['median_ms']:.3f} ms)")
    add("Q02", "FAIL" if fs < params["qa.min_fs_hz"] else "PASS", f"{fs:.2f}", params["qa.min_fs_hz"], note)
    # 걸음이 있어야 하는 검사
    stp = w.steps
    t_dep, t_arr = (stp.t_depart, stp.t_arrive) if stp is not None else (np.nan, np.nan)
    # Q03 끊김
    gaps = s["gaps"]
    walking_fail = [g for g in gaps if g[1] > params["qa.gap_fail_s"] and t_dep <= g[0] <= t_arr]
    st = "FAIL" if walking_fail else "WARN" if gaps else "PASS"
    add("Q03", st, len(gaps), f"{params['qa.gap_warn_s']}/{params['qa.gap_fail_s']} s",
        "; ".join(f"{d:.2f} s at t_s {t0:.1f}" for t0, d in gaps[:5]))
    # Q04 기록 길이
    ta = rec.t("Accelerometer")
    dur = ta[-1] - ta[0]
    if exp == "E1":
        add("Q04", "PASS" if dur >= params["qa.min_walk_duration_s"] else "FAIL", f"{dur:.1f}",
            params["qa.min_walk_duration_s"])
    else:
        add("Q04", "NA", f"{dur:.1f}", note="E1만 판정")
    # Q09 단위
    if w.units is None:
        add("Q09", "FAIL", note=w.units_error)
        return out
    u = w.units
    add("Q09", "PASS", f"{u.accel_units}, 중력 {'포함' if u.includes_gravity else '제외'}, 부호 {u.combine_sign:+d}",
        note=f"확신 {u.confidence}")
    stand = (f"시작 {stp.stand_start}, 끝 {stp.stand_end}, 출발 {t_dep:.1f} s, 도착 {t_arr:.1f} s"
             + (f", {', '.join(stp.flags)}" if stp.flags else ""))
    # Q05 시작·끝 서 있기(D-29)
    ok5 = stp.stand_start is not None and stp.stand_end is not None
    add("Q05", ("PASS" if ok5 else "WARN") if exp == "E1" else "NA", stand, f"≥ {params['exclude.stand_min_s']} s",
        "" if exp == "E1" else "E1만 판정")
    # Q06 직접 센 걸음
    win = _hand_window(row) or (t_dep, t_arr)
    det = len(stp.window_steps(*win))
    if exp in ("E1", "T") and row.get("hand_step_count", "").strip():
        hand = int(float(row["hand_step_count"]))
        add("Q06", "PASS" if abs(det - hand) <= params["qa.hand_count_tol_steps"] else "FAIL",
            f"검출 {det} / 직접 {hand}", f"±{params['qa.hand_count_tol_steps']}", f"창 {win[0]:.1f}–{win[1]:.1f} s")
    else:
        add("Q06", "NA", f"검출 {det}", note="직접 센 값 없음")
    # Q07 Pedometer(D-30 확정: 참고값이라 차이가 커도 INFO)
    if exp in ("E1", "T") and rec.has("Pedometer"):
        pt, pv = rec.t("Pedometer"), rec.sensors["Pedometer"]["steps"].to_numpy(float)
        inside = np.where((pt >= win[0]) & (pt <= win[1]))[0]
        if len(inside) >= 2:
            ua, ub = pt[inside[0]], pt[inside[-1]]
            ped = pv[inside[-1]] - pv[inside[0]]
            d7 = len(stp.window_steps(ua, ub))
            rel = (d7 - ped) / ped * 100 if ped else float("nan")
            add("Q07", "PASS" if abs(rel) <= params["qa.pedometer_tol_pct"] else "INFO",
                f"검출 {d7} / Pedometer {ped:.0f} ({rel:+.1f}%)", f"±{params['qa.pedometer_tol_pct']}%",
                f"갱신 {ua:.1f}–{ub:.1f} s. D-30: Pedometer는 기준이 아니다")
        else:
            add("Q07", "NA", note="창 안 Pedometer 갱신 부족")
    else:
        add("Q07", "NA", note="Pedometer 없음" if exp in ("E1", "T") else "E1·T만")
    # Q08 GPS
    if exp in ("E1", "T") and rec.has("Location"):
        sec = tables["sections"]
        sec = sec[sec.get("participant", pd.Series(dtype=str)) == row.get("participant")] if len(sec) else sec
        par = tables["participants"]
        prow = par[par["participant"] == row.get("participant")] if len(par) else par
        dist = float(prow["section_distance_m"].iloc[0]) if len(prow) and prow["section_distance_m"].iloc[0] else None
        gps = _section_gps_m(w, sec, params["speed.section_radius_m"]) if len(sec) >= 2 else None
        if dist and gps:
            rel = (gps - dist) / dist * 100
            add("Q08a", "PASS" if abs(rel) <= params["qa.gps_distance_tol_pct"] else "WARN",
                f"GPS {gps:.1f} m / 지도 {dist:.1f} m ({rel:+.1f}%)", f"±{params['qa.gps_distance_tol_pct']}%",
                "" if abs(rel) <= params["qa.gps_distance_tol_pct"] else "SPEC §5.5(e) 대안(D-26)")
        else:
            add("Q08a", "NA", note="구간 거리·웨이포인트 없음 또는 구간을 지나지 않음")
        hacc = float(np.nanmedian(rec.sensors["Location"]["horizontalAccuracy"].astype(float)))
        add("Q08b", "PASS" if hacc <= params["qa.gps_accuracy_warn_m"] else "WARN", f"{hacc:.2f}",
            params["qa.gps_accuracy_warn_m"])
    else:
        add("Q08a", "NA")
        add("Q08b", "NA")
    # Q10 zip ↔ manifest 연결(E1·T), Q11 배정표, Q12 곡 타임라인(E1)
    if exp in ("E1", "T"):
        out.append(_q10(w, tables, params))
    else:
        add("Q10", "NA", note="E1·T만 판정")
    if exp == "E1":
        out += _q11_q12(w, tables)
    else:
        for cid in ("Q11", "Q12"):
            add(cid, "NA", note="E1만 판정")
    # Q13 유효 걸음
    cs = cadence_summary(stp, params)
    add("Q13a", "NA", note="곡 구간은 Phase 2")
    bad = cs["bad_frac"]
    st13 = ("PASS" if bad <= params["qa.max_bad_interval_frac"] else "WARN") if exp in ("E1", "E2") else "NA"
    add("Q13b", st13, f"{bad:.3f}", params["qa.max_bad_interval_frac"],
        f"걸음 {cs['n_steps']}, rate {cs['cadence_rate_spm']:.1f} spm")
    w.extra.update(cadence=cs, stand=stand)
    return out


def _q10(w: Walk, tables: dict[str, pd.DataFrame], params: Params) -> Check:
    """Q10 zip ↔ manifest(D-27): 기록 시작 시각 ↔ 기록지 시각, zip 하나에 줄 하나, walk_id 규칙."""
    row, wid, exp, tol = w.row, w.walk_id, experiment_of(w.row), params["manifest.start_time_tol_s"]
    p, date = row.get("participant", ""), row.get("date", "")
    probs = []
    want = expected_walk_id(row)
    if exp == "E1" and wid != want:
        probs.append(f"walk_id가 규칙({want})과 다르다")
    if exp == "T" and not re.fullmatch(rf"TEST_{re.escape(p)}_{date[5:7]}{date[8:10]}(_.+)?", wid):
        probs.append(f"walk_id가 TEST_{p}_<MMDD>_<종류>가 아니다")
    man = tables.get("manifest", pd.DataFrame())
    if len(man):
        same = man[(man["zip_file"] == w.zip_path.name) & (man["participant"] == p)]
        if len(same) > 1:
            probs.append(f"같은 zip을 쓰는 manifest 줄이 {len(same)}개")
    t_sheet, value = sheet_time(row, params["time.timezone"]), ""
    if t_sheet is None:
        if exp == "T" and not probs:
            return Check(wid, "Q10", "NA", "", f"±{tol} s", "start_time이 비었다: 기록지의 시작 시각을 채운다")
        probs.append("start_time이 비었다")
    else:
        diff = (w.rec.kst(0) - t_sheet).total_seconds()
        value = f"{diff:+.0f} s"
        if abs(diff) > tol:
            probs.append(f"기록 시작 {w.rec.kst(0):%H:%M:%S}과 기록지 {row.get('start_time')}의 차이가 크다")
    return Check(wid, "Q10", "FAIL" if probs else "PASS", value, f"±{tol} s", "; ".join(probs))


def _q11_q12(w: Walk, tables: dict[str, pd.DataFrame]) -> list[Check]:
    row, wid, out = w.row, w.walk_id, []
    asg = tables["assignment"]
    wn = int(row.get("redo_of") or row.get("walk_no") or -1)
    a = asg[(asg["participant"] == row.get("participant")) & (asg["walk_no"].astype(int) == wn)]
    ok = len(a) == 1 and a["condition"].iloc[0] == row.get("condition") and \
        a["start_song"].iloc[0] == row.get("start_song", "")
    out.append(Check(wid, "Q11", "PASS" if ok else "FAIL", f"{row.get('condition')} {row.get('start_song')}",
                     f"배정 {wn}회차" + (f": {a['condition'].iloc[0]} {a['start_song'].iloc[0]}" if len(a) else ""),
                     "" if ok else "배정표와 다르다"))
    cond = row.get("condition", "")
    if cond == "S":
        out.append(Check(wid, "Q12", "NA", note="무음 회차"))
        return out
    mus = tables["music"]
    songs = mus[(mus["playlist"] == cond) & (mus["is_spare"] != "1")] if len(mus) else mus
    order_ok = bool(row.get("songs_played") or row.get("start_song"))
    dur_ok = len(songs) == 3 and all(songs["duration_s"].str.strip() != "")
    st = "PASS" if order_ok and dur_ok else "FAIL"
    note = "" if st == "PASS" else ("duration_s가 비었다: C에게 채우도록 알린다" if not dur_ok else "곡 순서 정보 없음")
    out.append(Check(wid, "Q12", st, f"곡 {len(songs)}개", note=note))
    return out


def cross_checks(walks: list[Walk], params: Params) -> list[Check]:
    """회차 사이 검사: Q09 단위가 같은 사람의 다른 회차와 같은지, Q14 폰 방향."""
    out: list[Check] = []
    by_p: dict[str, list[Walk]] = {}
    for w in walks:
        by_p.setdefault(w.row.get("participant", ""), []).append(w)
    for p, ws in by_p.items():
        kinds = {(w.units.accel_units, w.units.includes_gravity, w.units.combine_sign) for w in ws if w.units}
        if len(kinds) > 1:
            out += [Check(w.walk_id, "Q09x", "WARN", note=f"{p}의 회차 사이 단위·부호가 다르다: {sorted(kinds)}")
                    for w in ws if w.units]
        e1 = [w for w in ws if experiment_of(w.row) == "E1" and w.u_dir is not None]
        if len(e1) < 3:
            out += [Check(w.walk_id, "Q14", "NA", note=f"E1 회차 {len(e1)}개(3개 필요)")
                    for w in ws if experiment_of(w.row) == "E1"]
            continue
        center = median_direction(np.vstack([w.u_dir for w in e1]))
        for w in e1:
            ang = angle_deg(w.u_dir, center)
            out.append(Check(w.walk_id, "Q14", "PASS" if ang <= params["qa.phone_tilt_warn_deg"] else "WARN",
                             f"{ang:.1f}°", params["qa.phone_tilt_warn_deg"]))
    return out


def q15_scan(results: Path, walks: list[Walk]) -> Check:
    """results 아래 CSV·JSON에 위도·경도 열이나 실제 좌표 값이 있는지(Q15)."""
    coords = set()
    for w in walks:
        if w.rec is not None and w.rec.has("Location"):
            for c in ("latitude", "longitude"):
                vals = np.round(w.rec.sensors["Location"][c].to_numpy(float), 4)
                coords.update(f"{v:.4f}" for v in vals if abs(v) >= 1)  # 0 근처 합성 좌표는 다른 작은 수와 헷갈린다
    hits = []
    inputs = results / "data"  # 합성 입력(가짜 좌표 포함)은 결과가 아니다
    for f in sorted(results.rglob("*")):
        if f.suffix.lower() not in (".csv", ".json") or not f.is_file() or inputs in f.parents:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        head = text.splitlines()[0].lower() if text else ""
        if re.search(r"\b(latitude|longitude|lat|lon)\b", head):
            hits.append(f"{f.name}: 좌표 열")
        nums = set(re.findall(r"-?\d+\.\d{4}", text))
        if any(n[: n.index(".") + 5] in coords for n in nums):
            hits.append(f"{f.name}: 좌표 값")
    return Check("ALL", "Q15", "FAIL" if hits else "PASS", str(len(hits)), "0", "; ".join(hits[:5]))


def _walk_json(w: Walk) -> dict:
    d: dict = {"walk_id": w.walk_id, "zip": w.zip_path.name, "error": w.error or w.units_error}
    if w.rec is not None:
        s = interval_stats(w.rec.t("Accelerometer"), 0.25, 1.0) if w.rec.has("Accelerometer") else {}
        d.update(start_local=str(w.rec.kst(0)), epoch_source=w.rec.epoch_source, files=w.rec.files,
                 empty=w.rec.empty, unknown=w.rec.unknown, sampling={k: v for k, v in s.items() if k != "gaps"},
                 gaps=s.get("gaps", [])[:50])
    if w.units is not None:
        d["units"] = asdict(w.units)
    if w.steps is not None:
        st = w.steps
        d["steps"] = dict(signal=st.signal, t_depart=st.t_depart, t_arrive=st.t_arrive, stand_start=st.stand_start,
                          stand_end=st.stand_end, flags=st.flags, bouts=st.bouts, rejected=st.rejected,
                          **w.extra.get("cadence", {}))
    if w.u_dir is not None:
        d["phone_vertical_dir"] = [round(float(x), 4) for x in w.u_dir]
    return d


def run_checks(rows: list[dict], paths: Paths, params: Params) -> tuple[list[Check], list[Walk]]:
    """manifest 줄들을 검사하고 결과 파일을 쓴다."""
    tables = {"assignment": read_table(paths.assignment), "music": read_table(paths.music),
              "participants": read_table(paths.participants), "sections": read_table(paths.sections),
              "manifest": read_table(paths.manifest)}
    walks = [analyze_walk(r, paths, params) for r in rows]
    checks = [c for w in walks for c in check_walk(w, tables, params)]
    checks += cross_checks(walks, params)
    qa_dir = paths.results / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    for w in walks:
        (qa_dir / f"{w.walk_id}.json").write_text(
            json.dumps(_walk_json(w), ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    summary = paths.results / "qa_summary.csv"
    old = read_table(summary)
    if len(old):  # 이번에 검사하지 않은 회차의 줄은 남긴다
        old = old[~old["walk_id"].isin([w.walk_id for w in walks] + ["ALL"])]
    checks.append(q15_scan(paths.results, walks))
    df = pd.concat([old, pd.DataFrame([asdict(c) for c in checks])], ignore_index=True)
    df.to_csv(summary, index=False, encoding="utf-8", lineterminator="\n")
    return checks, walks


def criteria_fixed(path: Path = ROOT / "docs" / "DECISIONS.md", ids=("D-33", "D-34", "D-35", "D-36")) -> str:
    """관문 G1 '결과 전 기준': DECISIONS 표에서 네 항목의 상태가 모두 '확정'이면 PASS."""
    if not path.exists():
        return "NA"
    status = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (D-\d+) \|", line)
        if m:
            status[m.group(1)] = line.rstrip().rstrip("|").rsplit("|", 1)[-1].strip()
    return "PASS" if all(status.get(i, "").startswith("확정") for i in ids) else "FAIL"


def gate_g1(checks: list[Check], manifest: pd.DataFrame) -> pd.DataFrame:
    """관문 G1 표(사람 × 항목, QA_CHECKLIST §3). 100걸음은 사전 점검의 steps100 기록으로 본다(D-27)."""
    by = {(c.walk_id, c.check_id): c.status for c in checks}
    criteria = criteria_fixed()
    rows = []
    for p in sorted({r for r in manifest.get("participant", []) if r}):
        m = manifest[manifest["participant"] == p]
        e1 = m[(m["experiment"] == "E1") & (m["walk_no"].isin(["1", "2"]))]["walk_id"].tolist()
        tests = m[(m["experiment"] == "TEST") & (m["condition"] == "steps100")]["walk_id"].tolist()

        def all_pass(ids, cids):
            if not ids:
                return "NA"
            sts = [by.get((i, c), "NA") for i in ids for c in cids]
            return "PASS" if all(s == "PASS" for s in sts) else "FAIL" if "FAIL" in sts else "WARN/NA"

        rows.append(dict(participant=p, first_data=f"{len(e1)}/2", background=all_pass(e1, ["Q03", "Q04"]),
                         hand_100=all_pass(tests, ["Q06"]), gps=all_pass(e1, ["Q08a"]),
                         names_assignment_units=all_pass(e1, ["Q10", "Q11", "Q09"]), pre_result_criteria=criteria))
    return pd.DataFrame(rows)


def make_synthetic_dataset(paths: Paths, params: Params) -> None:
    """관문 G1 연습용 합성 자료: A·B·C의 1–2회차(배정표 조건)와 100걸음 사전 점검(steps100) 파일.

    zip은 raw/<사람>/에 두고, 기록 시작 시각은 기록지 시각 + 20 s다(D-27).
    """
    from walkmusic.synthetic import SynthSpec, write_zip

    def epoch_ms(date: str, hhmm: str) -> int:
        return int(sheet_time(dict(date=date, start_time=hhmm), params["time.timezone"]).value // 10**6) + 20_000

    (paths.sections.parent).mkdir(parents=True, exist_ok=True)
    asg = read_table(paths.assignment)
    rows, seed = [], 0
    for p in ("A", "B", "C"):
        (paths.raw / p).mkdir(parents=True, exist_ok=True)
        for wn, day, hhmm in ((1, "09", "08:30"), (2, "10", "08:35")):
            a = asg[(asg["participant"] == p) & (asg["walk_no"] == str(wn))].iloc[0]
            wid, date = f"E1_{p}_{wn:02d}_{a['condition']}_11{day}", f"2026-11-{day}"
            seed += 1
            write_zip(paths.raw / p / f"{wid}.zip", SynthSpec(walk_s=500, cadence_spm=105 + 5 * seed % 15, seed=seed,
                                                              epoch_ms=epoch_ms(date, hhmm)))
            rows.append(dict(walk_id=wid, experiment="E1", participant=p, walk_no=str(wn), date=date,
                             start_time=hhmm, condition=a["condition"], start_song=a["start_song"],
                             zip_file=f"{wid}.zip"))
        wid = f"TEST_{p}_1108_steps100"
        seed += 1
        write_zip(paths.raw / p / f"{wid}.zip", SynthSpec(n_walk_steps=100, cadence_spm=100, seed=seed,
                                                          epoch_ms=epoch_ms("2026-11-08", "19:00")))
        rows.append(dict(walk_id=wid, experiment="TEST", participant=p, date="2026-11-08", start_time="19:00",
                         condition="steps100", hand_step_count="100", zip_file=f"{wid}.zip", status="test"))
    cols = read_table(ROOT / "data" / "manifest.csv").columns.tolist()
    man = pd.DataFrame(rows).reindex(columns=cols, fill_value="").fillna("")
    man.to_csv(paths.manifest, index=False, lineterminator="\n")
    mus = read_table(ROOT / "data" / "music_bpm.csv")
    mus["duration_s"] = "180"  # 합성 전용 가짜 곡 길이
    mus.to_csv(paths.music, index=False, lineterminator="\n")
    par = read_table(ROOT / "data" / "participants.csv")
    par["section_distance_m"] = "200"
    par.to_csv(paths.participants, index=False, lineterminator="\n")
    d0, d1 = np.degrees(150 / R_EARTH), np.degrees(350 / R_EARTH)  # 합성 경로(위도 0.001에서 북쪽) 위 150–350 m
    pd.DataFrame([dict(participant=p, seq=s, lat=0.001 + d, lon=0.001, label="합성")
                  for p in ("A", "B", "C") for s, d in ((1, d0), (2, d1))]).to_csv(
        paths.sections, index=False, lineterminator="\n")


def _print_links(df: pd.DataFrame, path: Path) -> None:
    print(f"zip 연결 제안 {len(df)}개 → {path} (manifest는 고치지 않는다. 확인 뒤 zip_file을 채운다)")
    for r in df.itertuples():
        print(f"{r.participant} | {r.zip_name} | 시작 {r.start_kst} | {r.status} | {r.walk_id} | {r.diff_s} s")


def run_cli(zip_path: Path | None, walk: str | None, all_walks: bool, gate: str | None, synthetic: bool,
            links: bool = False) -> int:
    """`python -m walkmusic qa` 처리. 결과 요약을 출력하고 FAIL이 있으면 1. --links는 연결 제안만."""
    params = load_params()
    paths = Paths.synthetic() if synthetic else Paths.real()
    if synthetic and not paths.manifest.exists():
        make_synthetic_dataset(paths, params)
    if links or all_walks or gate:
        _print_links(write_zip_links(paths.manifest, paths.raw, paths.results, params),
                     paths.results / "zip_links.csv")
        if links and not (all_walks or gate or zip_path or walk):
            return 0
    rows = fill_walk_ids(read_table(paths.manifest).to_dict("records"))
    manifest = pd.DataFrame(rows)
    if zip_path is not None:
        name = Path(zip_path).name
        rows = [r for r in rows if r.get("zip_file") == name or f"{r['walk_id']}.zip" == name]
        if not rows:
            print(f"manifest에 {name}이 없다(zip_file 또는 walk_id로 찾는다)")
            return 2
    elif walk:
        rows = [r for r in rows if r["walk_id"] == walk]
    elif not (all_walks or gate):
        print("zip, --walk, --all, --gate 중 하나가 필요하다")
        return 2
    checks, _ = run_checks(rows, paths, params)
    bad = [c for c in checks if c.status in ("WARN", "FAIL")]
    print(f"검사 {len(checks)}줄 → {paths.results / 'qa_summary.csv'}")
    worst: dict[str, str] = {}
    for c in checks:
        cur = worst.setdefault(c.walk_id, "PASS")
        if WORST.get(c.status, 0) > WORST.get(cur, 0):
            worst[c.walk_id] = c.status
    print("walk_id | 상태 | WARN·FAIL 요약")
    for wid, st in worst.items():
        summ = "; ".join(f"{c.check_id}: {c.value} ({c.note})" if c.note else f"{c.check_id}: {c.value}"
                         for c in bad if c.walk_id == wid)
        print(f"{wid} | {st} | {summ}")
    if gate == "G1":
        g = gate_g1(checks, manifest)
        g.to_csv(paths.results / "gate_G1.csv", index=False, lineterminator="\n")
        print("\n관문 G1 (사람 × 항목)\n" + g.to_string(index=False))
    return 1 if any(c.status == "FAIL" for c in checks) else 0
