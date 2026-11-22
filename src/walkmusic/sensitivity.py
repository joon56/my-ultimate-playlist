"""민감도 분석 (SPEC §5.5d, §6, DECISIONS D-42).

정해 둔 기준을 한 가지씩 바꿔 사람별 값과 판정을 다시 내고, 기본 결과와 나란히 `sensitivity.csv`에 적는다.
기본 결과(`hypotheses*.csv`, `prescription.csv`)는 바꾸지 않는다. 변형:

- sync_tol_5pct: 동조 기준 ±3% → ±5%(`sync.tol_alt_pct`). 가설 1의 S3 비교, 가설 1-2, 처방 범위 상한.
- offset_minus_5s·offset_plus_5s: 첫 곡 재생 시각 ± `music.offset_sensitivity_s`. 실험 1 곡 구간을 다시 나눈다.
- exclude_hurried·exclude_rain: 서두른 회차·비 온 회차를 뺀다(기록지의 hurried·weather).
- pc_first_silent: 평소 케이던스를 첫 무음 회차 하나로(임시 PC) 둔다.
- exclude_tried_to_sync: 종료 설문에서 박자에 맞추려 했다고 적은 회차를 뺀다(D-42).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from walkmusic.config import Params
from walkmusic.exp2 import h12_rows, prescription_upper
from walkmusic.qa import Paths, read_table
from walkmusic.stats import (
    SKIP_STATUS,
    _music,
    _row,
    add_tempo_columns,
    group_rows,
    h1_rows,
    h2_rows,
    person_baseline,
    prescription_rows,
    require_freeze,
)

NAN = float("nan")
COLS = ["variant", "description", "hypothesis", "participant", "metric", "value_base", "value_variant",
        "supported_base", "supported_variant", "n_base", "n_variant", "value_changed", "supported_changed", "note"]
YES = ("예", "yes", "y", "1", "true", "o")


def exp1_outcome(segs: pd.DataFrame, base: pd.DataFrame, params: Params) -> list[dict]:
    """실험 1의 사람별 판정 줄(가설 1, 가설 2의 속도·보폭·충격), 집단 줄, 처방 범위 하한."""
    segs = segs.assign(flags=segs["flags"].fillna(""), playlist=segs["playlist"].fillna(""))
    rows = [r for r in h1_rows(segs, base, params) + h2_rows(segs, base, params) if r["hypothesis"] != "H2_variability"]
    rows += group_rows(rows, params, n_people=len(base))
    b = base.set_index("participant")
    for p in sorted(base["participant"]):
        m = _music(segs[segs["participant"] == p])
        if not len(m):
            continue
        pl = m.groupby("playlist").agg(t=("tempo_ratio_pct", "mean"), dc=("dC_pct", "mean")).reset_index()
        low = prescription_rows(p, pl, float(b.loc[p, "pc_spm"]), float(b.loc[p, "sesoi_pct"]), params)[-1]["t_low_pct"]
        rows.append(_row("prescription", p, "t_low_pct", low, n=len(pl), criterion="D-36"))
    return rows


def exp2_outcome(summary: pd.DataFrame, params: Params) -> list[dict]:
    """실험 2의 가설 1-2 줄, 집단 줄, 처방 범위 상한(평균 동조·S3 기준)."""
    if not len(summary):
        return []
    rows = h12_rows(summary, params)
    rows += group_rows(rows, params, n_people=summary["runner"].nunique())
    for r in prescription_upper(summary, params).to_dict("records"):
        for metric in ("t_high_pct", "t_high_s3_pct"):
            rows.append(_row("prescription", r["runner"], metric, r[metric], criterion="D-36·D-54", note=r["flags"]))
    return rows


def compare(variant: str, description: str, base: list[dict], other: list[dict], note: str = "") -> list[dict]:
    """기본 줄과 변형 줄을 (가설, 사람, 지표)로 맞춘다. value_changed는 값, supported_changed는 판정이 다른지."""
    key = lambda r: (r["hypothesis"], r["participant"], r["metric"])  # noqa: E731
    new = {key(r): r for r in other}
    out = []
    for r in base:
        v = new.get(key(r), dict(value=NAN, supported="NA", n=0, note="변형에서는 이 줄이 없다"))
        same_value = (not np.isfinite(r["value"]) and not np.isfinite(v["value"])) or np.isclose(r["value"], v["value"])
        out.append(dict(variant=variant, description=description, hypothesis=r["hypothesis"],
                        participant=r["participant"], metric=r["metric"], value_base=r["value"],
                        value_variant=v["value"], supported_base=r["supported"], supported_variant=v["supported"],
                        n_base=r["n"], n_variant=v["n"], value_changed=bool(not same_value),
                        supported_changed=bool(str(r["supported"]) != str(v["supported"])),
                        note="; ".join(x for x in (note, str(v["note"])) if x)))
    return out


def _nothing(variant: str, description: str, note: str) -> list[dict]:
    return [dict(variant=variant, description=description, hypothesis="", participant="ALL", metric="", value_base=NAN,
                 value_variant=NAN, supported_base="", supported_variant="", n_base=0, n_variant=0,
                 value_changed=False, supported_changed=False, note=note)]


def _used(walks: pd.DataFrame) -> pd.DataFrame:
    return walks[~walks["status"].fillna("").astype(str).isin(SKIP_STATUS)]


def synced_walks(debrief: pd.DataFrame) -> set[tuple[str, int]]:
    """종료 설문에서 '박자에 맞추려 한 적이 있다'고 적은 (사람, 회차 번호)들. sync_walks에서 숫자만 읽는다."""
    out = set()
    for r in debrief.to_dict("records"):
        if str(r.get("tried_to_sync", "")).strip().lower() in YES:
            out |= {(r["participant"], int(n)) for n in re.findall(r"\d+", str(r.get("sync_walks", "")))}
    return out


def sensitivity_table(segs: pd.DataFrame, walks: pd.DataFrame, summary: pd.DataFrame, debrief: pd.DataFrame,
                      shifted: dict[float, pd.DataFrame], params: Params) -> pd.DataFrame:
    """결과 표 → 민감도 표.

    segs·walks: 실험 1의 곡 구간·회차 표. summary: 실험 2 단계 표(없으면 빈 표).
    shifted: {오프셋 이동(s): 그 이동으로 다시 나눈 곡 구간 표}(PC가 붙기 전이어도 된다).
    """
    used = _used(walks)
    base = person_baseline(walks, params)
    segs = add_tempo_columns(segs, base, params)
    b1, b2 = exp1_outcome(segs, base, params), exp2_outcome(summary, params)
    rows: list[dict] = []

    alt = params["sync.tol_alt_pct"]
    desc = f"동조 기준 ±{params['sync.tol_pct']:g}% → ±{alt:g}%"
    rows += compare("sync_tol_5pct", desc, [r for r in b1 if r["hypothesis"] == "H1"],
                    exp1_outcome(segs.assign(sync3_pct=segs["sync5_pct"]), base, params))
    if len(summary):
        p5 = params.with_overrides({"sync.tol_pct": alt})
        rows += compare("sync_tol_5pct", desc, b2, exp2_outcome(summary.assign(sync3_pct=summary["sync5_pct"]), p5))

    for shift, s in sorted(shifted.items()):
        name = f"offset_{'minus' if shift < 0 else 'plus'}_{abs(shift):g}s"
        s = add_tempo_columns(s, base, params)
        rows += compare(name, f"첫 곡 재생 시각 {shift:+g} s", b1, exp1_outcome(s, base, params))

    def without(name: str, description: str, drop: pd.Series, unknown: int, why: str) -> list[dict]:
        ids = set(used.loc[drop, "walk_id"])
        tail = f"기록이 빈 회차 {unknown}개는 모르는 것으로 두고 빼지 않았다" if unknown else ""
        if not ids:
            return _nothing(name, description, "; ".join(x for x in (f"{why} 회차가 없어 기본 결과와 같다", tail) if x))
        w2 = walks[~walks["walk_id"].isin(ids)]
        base2 = person_baseline(w2, params)
        s2 = add_tempo_columns(segs[~segs["walk_id"].isin(ids)], base2, params)
        note = "; ".join(x for x in (f"뺀 회차 {len(ids)}개: {', '.join(sorted(ids))}", tail) if x)
        return compare(name, description, b1, exp1_outcome(s2, base2, params), note)

    hurried = used["hurried"].fillna("").astype(str).str.strip().str.lower()
    rows += without("exclude_hurried", "서두른 회차를 뺀다", hurried.isin(YES), int((hurried == "").sum()), "서두른")
    weather = used["weather"].fillna("").astype(str).str.strip().str.lower()
    rows += without("exclude_rain", "비 온 회차를 뺀다", weather.str.contains("비|rain"), int((weather == "").sum()),
                    "비 온")

    first = used[used["condition"] == "S"].groupby("participant", sort=True).head(1).set_index("participant")
    cprim = "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"
    base_pc = base.assign(pc_spm=base["participant"].map(first[cprim]).astype(float))
    note = "; ".join(f"{r.participant} {r.pc_spm:.1f} → {float(first.loc[r.participant, cprim]):.1f} 걸음/분"
                     for r in base.itertuples() if r.participant in first.index)
    rows += compare("pc_first_silent", "평소 케이던스를 첫 무음 회차 하나로(임시 PC)", b1,
                    exp1_outcome(add_tempo_columns(segs, base_pc, params), base_pc, params), note)

    desc = "박자에 맞추려 했다고 적은 회차를 뺀다(종료 설문, D-42)"
    if not len(debrief):
        rows += _nothing("exclude_tried_to_sync", desc, "종료 설문이 아직 없다(data/debrief.csv가 비어 있다)")
    else:
        pairs = synced_walks(debrief)
        no = pd.to_numeric(used["walk_no"], errors="coerce")
        drop = pd.Series([(p, int(n)) in pairs if np.isfinite(n) else False
                          for p, n in zip(used["participant"], no, strict=True)], index=used.index)
        missing = len(set(used["participant"]) - set(debrief["participant"]))
        tail = f"; 설문이 없는 사람 {missing}명" if missing else ""
        rows += (without("exclude_tried_to_sync", desc, drop, 0, "박자에 맞추려 했다고 적은") if drop.any() else
                 _nothing("exclude_tried_to_sync", desc, "박자에 맞추려 했다고 적은 회차가 없어 기본 결과와 같다"
                          + tail))
    return pd.DataFrame(rows, columns=COLS)


def run_sensitivity(paths: Paths, exp23_results: Path, params: Params, real: bool,
                    allow_unfrozen: bool = False) -> pd.DataFrame:
    """결과 폴더의 표를 읽고, 오프셋을 옮긴 곡 구간을 다시 계산해 민감도 표를 만든다(쓰지는 않는다)."""
    from walkmusic.exp1 import process_all

    require_freeze(real, allow_unfrozen, params["freeze.tag"])
    res = Path(paths.results)
    segs = pd.read_csv(res / "segments.csv")
    walks = pd.read_csv(res / "walks.csv", dtype={"status": str})
    p = Path(exp23_results) / "exp2_summary.csv"
    summary = pd.read_csv(p, dtype={"ratio_pct": str}) if p.exists() and p.stat().st_size > 1 else pd.DataFrame()
    d = params["music.offset_sensitivity_s"]
    shifted = {s: process_all(paths, params, offset_shift_s=s)[0] for s in (-d, d)}
    return sensitivity_table(segs, walks, summary, read_table(paths.manifest.parent / "debrief.csv"), shifted, params)
