"""측정 검증표 (SPEC §5.10, DECISIONS D-38).

폰으로 잰 값(방법 A)과 다른 방법의 값(방법 B)을 짝지어 Bland–Altman(차이 = A − B, 95% 일치 한계 = bias ± 1.96 SD)을
한 표(`validation.csv`)에 낸다. 통과 기준은 두지 않고 그대로 보고한다. 사람마다 한 줄, 두 명 이상이면 ALL 줄을 더한다.
입력은 이미 계산된 결과 표다: 실험 1의 segments·walks, 실험 2·3의 exp2_stages·jumps·exp3_swings, 영상 판독 표.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from walkmusic.config import Params
from walkmusic.metrics import bland_altman
from walkmusic.qa import Paths, _hand_window, analyze_walk, read_table

NAN = float("nan")
COLS = ["measure", "participant", "n", "mean_a", "mean_b", "bias", "loa_low", "loa_high", "mean_abs_diff", "unit",
        "resolution", "method_a", "method_b", "note"]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """표의 열을 숫자로(없거나 빈칸이면 NaN)."""
    if col not in df:
        return pd.Series(NAN, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _flag(df: pd.DataFrame, word: str) -> pd.Series:
    if "flags" not in df:
        return pd.Series(False, index=df.index)
    return df["flags"].fillna("").astype(str).str.contains(word)


def _keep(df: pd.DataFrame, mask: pd.Series | None = None, who: str = "runner") -> pd.DataFrame:
    """쓸 줄만 남기고 줄 번호를 0부터 다시 매긴다(빈 표면 who 열만 있는 빈 표)."""
    if not len(df):
        return pd.DataFrame(columns=[who])
    return (df if mask is None else df[mask]).reset_index(drop=True)


def _block(measure: str, who, a, b, ddof: int, unit: str, method_a: str, method_b: str, resolution: str = "",
           note: str = "", note_fn: Callable[[pd.DataFrame], str] | None = None, loa: bool = True) -> list[dict]:
    """짝지은 값 → 사람마다 한 줄(+ 두 명 이상이면 ALL). 짝이 없으면 n = 0인 ALL 한 줄.

    note_fn은 그 줄에 들어간 짝들(열 who·a·b, 줄 번호는 넘겨준 순서)을 받아 덧붙일 말을 돌려준다.
    """
    df = pd.DataFrame(dict(who=list(who), a=np.asarray(a, float), b=np.asarray(b, float)))
    df = df[np.isfinite(df["a"]) & np.isfinite(df["b"])]
    groups = [(str(p), d) for p, d in df.groupby("who", sort=True)]
    if len(groups) != 1:
        groups.append(("ALL", df))
    rows = []
    for p, d in groups:
        ba = bland_altman(d["a"], d["b"], ddof)
        notes = [note] if note else []
        if ba["n"] and ba["mean_b"]:
            notes.append(f"A − B 평균 {ba['bias'] / ba['mean_b'] * 100:+.1f}%")
        if note_fn is not None and ba["n"]:
            notes += [x for x in [note_fn(d)] if x]
        if p == "ALL" and len(groups) > 1 and ba["n"]:
            notes.append("한 사람 안의 짝들은 서로 독립이 아니다")
        rows.append(dict(measure=measure, participant=p, n=ba["n"], mean_a=ba["mean_a"], mean_b=ba["mean_b"],
                         bias=ba["bias"], loa_low=ba["loa_low"] if loa else NAN,
                         loa_high=ba["loa_high"] if loa else NAN, mean_abs_diff=ba["mean_abs_diff"], unit=unit,
                         resolution=resolution, method_a=method_a, method_b=method_b, note=". ".join(notes)))
    return rows


def _frame(fps: float) -> str:
    return f"영상 1프레임 = 1/{fps:g} s({1000 / fps:.1f} ms)" if np.isfinite(fps) and fps > 0 else ""


def validation_table(trials: pd.DataFrame, jumps: pd.DataFrame, swings: pd.DataFrame, segments: pd.DataFrame,
                     walks: pd.DataFrame, video_checks: pd.DataFrame, hand_counts: pd.DataFrame, params: Params,
                     fps: dict[str, float] | None = None) -> pd.DataFrame:
    """결과 표들 → 검증표. 비어 있는 표는 그 비교를 n = 0으로 남긴다.

    fps: 영상 초당 프레임 수 {"exp2", "jump", "swing", "run"}(분해능을 적는 데만 쓴다).
    hand_counts: participant, detected, hand(직접 센 걸음 수와 같은 창의 검출 걸음 수).
    """
    ddof = params["stats.sd_ddof"]
    fps = fps or {}
    cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"
    rows: list[dict] = []

    t = _keep(trials, ~_flag(trials, "invalid_sheet"))
    rows += _block("exp2_cadence", t["runner"], _num(t, "cadence_record_spm"), _num(t, cprim), ddof,
                   "spm", "기록지 N ÷ t30 × 60(영상에서 읽은 걸음 수와 30 m 시간, D-83)",
                   "센서 케이던스(분석 창 안 순간 케이던스의 중앙값)",
                   (_frame(fps.get("exp2", NAN)) + ", N은 1걸음").lstrip(", "),
                   "센서 창은 걸음 열의 가운데 75%(D-13 대안)라 영상의 30 m 구간과 같은 걸음이 아니다")

    j = _keep(jumps)

    def jump_note(d: pd.DataFrame) -> str:
        only = int(_flag(j.loc[d.index], "invalid_sheet").sum())
        return f"검증에만 쓰는 기록(valid=0, D-87)의 점프 {only}개 포함" if only else ""

    rows += _block("jump_flight", j["runner"], _num(j, "flight_time_s"), _num(j, "flight_time_video_s"), ddof, "s",
                   "폰 체공 t_f(가속도 사건, D-77)", "영상 체공(이륙·착지 프레임 시각의 차, D-84)",
                   _frame(fps.get("jump", NAN)), note_fn=jump_note)
    jv = _keep(j, ~_flag(j, "invalid_sheet"))
    rows += _block("jump_takeoff_velocity", jv["runner"], _num(jv, "takeoff_v_flight_ms"),
                   _num(jv, "takeoff_v_int_ms"), ddof, "m/s", "v_flight = g t_f ÷ 2", "v_int(밀기 구간 가속도 적분)")

    s = _keep(swings, ~_flag(swings, "no_swing"))
    f_sw = fps.get("swing", NAN)

    def swing_note(d: pd.DataFrame) -> str:
        k = s.loc[d.index]
        bent = int((k["knee"] == "bent").sum())
        bad = int(_flag(k, "invalid_sheet").sum())
        return f"곧은 다리 {len(k) - bent}개·굽힌 다리 {bent}개" + (f", valid=0 시행 {bad}개 포함" if bad else "")

    rows += _block("swing_period", s["runner"], _num(s, "swing_period_s"), _num(s, "video_period_s"), ddof, "s",
                   "폰 주기 P·P_K(정강이 자이로 봉우리 간격의 중앙값)", "영상 10번 흔들림 시간 ÷ 10(D-84)",
                   (_frame(f_sw) + f", 10주기로 나눠 {100 / f_sw:.1f} ms") if np.isfinite(f_sw) else "",
                   "폰은 주기의 중앙값, 영상은 10주기 평균", swing_note)

    g = _keep(segments, ~_flag(segments, "gps_sparse"), "participant")
    rows += _block("step_length", g["participant"], _num(g, "step_length_zh_m"), _num(g, "step_length_m"), ddof, "m",
                   f"역진자 보폭 SL_ZH(몸 중심 수직 변위, K = {params['com.zh_correction']:g}, D-40)",
                   "보폭 SL = GPS 경로 속도 ÷ 케이던스(D-01)", note="곡 구간마다 한 짝",
                   note_fn=lambda d: f"SL_ZH ÷ SL 평균 {(d['a'] / d['b']).mean():.2f}")

    v = video_checks if len(video_checks) else pd.DataFrame(columns=["trial_id", "kind", "value_s"])
    for kind, col, label in (("run_contact", "contact_time_s", "접촉 t_c"), ("run_flight", "flight_time_median_s",
                                                                           "체공 t_f")):
        vid = v[v["kind"] == kind].assign(x=lambda d: pd.to_numeric(d["value_s"], errors="coerce"))
        by_trial = vid.groupby("trial_id")["x"].median()
        video = t["trial_id"].map(by_trial) if len(t) else pd.Series(dtype=float)
        rows += _block(f"{kind}_time", t["runner"], _num(t, col), video, ddof, "s",
                       f"폰 {label}(달린 단계의 시행 중앙값)", f"발 카메라 프레임에서 읽은 {label}(D-86)",
                       _frame(fps.get("run", NAN)),
                       f"영상 판독 {int(vid['x'].notna().sum())}개. 폰 값은 체공이 걸음의 절반 미만에서만 잡혀 "
                       "비웠다(D-74): 짝이 없으면 n = 0")

    w = _keep(walks, _num(walks, "mean_av_g").notna(), "participant")
    av = _num(w, "mean_av_g")
    rows += _block("mean_vertical_accel", w["participant"], av, np.ones(len(w)), ddof, "g",
                   "걷는 동안 평균 수직 가속도 ā_v(회차마다)", "이론값 1 g(등속 보행)", loa=False,
                   note_fn=lambda d: (f"SD {d['a'].std(ddof=ddof):.4f} g, " if len(d) > ddof else "")
                   + f"범위 {d['a'].min():.3f}–{d['a'].max():.3f} g")

    h = hand_counts if len(hand_counts) else pd.DataFrame(columns=["participant", "detected", "hand"])
    rows += _block("steps_100", h["participant"], _num(h, "detected"), _num(h, "hand"), ddof, "steps", "검출 걸음 수",
                   "직접 센 걸음 수(사전 점검 100걸음, Q06)", "1걸음")
    sec = _num(w, "section_gps_m")
    rows += _block("section_distance", w["participant"], sec, _num(w, "speed_section_ms") * _num(w, "section_time_s"),
                   ddof, "m", "측정 구간 GPS 경로 거리(구간 통과 두 시각 사이, Q08a)", "지도 거리",
                   "위치 점 약 1 Hz")
    rows += _block("section_speed_doppler", w["participant"], _num(w, "speed_doppler_section_ms"),
                   _num(w, "speed_section_ms"), ddof, "m/s", "Doppler 속도 중앙값(구간 통과 두 시각 사이, 참고값)",
                   "지도 거리 ÷ 통과 시간(SPEC §5.5e)", "통과 시각 ±0.5 s(위치 점 약 1 Hz)")
    return pd.DataFrame(rows, columns=COLS)


def hand_count_rows(paths: Paths, params: Params) -> pd.DataFrame:
    """manifest에서 직접 센 걸음 수(`hand_step_count`)가 있는 기록의 검출 걸음 수(Q06과 같은 창)."""
    rows = []
    for r in read_table(paths.manifest).to_dict("records"):
        if not str(r.get("hand_step_count", "")).strip():
            continue
        w = analyze_walk(r, paths, params)
        if w.steps is None:
            continue
        win = _hand_window(r) or (w.steps.t_depart, w.steps.t_arrive)
        rows.append(dict(participant=r["participant"], walk_id=r["walk_id"], detected=len(w.steps.window_steps(*win)),
                         hand=float(r["hand_step_count"])))
    return pd.DataFrame(rows, columns=["participant", "walk_id", "detected", "hand"])


def _fps(sheet: pd.DataFrame, rows: pd.Series) -> float:
    vals = pd.to_numeric(sheet.loc[rows, "video_fps"], errors="coerce").dropna() if "video_fps" in sheet else []
    return float(np.median(vals)) if len(vals) else NAN


def build_validation(exp1: Paths, exp23_data: Path, exp23_results: Path, params: Params) -> pd.DataFrame:
    """결과 폴더의 표를 읽어 검증표를 만든다(쓰지는 않는다)."""
    t2, t3 = read_table(exp23_data / "exp2_trials.csv"), read_table(exp23_data / "exp3_swings.csv")
    checks = read_table(exp23_data / "video_checks.csv")
    is_jump = t2["ratio_pct"].str.upper() == "J" if len(t2) else pd.Series(dtype=bool)
    run_fps = pd.to_numeric(checks.loc[checks["kind"] == "run_contact", "fps"], errors="coerce").dropna() \
        if len(checks) else []
    fps = dict(exp2=_fps(t2, ~is_jump) if len(t2) else NAN, jump=_fps(t2, is_jump) if len(t2) else NAN,
               swing=_fps(t3, t3.index) if len(t3) else NAN, run=float(np.median(run_fps)) if len(run_fps) else NAN)

    def table(folder: Path, name: str) -> pd.DataFrame:
        p = folder / name
        return pd.read_csv(p) if p.exists() and p.stat().st_size > 1 else pd.DataFrame()

    res1 = Path(exp1.results)
    return validation_table(table(exp23_results, "exp2_stages.csv"), table(exp23_results, "jumps.csv"),
                            table(exp23_results, "exp3_swings.csv"), table(res1, "segments.csv"),
                            table(res1, "walks.csv"), checks, hand_count_rows(exp1, params), params, fps)
