"""평소 케이던스·SESOI·가설 판정·재표집 신뢰구간·처방 범위·시나리오 신호·분석 고정 (SPEC §4.5, §5.9, §6).

결정: D-14(ddof 1), D-23(구간 8개 미만은 판정 안 함), D-33(SESOI), D-34(회차 단위 재표집), D-35(분석 고정),
D-36(처방 범위), D-60(가설 2는 부분마다, ρ > 0이면 '증가 경향'), D-62·D-69(무음 3회 미만은 임시 PC), D-67.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from walkmusic.config import ROOT, Params
from walkmusic.metrics import follow_ratio

SKIP_STATUS = ("redo", "excluded", "test")
NAN = float("nan")


class FreezeError(RuntimeError):
    """분석 고정 태그 없이 실제 음악 회차의 가설 결과를 계산하려 했다(D-35)."""


def _cprim(params: Params) -> str:
    return "cadence_median_spm" if params["cadence.primary"] == "median" else "cadence_rate_spm"


def person_baseline(walks: pd.DataFrame, params: Params) -> pd.DataFrame:
    """사람마다 PC(무음 회차 C의 평균), 무음 변동계수, SESOI(D-33), 무음 충격 중앙값."""
    c = _cprim(params)
    floor = params["stats.sesoi_floor_pct"]
    out = []
    for p, w in walks.groupby("participant", sort=True):
        s = w[(w["condition"] == "S") & ~w.get("status", pd.Series("", index=w.index)).fillna("").isin(SKIP_STATUS)]
        vals = s[c].astype(float).dropna().to_numpy()
        n = len(vals)
        cv = float(vals.std(ddof=params["stats.sd_ddof"]) / vals.mean() * 100) if n >= 2 else NAN
        flags = [] if n >= 2 else ["sesoi_floor_only"]
        out.append(dict(participant=p, n_silent=n, pc_spm=float(vals.mean()) if n else NAN, pc_provisional=n < 3,
                        silent_cv_pct=cv, sesoi_pct=max(cv, floor) if np.isfinite(cv) else floor,
                        silent_impact_g=float(np.nanmedian(s["impact_g"].astype(float))) if n else NAN,
                        flags=";".join(flags)))
    return pd.DataFrame(out)


def add_tempo_columns(segs: pd.DataFrame, base: pd.DataFrame, params: Params) -> pd.DataFrame:
    """곡 구간에 T, ΔC%, R, change_class, 충격 상대값, PC를 붙인다(SPEC §4.2, §4.5)."""
    b = base.set_index("participant")
    out = segs.copy()
    pc = out["participant"].map(b["pc_spm"]).astype(float)
    sesoi = out["participant"].map(b["sesoi_pct"]).astype(float)
    c = out[_cprim(params)].astype(float)
    out["pc_spm"] = pc
    out["pc_provisional"] = out["participant"].map(b["pc_provisional"])
    out["tempo_ratio_pct"] = out["bpm"].astype(float) / pc * 100
    out["dC_pct"] = (c - pc) / pc * 100
    lo, hi = params["sync.r_exclude_low"], params["sync.r_exclude_high"]
    out["R"] = [follow_ratio(d, t, lo, hi) if np.isfinite(d) and np.isfinite(t) else NAN
                for d, t in zip(out["dC_pct"], out["tempo_ratio_pct"], strict=True)]
    out["change_class"] = np.where(~np.isfinite(out["dC_pct"]), "",
                                   np.where(out["dC_pct"].abs() <= sesoi, "within_band",
                                            np.where(out["dC_pct"] > 0, "meaningful_up", "meaningful_down")))
    si = out["participant"].map(b["silent_impact_g"]).astype(float)
    out["impact_rel_pct"] = (out["impact_g"].astype(float) - si) / si * 100
    return out


def _music(segs: pd.DataFrame) -> pd.DataFrame:
    m = segs[(segs["condition"] != "S")]
    return m[np.isfinite(m["tempo_ratio_pct"].astype(float)) & np.isfinite(m["dC_pct"].astype(float))]


def _rho(x, y) -> tuple[float, float]:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return NAN, NAN
    r = spearmanr(x, y)
    return float(r[0]), float(r[1])


def bootstrap_ci(music: pd.DataFrame, params: Params) -> dict[str, tuple[float, float]]:
    """한 사람의 음악 구간으로 ρ(T, ΔC%)와 평균 R의 회차 단위 재표집 신뢰구간(D-34). 음악 회차가 1개면 NaN."""
    walks = sorted(music["walk_id"].unique())
    if len(walks) < 2:
        return dict(rho=(NAN, NAN), R=(NAN, NAN))
    by = {w: (g["tempo_ratio_pct"].to_numpy(float), g["dC_pct"].to_numpy(float), g["R"].to_numpy(float))
          for w, g in music.groupby("walk_id")}
    rng = np.random.default_rng(params["stats.bootstrap_seed"])
    rhos, rs = [], []
    for _ in range(int(params["stats.bootstrap_n"])):
        pick = rng.choice(walks, size=len(walks), replace=True)
        t = np.concatenate([by[w][0] for w in pick])
        d = np.concatenate([by[w][1] for w in pick])
        r = np.concatenate([by[w][2] for w in pick])
        rhos.append(_rho(t, d)[0])
        rs.append(np.nanmean(r) if np.isfinite(r).any() else NAN)
    q = (1 - params["stats.ci_level"]) / 2 * 100

    def ci(v):
        v = np.asarray(v, float)
        return (NAN, NAN) if not np.isfinite(v).any() else (float(np.nanpercentile(v, q)),
                                                            float(np.nanpercentile(v, 100 - q)))
    return dict(rho=ci(rhos), R=ci(rs))


def _row(h, p, metric, value=NAN, ci=(NAN, NAN), n=0, criterion="", supported="NA", note="") -> dict:
    return dict(hypothesis=h, participant=p, metric=metric, value=value, ci_low=ci[0], ci_high=ci[1], n=n,
                criterion=criterion, supported=supported, note=note)


def h1_rows(segs: pd.DataFrame, base: pd.DataFrame, params: Params) -> list[dict]:
    """가설 1(SPEC §2): 사람마다 ρ(T, ΔC%) > 0, p < α, 그리고 PC ±10% 곡의 동조율이 그 밖의 곡보다 높다."""
    crit = "rho(T,dC)>0 & p<0.05 & S3(near PC +-10%) > S3(far)"
    rows = []
    for p in sorted(base["participant"]):
        m = _music(segs[segs["participant"] == p])
        pc = float(base.set_index("participant").loc[p, "pc_spm"])
        n = len(m)
        if n < params["stats.min_n_for_corr"]:
            rows.append(_row("H1", p, "rho(T,dC)", n=n, criterion=crit,
                             note=f"표본 부족(곡 구간 {n}개 < {params['stats.min_n_for_corr']})"))
            continue
        rho, pval = _rho(m["tempo_ratio_pct"], m["dC_pct"])
        near = (m["bpm"].astype(float) - pc).abs() <= params["sync.near_pc_pct"] / 100 * pc
        s_near = float(m.loc[near, "sync3_pct"].mean()) if near.any() else NAN
        s_far = float(m.loc[~near, "sync3_pct"].mean()) if (~near).any() else NAN
        ci = bootstrap_ci(m, params)
        part1 = bool(rho > 0 and pval < params["stats.alpha"])
        if np.isfinite(s_near) and np.isfinite(s_far):
            supported = part1 and bool(s_near > s_far)
        else:
            supported = "NA"
        note = (f"p={pval:.4f}(곡 구간은 같은 회차 안에서 독립이 아니라 참고치), S3 PC±10% 곡 {s_near:.1f}% / 그 밖 "
                f"{s_far:.1f}%, 평균 R {np.nanmean(m['R']):.3f} [{ci['R'][0]:.3f}, {ci['R'][1]:.3f}]")
        if supported == "NA":
            note += ". PC ±10% 안이나 밖의 곡 구간이 없어 두 번째 조건을 볼 수 없다"
        rows.append(_row("H1", p, "rho(T,dC)", rho, ci["rho"], n, crit, supported, note))
    return rows


def h2_rows(segs: pd.DataFrame, base: pd.DataFrame, params: Params) -> list[dict]:
    """가설 2(D-60): 속도·보폭·충격 각각 ρ(T, 지표) > 0이면 '증가 경향'(p는 참고). 변동성은 실험 2가 필요하다."""
    rows = []
    for p in sorted(base["participant"]):
        m = _music(segs[segs["participant"] == p])
        for name, col in (("H2_speed", "speed_ms"), ("H2_step_length", "step_length_m"), ("H2_impact", "impact_g")):
            d = m[np.isfinite(m[col].astype(float))]
            note = ""
            if col != "impact_g":
                sparse = d["flags"].fillna("").str.contains("gps_sparse")
                if sparse.any():
                    note = f"위치 점이 드문 구간 {int(sparse.sum())}개는 참고값이라 뺐다(D-67). "
                d = d[~sparse]
            n = len(d)
            if n < params["stats.min_n_for_corr"]:
                rows.append(_row(name, p, f"rho(T,{col})", n=n, criterion="rho>0",
                                 note=note + f"표본 부족(곡 구간 {n}개)"))
                continue
            rho, pval = _rho(d["tempo_ratio_pct"], d[col])
            rows.append(_row(name, p, f"rho(T,{col})", rho, n=n, criterion="rho>0 ('증가 경향', D-60)",
                             supported=bool(rho > 0), note=note + f"p={pval:.4f}(참고)"))
        rows.append(_row("H2_variability", p, "CV exp2 vs exp1", note="실험 2 데이터가 필요하다(D-11)"))
    return rows


def group_rows(rows: list[dict], params: Params, n_people: int, all_needed: tuple[str, ...] = ("H4",)) -> list[dict]:
    """가설마다 '지지'인 사람 수. 3명 중 2명 이상이면 집단 지지(가설 4는 모두)."""
    out = []
    for h in dict.fromkeys(r["hypothesis"] for r in rows):
        rs = [r for r in rows if r["hypothesis"] == h and r["participant"] != "ALL"]
        sup = sum(r["supported"] is True for r in rs)
        judged = sum(r["supported"] in (True, False) for r in rs)
        need = n_people if h in all_needed else params["stats.agree_min_persons"]
        if sup >= need:
            g = True
        elif judged - sup > n_people - need:
            g = False
        else:
            g = "NA"
        out.append(_row(h, "ALL", "n_supported", sup, n=judged, criterion=f">= {need} of {n_people}", supported=g,
                        note=f"판정한 사람 {judged}명 중 지지 {sup}명"))
    return out


def prescription_rows(participant: str, playlists: pd.DataFrame, pc: float, sesoi: float,
                      params: Params) -> list[dict]:
    """처방 범위 하한(D-36): 평균 ΔC%가 +SESOI를 넘은 플레이리스트 중 평균 T가 가장 낮은 것(평균 T ≤ 100%는 뺀다).

    playlists: playlist, t(평균 T %), dc(평균 ΔC %). 상한은 실험 2 뒤에 채운다.
    """
    rows = []
    for r in playlists.itertuples():
        cls = "within_band" if abs(r.dc) <= sesoi else ("meaningful_up" if r.dc > 0 else "meaningful_down")
        rows.append(dict(participant=participant, row_type="playlist", playlist=r.playlist, pc_spm=pc, sesoi_pct=sesoi,
                         playlist_t_pct=r.t, playlist_dc_pct=r.dc, change_class=cls))
    ok = playlists[(playlists["dc"] > sesoi) & (playlists["t"] > 100)]
    t_low = float(ok["t"].min()) if len(ok) else NAN
    statement = "" if len(ok) else "듣기만으로는 걸음이 바뀌지 않고, 박자에 맞춰 걷겠다는 의도가 필요하다"
    rows.append(dict(participant=participant, row_type="summary", playlist="", pc_spm=pc, sesoi_pct=sesoi,
                     t_low_pct=t_low, t_high_pct=NAN, t_high_s3_pct=NAN, bpm_low=t_low / 100 * pc, bpm_high=NAN,
                     statement=statement, flags="t_high는 실험 2 뒤"))
    return rows


def g2_flag_rows(segs: pd.DataFrame, walks: pd.DataFrame, base: pd.DataFrame, params: Params) -> list[dict]:
    """시나리오 신호(SPEC §5.9). 계획서에 숫자가 있는 것만 triggered를 판정한다."""
    rows = []
    b = base.set_index("participant")
    for p in sorted(base["participant"]):
        m = _music(segs[segs["participant"] == p])
        def add(fid, desc, value, thr, trig, resp="", p=p):
            rows.append(dict(participant=p, flag_id=fid, description=desc, value=value, threshold=thr,
                             triggered=trig, suggested_response=resp))

        within = (m.groupby("playlist")["dC_pct"].mean().abs() <= b.loc[p, "sesoi_pct"]).all() if len(m) else "NA"
        add("F1", "일상에서 동조가 거의 없음", f"playlist mean dC within SESOI: {within}", "", "NA(사람)")
        over = (m["sync3_pct"] >= params["sync.over_sync_frac"] * 100).sum() if len(m) else 0
        add("F2", "과동조", int(over), f"S3 >= {params['sync.over_sync_frac'] * 100:.0f}%", bool(over > 0))
        ss = int(m["sub_super"].isin(["sub", "super"]).sum()) if len(m) else 0
        add("F3", "반 박자·두 배 박자", ss, ">= 1", bool(ss >= 1))
        if len(m) and m["playlist"].nunique() >= 2:
            within = float(m.groupby("playlist")["dC_pct"].var(ddof=1).mean())
            between = float(m.groupby("playlist")["dC_pct"].mean().var(ddof=1))
            add("F4", "곡마다 들쭉날쭉", f"within {within:.3f} / between {between:.3f}", "within > between",
                bool(within > between))
        else:
            add("F4", "곡마다 들쭉날쭉", "NA", "within > between", "NA")
        cv = b.loc[p, "silent_cv_pct"]
        add("F5", "날마다 편차 큼(무음 C의 CV)", cv, f"> {params['g2.silent_cv_max_pct']}%",
            bool(cv > params["g2.silent_cv_max_pct"]) if np.isfinite(cv) else "NA")
        add("F6", "가장 높은 단계에서도 안 뜀", "NA", "", "NA", "실험 2 뒤")
        w = walks[(walks["participant"] == p) & ~walks["status"].fillna("").isin(SKIP_STATUS)]
        cvs = [float(g["impact_g"].std(ddof=1) / g["impact_g"].mean() * 100)
               for _, g in w.groupby("condition") if g["impact_g"].notna().sum() >= 2]
        worst = max(cvs) if cvs else NAN
        add("F7", "충격 잡음 큼(같은 조건 회차 간 CV 최대)", worst, f"> {params['g2.impact_cv_max_pct']}%",
            bool(worst > params["g2.impact_cv_max_pct"]) if np.isfinite(worst) else "NA")
        add("F8", "진자 예측과 실측의 큰 차이", "NA", "", "NA", "실험 3 뒤, 예상된 결과로 보고")
    return rows


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip() if r.returncode == 0 else ""


def freeze_state(tag: str) -> dict:
    """분석 고정 태그의 상태: 있는지, HEAD가 태그 뒤 몇 커밋인지."""
    exists = bool(_git("tag", "-l", tag))
    after = _git("rev-list", "--count", f"{tag}..HEAD") if exists else ""
    return dict(tag=tag, exists=exists, head=_git("rev-parse", "HEAD"),
                commits_after_tag=int(after) if after.isdigit() else None)


def require_freeze(real: bool, allow_unfrozen: bool, tag: str) -> dict:
    """실제 데이터면 분석 고정 태그를 요구한다(D-35). 합성 데이터는 그대로 돈다."""
    if not real:
        return dict(synthetic=True, unfrozen=False)
    st = freeze_state(tag)
    if not st["exists"] and not allow_unfrozen:
        raise FreezeError(f"분석 고정 태그 '{tag}'가 없다. 사용자 승인 뒤 태그를 붙이고 다시 실행한다(D-35). "
                          "태그 없이 돌리려면 --allow-unfrozen(run_info.json에 unfrozen=true가 남는다)")
    st["unfrozen"] = not st["exists"]
    st["synthetic"] = False
    return st


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_info(paths, params: Params, freeze: dict) -> dict:
    """run_info.json 내용: 고정 태그 상태, params·입력 파일 해시, 패키지 버전."""
    import numpy
    import scipy

    zips = sorted(Path(paths.raw).rglob("*.zip"))
    return dict(time_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), freeze=freeze,
                params_sha256=_sha(ROOT / "config" / "params.toml"),
                inputs={str(p.relative_to(paths.raw.parent)): _sha(p) for p in [paths.manifest, paths.music, *zips]
                        if p.exists()},
                versions=dict(numpy=numpy.__version__, pandas=pd.__version__, scipy=scipy.__version__))


def run_pipeline(paths, params: Params, real: bool, allow_unfrozen: bool = False, do_process: bool = True,
                 do_stats: bool = True) -> dict:
    """process(구간·회차·사람 표) → stats(가설·처방·시나리오). 결과는 paths.results 아래."""
    from walkmusic.exp1 import process_all

    freeze = require_freeze(real, allow_unfrozen, params["freeze.tag"])
    out = Path(paths.results)
    out.mkdir(parents=True, exist_ok=True)
    if do_process:
        segs, walks, steps = process_all(paths, params)
        base = person_baseline(walks, params)
        segs = add_tempo_columns(segs, base, params)
        segs.to_csv(out / "segments.csv", index=False, lineterminator="\n")
        walks.to_csv(out / "walks.csv", index=False, lineterminator="\n")
        base.to_csv(out / "participants.csv", index=False, lineterminator="\n")
        (out / "steps").mkdir(exist_ok=True)
        for wid, st in steps.items():
            st.to_csv(out / "steps" / f"{wid}_steps.csv", index=False, lineterminator="\n")
    segs = pd.read_csv(out / "segments.csv", keep_default_na=True)
    walks = pd.read_csv(out / "walks.csv", keep_default_na=True, dtype={"status": str})
    base = pd.read_csv(out / "participants.csv")
    summary = {}
    if do_stats:
        segs["flags"] = segs["flags"].fillna("")
        segs["playlist"] = segs["playlist"].fillna("")
        rows = h1_rows(segs, base, params) + h2_rows(segs, base, params)
        rows += group_rows(rows, params, n_people=len(base))
        pd.DataFrame(rows).to_csv(out / "hypotheses.csv", index=False, lineterminator="\n")
        pres = []
        for p in sorted(base["participant"]):
            m = _music(segs[segs["participant"] == p])
            if not len(m):
                continue
            pl = m.groupby("playlist").agg(t=("tempo_ratio_pct", "mean"), dc=("dC_pct", "mean")).reset_index()
            b = base.set_index("participant").loc[p]
            pres += prescription_rows(p, pl, float(b["pc_spm"]), float(b["sesoi_pct"]), params)
        pd.DataFrame(pres).to_csv(out / "prescription.csv", index=False, lineterminator="\n")
        pd.DataFrame(g2_flag_rows(segs, walks, base, params)).to_csv(out / "g2_flags.csv", index=False,
                                                                       lineterminator="\n")
        summary = dict(hypotheses=rows)
    (out / "run_info.json").write_text(json.dumps(run_info(paths, params, freeze), ensure_ascii=False, indent=1,
                                                  default=str), encoding="utf-8")
    return summary
