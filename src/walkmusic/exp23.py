"""실험 2·3 파이프라인 (SPEC §5.7–5.8, §6, §7; DECISIONS D-04·D-11·D-35·D-41·D-55·D-57).

입력: `data/exp2_trials.csv`, `data/exp3_swings.csv`(기록지), `data/participants.csv`(몸 치수),
`data/video_checks.csv`·`video_markers.csv`(영상에서 읽은 값), 실험 1 결과(`results/participants.csv`의 PC·SESOI,
`results/segments.csv`, `results/prescription.csv`).
출력(`results/`): exp2_stages.csv(시행), exp2_summary.csv(단계), exp2_pc.csv(현장 PC와 실험 1 PC), jumps.csv,
exp3_swings.csv(시행), exp3_summary.csv(사람), hypotheses_exp23.csv, qa_exp23.csv, prescription.csv의 상한,
run_info_exp23.json. 좌표는 읽지도 쓰지도 않는다(실험 2·3은 위치를 쓰지 않는다).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from walkmusic.config import ROOT, Params
from walkmusic.exp2 import analyze_trial, h3_rows, h12_rows, prescription_upper, stage_summary
from walkmusic.exp3 import analyze_gyro
from walkmusic.io_sensorlogger import interval_stats, read_zip
from walkmusic.jumps import analyze_jumps, q17_status
from walkmusic.metrics import (
    froude,
    knee_angles,
    pendulum_cadence_spm,
    pendulum_energy,
    pendulum_period_model_s,
    running_flight,
    segment_pendulum,
    spring_mass,
)
from walkmusic.qa import read_table
from walkmusic.stats import _row, _sha, group_rows, require_freeze
from walkmusic.units import determine_units, total_accel_g

NAN = float("nan")
SPRING_COLS = ("fmax_bw", "delta_y_m", "delta_l_m", "kvert_kn_m", "kleg_kn_m", "elastic_energy_j",
               "mean_grf_contact_bw")


@dataclass
class Paths23:
    """실험 2·3 입력·출력 위치."""

    data: Path
    raw: Path
    results: Path

    @classmethod
    def real(cls) -> Paths23:
        return cls(ROOT / "data", ROOT / "data" / "raw", ROOT / "results")

    @classmethod
    def under(cls, root: Path) -> Paths23:
        """합성·시험용: root/data, root/data/raw, root/results."""
        return cls(root / "data", root / "data" / "raw", root / "results")


def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return NAN
    return v


def body_table(paths: Paths23) -> dict[str, dict[str, float]]:
    """data/participants.csv → 사람 → 몸 치수(빈칸은 NaN)."""
    out = {}
    for r in read_table(paths.data / "participants.csv").to_dict("records"):
        out[r["participant"]] = {k: _f(r.get(k)) for k in ("leg_length_m", "thigh_length_m", "shank_length_m",
                                                           "mass_kg", "height_cm")}
    return out


def exp1_base(paths: Paths23) -> dict[str, dict[str, float]]:
    """실험 1 결과의 PC·SESOI(없으면 빈 dict)."""
    t = read_table(paths.results / "participants.csv")
    if not len(t) or "pc_spm" not in t:
        return {}
    return {r["participant"]: dict(pc_spm=_f(r["pc_spm"]), sesoi_pct=_f(r.get("sesoi_pct")))
            for r in t.to_dict("records")}


def video_seconds(paths: Paths23) -> dict[tuple[str, str, int], float]:
    """video_checks.csv → (trial_id, kind, event_no) → 초(frames ÷ fps가 있으면 그것)."""
    out = {}
    for r in read_table(paths.data / "video_checks.csv").to_dict("records"):
        frames, fps, val = _f(r.get("frames")), _f(r.get("fps")), _f(r.get("value_s"))
        sec = frames / fps if np.isfinite(frames) and np.isfinite(fps) and fps > 0 else val
        no = int(_f(r.get("event_no"))) if np.isfinite(_f(r.get("event_no"))) else 1
        out[(r["trial_id"], r["kind"], no)] = sec
    return out


def _zip(paths: Paths23, runner: str, name: str) -> Path | None:
    if not str(name).strip():
        return None
    for p in (paths.raw / runner / name, paths.raw / name):
        if p.exists():
            return p
    return None


def _file_qa(trial_id: str, rec, params: Params, name: str) -> list[dict]:
    """파일 단위 검사(Q02 샘플링, Q03 끊김)."""
    s = interval_stats(rec.t(name), params["qa.gap_warn_s"], params["qa.gap_fail_s"])
    fs_ok = s["fs_hz"] >= params["qa.min_fs_hz"]
    gap = s.get("max_s", NAN)
    gap_st = "PASS" if gap <= params["qa.gap_warn_s"] else "WARN" if gap <= params["qa.gap_fail_s"] else "FAIL"
    return [dict(walk_id=trial_id, check_id="Q02", status="PASS" if fs_ok else "FAIL", value=f"{s['fs_hz']:.2f}",
                 threshold=f">= {params['qa.min_fs_hz']}", note=name),
            dict(walk_id=trial_id, check_id="Q03", status=gap_st, value=f"{gap:.3f}",
                 threshold=f"<= {params['qa.gap_warn_s']}", note="가장 긴 끊김(s)")]


def _imu(path: Path, params: Params):
    rec = read_zip(path, params)
    t, total, grav = total_accel_g(rec, determine_units(rec))
    return rec, t, total, grav


def process_exp2(paths: Paths23, params: Params, body: dict, base: dict, video: dict
                 ) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, list[dict]]:
    """기록지 + zip → (시행 표, 단계 중앙값용 체공·접촉, 점프 표, 현장 PC 표, QA 줄)."""
    g = params["constants.g"]
    sheet = read_table(paths.data / "exp2_trials.csv")
    rows, phases, jump_rows, qa = [], {}, [], []
    for r in sheet.to_dict("records"):
        tid, runner, ratio = r["trial_id"], r["runner"], str(r.get("ratio_pct", "")).strip().upper()
        zp = _zip(paths, runner, r.get("zip_file", ""))
        if zp is None:
            qa.append(dict(walk_id=tid, check_id="Q01", status="FAIL", value="", threshold="",
                           note=f"zip 없음: '{r.get('zip_file', '')}'(zip_file을 채워야 한다, D-55)"))
            continue
        rec, t, total, grav = _imu(zp, params)
        qa += _file_qa(tid, rec, params, "Accelerometer")
        mass = body.get(runner, {}).get("mass_kg", NAN)
        if ratio == "J":
            js = analyze_jumps(t, total, grav, params, mass)
            st = q17_status(len(js), params)
            qa.append(dict(walk_id=tid, check_id="Q17", status=st, value=str(len(js)),
                           threshold=f"{params['jump.n_jumps']}",
                           note="체공(s): " + ", ".join(f"{j['flight_time_s']:.3f}" for j in js)))
            for j in js:
                j.update(runner=runner, trial_id=tid,
                         flight_time_video_s=video.get((tid, "jump_flight", j["jump_no"]), NAN))
                jump_rows.append(j)
            continue
        bpm = _f(r.get("bpm_played"))
        s = analyze_trial(t, total, grav, params, bpm=bpm, t_in=_f(r.get("t_in_sensor_s")),
                          t_out=_f(r.get("t_out_sensor_s")))
        phases[tid] = (s.pop("_tf", np.array([])), s.pop("_tc", np.array([])))
        flags = s.pop("flags")
        t30, n = _f(r.get("t30_s")), _f(r.get("steps_N"))
        v = params["exp2.analysis_m"] / t30 if np.isfinite(t30) and t30 > 0 else NAN
        gait = str(r.get("gait_video", "")).strip().lower()
        row = dict(trial_id=tid, runner=runner, ratio_pct=ratio, repeat=r.get("repeat", ""), bpm_played=bpm,
                   direction=r.get("direction", ""), pc_field_sheet_spm=_f(r.get("pc_field_spm")), t30_s=t30,
                   steps_N=n, v_ms=v, cadence_record_spm=n / t30 * 60 if np.isfinite(n) and np.isfinite(t30) else NAN,
                   gait_video=gait, zip_file=zp.name, **s)
        if gait and s["sensor_gait"] and {gait, s["sensor_gait"]} == {"walk", "run"}:
            flags.append("gait_mismatch")
        leg = body.get(runner, {}).get("leg_length_m", NAN)
        row["fr"] = froude(v, leg, g) if np.isfinite(v) and np.isfinite(leg) else NAN
        if gait in ("run", "mixed"):
            tf, tc = row["flight_time_median_s"], row["contact_time_s"]
            if all(np.isfinite(x) for x in (mass, leg, v, tf, tc)):
                row.update({k: x for k, x in spring_mass(mass, tc, tf, v, leg, g).items() if k in SPRING_COLS})
                row["takeoff_angle_deg"] = running_flight(v, tf, g)["takeoff_angle_deg"]
            if gait == "mixed":
                flags.append("mixed_gait")
        row["flags"] = ";".join(flags)
        rows.append(row)
    trials = pd.DataFrame(rows)
    jumps = pd.DataFrame(jump_rows)
    pcs = []
    if len(trials):
        for runner, d in trials.groupby("runner"):
            silent = d[d["ratio_pct"] == "S"]
            calc = float(silent["cadence_record_spm"].mean()) if silent["cadence_record_spm"].notna().any() else NAN
            sheet_pc = float(d["pc_field_sheet_spm"].dropna().iloc[0]) if d["pc_field_sheet_spm"].notna().any() else NAN
            flags = []
            pc = calc
            if not np.isfinite(calc):
                pc = sheet_pc
                flags.append("pc_field_from_sheet")
            elif np.isfinite(sheet_pc) and abs(calc - sheet_pc) > params["exp2.pc_field_tol_spm"]:
                flags.append("pc_field_mismatch")
            pc1 = base.get(runner, {}).get("pc_spm", NAN)
            pcs.append(dict(runner=runner, n_silent=len(silent), pc_field_spm=pc, pc_field_calc_spm=calc,
                            pc_field_sheet_spm=sheet_pc, pc_exp1_spm=pc1, diff_spm=pc - pc1,
                            diff_pct=(pc - pc1) / pc1 * 100, flags=";".join(flags)))
        pc_by = {p["runner"]: p["pc_field_spm"] for p in pcs}
        trials["pc_field_spm"] = trials["runner"].map(pc_by)
        trials["tempo_ratio_pct"] = trials["bpm_played"] / trials["pc_field_spm"] * 100
        cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"
        trials["dC_pct"] = (trials[cprim] - trials["pc_field_spm"]) / trials["pc_field_spm"] * 100
        ses = trials["runner"].map({k: v.get("sesoi_pct", NAN) for k, v in base.items()}).astype(float)
        dc = trials["dC_pct"]
        trials["change_class"] = np.where(~(np.isfinite(dc) & np.isfinite(ses)), "",
                                          np.where(dc.abs() <= ses, "within_band",
                                                   np.where(dc > 0, "meaningful_up", "meaningful_down")))
    return trials, phases, jumps, pd.DataFrame(pcs), qa


def _knee_deg(trial_id: str, markers: pd.DataFrame) -> float:
    if not len(markers):
        return NAN
    m = markers[(markers["trial_id"] == trial_id) & (markers["event"] == "pendulum_bent")]
    vals = []
    for r in m.to_dict("records"):
        pts = [(_f(r[f"{k}_x"]), _f(r[f"{k}_y"])) for k in ("hip", "knee", "ankle")]
        if all(np.isfinite(c) for p in pts for c in p):
            vals.append(knee_angles(*pts)["knee_flexion_deg"])
    return float(np.mean(vals)) if vals else NAN


def _segments(body: dict, params: Params) -> tuple[float, float, list[str]]:
    thigh, shank, flags = body.get("thigh_length_m", NAN), body.get("shank_length_m", NAN), []
    h = body.get("height_cm", NAN) / 100
    if not np.isfinite(thigh) and np.isfinite(h):
        thigh = params["pendulum.fallback_thigh_over_H"] * h
        flags.append("seg_len_from_height")
    if not np.isfinite(shank) and np.isfinite(h):
        shank = params["pendulum.fallback_shank_over_H"] * h
        if "seg_len_from_height" not in flags:
            flags.append("seg_len_from_height")
    return thigh, shank, flags


def _fractions(params: Params) -> dict[str, float]:
    return {k: params[f"pendulum.seg_{k}_frac"] for k in ("thigh_mass", "thigh_com", "thigh_kcm", "shank_mass",
                                                          "shank_com", "shank_kcm")}


def process_exp3(paths: Paths23, params: Params, body: dict, base: dict, video: dict
                 ) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """진자 기록지 + zip → (시행 표, 사람 표, QA 줄)."""
    g = params["constants.g"]
    sheet = read_table(paths.data / "exp3_swings.csv")
    markers = read_table(paths.data / "video_markers.csv")
    frac = _fractions(params)
    measured = {}  # 사람 → 영상 마커로 잰 굽힘 각들(굽힌 다리는 3회 중 1회만 찍는다, PROTOCOL 4.5)
    for r in sheet.to_dict("records"):
        phi = _knee_deg(r["trial_id"], markers)
        if np.isfinite(phi):
            measured.setdefault(r["runner"], []).append(phi)
    rows, qa = [], []
    for r in sheet.to_dict("records"):
        tid, runner = r["trial_id"], r["runner"]
        knee = str(r.get("knee", "")).strip().lower() or ("bent" if "_K_" in tid else "straight")
        zp = _zip(paths, runner, r.get("zip_file", ""))
        if zp is None:
            qa.append(dict(walk_id=tid, check_id="Q01", status="FAIL", value="", threshold="",
                           note=f"zip 없음: '{r.get('zip_file', '')}'(zip_file을 채워야 한다, D-55)"))
            continue
        rec = read_zip(zp, params)
        if not rec.has("Gyroscope"):
            qa.append(dict(walk_id=tid, check_id="Q01", status="FAIL", value="", threshold="Gyroscope",
                           note="자이로 파일이 없다"))
            continue
        qa += _file_qa(tid, rec, params, "Gyroscope")
        s = analyze_gyro(rec.t("Gyroscope"), rec.xyz("Gyroscope"), params)
        flags = list(s.pop("flags"))
        if str(r.get("valid", "")).strip() == "0":
            flags.append("invalid_sheet")
        b = body.get(runner, {})
        leg, mass = b.get("leg_length_m", NAN), b.get("mass_kg", NAN)
        thigh, shank, seg_flags = _segments(b, params)
        if knee == "bent":
            phi = _knee_deg(tid, markers)
            if not np.isfinite(phi) and measured.get(runner):
                phi = float(np.mean(measured[runner]))
                flags.append("knee_from_other_trial")
            elif not np.isfinite(phi):
                phi = params["pendulum.bent_knee_deg"]
                flags.append("knee_nominal")
        else:
            phi = 0.0
        P = s["swing_period_s"]
        row = dict(trial_id=tid, runner=runner, repeat=r.get("repeat", ""), knee=knee, knee_deg=phi, **s,
                   cadence_pend_spm=pendulum_cadence_spm(P) if np.isfinite(P) else NAN, leg_length_m=leg,
                   video_period_s=video.get((tid, "swing_10", 1), NAN) / 10, zip_file=zp.name)
        if knee == "straight" and np.isfinite(leg):
            pm = pendulum_period_model_s(leg, params["pendulum.k_over_L"], params["pendulum.d_over_L"], g)
            row.update(period_model_s=pm, period_error_pct=(P - pm) / pm * 100)
        if all(np.isfinite(x) for x in (mass, thigh, shank)):
            seg = segment_pendulum(mass, thigh, shank, phi, g, frac)
            row["period_model_seg_s"] = seg["period_s"]
            row["period_ratio_model"] = seg["period_s"] / segment_pendulum(mass, thigh, shank, 0.0, g, frac)["period_s"]
            if np.isfinite(s["amp_deg"]):
                row["omega_pred_rad_s"] = pendulum_energy(seg["mass_kg"], seg["com_dist_m"], seg["inertia_hip_kgm2"],
                                                          s["amp_deg"], g)["omega_pred_rad_s"]
            flags += seg_flags
        else:
            flags.append("no_body_for_segment_model")
        row["flags"] = ";".join(flags)
        if "few_cycles" in flags or "no_swing" in flags:
            qa.append(dict(walk_id=tid, check_id="swing_cycles", status="WARN", value=str(s["n_cycles_total"]),
                           threshold=f">= {params['pendulum.min_cycles']}",
                           note="흔들림이 10주기 미만이거나 없다(D-58: 다시 한다)"))
        rows.append(row)
    sw = pd.DataFrame(rows)
    people = []
    if len(sw):
        ok = ~sw["flags"].fillna("").str.contains("invalid_sheet|no_swing")
        for runner, d in sw[ok].groupby("runner"):
            st, bt = d[d["knee"] == "straight"], d[d["knee"] == "bent"]
            P = float(st["swing_period_s"].median()) if len(st) else NAN
            PK = float(bt["swing_period_s"].median()) if len(bt) else NAN
            pc = base.get(runner, {}).get("pc_spm", NAN)
            pm = float(st["period_model_s"].median()) if "period_model_s" in st and len(st) else NAN
            people.append(dict(runner=runner, n_straight=len(st), n_bent=len(bt), swing_period_s=P,
                               swing_period_bent_s=PK, cadence_pend_spm=120 / P if np.isfinite(P) else NAN,
                               cadence_pend_bent_spm=120 / PK if np.isfinite(PK) else NAN, period_model_s=pm,
                               period_error_pct=(P - pm) / pm * 100 if np.isfinite(pm) else NAN,
                               period_model_seg_s=_med(st, "period_model_seg_s"),
                               period_model_seg_bent_s=_med(bt, "period_model_seg_s"),
                               period_ratio_bent=PK / P if np.isfinite(P) and np.isfinite(PK) else NAN,
                               period_ratio_model=_med(bt, "period_ratio_model"),
                               knee_deg=_med(bt, "knee_deg"), pc_spm=pc))
        ratio = sw["swing_period_s"] / sw["runner"].map({p["runner"]: p["swing_period_s"] for p in people})
        sw["period_ratio_bent"] = np.where(sw["knee"] == "bent", ratio, NAN)
    return sw, pd.DataFrame(people), qa


def _med(d: pd.DataFrame, col: str) -> float:
    return float(d[col].median()) if col in d and d[col].notna().any() else NAN


def h4_rows(people: pd.DataFrame, params: Params) -> list[dict]:
    """가설 4: 곧은 다리 진자 예측 케이던스 C_pend < 실측 PC(사람마다). 모델 타당성은 집단 한 줄(SPEC §5.8)."""
    rows = []
    for r in people.to_dict("records"):
        c, pc = r["cadence_pend_spm"], r["pc_spm"]
        if not (np.isfinite(c) and np.isfinite(pc)):
            rows.append(_row("H4", r["runner"], "C_pend vs PC", c, criterion="C_pend < PC",
                             note="곧은 다리 주기나 실험 1 PC가 없다"))
            continue
        rows.append(_row("H4", r["runner"], "C_pend vs PC", c, n=r["n_straight"], criterion="C_pend < PC",
                         supported=bool(c < pc), note=f"C_pend {c:.1f} 걸음/분, PC {pc:.1f} 걸음/분"))
    errs = people["period_error_pct"].astype(float).dropna() if len(people) else pd.Series(dtype=float)
    lim = params["pendulum.valid_error_pct"]
    mean_abs = float(errs.abs().mean()) if len(errs) else NAN
    rows.append(_row("H4_model", "ALL", "mean |period error| %", mean_abs, n=len(errs),
                     criterion=f"<= {lim}%", supported=bool(mean_abs <= lim) if len(errs) else "NA",
                     note="모델 타당성(SPEC §5.8). 가설 4의 지지 판정과 따로 본다"))
    return rows


def h2_variability_rows(summary: pd.DataFrame, paths: Paths23, params: Params) -> list[dict]:
    """가설 2 변동성(D-11, 초안): 실험 2 단계와 T가 ±`stats.same_tempo_pct` 안인 실험 1 곡 구간의 CV 평균 비교."""
    segs = read_table(paths.results / "segments.csv")
    rows = []
    if not len(segs) or not len(summary):
        return rows
    segs = segs[segs["condition"] != "S"]
    tol = params["stats.same_tempo_pct"]
    for p, s in summary[summary["ratio_pct"].map(lambda r: str(r).replace(".", "", 1).isdigit())].groupby("runner"):
        e1 = segs[segs["participant"] == p]
        t1, cv1 = e1["tempo_ratio_pct"].astype(float).to_numpy(), e1["cv_pct"].astype(float).to_numpy()
        pairs = []
        for st in s.to_dict("records"):
            near = np.abs(t1 - st["tempo_ratio_pct"]) <= tol
            if near.any() and np.isfinite(st.get("cv_pct", NAN)):
                pairs.append((st["cv_pct"], float(np.nanmean(cv1[near]))))
        if not pairs:
            rows.append(_row("H2_variability", p, "CV exp2 - exp1", criterion="mean CV exp2 > exp1",
                             note="T가 가까운 실험 1 곡 구간이 없다(D-11)"))
            continue
        a, b = np.mean([x[0] for x in pairs]), np.mean([x[1] for x in pairs])
        rows.append(_row("H2_variability", p, "CV exp2 - exp1", float(a - b), n=len(pairs),
                         criterion="mean CV exp2 > exp1", supported=bool(a > b),
                         note=f"짝지은 단계 {len(pairs)}개: 실험 2 CV {a:.2f}%, 실험 1 CV {b:.2f}%(D-11 초안)"))
    return rows


def fill_prescription(paths: Paths23, upper: pd.DataFrame) -> None:
    """실험 1이 만든 prescription.csv의 요약 줄에 상한(T_high, T_high_s3, bpm_high)을 채운다."""
    path = paths.results / "prescription.csv"
    if not path.exists() or not len(upper):
        return
    pres = pd.read_csv(path)
    up = upper.set_index("runner")
    for i, r in pres[pres["row_type"] == "summary"].iterrows():
        p = r["participant"]
        if p not in up.index:
            continue
        th, ts = up.loc[p, "t_high_pct"], up.loc[p, "t_high_s3_pct"]
        pres.loc[i, "t_high_pct"], pres.loc[i, "t_high_s3_pct"] = th, ts
        pres.loc[i, "bpm_high"] = th / 100 * float(r["pc_spm"]) if np.isfinite(th) else NAN
        flags = [f for f in str(r.get("flags", "")).split(";") if f and f != "nan" and f != "t_high는 실험 2 뒤"]
        flags += [f for f in str(up.loc[p, "flags"]).split(";") if f]
        tl = float(r["t_low_pct"]) if np.isfinite(_f(r["t_low_pct"])) else NAN
        if np.isfinite(tl) and np.isfinite(th) and tl > th:
            flags.append("inconsistent")
        pres.loc[i, "flags"] = ";".join(flags)
    pres.to_csv(path, index=False, lineterminator="\n")


def _write(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, lineterminator="\n")


def run_exp23(paths: Paths23, params: Params, real: bool, allow_unfrozen: bool = False) -> dict:
    """실험 2·3 전체. 결과 표를 paths.results에 쓰고 요약을 돌려준다."""
    freeze = require_freeze(real, allow_unfrozen, params["freeze.tag"])
    out = Path(paths.results)
    out.mkdir(parents=True, exist_ok=True)
    body, base, video = body_table(paths), exp1_base(paths), video_seconds(paths)
    trials, phases, jumps, pcs, qa2 = process_exp2(paths, params, body, base, video)
    legs = {k: v.get("leg_length_m", NAN) for k, v in body.items()}
    summary = stage_summary(trials, legs, params, sesoi={k: v.get("sesoi_pct", NAN) for k, v in base.items()},
                            body=body, phases=phases) if len(trials) else pd.DataFrame()
    swings, people3, qa3 = process_exp3(paths, params, body, base, video)
    rows = []
    if len(summary):
        rows += h12_rows(summary, params) + h3_rows(trials, summary, params)
        rows += h2_variability_rows(summary, paths, params)
    if len(people3):
        rows += h4_rows(people3, params)
    runners = sorted(set(trials.get("runner", pd.Series(dtype=str))) | set(people3.get("runner", pd.Series(dtype=str))))
    rows += group_rows([r for r in rows if r["participant"] != "ALL"], params, n_people=max(len(runners), 1))
    upper = prescription_upper(summary, params) if len(summary) else pd.DataFrame()
    for df, name in ((trials, "exp2_stages.csv"), (summary, "exp2_summary.csv"), (pcs, "exp2_pc.csv"),
                     (jumps, "jumps.csv"), (swings, "exp3_swings.csv"), (people3, "exp3_summary.csv"),
                     (pd.DataFrame(rows), "hypotheses_exp23.csv"), (pd.DataFrame(qa2 + qa3), "qa_exp23.csv"),
                     (upper, "prescription_upper.csv")):
        _write(df, out / name)
    fill_prescription(paths, upper)
    inputs = [paths.data / n for n in ("exp2_trials.csv", "exp3_swings.csv", "participants.csv", "video_checks.csv",
                                       "video_markers.csv")]
    zips = [z for n in ("exp2_trials.csv", "exp3_swings.csv") for r in read_table(paths.data / n).to_dict("records")
            if (z := _zip(paths, r["runner"], r.get("zip_file", ""))) is not None]
    info = dict(time_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), freeze=freeze,
                params_sha256=_sha(params.path) if params.path else "",
                inputs={str(p.relative_to(paths.data)): _sha(p) for p in inputs + zips if p.exists()})
    (out / "run_info_exp23.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str),
                                             encoding="utf-8")
    return dict(trials=trials, summary=summary, jumps=jumps, swings=swings, people3=people3, hypotheses=rows,
                qa=qa2 + qa3, pcs=pcs)


def field_report(res: dict) -> str:
    """현장 당일 점검용 짧은 표(시행마다 한 줄). 다시 해야 할 시행을 찾는 데 쓴다."""
    lines = []
    tr = res["trials"]
    if len(tr):
        lines.append("실험 2 시행: trial_id | 창(걸음 수) | 센서 C / BPM | S3 | 체공 걸음 % | 센서·영상 판정 | "
                     "싱크 점프 | flags")
        for r in tr.to_dict("records"):
            c = r["cadence_median_spm"]
            fl = r["flight_step_frac"] * 100 if np.isfinite(r["flight_step_frac"]) else NAN
            lines.append(f"  {r['trial_id']} | {r['window_method']}({r['n_steps_window']}) | "
                         f"{c:.1f} / {r['bpm_played'] if np.isfinite(r['bpm_played']) else '-'} | "
                         f"{_fmt(r['sync3_pct'])} | {_fmt(fl)} | "
                         f"{r['sensor_gait'] or '-'}·{r['gait_video'] or '-'} | {r['n_sync_jumps']} | {r['flags']}")
    js = res["jumps"]
    if len(js):
        lines.append("점프: runner | 점프 수 | 체공(s) | 높이(cm)")
        for p, d in js.groupby("runner"):
            lines.append(f"  {p} | {len(d)} | {', '.join(f'{x:.3f}' for x in d['flight_time_s'])} | "
                         f"{', '.join(f'{x * 100:.1f}' for x in d['height_m'])}")
    sw = res["swings"]
    if len(sw):
        lines.append("진자: trial_id | 무릎 | 주기(s) | 이어진 주기 수 | flags")
        for r in sw.to_dict("records"):
            lines.append(f"  {r['trial_id']} | {r['knee']} | {_fmt(r['swing_period_s'], 3)} | {r['n_cycles_total']} | "
                         f"{r['flags']}")
    bad = [q for q in res["qa"] if q["status"] in ("FAIL", "WARN")]
    if bad:
        lines.append("주의:")
        lines += [f"  {q['walk_id']} {q['check_id']} {q['status']} {q['value']} {q['note']}" for q in bad]
    return "\n".join(lines)


def _fmt(x: float, nd: int = 1) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


# --- 합성 자료(SPEC §10: 실제 데이터 없이 실험 2·3 전체가 끝까지 돈다. 결과는 results_synthetic/에만) ---

SYN_PEOPLE = {  # PC, 다리, 체중, 허벅지·정강이(B는 비움 → 키로 대신), 키, 단계별 걸음새
    "A": dict(pc=110.0, leg=0.90, mass=60.0, thigh=0.4165, shank=0.4182, height=170.0,
              gait={100: "walk", 120: "walk", 135: "walk", 150: "run", 165: "run"}),
    "B": dict(pc=105.0, leg=0.85, mass=70.0, thigh=None, shank=None, height=165.0,
              gait={100: "walk", 120: "walk", 135: "walk", 150: "walk", 165: "walk"}),
    "C": dict(pc=115.0, leg=0.95, mass=55.0, thigh=0.45, shank=0.44, height=180.0,
              gait={100: "walk", 120: "walk", 135: "walk", 150: "mixed", 165: "run"}),
}


def make_synthetic_exp23(root: Path, params: Params) -> dict:
    """root/data(기록지·몸 치수·영상 값·zip)와 root/results(실험 1 결과 흉내)를 만들고 정답을 돌려준다."""
    from walkmusic.metrics import tempo_file_bpm
    from walkmusic.synthetic import (
        JumpSpec,
        SwingSpec,
        TrialSpec,
        make_jump_imu,
        make_swing_gyro,
        make_trial_imu,
        write_imu_zip,
    )

    paths = Paths23.under(Path(root))
    for d in (paths.data, paths.results):
        d.mkdir(parents=True, exist_ok=True)
    g = params["constants.g"]
    frac = _fractions(params)
    trials, swings, checks, people, base, segs = [], [], [], [], [], []
    truth: dict = dict(pc={}, periods={})
    epoch = 1_800_000_000_000
    for k, (p, spec) in enumerate(SYN_PEOPLE.items()):
        raw = paths.raw / p
        raw.mkdir(parents=True, exist_ok=True)
        pc = spec["pc"]
        truth["pc"][p] = pc
        people.append(dict(participant=p, leg_length_m=spec["leg"], mass_kg=spec["mass"], height_cm=spec["height"],
                           thigh_length_m=spec["thigh"] or "", shank_length_m=spec["shank"] or ""))
        base.append(dict(participant=p, n_silent=3, pc_spm=pc, pc_provisional=False, silent_cv_pct=1.2,
                         sesoi_pct=1.5))
        segs += [dict(participant=p, condition="P", tempo_ratio_pct=t, cv_pct=2.5) for t in (95, 100, 105, 120)]
        plan = [("S", r, "walk", pc) for r in (1, 2)]
        plan += [(str(ratio), r, ("run" if (gait == "mixed" and r == 1) else "walk") if gait == "mixed" else gait,
                  float(tempo_file_bpm(pc, ratio / 100, params["music.tempo_file_step_bpm"])))
                 for ratio, gait in spec["gait"].items() for r in (1, 2)]
        for i, (ratio, rep, gait, bpm) in enumerate(plan):
            tid = f"E2_{p}_{ratio}_{rep}"
            run = gait == "run"
            sl = 1.0 if run else 0.70
            v = sl * bpm / 60
            t30 = 30 / v
            ts = TrialSpec(cadence_spm=bpm, n_steps=int(40 / sl) + 2, run=run, flight_s=0.09, seed=100 * k + i,
                           epoch_ms=epoch)
            t, f, _, _ = make_trial_imu(ts)
            write_imu_zip(raw / f"{tid}.zip", t, f, epoch_ms=epoch)
            epoch += 120_000
            sheet_gait = spec["gait"][int(ratio)] if ratio != "S" else "walk"
            trials.append(dict(trial_id=tid, runner=p, ratio_pct=ratio, repeat=rep,
                               bpm_played="" if ratio == "S" else bpm, direction="→" if rep == 1 else "←",
                               pc_field_spm=pc, t30_s=round(t30, 2), steps_N=round(bpm * t30 / 60),
                               gait_video=gait if sheet_gait == "mixed" else sheet_gait, zip_file=f"{tid}.zip"))
        tid = f"E2_{p}_J_1"
        flights = (0.45, 0.48, 0.50)
        t, f, _, _ = make_jump_imu(JumpSpec(flight_times_s=flights, rest_s=8.0, seed=10 + k, epoch_ms=epoch))
        write_imu_zip(raw / f"{tid}.zip", t, f, epoch_ms=epoch)
        epoch += 120_000
        trials.append(dict(trial_id=tid, runner=p, ratio_pct="J", repeat=1, zip_file=f"{tid}.zip",
                           video_file="jump.mov", video_fps=240))
        if p == "A":
            checks += [dict(trial_id=tid, kind="jump_flight", event_no=j + 1, fps=240, frames=round(tf * 240))
                       for j, tf in enumerate(flights)]
        thigh = spec["thigh"] or params["pendulum.fallback_thigh_over_H"] * spec["height"] / 100
        shank = spec["shank"] or params["pendulum.fallback_shank_over_H"] * spec["height"] / 100
        for knee, phi in (("straight", 0.0), ("bent", 85.0 if p == "A" else 90.0)):
            period = segment_pendulum(spec["mass"], thigh, shank, phi, g, frac)["period_s"]
            for rep in (1, 2, 3):
                tid = f"E3_{p}_{rep}" if knee == "straight" else f"E3_{p}_K_{rep}"
                t, gyro, _ = make_swing_gyro(SwingSpec(period_s=period, seed=200 + 10 * k + rep, epoch_ms=epoch))
                f = np.tile([0.0, 0.0, 1.0], (len(t), 1))
                write_imu_zip(raw / f"{tid}.zip", t, f, gyro=gyro, epoch_ms=epoch)
                epoch += 60_000
                truth["periods"][tid] = period
                swings.append(dict(trial_id=tid, runner=p, repeat=rep, zip_file=f"{tid}.zip", valid=1, knee=knee))
        checks.append(dict(trial_id=f"E3_{p}_1", kind="swing_10", event_no=1,
                           value_s=round(10 * truth["periods"][f"E3_{p}_1"], 2)))
    cols2 = ["trial_id", "runner", "ratio_pct", "repeat", "bpm_played", "direction", "pc_field_spm", "t30_s",
             "steps_N", "gait_video", "zip_file", "t_in_sensor_s", "t_out_sensor_s", "notes", "video_file", "video_fps"]
    pd.DataFrame(trials).reindex(columns=cols2).to_csv(paths.data / "exp2_trials.csv", index=False)
    cols3 = ["trial_id", "runner", "repeat", "zip_file", "valid", "notes", "knee", "video_file", "video_fps"]
    pd.DataFrame(swings).reindex(columns=cols3).to_csv(paths.data / "exp3_swings.csv", index=False)
    pd.DataFrame(people).to_csv(paths.data / "participants.csv", index=False)
    pd.DataFrame(checks).reindex(columns=["trial_id", "kind", "event_no", "video_file", "fps", "frames", "value_s",
                                          "measurer", "notes"]).to_csv(paths.data / "video_checks.csv", index=False)
    knee_pt = (420 * 0 + 400 * math.sin(math.radians(85)), 420 + 400 * math.cos(math.radians(85)))
    pd.DataFrame([dict(trial_id="E3_A_K_1", event="pendulum_bent", event_no=1, hip_x=0, hip_y=0, knee_x=0,
                       knee_y=420, ankle_x=knee_pt[0], ankle_y=knee_pt[1])]).to_csv(
        paths.data / "video_markers.csv", index=False)
    pd.DataFrame(base).to_csv(paths.results / "participants.csv", index=False)
    pd.DataFrame(segs).to_csv(paths.results / "segments.csv", index=False)
    pd.DataFrame([dict(participant=p, row_type="summary", playlist="", pc_spm=s["pc"], sesoi_pct=1.5,
                       t_low_pct=104.0, t_high_pct=NAN, t_high_s3_pct=NAN, bpm_low=1.04 * s["pc"], bpm_high=NAN,
                       statement="", flags="t_high는 실험 2 뒤") for p, s in SYN_PEOPLE.items()]).to_csv(
        paths.results / "prescription.csv", index=False)
    return truth


# --- zip 연결 제안(D-55: zip_file이 비면 기록 시작 순서로 기록지 시행 순서와 맞춘다. A가 확인한 뒤 채운다) ---


def _detect_kind(path: Path, params: Params) -> tuple[str, float]:
    """zip 하나가 진자(swing)·시행(trial)·점프(jump) 중 무엇처럼 보이는가와 기록 길이(s). 연결 확인용이다.

    순서: 자이로 흔들림이 크고 이어지면 swing → 걷기 묶음이 있으면 trial(시작의 싱크 점프가 있어도) →
    체공(`jump.min_flight_s` 이상)이 2개 이상이면 jump → 그 밖은 unknown.
    """
    from walkmusic.exp2 import exp2_params
    from walkmusic.steps import detect_steps

    rec = read_zip(path, params)
    dur = float(rec.t("Accelerometer")[-1]) if rec.has("Accelerometer") else NAN
    if rec.has("Gyroscope"):
        s = analyze_gyro(rec.t("Gyroscope"), rec.xyz("Gyroscope"), params)
        if (s["n_cycles_total"] >= params["pendulum.min_cycles"] // 2
                and s["omega_peak_rad_s"] >= params["exp2.link_swing_min_omega_rad_s"]):
            return "swing", dur
    if rec.has("Accelerometer"):
        t, total, grav = total_accel_g(rec, determine_units(rec))
        if detect_steps(t, total, grav, exp2_params(params)).bouts:
            return "trial", dur
        if len(analyze_jumps(t, total, grav, params, NAN)) >= 2:
            return "jump", dur
    return "unknown", dur


def propose_links23(paths: Paths23, params: Params, date: str | None = None) -> pd.DataFrame:
    """사람마다, 어디에도 쓰이지 않은 zip을 기록 시작 순서로 놓고 zip_file이 빈 기록지 줄(실험 2 순서 → 실험 3 순서)과
    짝짓는다. 신호 모양이 기대와 다르면 status=check, 남거나 모자라면 extra_zip·no_zip. 결과는 제안일 뿐이다.
    """
    from walkmusic.io_sensorlogger import read_start_epoch

    used = set(read_table(paths.data / "manifest.csv").get("zip_file", pd.Series(dtype=str)))
    sheets = {n: read_table(paths.data / n) for n in ("exp2_trials.csv", "exp3_swings.csv")}
    for s in sheets.values():
        used |= set(s.get("zip_file", pd.Series(dtype=str)))
    used.discard("")
    rows = []
    for runner in sorted({r for s in sheets.values() for r in s.get("runner", [])}):
        want = []
        for name, s in sheets.items():
            for r in s[s["runner"] == runner].to_dict("records"):
                if not str(r.get("zip_file", "")).strip():
                    ratio = str(r.get("ratio_pct", "")).strip().upper()
                    kind = "swing" if name.startswith("exp3") else "jump" if ratio == "J" else "trial"
                    want.append((r["trial_id"], kind))
        folder = paths.raw / runner
        zips = []
        for z in sorted(folder.glob("*.zip")) if folder.exists() else []:
            if z.name in used:
                continue
            epoch, _ = read_start_epoch(z)
            start = pd.Timestamp(epoch, unit="ns", tz="UTC").tz_convert(params["time.timezone"])
            if date and start.strftime("%Y-%m-%d") != date:
                continue
            zips.append((start, z))
        zips.sort(key=lambda x: x[0])
        for k in range(max(len(want), len(zips))):
            tid, kind = want[k] if k < len(want) else ("", "")
            row = dict(runner=runner, order=k + 1, trial_id=tid, expected_kind=kind, zip_name="", start_kst="",
                       duration_s=NAN, detected_kind="", status="no_zip")
            if k < len(zips):
                start, z = zips[k]
                det, dur = _detect_kind(z, params)
                row.update(zip_name=z.name, start_kst=start.strftime("%Y-%m-%d %H:%M:%S"), duration_s=round(dur, 1),
                           detected_kind=det, status="extra_zip" if not tid else "ok" if det == kind else "check")
            rows.append(row)
    return pd.DataFrame(rows, columns=["runner", "order", "trial_id", "expected_kind", "zip_name", "start_kst",
                                       "duration_s", "detected_kind", "status"])
