"""실험 2: 템포 챌린지 (SPEC §4.4–4.6, §5.7, DECISIONS D-04·D-10·D-13·D-39·D-54·D-55·D-56·D-57·D-73).

원칙: 기록지 값(t30, N, 걷기/뛰기)은 사람이 읽은 값, 센서 값(체공, 충격, 센서 케이던스)은 코드가 낸 값.
한 표에 나란히 둔다.

시행 하나(센서):
1. 걸음 검출은 실험 1과 같고 걸음 간격 하한만 `exp2.min_interval_s`(0.23 s, D-56).
2. 시행 = 걸음이 가장 많은 걷기 묶음. 싱크 점프 = 그 앞의 점프 사건(§4.6의 수직 점프와 같은 정의: 밀기 → 0.2 g
   아래로 이륙 → 첫 충격 앞 1 g 위로 착지, D-77) 가운데 마지막 `exp2.n_sync_jumps`개, 착지 시각을
   `sync_jumps_sensor_s`로 낸다(영상 시각을 센서 시각으로 옮길 때 쓴다). 가만히 선 구간 조건은 쓰지 않는다.
   전에는 체공(§4.4)으로 찾았는데 파우치 출렁임으로 점프를 놓치거나 착지 뒤 튕김을 골랐다(D-80).
3. 분석 창: 기록지의 `t_in_sensor_s`~`t_out_sensor_s`가 있으면 그 창, 없으면 그 묶음 걸음의 가운데
   `exp2.central_step_frac`(75%)이고 flags=central_steps(D-13).
4. 창 안 유효 간격(0.23–`steps.max_interval_s`)으로 케이던스, S3·S5·반/두 배 박자, CV, 충격 중앙값.
5. 체공: 창 안 체공 이벤트를 걸음 간격마다 더한 t_f, 접촉 t_c = 간격 − t_f. 체공 있는 걸음 비율, 체공·접촉 중앙값.
   센서 판정: 비율 ≥ `exp2.sensor_run_frac`이면 run, 0이면 walk, 사이는 mixed. 영상과 다르면 gait_mismatch.
   센서 판정이 run이 아니면(체공이 걸음의 절반 미만에서만 잡힘) 체공·접촉 값을 비우고 few_flights(D-74).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from walkmusic.config import Params
from walkmusic.exp1 import _lowpass, _step_impacts
from walkmusic.exp3 import _uniform
from walkmusic.jumps import _crossing, _jump_events
from walkmusic.metrics import flight_events, froude, running_flight, spring_mass, sync_counts
from walkmusic.orientation import vertical_signal
from walkmusic.stats import _row
from walkmusic.steps import detect_steps

NAN = float("nan")
MEAN_COLS = ("bpm_played", "pc_field_spm", "tempo_ratio_pct", "v_ms", "cadence_record_spm", "cadence_median_spm",
             "cadence_rate_spm", "sync3_pct", "sync5_pct", "sync3_half_pct", "sync3_double_pct", "cv_pct", "impact_g",
             "flight_step_frac", "flight_time_median_s", "rise_height_m", "contact_time_s", "dC_pct")
SPRING_COLS = ("fmax_bw", "delta_y_m", "delta_l_m", "kvert_kn_m", "kleg_kn_m", "elastic_energy_j",
               "mean_grf_contact_bw")
GAIT_WORDS = {"walk": ("walk", "w", "걷기", "걸음", "걷"), "run": ("run", "r", "뛰기", "달리기", "뜀", "뛰"),
              "mixed": ("mixed", "m", "mix", "섞임", "혼합")}


def normalize_gait(label) -> str:
    """영상 판정 표기 → walk·run·mixed. 비었으면 '', 알 수 없는 말이면 unknown(기록지는 한글로도 적는다)."""
    s = str(label).strip().lower()
    if s in ("", "nan", "none"):
        return ""
    for name, words in GAIT_WORDS.items():
        if s in words:
            return name
    return "unknown"


def exp2_params(params: Params) -> Params:
    """실험 2용 설정: 걸음 간격 하한(검출 최소 간격 포함)만 `exp2.min_interval_s`로(D-56)."""
    return params.with_overrides({"steps.min_interval_s": params["exp2.min_interval_s"]})


def central_window(steps_t: np.ndarray, frac: float) -> tuple[float, float]:
    """걸음 열의 가운데 frac 부분 [첫 걸음, 마지막 걸음] 시각(D-13). 양쪽에서 같은 수의 걸음을 뺀다."""
    n = len(steps_t)
    k = int(np.floor(n * (1 - frac) / 2))
    return float(steps_t[k]), float(steps_t[n - 1 - k])


def _flight_intervals(tg: np.ndarray, mag: np.ndarray, fs: float, params: Params) -> list[tuple[float, float]]:
    thr = params["flight.a_thresh_g"]
    return [(_crossing(tg, mag, i, thr), _crossing(tg, mag, j, thr))
            for i, j in flight_events(mag, fs, thr, params["flight.min_duration_s"])]


def empty_trial_result() -> dict:
    """센서 값이 없는 시행(zip 없음·못 읽음)의 같은 열 틀."""
    return dict(n_steps_window=0, window_t0_s=NAN, window_t1_s=NAN, window_method="", cadence_median_spm=NAN,
                cadence_rate_spm=NAN, n_valid_intervals=0, sync3_pct=NAN, sync5_pct=NAN, sync3_half_pct=NAN,
                sync3_double_pct=NAN, cv_pct=NAN, impact_g=NAN, flight_step_frac=NAN, flight_time_median_s=NAN,
                contact_time_s=NAN, rise_height_m=NAN, sensor_gait="", n_sync_jumps=0, sync_jump_sensor_s="",
                n_bouts=0, flags=[], _tf=np.array([]), _tc=np.array([]))


def analyze_trial(t: np.ndarray, total_g: np.ndarray, gravity: np.ndarray, params: Params, bpm: float = NAN,
                  t_in: float = NAN, t_out: float = NAN) -> dict:
    """실험 2 시행 하나의 센서 값. total_g는 총 가속도(g, N×3). bpm은 실제로 틀어 준 BPM(무음이면 NaN)."""
    p2 = exp2_params(params)
    st = detect_steps(t, total_g, gravity, p2)
    out = empty_trial_result()
    out["n_bouts"] = len(st.bouts)
    tg, x, fs = _uniform(np.asarray(t, float), np.column_stack([total_g, gravity]))
    mag = np.linalg.norm(x[:, :3], axis=1)
    flights = _flight_intervals(tg, mag, fs, params)
    if not st.bouts:
        out["flags"].append("no_walking")
        return out
    if len(st.bouts) > 1:
        out["flags"].append("multiple_bouts")
    b0, b1, _ = max(st.bouts, key=lambda b: b[2])
    av = vertical_signal(x[:, :3], x[:, 3:])
    # 싱크 점프는 체공이 아니라 점프 사건(D-77)으로 찾는다: 공중에서 파우치가 출렁이면 체공을 놓치고, 착지 뒤 튕김이
    # 체공으로 잡혀 엉뚱한 3개를 골랐다(D-80, 2026-11-20 test-sync·test-sync-2)
    sync = [e for e in _jump_events(tg, av, fs, params) if e[2] < b0][-params["exp2.n_sync_jumps"]:]
    out.update(n_sync_jumps=len(sync), sync_jump_sensor_s=";".join(f"{e[2]:.3f}" for e in sync))
    if len(sync) != params["exp2.n_sync_jumps"]:
        out["flags"].append(f"sync_jumps_{len(sync)}")

    bout = st.t_s[(st.t_s >= b0 - 1e-9) & (st.t_s <= b1 + 1e-9)]
    if np.isfinite(t_in) and np.isfinite(t_out) and t_out > t_in:
        w0, w1, method = float(t_in), float(t_out), "video"
    else:
        (w0, w1), method = central_window(bout, params["exp2.central_step_frac"]), "central_steps"
        out["flags"].append("central_steps")
    steps = st.t_s[(st.t_s >= w0 - 1e-9) & (st.t_s <= w1 + 1e-9)]
    out.update(n_steps_window=len(steps), window_t0_s=w0, window_t1_s=w1, window_method=method)
    if len(steps) < 3:
        out["flags"].append("few_steps")
        return out
    iv = np.diff(steps)
    valid = (iv >= params["exp2.min_interval_s"]) & (iv <= params["steps.max_interval_s"])
    ok = iv[valid]
    out["n_valid_intervals"] = len(ok)
    if len(ok) >= 2:
        c = 60.0 / ok
        out.update(cadence_median_spm=float(np.median(c)), cadence_rate_spm=float(len(ok) / ok.sum() * 60),
                   cv_pct=float(ok.std(ddof=params["stats.sd_ddof"]) / ok.mean() * 100))
        if np.isfinite(bpm):
            s3, s5 = sync_counts(c, bpm, params["sync.tol_pct"]), sync_counts(c, bpm, params["sync.tol_alt_pct"])
            out.update(sync3_pct=s3["sync_pct"], sync5_pct=s5["sync_pct"], sync3_half_pct=s3["n_half"] / len(c) * 100,
                       sync3_double_pct=s3["n_double"] / len(c) * 100)
    imp = _step_impacts(tg, _lowpass(tg, av, params["steps.impact_lowpass_hz"]), steps,
                        params["steps.impact_window_s"])
    out["impact_g"] = float(np.nanmedian(imp)) if np.isfinite(imp).any() else NAN

    tf = np.zeros(len(iv))
    for a, b in flights:
        k = np.searchsorted(steps, a, side="right") - 1  # 체공이 시작된 걸음 간격
        if 0 <= k < len(iv):
            tf[k] += min(b, steps[k + 1]) - a
    tf, ivv = tf[valid], iv[valid]
    has = tf > 0
    frac = float(has.mean()) if len(has) else NAN
    out["flight_step_frac"] = frac
    out["sensor_gait"] = ("" if not np.isfinite(frac) else "run" if frac >= params["exp2.sensor_run_frac"]
                          else "walk" if frac == 0 else "mixed")
    if has.any() and out["sensor_gait"] != "run":
        # 폰이 체공을 걸음의 절반 미만에서만 잡았다: 체공을 제대로 못 잰 것이라(허리 파우치 출렁임) 체공·접촉 값을
        # 비우고 단계 중앙값에도 넣지 않는다. 그래서 스프링 지표도 빈다(D-74)
        out["flags"].append("few_flights")
    elif has.any():
        tfm = float(np.median(tf[has]))
        out.update(flight_time_median_s=tfm, contact_time_s=float(np.median(ivv[has] - tf[has])),
                   rise_height_m=params["constants.g"] * tfm**2 / 8)
        out["_tf"], out["_tc"] = tf[has], ivv[has] - tf[has]  # 단계 중앙값용(표에는 쓰지 않는다)
    return out


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return NAN


def _ratio_key(r: str) -> float:
    return _num(r) if str(r).replace(".", "", 1).isdigit() else -1.0


def _gait(values: pd.Series) -> str:
    """단계 걸음새: 시행 판정이 모두 walk면 walk, 모두 run이면 run, 섞이면 mixed. 빈칸·unknown은 빼고 본다."""
    v = {normalize_gait(x) for x in values} - {"", "unknown"}
    if not v:
        return ""
    return "walk" if v == {"walk"} else "run" if v == {"run"} else "mixed"


def stage_summary(trials: pd.DataFrame, legs: dict[str, float], params: Params, sesoi: dict[str, float] | None = None,
                  body: dict[str, dict] | None = None, phases: dict[str, tuple] | None = None,
                  video: dict[tuple[str, str, int], float] | None = None) -> pd.DataFrame:
    """시행 표 → 단계 표(사람 × 비율). 수치는 시행 평균, Fr는 평균 속도로(D-57), 평균 동조(D-54).

    body가 있으면(사람 → mass_kg) 달리기 단계의 스프링 값을 단계 중앙값 t_c·t_f로 계산한다(D-39).
    phases: trial_id → (t_f 배열, t_c 배열). 없으면 시행 중앙값의 평균을 쓴다.
    video: (trial_id, kind, 번호) → 초(`video_checks.csv`). 폰 체공이 빈(D-74) 달린 단계는 발 카메라 프레임의
    접촉 시간 `run_contact`로 낸다(D-86). 체공은 `run_flight`가 있으면 그 값, 없으면 걸음 간격 − 접촉.
    """
    g = params["constants.g"]
    tol = params["sync.tol_pct"] / 100
    cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"
    rows = []
    for (runner, ratio), d in trials.groupby(["runner", "ratio_pct"], sort=False):
        row = dict(runner=runner, ratio_pct=str(ratio), n_trials=len(d))
        for col in MEAN_COLS:
            if col in d:
                vals = pd.to_numeric(d[col], errors="coerce")
                row[col] = float(vals.mean()) if vals.notna().any() else NAN
        row["gait_video"] = _gait(d["gait_video"]) if "gait_video" in d else ""
        leg = legs.get(runner, NAN)
        v = row.get("v_ms", NAN)
        row["fr"] = froude(v, leg, g) if np.isfinite(v) and np.isfinite(leg) else NAN
        c, bpm = row.get(cprim, NAN), row.get("bpm_played", NAN)
        row["mean_sync"] = bool(abs(c / bpm - 1) <= tol) if np.isfinite(c) and np.isfinite(bpm) else "NA"
        s = (sesoi or {}).get(runner, NAN)
        dc = row.get("dC_pct", NAN)
        row["change_class"] = ("" if not (np.isfinite(dc) and np.isfinite(s)) else "within_band" if abs(dc) <= s
                               else "meaningful_up" if dc > 0 else "meaningful_down")
        flags = sorted({f for x in d.get("flags", pd.Series(dtype=str)).fillna("") for f in str(x).split(";") if f})
        mass = (body or {}).get(runner, {}).get("mass_kg", NAN)
        ids = [i for i in d.get("trial_id", []) if phases and i in phases]
        tf_all = np.concatenate([phases[i][0] for i in ids] or [[]])
        tc_all = np.concatenate([phases[i][1] for i in ids] or [[]])
        if len(tf_all):  # 단계 값은 두 시행의 걸음을 모은 중앙값(SPEC §4.6)
            row.update(flight_time_median_s=float(np.median(tf_all)), contact_time_s=float(np.median(tc_all)),
                       rise_height_m=g * float(np.median(tf_all)) ** 2 / 8)
        tfm, tcm = row.get("flight_time_median_s", NAN), row.get("contact_time_s", NAN)
        tids = set(d["trial_id"]) if "trial_id" in d else set()
        seen = {kind: [x for (i, k, _), x in (video or {}).items() if i in tids and k == kind and np.isfinite(x)]
                for kind in ("run_contact", "run_flight")}
        row["phase_source"] = "phone" if np.isfinite(tfm) and np.isfinite(tcm) else ""
        row["n_contacts_video"] = len(seen["run_contact"])
        if row["gait_video"] == "run" and not row["phase_source"] and seen["run_contact"]:  # D-86
            tcm = float(np.median(seen["run_contact"]))
            flags.append("tc_video")
            if seen["run_flight"]:
                tfm = float(np.median(seen["run_flight"]))
            else:  # 다음 발의 착지가 화면 밖이다: 걸음 간격에서 접촉을 뺀다(SPEC §4.6과 같은 관계)
                tfm = 60 / c - tcm if np.isfinite(c) and c > 0 else NAN
                flags.append("tf_from_cadence")
            row.update(contact_time_s=tcm, phase_source="video")
            if np.isfinite(tfm) and tfm > 0:
                row.update(flight_time_median_s=tfm, rise_height_m=g * tfm**2 / 8)
            else:  # 접촉이 걸음 간격보다 길다: 체공과 스프링 값은 내지 않는다
                tfm = NAN
                flags.append("no_flight_from_video")
        if row["gait_video"] in ("run", "mixed") and np.isfinite(mass) and np.isfinite(leg) and np.isfinite(v):
            if np.isfinite(tfm) and np.isfinite(tcm):
                row.update({k: val for k, val in spring_mass(mass, tcm, tfm, v, leg, g).items()
                            if k in ("fmax_bw", "delta_y_m", "delta_l_m", "kvert_kn_m", "kleg_kn_m",
                                     "elastic_energy_j", "mean_grf_contact_bw")})
                row["takeoff_angle_deg"] = running_flight(v, tfm, g)["takeoff_angle_deg"]
            if row["gait_video"] == "mixed":
                flags.append("mixed_gait")
        row["flags"] = ";".join(flags)
        rows.append(row)
    out = pd.DataFrame(rows)
    for col in (*SPRING_COLS, "takeoff_angle_deg"):  # 달린 단계가 없어도 열은 있다(SPEC §7)
        if col not in out:
            out[col] = NAN
    if len(out):
        out = out.assign(_k=out["ratio_pct"].map(_ratio_key)).sort_values(["runner", "_k"]).drop(columns="_k")
    return out.reset_index(drop=True)


def _stages(summary: pd.DataFrame, runner: str) -> pd.DataFrame:
    s = summary[(summary["runner"] == runner) & (summary["ratio_pct"].map(_ratio_key) > 0)]
    return s.assign(_k=s["ratio_pct"].map(_ratio_key)).sort_values("_k")


def h12_rows(summary: pd.DataFrame, params: Params) -> list[dict]:
    """가설 1-2(D-10): 100%와 120% 단계 각각에서 S3 ≥ `exp2.h1_2_min_sync_frac`. 평균 동조(D-54)는 함께 적는다."""
    need = params["exp2.h1_2_min_sync_frac"] * 100
    rows = []
    for p in sorted(summary["runner"].unique()):
        s = _stages(summary, p).set_index("ratio_pct")
        have = [r for r in ("100", "120") if r in s.index and np.isfinite(_num(s.loc[r, "sync3_pct"]))]
        note = "; ".join(f"{r}%: S3 {float(s.loc[r, 'sync3_pct']):.1f}%, 평균 동조 {s.loc[r, 'mean_sync']}"
                         for r in have)
        if len(have) < 2:
            rows.append(_row("H1-2", p, "S3 at 100% and 120%", n=len(have), criterion=f"S3 >= {need:.0f}% at both",
                             note=(note + "; " if note else "") + "100%·120% 단계가 다 있어야 판정한다"))
            continue
        vals = [float(s.loc[r, "sync3_pct"]) for r in have]
        rows.append(_row("H1-2", p, "S3 at 100% and 120%", min(vals), n=2, criterion=f"S3 >= {need:.0f}% at both",
                         supported=bool(min(vals) >= need), note=note))
    return rows


def h3_rows(trials: pd.DataFrame, summary: pd.DataFrame, params: Params) -> list[dict]:
    """가설 3(D-57): 마지막으로 걸은 단계의 Fr ≤ 0.5 ≤ 처음 뛴 단계의 Fr. 영상 판정이 기준."""
    lim = params["stats.froude_walk_run"]
    crit = f"Fr(last walk) <= {lim} <= Fr(first run)"
    rows = []
    for p in sorted(summary["runner"].unique()):
        s = _stages(summary, p)
        gaits = {str(r): [normalize_gait(x) for x in d["gait_video"]]
                 for r, d in trials[trials["runner"] == p].groupby("ratio_pct")}
        order = list(s["ratio_pct"])
        if not any(x in ("walk", "run", "mixed") for r in order for x in gaits.get(r, [])):
            rows.append(_row("H3", p, "Fr at transition", criterion=crit,
                             note="영상 판정(gait_video)이 비어 판정 못 함"))
            continue
        unclear = [r for r in order if any(x in ("", "unknown") for x in gaits.get(r, [""]))]
        notes = [f"영상 판정이 비었거나 알 수 없는 단계: {', '.join(unclear)}%"] if unclear else []
        run = [r for r in order if any(x in ("run", "mixed") for x in gaits.get(r, []))]
        if not run:
            rows.append(_row("H3", p, "Fr at transition", criterion=crit,
                             note="; ".join(["no_run: 가장 높은 단계에서도 걷기(F6)"] + notes)))
            continue
        first = run[0]
        below = [r for r in order[:order.index(first)] if gaits.get(r) and all(x == "walk" for x in gaits[r])]
        above = [r for r in order[order.index(first) + 1:] if gaits.get(r) and all(x == "walk" for x in gaits[r])]
        if above:
            notes.append(f"non_monotonic: {', '.join(above)}%에서 다시 두 시행 모두 걷기")
        fr = s.set_index("ratio_pct")["fr"]
        if not below:
            rows.append(_row("H3", p, "Fr at transition", criterion=crit,
                             note="; ".join([f"처음 뛴 단계 {first}%보다 낮은 걷기 단계가 없다"] + notes)))
            continue
        last = below[-1]
        f_walk, f_run = float(fr[last]), float(fr[first])
        if not (np.isfinite(f_walk) and np.isfinite(f_run)):
            rows.append(_row("H3", p, "Fr at transition", criterion=crit,
                             note="; ".join(["다리 길이나 속도(t30)가 없어 Fr를 못 낸다"] + notes)))
            continue
        notes.insert(0, f"마지막 걷기 {last}% Fr {f_walk:.3f}, 처음 뜀 {first}% Fr {f_run:.3f}")
        rows.append(_row("H3", p, "Fr at transition", f_run, n=2, criterion=crit,
                         supported=bool(f_walk <= lim <= f_run), note="; ".join(notes)))
    return rows


def prescription_upper(summary: pd.DataFrame, params: Params) -> pd.DataFrame:
    """처방 범위 상한(SPEC §4.5, D-54): T 순서로 처음 평균 동조가 깨진 단계 바로 앞 단계의 T.

    T_high_s3는 처음 S3 < `exp2.h1_2_min_sync_frac`가 된 단계 바로 앞. 100% 단계부터 깨지면 NaN(없음).
    끝까지 깨지지 않으면 가장 높은 단계의 T와 flags=not_broken.
    """
    tol = params["sync.tol_pct"] / 100
    need = params["exp2.h1_2_min_sync_frac"] * 100
    cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"
    out = []
    for p in sorted(summary["runner"].unique()):
        s = summary[(summary["runner"] == p) & (summary["ratio_pct"].map(_ratio_key) > 0)]
        s = s.sort_values("tempo_ratio_pct")
        t = s["tempo_ratio_pct"].astype(float).to_numpy()
        c, b, s3 = (s[k].astype(float).to_numpy() for k in (cprim, "bpm_played", "sync3_pct"))
        row, flags = dict(runner=p), []
        # 값이 빈 단계는 '깨짐'이 아니라 '모름'이라 건너뛰고 표시한다
        have_sync = np.isfinite(t) & np.isfinite(c) & np.isfinite(b)
        have_s3 = np.isfinite(t) & np.isfinite(s3)
        ok_sync, ok_s3 = np.zeros(len(t), bool), np.zeros(len(t), bool)
        ok_sync[have_sync] = np.abs(c[have_sync] / b[have_sync] - 1) <= tol
        ok_s3[have_s3] = s3[have_s3] >= need
        for name, have, ok in (("t_high_pct", have_sync, ok_sync), ("t_high_s3_pct", have_s3, ok_s3)):
            flags += [f"missing_{r}" for r, h in zip(s["ratio_pct"], have, strict=True)
                      if not h and f"missing_{r}" not in flags]
            tt, okk = t[have], ok[have]
            broken = np.where(~okk)[0]
            if not len(tt):
                row[name] = NAN
            elif not len(broken):
                row[name] = float(tt[-1])
                flags.append(f"{name}_not_broken")
            else:
                row[name] = float(tt[broken[0] - 1]) if broken[0] > 0 else NAN
        row["flags"] = ";".join(flags)
        out.append(row)
    return pd.DataFrame(out)
