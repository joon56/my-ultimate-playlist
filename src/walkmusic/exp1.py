"""실험 1: 곡 구간 나누기와 구간·회차 지표 (SPEC §5.5–5.6).

결정: D-01(속도 = 곡 구간 GPS 경로 거리 ÷ 시간, Doppler는 참고), D-05(케이던스는 순간 케이던스 중앙값),
D-07(충격 = 걸음 시각 ± 창의 a_v,total 최댓값), D-09(유효 간격 0.30–1.50 s), D-19(정지 앞뒤 제외),
D-59(간격은 앞 걸음이 속한 곡에), D-67(위치 점이 드물면 속도·보폭은 참고값), D-68(센서 끊김), D-70(서 있기 없음).
PC가 필요한 값(T, ΔC%, R, change_class)은 stats.add_tempo_columns가 붙인다. 좌표는 거리 계산에만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

from walkmusic.config import ROOT, Params
from walkmusic.io_sensorlogger import Recording, read_zip
from walkmusic.links import fill_walk_ids, find_zip, sheet_time
from walkmusic.metrics import sync_counts
from walkmusic.orientation import vertical_signal
from walkmusic.qa import Paths, _hav, read_table
from walkmusic.steps import analyze_recording
from walkmusic.units import total_accel_g

SKIP_STATUS = ("redo", "excluded", "test")
NAN = float("nan")


@dataclass
class Song:
    """재생된 곡 하나. t0·t1은 기록 시각(s)."""

    idx: int
    playlist: str
    order: str
    title: str
    bpm: float
    t0: float
    t1: float


def song_timeline(row: dict, music: pd.DataFrame, offset_s: float, rec_end_s: float) -> list[Song]:
    """회차의 곡 시간표(SPEC §5.5d). songs_played가 있으면 그 순서, 없으면 start_song부터 플레이리스트를 돈다.

    duration_s가 비면 추측하지 않고 ValueError. 목록 밖 곡(`X:제목`)을 만나면 그 뒤는 시각을 몰라 멈춘다.
    """
    cond = str(row.get("condition", ""))
    main = music[(music["playlist"] == cond) & (music["is_spare"].astype(str) != "1")]
    orders = sorted(main["order"].astype(str), key=int)
    if not orders:
        raise ValueError(f"music_bpm.csv에 플레이리스트 {cond}의 곡이 없다")
    lookup = {(str(r.playlist), str(r.order)): r for r in music.itertuples()}
    queue = []
    for s in str(row.get("songs_played") or "").split(";"):
        s = s.strip()
        if s:
            queue.append(("X", s[2:]) if s.startswith("X:") else tuple(x.strip() for x in s.split("-", 1)))
    start = str(int(float(row.get("start_song") or 1)))
    songs, t, cur = [], float(offset_s), None
    while t < rec_end_s:
        if queue:
            p, o = queue.pop(0)
            if p == "X":
                break
        else:
            p, o = cond, (start if cur is None else orders[(orders.index(cur) + 1) % len(orders)])
        r = lookup.get((p, o))
        if r is None:
            raise ValueError(f"music_bpm.csv에 {p}-{o}가 없다")
        dur = str(r.duration_s).strip()
        if not dur:
            raise ValueError(f"duration_s가 비었다: {p}-{o}({r.title}). 추측하지 않고 멈춘다(SPEC §5.5d)")
        songs.append(Song(len(songs), p, o, str(r.title), float(r.bpm_public), t, t + float(dur)))
        t += float(dur)
        cur = o if p == cond else cur
    return songs


def interval_table(t_steps: np.ndarray, t_depart: float, t_arrive: float, params: Params,
                   manual: list[tuple[float, float]] = ()) -> pd.DataFrame:
    """걸음 간격 표(t0, t1, interval_s, reason, valid). reason: edge·stop·manual·range, 빈 칸이면 유효(SPEC §5.5a–c)."""
    t = np.sort(np.asarray(t_steps, float))
    t0, t1 = t[:-1], t[1:]
    iv = t1 - t0
    reason = np.full(len(iv), "", dtype=object)
    w0, w1 = t_depart + params["exclude.edge_s"], t_arrive - params["exclude.edge_s"]
    reason[(t0 < w0) | (t1 > w1)] = "edge"
    stop = iv > params["exclude.stop_gap_s"]
    pad = params["exclude.stop_pad_s"]
    for a, b in zip(t0[stop] - pad, t1[stop] + pad, strict=True):
        reason[(reason == "") & (t1 > a) & (t0 < b)] = "stop"
    for a, b in manual:
        reason[(reason == "") & (t1 > a) & (t0 < b)] = "manual"
    lo, hi = params["steps.min_interval_s"], params["steps.max_interval_s"]
    reason[(reason == "") & ((iv < lo) | (iv > hi))] = "range"
    return pd.DataFrame(dict(t0=t0, t1=t1, interval_s=iv, reason=reason, valid=reason == ""))


def segment_metrics(iv: np.ndarray, impact: np.ndarray, bpm: float, params: Params) -> dict:
    """유효 간격(s)과 걸음마다 충격(g)으로 구간 지표. 유효 간격이 모자라면 NaN과 few_steps(D-08)."""
    iv, impact = np.asarray(iv, float), np.asarray(impact, float)
    n = len(iv)
    out = dict(n_valid_steps=n, valid_duration_s=float(iv.sum()), cadence_median_spm=NAN, cadence_rate_spm=NAN,
               cv_pct=NAN, impact_g=NAN, sync3_pct=NAN, sync5_pct=NAN, sync3_half_pct=NAN, sync3_double_pct=NAN,
               sub_super="", flags="")
    if n < params["qa.min_valid_steps_per_segment"]:
        out["flags"] = "few_steps"
        return out
    c = 60.0 / iv
    out.update(cadence_median_spm=float(np.median(c)), cadence_rate_spm=float(n / iv.sum() * 60),
               cv_pct=float(iv.std(ddof=params["stats.sd_ddof"]) / iv.mean() * 100),
               impact_g=float(np.nanmedian(impact)) if np.isfinite(impact).any() else NAN)
    if np.isfinite(bpm):
        s3 = sync_counts(c, bpm, params["sync.tol_pct"])
        s5 = sync_counts(c, bpm, params["sync.tol_alt_pct"])
        cprim = out["cadence_median_spm"] if params["cadence.primary"] == "median" else out["cadence_rate_spm"]
        r, tol = cprim / bpm, params["sync.tol_pct"] / 100
        sub_super = "sub" if abs(r - 0.5) <= 0.5 * tol else "super" if abs(r - 2) <= 2 * tol else "none"
        out.update(sync3_pct=s3["sync_pct"], sync5_pct=s5["sync_pct"], sync3_half_pct=s3["n_half"] / n * 100,
                   sync3_double_pct=s3["n_double"] / n * 100, sub_super=sub_super)
    return out


def _lowpass(t: np.ndarray, x: np.ndarray, hz: float) -> np.ndarray:
    fs = 1.0 / float(np.median(np.diff(t)))
    if hz >= fs / 2:
        return x
    b, a = butter(2, hz / (fs / 2))
    return filtfilt(b, a, x)


def _step_impacts(t: np.ndarray, av: np.ndarray, steps_t: np.ndarray, win_s: float) -> np.ndarray:
    lo = np.searchsorted(t, steps_t - win_s)
    hi = np.searchsorted(t, steps_t + win_s, side="right")
    return np.array([av[a:b].max() if b > a else NAN for a, b in zip(lo, hi, strict=True)])


def location_speeds(rec: Recording, a: float, b: float, params: Params) -> tuple[float, float]:
    """[a, b] 안 GPS 경로 속도(D-01)와 Doppler 중앙값(참고). 위치 점이 모자라면 NaN."""
    if not rec.has("Location"):
        return NAN, NAN
    loc = rec.sensors["Location"]
    t = loc["t_s"].to_numpy(float)
    sel = (t >= a) & (t <= b)
    every = max(1, int(params["speed.gps_path_every_n"]))
    ts = t[sel][::every]
    lat = np.radians(loc["latitude"].to_numpy(float)[sel][::every])
    lon = np.radians(loc["longitude"].to_numpy(float)[sel][::every])
    v_gps = NAN
    if len(ts) >= 2 and ts[-1] - ts[0] >= params["speed.min_path_span_s"]:
        v_gps = float(np.sum(_hav(lat[:-1], lon[:-1], lat[1:], lon[1:])) / (ts[-1] - ts[0]))
    sp = loc["speed"].to_numpy(float)[sel]
    acc = loc["speedAccuracy"].to_numpy(float)[sel] if "speedAccuracy" in loc else np.zeros_like(sp)
    ok = (sp >= 0) & (acc >= 0) & (acc <= params["speed.doppler_max_speed_accuracy_ms"])
    return v_gps, (float(np.median(sp[ok])) if ok.any() else NAN)


def _walk_flags(rec: Recording, st, params: Params) -> list[str]:
    flags = list(st.flags)
    w0, w1 = st.t_depart + params["exclude.edge_s"], st.t_arrive - params["exclude.edge_s"]
    tl = rec.t("Location") if rec.has("Location") else np.array([])
    n_in = int(((tl >= w0) & (tl <= w1)).sum())
    if w1 <= w0 or n_in / (w1 - w0) < params["speed.min_location_rate_hz"]:
        flags.append("gps_sparse")  # D-67: 걷는 동안 위치 점이 모자란다
    ta = rec.t("Accelerometer")
    inside = (ta[:-1] >= st.t_depart) & (ta[1:] <= st.t_arrive)
    if (np.diff(ta)[inside] > params["qa.gap_fail_s"]).any():
        flags.append("sensor_gap")  # D-68
    return flags


def _manual_ranges(walk_id: str, exclusions: pd.DataFrame, params: Params) -> list[tuple[float, float]]:
    if not len(exclusions):
        return []
    pad = params["exclude.phone_touch_pad_s"]
    out = []
    for r in exclusions[exclusions["walk_id"] == walk_id].itertuples():
        a, b = float(r.start_s), float(r.end_s or r.start_s)
        out.append((a - pad, b + pad) if str(r.reason) == "phone_touch" else (a, b))
    return out


def _row_value(row: dict, key: str) -> str:
    v = row.get(key, "")
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def process_walk(row: dict, paths: Paths, params: Params, music: pd.DataFrame,
                 exclusions: pd.DataFrame) -> tuple[list[dict], dict, pd.DataFrame]:
    """실험 1 회차 하나 → (곡 구간 줄들, 회차 줄, 걸음 표)."""
    rec = read_zip(find_zip(paths.raw, row), params)
    units, st = analyze_recording(rec, params)
    t, total, g = total_accel_g(rec, units)
    av = vertical_signal(total, g)
    av_f = _lowpass(t, av, params["steps.impact_lowpass_hz"])
    iv = interval_table(st.t_s, st.t_depart, st.t_arrive, params, _manual_ranges(row["walk_id"], exclusions, params))
    iv["impact_g"] = _step_impacts(t, av_f, iv["t0"].to_numpy(), params["steps.impact_window_s"])
    iv["song_idx"] = -1
    flags = _walk_flags(rec, st, params)
    w0, w1 = st.t_depart + params["exclude.edge_s"], st.t_arrive - params["exclude.edge_s"]
    base = dict(walk_id=row["walk_id"], participant=row["participant"], condition=row["condition"])
    cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"

    def seg_row(a: float, b: float, song: Song | None) -> dict:
        sel = iv["valid"] & (iv["t0"] >= a) & (iv["t0"] < b)
        if song is not None:
            iv.loc[sel, "song_idx"] = song.idx
        m = segment_metrics(iv.loc[sel, "interval_s"], iv.loc[sel, "impact_g"], song.bpm if song else NAN, params)
        v_gps, v_dop = location_speeds(rec, a, b, params)
        sl = v_gps / (m[cprim] / 60) if np.isfinite(v_gps) and np.isfinite(m[cprim]) else NAN
        fl = [f for f in [m.pop("flags")] + [f for f in flags if f in ("gps_sparse", "sensor_gap")] if f]
        return dict(base, playlist=song.playlist if song else "", song_idx=song.idx if song else -1,
                    song_order=song.order if song else "", song_title=song.title if song else "",
                    bpm=song.bpm if song else NAN, seg_t0_s=a, seg_t1_s=b, **m, speed_ms=v_gps,
                    speed_doppler_ms=v_dop, step_length_m=sl, flags=";".join(fl))

    segs: list[dict] = []
    if row["condition"] == "S" or _row_value(row, "status") == "no_song_segments":
        segs.append(seg_row(w0, w1, None))
    else:
        offset = float(_row_value(row, "music_offset_s") or params["music.default_offset_s"])
        bnd = params["exclude.boundary_s"]
        for song in song_timeline(row, music, offset, float(rec.t("Accelerometer")[-1])):
            a, b = max(song.t0 + bnd, w0), min(song.t1 - bnd, w1)
            if b > a:
                segs.append(seg_row(a, b, song))

    allv = iv["valid"]
    wm = segment_metrics(iv.loc[allv, "interval_s"], iv.loc[allv, "impact_g"], NAN, params)
    v_gps, v_dop = location_speeds(rec, w0, w1, params)
    ped = NAN
    if rec.has("Pedometer"):
        pt, pv = rec.t("Pedometer"), rec.sensors["Pedometer"]["steps"].to_numpy(float)
        inside = np.where((pt >= w0) & (pt <= w1))[0]
        ped = float(pv[inside[-1]] - pv[inside[0]]) if len(inside) >= 2 else NAN
    in_w = (t >= w0) & (t <= w1)
    walk = dict(base, walk_no=_row_value(row, "walk_no"), date=_row_value(row, "date"),
                status=_row_value(row, "status"), duration_s=float(rec.t("Accelerometer")[-1]),
                valid_duration_s=wm["valid_duration_s"], n_valid_steps=wm["n_valid_steps"],
                detected_steps=int(((st.t_s >= w0) & (st.t_s <= w1)).sum()), pedometer_steps=ped,
                hand_count=_row_value(row, "hand_step_count"), cadence_median_spm=wm["cadence_median_spm"],
                cadence_rate_spm=wm["cadence_rate_spm"], cv_pct=wm["cv_pct"], impact_g=wm["impact_g"],
                speed_ms=v_gps, speed_doppler_ms=v_dop, mean_av_g=float(av[in_w].mean()) if in_w.any() else NAN,
                t_depart_s=st.t_depart, t_arrive_s=st.t_arrive, hurried=_row_value(row, "hurried"),
                weather=_row_value(row, "weather"), flags=";".join(flags))
    steps = iv.rename(columns={"t0": "t_s"}).assign(cadence_inst_spm=lambda d: 60 / d["interval_s"],
                                                    exclude_reason=lambda d: d["reason"])
    return segs, walk, steps[["t_s", "interval_s", "cadence_inst_spm", "impact_g", "valid", "exclude_reason",
                              "song_idx"]]


def process_all(paths: Paths, params: Params, participant: str | None = None
                ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """manifest의 실험 1 회차를 모두 처리한다. status가 redo·excluded인 회차는 지표 없이 상태만 남긴다."""
    rows = [r for r in fill_walk_ids(read_table(paths.manifest).to_dict("records"))
            if str(r.get("experiment", "")).upper() == "E1"
            and (participant is None or r["participant"] == participant)]
    music = read_table(paths.music)
    exclusions = read_table(paths.manifest.parent / "exclusions.csv")
    segs, walks, steps = [], [], {}
    for r in rows:
        if _row_value(r, "status") in SKIP_STATUS:
            walks.append(dict(walk_id=r["walk_id"], participant=r["participant"], condition=r["condition"],
                              walk_no=_row_value(r, "walk_no"), date=_row_value(r, "date"), status=r["status"]))
            continue
        s, w, st = process_walk(r, paths, params, music, exclusions)
        segs += s
        walks.append(w)
        steps[r["walk_id"]] = st
    return pd.DataFrame(segs), pd.DataFrame(walks), steps


def synthetic_paths(root: Path) -> Paths:
    """합성 실험 1 자료의 위치(root/data, root/results)."""
    data = Path(root) / "data"
    return Paths(data / "raw", data / "manifest.csv", ROOT / "data" / "assignment.csv", data / "music.csv",
                 data / "participants.csv", data / "private" / "sections.csv", Path(root) / "results")


def make_synthetic_dataset(root: Path, params: Params, people: tuple[str, ...] = ("A", "B", "C"),
                           follow: float = 0.3, pc: float = 110.0, song_s: float = 80.0, n_walks: int | None = None,
                           seed: int = 0) -> tuple[Paths, dict]:
    """실험 1 합성 자료: 배정표 순서의 회차, 곡마다 케이던스 = PC × (1 + follow × (T − 100)/100).

    보폭은 일정해서 속도도 케이던스에 비례한다. 무음 회차는 PC ± 1%. 정답 {walk_id: {song_idx: (C, v)}}.
    결과는 root 아래에만 쓴다(results_synthetic 등). 곡 길이는 song_s로 바꾼 합성 전용 값이다.
    """
    from walkmusic.synthetic import SynthSpec, write_zip

    data = Path(root) / "data"
    paths = synthetic_paths(root)
    music = read_table(ROOT / "data" / "music_bpm.csv")
    music["duration_s"] = str(int(song_s))
    data.mkdir(parents=True, exist_ok=True)
    music.to_csv(paths.music, index=False, lineterminator="\n")
    read_table(ROOT / "data" / "participants.csv").to_csv(paths.participants, index=False, lineterminator="\n")
    pd.DataFrame(columns=["walk_id", "start_s", "end_s", "reason", "note"]).to_csv(
        data / "exclusions.csv", index=False, lineterminator="\n")
    asg = read_table(paths.assignment)
    rng = np.random.default_rng(seed)
    cols = read_table(ROOT / "data" / "manifest.csv").columns.tolist()
    rows, truth = [], {}
    offset, step_len = params["music.default_offset_s"], 1.3 / pc * 60  # m/걸음
    for pi, p in enumerate(people):
        (paths.raw / p).mkdir(parents=True, exist_ok=True)
        mine = asg[asg["participant"] == p]
        if n_walks is None:
            want = {"S": 3, "P1": 2, "P2": 2, "P3": 2, "P4": 2}
            keep, seen = [], {}
            for a in mine.itertuples():
                if seen.get(a.condition, 0) < want[a.condition]:
                    keep.append(a)
                    seen[a.condition] = seen.get(a.condition, 0) + 1
        else:
            keep = list(mine.itertuples())[:n_walks]
        for k, a in enumerate(keep):
            day = 10 + k
            wid = f"E1_{p}_{int(a.walk_no):02d}_{a.condition}_11{day:02d}"
            row = dict(walk_id=wid, experiment="E1", participant=p, walk_no=str(a.walk_no), date=f"2026-11-{day:02d}",
                       start_time="19:00", condition=a.condition, start_song=a.start_song, zip_file=f"{wid}.zip")
            epoch = int(sheet_time(row, params["time.timezone"]).value // 10**6) + 20_000
            if a.condition == "S":
                c0 = pc * (1 + 0.01 * rng.standard_normal())
                spec = SynthSpec(walk_s=3 * song_s + 20, cadence_spm=c0, speed_mps=step_len * c0 / 60,
                                 seed=seed * 1000 + pi * 100 + k, epoch_ms=epoch)
            else:
                songs = song_timeline(row, music, offset, offset + 3 * song_s + 120)
                cad = [pc * (1 + follow * (s.bpm / pc * 100 - 100) / 100) for s in songs]
                pairs = list(zip(songs, cad, strict=True))
                spec = SynthSpec(walk_s=3 * song_s + 20, cadence_spm=cad[0], speed_mps=step_len * cad[0] / 60,
                                 cadence_schedule=tuple((s.t0, c) for s, c in pairs),
                                 speed_schedule=tuple((s.t0, step_len * c / 60) for s, c in pairs),
                                 seed=seed * 1000 + pi * 100 + k, epoch_ms=epoch)
                truth[wid] = {s.idx: (c, step_len * c / 60) for s, c in zip(songs, cad, strict=True)}
            write_zip(paths.raw / p / f"{wid}.zip", spec)
            rows.append(row)
    pd.DataFrame(rows).reindex(columns=cols, fill_value="").fillna("").to_csv(paths.manifest, index=False,
                                                                               lineterminator="\n")
    return paths, truth
