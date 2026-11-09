"""zip ↔ manifest 연결과 walk_id (SPEC §3.4, DECISIONS D-27).

- 걷는 사람은 파일 이름을 바꾸지 않는다. zip은 ``data/raw/<사람>/``에 둔다(A의 예전 파일은 ``data/raw/`` 바로 아래).
- 코드는 zip의 기록 시작 시각(KST)과 manifest의 ``date``·``start_time``을 맞춘 연결 제안만 낸다
  (``results/zip_links.csv``). manifest는 고치지 않는다. 확인한 사람이 ``zip_file``을 채운다.
- walk_id: 실험 1은 ``E1_<사람>_<회차 2자리>_<조건>_<MMDD>``, 사전 점검은 ``TEST_<사람>_<MMDD>_<종류>``
  (같은 날 같은 종류가 또 있으면 ``_2``). manifest에 이미 적힌 walk_id는 그대로 쓴다.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from walkmusic.config import Params
from walkmusic.io_sensorlogger import read_start_epoch

LINK_COLUMNS = ["zip_name", "participant", "start_kst", "walk_id", "diff_s", "status"]


def _mmdd(date: str) -> str:
    return date[5:7] + date[8:10]


def expected_walk_id(row: dict) -> str | None:
    """실험 1 줄의 규칙상 walk_id. 실험 1이 아니거나 필요한 칸이 비면 None."""
    if row.get("experiment", "").strip().upper() != "E1":
        return None
    p, wn, cond, date = (row.get(k, "").strip() for k in ("participant", "walk_no", "condition", "date"))
    if not (p and wn.isdigit() and cond and len(date) == 10):
        return None
    return f"E1_{p}_{int(wn):02d}_{cond}_{_mmdd(date)}"


def fill_walk_ids(rows: list[dict]) -> list[dict]:
    """빈 walk_id를 규칙대로 채운 사본을 돌려준다. 입력 줄은 고치지 않는다."""
    out, seen = [], set()
    for r in rows:
        r = dict(r)
        if not r.get("walk_id", "").strip():
            if r.get("experiment", "").strip().upper() == "TEST":
                base = f"TEST_{r.get('participant', '')}_{_mmdd(r.get('date', ''))}_{r.get('condition', '')}"
                wid, k = base, 2
                while wid in seen:
                    wid, k = f"{base}_{k}", k + 1
                r["walk_id"] = wid
            else:
                r["walk_id"] = expected_walk_id(r) or ""
        seen.add(r["walk_id"])
        out.append(r)
    return out


def sheet_time(row: dict, tz: str) -> pd.Timestamp | None:
    """기록지의 날짜와 기록 시작 시각(시:분) → 시각(tz). 둘 중 하나라도 비면 None."""
    date, hhmm = row.get("date", "").strip(), row.get("start_time", "").strip()
    if not date or not hhmm:
        return None
    return pd.Timestamp(f"{date} {hhmm}").tz_localize(tz)


def find_zip(raw: Path, row: dict) -> Path:
    """zip 위치: ``raw/<사람>/<zip_file>``, 없으면 ``raw/<zip_file>``. zip_file이 비면 ``<walk_id>.zip``."""
    name = row.get("zip_file") or f"{row.get('walk_id', '')}.zip"
    nested = raw / row.get("participant", "") / name
    return nested if row.get("participant") and nested.exists() else raw / name


def propose_links(rows: list[dict], raw: Path, tol_s: float, tz: str) -> pd.DataFrame:
    """``raw/<사람>/*.zip``마다 같은 사람 manifest 줄 가운데 기록 시작 시각이 tol_s 안인 줄을 찾는다.

    status: matched(zip도 줄도 서로 하나뿐), ambiguous(어느 쪽이든 둘 이상), none(없음).
    ambiguous의 walk_id·diff_s는 후보를 ``|``로 잇는다. diff_s = zip 시작 − 기록지 시각(s).
    """
    rows = fill_walk_ids(rows)
    out = []
    folders = sorted(d for d in raw.iterdir() if d.is_dir()) if raw.exists() else []
    for folder in folders:
        p = folder.name
        sheet = [(r, sheet_time(r, tz)) for r in rows if r.get("participant") == p]
        sheet = [(r, t) for r, t in sheet if t is not None]
        zips = [(z, pd.Timestamp(read_start_epoch(z)[0], unit="ns", tz="UTC").tz_convert(tz))
                for z in sorted(folder.glob("*.zip"))]
        near = {}
        for z, start in zips:
            diffs = [(r, (start - t).total_seconds()) for r, t in sheet]
            near[z.name] = [(r, d) for r, d in diffs if abs(d) <= tol_s]
        uses = Counter(r["walk_id"] for hits in near.values() for r, _ in hits)
        for z, start in zips:
            hits = near[z.name]
            one = len(hits) == 1 and uses[hits[0][0]["walk_id"]] == 1
            status = "none" if not hits else "matched" if one else "ambiguous"
            out.append(dict(zip_name=z.name, participant=p, start_kst=start.strftime("%Y-%m-%d %H:%M:%S"),
                            walk_id="|".join(r["walk_id"] for r, _ in hits),
                            diff_s="|".join(f"{d:.0f}" for _, d in hits), status=status))
    return pd.DataFrame(out, columns=LINK_COLUMNS)


def write_zip_links(manifest: Path, raw: Path, results: Path, params: Params) -> pd.DataFrame:
    """``results/zip_links.csv``를 쓴다. manifest는 고치지 않는다."""
    rows = []
    if manifest.exists():
        rows = pd.read_csv(manifest, dtype=str, keep_default_na=False, encoding="utf-8-sig").to_dict("records")
    df = propose_links(rows, raw, params["manifest.start_time_tol_s"], params["time.timezone"])
    results.mkdir(parents=True, exist_ok=True)
    df.to_csv(results / "zip_links.csv", index=False, encoding="utf-8", lineterminator="\n")
    return df
