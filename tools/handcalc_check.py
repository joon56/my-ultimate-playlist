"""손계산 검산 도구: 결과 표를 읽어 손계산을 식 그대로 다시 풀고 검산표(docs/총정리본_검산표.csv)를 쓴다.

- 입력: results/*.csv(파이프라인이 낸 결과 표), data/participants.csv(몸 치수와 지도 거리),
  data/video_markers.csv·data/video_exp2.csv·data/exp2_trials.csv(영상에서 읽은 값).
  좌표와 기기 이름이 든 열은 읽지 않는다. data/raw/는 읽기만 한다.
- 손계산 값: walkmusic 패키지의 계산 함수를 거치지 않고 이 파일에 적은 식으로 푼다.
  예외는 HC-A6의 걸음 시각 하나다(실험 2의 걸음 시각은 결과 표에 없어서 패키지의 걸음 검출로 zip을 읽는다).
- 코드 값: 결과 표의 열을 그대로 읽은 값. 결과 표에 그 값이 없으면 비운다.
- 검산 기준값: 11/22–23 검산에서 반올림한 표시값으로 손계산한 값(총정리본 제작 지시 v2). 여기서는 원값으로 푼다.
- 교안 예제(E1–E50)의 입력과 가정 예시(G-1–G-18)의 가정값은 이 파일에 적혀 있다. 실측이 아니다.

같은 입력이면 같은 출력이 나온다(시각·난수를 쓰지 않는다).

실행: python tools/handcalc_check.py              # docs/총정리본_검산표.csv를 쓰고 요약을 찍는다
      python tools/handcalc_check.py --no-steps   # zip을 읽지 않는다(HC-A6이 빠진다)
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
G = 9.81
COLUMNS = ["id", "구분", "교안", "입력", "식", "손계산 값", "코드 값", "차이", "일치", "상태", "항목", "검산 기준값",
           "기준값과 같은지"]
KINDS = ("결론", "교안 짝", "교안 예제", "가정 예시")
SILENT = "S"


# ---------------------------------------------------------------- 숫자와 글자
def ref_number(ref: str) -> tuple[float, int]:
    """기준값 글자 → (값, 소수 자릿수)."""
    s = ref.replace("−", "-").replace("+", "").replace(",", "")
    return float(s), (len(s.split(".")[1]) if "." in s else 0)


def same_as_ref(value: float, ref: str) -> bool:
    """기준값의 자릿수로 반올림했을 때 같은가."""
    d, nd = ref_number(ref)
    return abs(value - d) <= 0.5 * 10 ** (-nd) + 1e-9


def show(value: float, ref: str = "", nd: int | None = None) -> str:
    """본문에 적을 글자. 기준값과 같으면 기준값 글자 그대로, 다르면 같은 자릿수로 원값을 적는다."""
    if ref:
        if same_as_ref(value, ref):
            return ref
        nd = ref_number(ref)[1]
    nd = 3 if nd is None else nd
    if round(abs(value), nd) == 0:
        return f"{0:.{nd}f}"
    body = f"{abs(value):,.{nd}f}" if (not ref or "," in ref or abs(value) >= 10000) else f"{abs(value):.{nd}f}"
    sign = "−" if value < 0 else ("+" if ref.startswith("+") else "")
    return sign + body


def lst(values, nd: int) -> str:
    return ", ".join(f"{float(v):.{nd}f}" for v in values)


@dataclass
class Row:
    id: str
    kind: str
    lecture: str
    inputs: str
    formula: str
    hand: float | None
    code: float | None
    status: str
    item: str
    ref: str = ""
    nd: int | None = None

    @property
    def value(self) -> float | None:
        return self.hand if self.hand is not None else self.code

    @property
    def diff(self) -> float | None:
        return None if self.hand is None or self.code is None else self.hand - self.code

    @property
    def match(self) -> str:
        d = self.diff
        if d is None:
            return ""
        return "일치" if abs(d) <= 1e-9 * max(1.0, abs(self.code)) else "불일치"

    @property
    def ref_match(self) -> str:
        if not self.ref or self.value is None:
            return ""
        return "같음" if same_as_ref(self.value, self.ref) else "다름"

    @property
    def shown(self) -> str:
        return "" if self.value is None else show(self.value, self.ref, self.nd)

    def cells(self) -> list[str]:
        def f(x):
            return "" if x is None else f"{x:.10g}"
        d = self.diff
        return [self.id, self.kind, self.lecture, self.inputs, self.formula, f(self.hand), f(self.code),
                "" if d is None else ("0" if d == 0 else f"{d:.3g}"), self.match, self.status, self.item, self.ref,
                self.ref_match]


class Sheet:
    """검산표의 줄을 모은다. begin()으로 손계산 하나의 공통 칸을 정하고 add()로 값을 하나씩 더한다."""

    def __init__(self) -> None:
        self.rows: list[Row] = []
        self._c: dict[str, str] = {}

    def begin(self, id_: str, kind: str, lecture: str = "", status: str = "", formula: str = "", inputs: str = ""):
        assert kind in KINDS, kind
        self._c = dict(id=id_, kind=kind, lecture=lecture, status=status, formula=formula, inputs=inputs)

    def add(self, item: str, hand=None, code=None, ref: str = "", *, inputs: str | None = None,
            formula: str | None = None, status: str | None = None, nd: int | None = None) -> None:
        def num(x):
            if x is None:
                return None
            x = float(x)
            return x if math.isfinite(x) else None
        c = self._c
        self.rows.append(Row(c["id"], c["kind"], c["lecture"], c["inputs"] if inputs is None else inputs,
                             c["formula"] if formula is None else formula, num(hand), num(code),
                             c["status"] if status is None else status, item, ref, nd))

    def get(self, id_: str, item: str) -> Row:
        hit = [r for r in self.rows if r.id == id_ and r.item == item]
        if len(hit) != 1:
            raise KeyError(f"{id_} | {item}: {len(hit)}줄")
        return hit[0]

    def of(self, id_: str) -> list[Row]:
        return [r for r in self.rows if r.id == id_]


# ---------------------------------------------------------------- 손계산 식
def rank_average(values) -> list[float]:
    """작은 값부터 1, 2, …. 같은 값은 순위의 평균을 준다."""
    x = [float(v) for v in values]
    order = sorted(range(len(x)), key=lambda i: x[i])
    ranks = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(x, y) -> float:
    x, y = [float(v) for v in x], [float(v) for v in y]
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def spearman(x, y) -> float:
    """Spearman ρ = 두 순위 열의 피어슨 상관(같은 값이 있어도 맞는 식)."""
    return pearson(rank_average(x), rank_average(y))


def spearman_no_ties(x, y) -> tuple[float, float]:
    """같은 값이 없을 때의 식 1 − 6Σd² ÷ (n(n² − 1))과 Σd²."""
    rx, ry = rank_average(x), rank_average(y)
    n = len(rx)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1)), d2


def rank_table(x, y) -> pd.DataFrame:
    rx, ry = rank_average(x), rank_average(y)
    return pd.DataFrame(dict(x=list(map(float, x)), y=list(map(float, y)), rank_x=rx, rank_y=ry,
                             d=[a - b for a, b in zip(rx, ry)]))


def bland_altman(a, b) -> SimpleNamespace:
    """두 방법의 차(a − b): 평균, 표본 SD, 95% 일치 한계 = 평균 ± 1.96 SD."""
    d = [float(x) - float(y) for x, y in zip(a, b)]
    n = len(d)
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else float("nan")
    return SimpleNamespace(n=n, mean=mean, sd=sd, low=mean - 1.96 * sd, high=mean + 1.96 * sd, diffs=d,
                           mean_b=sum(float(y) for y in b) / n)


def segment_model(mass: float, thigh: float, shank: float, knee_deg: float, fr: dict) -> SimpleNamespace:
    """허벅지 + (정강이+발) 두 분절 진자. 엉덩관절 기준 I = Σ m(k² + r²), 질량중심 거리 d, 주기 P = 2π√(I ÷ mgd)."""
    mt, ms = fr["thigh_mass"] * mass, fr["shank_mass"] * mass
    rt = fr["thigh_com"] * thigh
    ph = math.radians(knee_deg)
    sx, sy = thigh + fr["shank_com"] * shank * math.cos(ph), fr["shank_com"] * shank * math.sin(ph)
    inertia = mt * ((fr["thigh_k"] * thigh) ** 2 + rt ** 2) + ms * ((fr["shank_k"] * shank) ** 2 + sx ** 2 + sy ** 2)
    cx, cy = (mt * rt + ms * sx) / (mt + ms), ms * sy / (mt + ms)
    d, m = math.hypot(cx, cy), mt + ms
    return SimpleNamespace(m=m, I=inertia, d=d, P=2 * math.pi * math.sqrt(inertia / (m * G * d)))


def whole_leg_period(leg: float, k_over_l: float, d_over_l: float) -> float:
    """다리 전체 비율 모델 P_model = 2π√((k L)² ÷ (g d L))."""
    return 2 * math.pi * math.sqrt((k_over_l * leg) ** 2 / (G * d_over_l * leg))


def knee_cosine(hip, knee, ankle) -> tuple[float, float]:
    """코사인 법칙: 맞은편 변 a(엉덩–발목), b(엉덩–무릎), c(무릎–발목) → 무릎 안쪽 각, 굽힘 각(도)."""
    a, b, c = math.dist(hip, ankle), math.dist(hip, knee), math.dist(knee, ankle)
    inner = math.degrees(math.acos((b * b + c * c - a * a) / (2 * b * c)))
    return inner, 180 - inner


def absolute_angles(hip, knee, ankle, image_y_down: bool = False) -> tuple[float, float]:
    """분절 절대각(오른쪽 수평에서 반시계, 아래 끝점 기준): 허벅지, 정강이(도). 영상 좌표면 y를 뒤집는다."""
    s = -1.0 if image_y_down else 1.0
    thigh = math.degrees(math.atan2(s * (hip[1] - knee[1]), hip[0] - knee[0]))
    shank = math.degrees(math.atan2(s * (knee[1] - ankle[1]), knee[0] - ankle[0]))
    return thigh, shank


def spring(mass: float, leg: float, v: float, tc: float, tf: float) -> SimpleNamespace:
    """Morin 외(2005) 반 사인파 모델(교안 밖): F_max, Δy, ΔL, k_vert, k_leg, 탄성에너지."""
    fmax = mass * G * math.pi / 2 * (tf / tc + 1)
    dy = fmax * tc ** 2 / (mass * math.pi ** 2) - G * tc ** 2 / 8
    dl = leg - math.sqrt(leg ** 2 - (v * tc / 2) ** 2) + dy
    return SimpleNamespace(fmax=fmax, bw=fmax / (mass * G), dy=dy, dl=dl, kvert=fmax / dy / 1000, kleg=fmax / dl / 1000,
                           energy=0.5 * fmax * dy)


def sync_count(step_times, t0: float, t1: float, bpm: float, tol_pct: float, min_iv: float, max_iv: float):
    """분석 창 안 걸음 시각 → (창 안 걸음 수, 유효 간격 수, 동조 간격 수, S3 %). c_i = 60 ÷ 간격."""
    t = np.asarray(step_times, float)
    t = t[(t >= t0 - 1e-9) & (t <= t1 + 1e-9)]
    iv = np.diff(t)
    valid = iv[(iv >= min_iv) & (iv <= max_iv)]
    inside = np.abs(60 / valid - bpm) <= tol_pct / 100 * bpm
    return len(t), len(valid), int(inside.sum()), float(inside.mean() * 100) if len(valid) else float("nan")


# ---------------------------------------------------------------- 표 읽기
def load_tables(root: Path = ROOT) -> SimpleNamespace:
    res, dat = root / "results", root / "data"
    t = SimpleNamespace()
    t.body = pd.read_csv(dat / "participants.csv", usecols=["participant", "mass_kg", "leg_length_m", "thigh_length_m",
                                                           "shank_length_m", "section_distance_m"]
                         ).set_index("participant")
    t.base = pd.read_csv(res / "participants.csv").set_index("participant")
    t.walks = pd.read_csv(res / "walks.csv")
    t.segs = pd.read_csv(res / "segments.csv")
    t.hyp = pd.concat([pd.read_csv(res / "hypotheses.csv"), pd.read_csv(res / "hypotheses_exp23.csv")],
                      ignore_index=True)
    t.pres = pd.read_csv(res / "prescription.csv")
    t.s2 = pd.read_csv(res / "exp2_summary.csv", dtype={"ratio_pct": str})
    t.st2 = pd.read_csv(res / "exp2_stages.csv", dtype={"ratio_pct": str})
    t.pcs = pd.read_csv(res / "exp2_pc.csv").set_index("runner")
    t.jumps = pd.read_csv(res / "jumps.csv")
    t.sw = pd.read_csv(res / "exp3_swings.csv")
    t.p3 = pd.read_csv(res / "exp3_summary.csv").set_index("runner")
    t.val = pd.read_csv(res / "validation.csv")
    t.sens = pd.read_csv(res / "sensitivity.csv")
    t.steps_dir = res / "steps"
    t.markers = pd.read_csv(dat / "video_markers.csv")
    t.vexp2 = pd.read_csv(dat / "video_exp2.csv")
    t.trials = pd.read_csv(dat / "exp2_trials.csv")
    return t


def load_params(root: Path = ROOT):
    sys.path.insert(0, str(root / "src"))
    from walkmusic.config import load_params as _load
    return _load()


def detect_exp2_steps(trial_ids, root: Path = ROOT) -> dict[str, np.ndarray]:
    """실험 2 시행의 걸음 시각. 패키지의 걸음 검출을 그대로 부른다(zip은 읽기만 한다)."""
    sys.path.insert(0, str(root / "src"))
    from walkmusic.config import load_params as _load
    from walkmusic.exp2 import detect_steps, exp2_params
    from walkmusic.exp23 import Paths23, _dup_zips, _open, determine_units, read_table, total_accel_g
    params, paths = _load(), Paths23.real()
    sheet, dups, out = read_table(paths.data / "exp2_trials.csv"), _dup_zips(Paths23.real()), {}
    for tid in trial_ids:
        rec, _, _ = _open(paths, params, sheet[sheet["trial_id"] == tid].to_dict("records")[0], dups, [])
        t, total_g, gravity = total_accel_g(rec, determine_units(rec))
        out[tid] = np.asarray(detect_steps(t, total_g, gravity, exp2_params(params)).t_s, float)
    return out


def variability_pairs(t, params) -> list[SimpleNamespace]:
    """가설 2 변동성의 짝: 실험 2 단계마다 T가 ±same_tempo_pct 안이고 CV가 있는 실험 1 곡 구간(D-11)."""
    same = params["stats.same_tempo_pct"]
    num = t.s2[t.s2["ratio_pct"].str.isdigit()]
    out = []
    for p in sorted(num["runner"].unique()):
        e1 = t.segs[(t.segs["participant"] == p) & (t.segs["condition"] != SILENT)]
        for r in num[num["runner"] == p].itertuples():
            near = ((e1["tempo_ratio_pct"] - r.tempo_ratio_pct).abs() <= same) & e1["cv_pct"].notna()
            if near.any() and math.isfinite(r.cv_pct):
                out.append(SimpleNamespace(p=p, ratio=r.ratio_pct, cv2=float(r.cv_pct), segs=e1[near]))
    return out


def step_trials(t, params) -> list[str]:
    """걸음 시각이 필요한 실험 2 시행: HC-A6(A 100% 두 시행)과 HC-A7 변동성에 짝지은 단계의 시행."""
    ids = ["E2_A_100_1", "E2_A_100_2"]
    for q in variability_pairs(t, params):
        ids += list(t.st2[(t.st2["runner"] == q.p) & (t.st2["ratio_pct"] == q.ratio)]["trial_id"])
    return sorted(set(ids))


def interval_cv(intervals) -> float:
    """걸음 간격의 변동계수(%) = 표본 SD ÷ 평균 × 100."""
    iv = np.asarray(intervals, float)
    return float(iv.std(ddof=1) / iv.mean() * 100)


def _used(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["flags"].fillna("").str.contains("invalid_sheet")]


def _stage(t, p: str, r: str) -> pd.Series:
    return t.s2[(t.s2["runner"] == p) & (t.s2["ratio_pct"] == r)].iloc[0]


def _hyp(t, h: str, p: str):
    d = t.hyp[(t.hyp["hypothesis"] == h) & (t.hyp["participant"] == p)]
    d = d[d["value"].notna()] if d["value"].notna().any() else d
    return d.iloc[-1]


def _note_number(note, pattern: str) -> float:
    """결과 표의 note 글에서 숫자 하나를 읽는다(없으면 NaN)."""
    import re
    m = re.search(pattern, str(note))
    return float(m.group(1)) if m else float("nan")


def _fractions(params) -> dict:
    return dict(thigh_mass=params["pendulum.seg_thigh_mass_frac"], thigh_com=params["pendulum.seg_thigh_com_frac"],
                thigh_k=params["pendulum.seg_thigh_kcm_frac"], shank_mass=params["pendulum.seg_shank_mass_frac"],
                shank_com=params["pendulum.seg_shank_com_frac"], shank_k=params["pendulum.seg_shank_kcm_frac"])


def _music(t) -> pd.DataFrame:
    s = t.segs
    return s[(s["condition"] != SILENT) & s["tempo_ratio_pct"].notna() & s["dC_pct"].notna()]


def speed_table(t) -> dict:
    """실험 1 속도 표(곡 구간 평균): (사람, 조건) → 구간 수 n, 평균 T, v, 케이던스 c, 보폭 sl = v ÷ (c ÷ 60)."""
    s = t.segs
    ok = s[s["speed_ms"].notna() & s["cadence_median_spm"].notna()
           & ~s["flags"].fillna("").str.contains("gps_sparse|few_steps")]
    out = {}
    for p in sorted(ok["participant"].unique()):
        who = ok[ok["participant"] == p]
        groups = [(SILENT, who[who["condition"] == SILENT])]
        groups += [(pl, d) for pl, d in who[who["condition"] != SILENT].groupby("playlist")]
        for cond, d in groups:
            if len(d):
                v, c = float(d["speed_ms"].mean()), float(d["cadence_median_spm"].mean())
                out[(p, cond)] = SimpleNamespace(n=len(d), t=float(d["tempo_ratio_pct"].mean()), v=v, c=c, sl=v / (c / 60))
    return out


def models(t, params) -> dict:
    """사람별 분절 모델: 곧은 다리 s, 잰 무릎 각 k, 90° r."""
    fr, out = _fractions(params), {}
    for p in t.p3.index:
        m, lt, ls, leg = (float(t.body.loc[p, k]) for k in ("mass_kg", "thigh_length_m", "shank_length_m",
                                                             "leg_length_m"))
        knee = float(t.p3.loc[p, "knee_deg"])
        out[p] = SimpleNamespace(M=m, L=leg, lt=lt, ls=ls, knee=knee, s=segment_model(m, lt, ls, 0, fr),
                                 k=segment_model(m, lt, ls, knee, fr), r=segment_model(m, lt, ls, 90, fr))
    return out


# ---------------------------------------------------------------- 결론으로 가는 손계산 (HC-A1–A14)
def rows_conclusion(sh: Sheet, t, params, steps: dict | None) -> None:
    kind, base, segs, music = "결론", t.base, t.segs, _music(t)
    floor = params["stats.sesoi_floor_pct"]
    sil = t.walks[(t.walks["condition"] == SILENT) & t.walks["status"].isna()]

    sh.begin("HC-A1", kind, "5주차 케이던스(p6–8)", "실측", "PC = 무음 회차 케이던스의 평균")
    for p, ref in (("A", "99.72"), ("B", "98.00"), ("C", "118.54")):
        c = sil[sil["participant"] == p]["cadence_median_spm"].to_numpy(float)
        note = "" if len(c) >= 3 else " 무음 3회 미만이라 임시값."
        sh.add(f"{p} PC (걸음/분)", c.mean(), base.loc[p, "pc_spm"], ref,
               inputs=f"무음 회차 {len(c)}개의 케이던스 {lst(c, 2)} 걸음/분 (results/walks.csv: cadence_median_spm).{note}")

    sh.begin("HC-A2", kind, "", "실측", f"SESOI = max(표본 SD ÷ 평균 × 100, 하한 {floor:.1f})")
    for p, sd_ref, cv_ref, ses_ref in (("A", "0.750", "0.75", "1.00"), ("B", "2.072", "2.11", "2.11"),
                                       ("C", "", "", "1.00")):
        c = sil[sil["participant"] == p]["cadence_median_spm"].to_numpy(float)
        src = f"무음 회차 케이던스 {lst(c, 2)} 걸음/분 (results/walks.csv: cadence_median_spm)"
        if len(c) >= 2:
            sd = float(c.std(ddof=1))
            cv = sd / c.mean() * 100
            sh.add(f"{p} 무음 케이던스의 표본 SD (걸음/분)", sd, None, sd_ref, inputs=src)
            sh.add(f"{p} 변동계수 (%)", cv, base.loc[p, "silent_cv_pct"], cv_ref, inputs=src)
            ses = max(cv, floor)
        else:
            ses = floor
            src += ". 무음 1회라 변동계수를 낼 수 없어 하한을 쓴다(임시값)"
        sh.add(f"{p} SESOI (%)", ses, base.loc[p, "sesoi_pct"], ses_ref, inputs=src)

    sh.begin("HC-A3", kind, "", "실측", "T = BPM ÷ PC × 100 (실험 2는 튼 BPM ÷ 현장 PC × 100)")
    pc_a = float(base.loc["A", "pc_spm"])
    sh.add("예: 120 BPM 곡을 A가 들을 때 T (%)", 120 / pc_a * 100, None, "120.3",
           inputs=f"BPM 120(예), A의 PC {pc_a:.2f} 걸음/분 (results/participants.csv: pc_spm)")
    refs = {("A", "100"): "104.3", ("A", "120"): "124.1", ("B", "100"): "97.8"}
    for r in t.s2[t.s2["bpm_played"].notna()].itertuples():
        pcf = float(t.pcs.loc[r.runner, "pc_field_spm"])
        sh.add(f"실험 2 {r.runner} {r.ratio_pct}% 단계 T (%)", r.bpm_played / pcf * 100, r.tempo_ratio_pct,
               refs.get((r.runner, r.ratio_pct), ""), nd=1,
               inputs=f"튼 BPM {r.bpm_played:.0f} (results/exp2_summary.csv: bpm_played), 현장 PC {pcf:.2f} 걸음/분 "
                      "(results/exp2_pc.csv: pc_field_spm)")
    pl_code = t.pres[t.pres["row_type"] == "playlist"].set_index(["participant", "playlist"])
    t_hand = music["bpm"] / music["participant"].map(base["pc_spm"]) * 100
    dc_hand = (music["cadence_median_spm"] / music["participant"].map(base["pc_spm"]) - 1) * 100
    for (p, pl), idx in music.groupby(["participant", "playlist"]).groups.items():
        sh.add(f"실험 1 {p} {pl} 평균 T (%)", t_hand[idx].mean(), pl_code.loc[(p, pl), "playlist_t_pct"], nd=1,
               inputs=f"곡 구간 {len(idx)}개의 BPM (results/segments.csv: bpm), PC {base.loc[p, 'pc_spm']:.2f} 걸음/분",
               formula="곡 구간마다 T = BPM ÷ PC × 100을 내고 평균한다")
    for p, lo_ref, hi_ref in (("A", "100", "132"), ("B", "102", "135"), ("C", "84", "111")):
        d = music[music["participant"] == p]
        src = f"곡 구간 {len(d)}개의 BPM (results/segments.csv: bpm), PC {base.loc[p, 'pc_spm']:.2f} 걸음/분"
        sh.add(f"실험 1 {p} 곡 구간 T, 최소 (%)", t_hand[d.index].min(), d["tempo_ratio_pct"].min(), lo_ref, inputs=src)
        sh.add(f"실험 1 {p} 곡 구간 T, 최대 (%)", t_hand[d.index].max(), d["tempo_ratio_pct"].max(), hi_ref, inputs=src)
    sh.add("실험 1 곡 BPM, 최소", None, music["bpm"].min(), "100", inputs="results/segments.csv: bpm", formula="읽은 값")
    sh.add("실험 1 곡 BPM, 최대", None, music["bpm"].max(), "132", inputs="results/segments.csv: bpm", formula="읽은 값")
    for p, vid_ref, sheet_ref in (("A", "100.7", "104.1"), ("B", "117.6", "116.9")):
        sil2 = t.st2[(t.st2["runner"] == p) & (t.st2["ratio_pct"] == SILENT)]
        cad = sil2["steps_N"] / sil2["t30_s"] * 60
        src = (f"무음 두 시행의 영상 걸음 수 {lst(sil2['steps_N'], 0)}, 통과 시간 {lst(sil2['t30_s'], 2)} s "
               "(results/exp2_stages.csv: steps_N, t30_s)")
        sh.add(f"실험 2 {p} 현장 PC, 영상에서 다시 읽은 값 (걸음/분)", cad.mean(), t.pcs.loc[p, "pc_field_spm"], vid_ref, inputs=src,
               formula="시행마다 걸음 수 ÷ 통과 시간 × 60을 내고 두 시행을 평균한다")
        sh.add(f"실험 2 {p} 현장 PC, 스톱워치로 잰 값 (걸음/분)", None, t.pcs.loc[p, "pc_field_sheet_spm"], sheet_ref,
               inputs="results/exp2_pc.csv: pc_field_sheet_spm", formula="읽은 값(기록지)")

    sh.begin("HC-A4", kind, "", "실측", "곡 구간마다 ΔC% = (C − PC) ÷ PC × 100을 내고 평균한다. |ΔC%| > SESOI이면 실질적 변화")
    for (p, pl), idx in music.groupby(["participant", "playlist"]).groups.items():
        sh.add(f"실험 1 {p} {pl} 평균 ΔC% (%)", dc_hand[idx].mean(), pl_code.loc[(p, pl), "playlist_dc_pct"], nd=1,
               inputs=f"곡 구간 {len(idx)}개의 케이던스 (results/segments.csv: cadence_median_spm), "
                      f"PC {base.loc[p, 'pc_spm']:.2f} 걸음/분, SESOI {base.loc[p, 'sesoi_pct']:.2f}%")
    tab = speed_table(t)
    for p, ref in (("A", "99.76"), ("C", "118.54")):
        s0 = tab[(p, SILENT)]
        sh.add(f"교차 확인: {p} 무음 구간의 v ÷ 보폭 × 60 (걸음/분)", s0.v / s0.sl * 60, None, ref,
               inputs=f"속도 표의 {p} 무음 v {s0.v:.3f} m/s, 보폭 {s0.sl:.3f} m (HC-A12의 속도 표)",
               formula="v ÷ 보폭 × 60. PC와 같아야 한다")
    worst = max(abs((x.c / tab[(p, SILENT)].c - 1) * 100 - float(pl_code.loc[(p, pl), "playlist_dc_pct"]))
                for (p, pl), x in tab.items() if pl != SILENT)
    sh.add("교차 확인: 속도 표의 케이던스 변화와 플레이리스트 평균 ΔC%의 최대 차 (%p)", worst, None, "0.15",
           inputs="속도 표의 조건별 평균 케이던스(속도가 있는 구간만), results/prescription.csv: playlist_dc_pct",
           formula="|(조건 케이던스 ÷ 무음 케이던스 − 1) × 100 − ΔC%|의 최댓값")
    # 따라간 비율 R: 정의와 제외 규칙은 결과 전에 정했다(SPEC §4.2). 실험 2 단계의 R은 결과를 본 뒤 낸 탐색 값이다(D-85)
    r_lo, r_hi = params["sync.r_exclude_low"], params["sync.r_exclude_high"]
    explore = "탐색(결과를 본 뒤 낸 값, D-85)"
    f_r = f"R = ΔC% ÷ (T − 100). T가 {r_lo:.0f}–{r_hi:.0f}%이면 내지 않는다"
    r_ref = {"A": ("0.69", "0.69", "0.40", "0.25"), "B": ("1.04", "0.37", "0.28", "0.11"), "C": ("0.11", "0.56", "", "−0.13")}
    for (p, pl), idx in music.groupby(["participant", "playlist"]).groups.items():
        tm, dm = float(t_hand[idx].mean()), float(dc_hand[idx].mean())
        src = f"플레이리스트 평균 T {tm:.2f}%, ΔC% {dm:+.2f}% (HC-A3, HC-A4)"
        if r_lo <= tm <= r_hi:
            sh.add(f"실험 1 {p} {pl} 따라간 비율 R은 내지 않는다(T가 {r_lo:.0f}–{r_hi:.0f}% 안)", inputs=src, formula=f_r)
        else:
            sh.add(f"실험 1 {p} {pl} 따라간 비율 R(플레이리스트 평균으로)", dm / (tm - 100), None, r_ref[p][int(pl[1]) - 1], inputs=src,
                   formula=f_r)
    r2_ref = {("A", "120"): "0.78", ("A", "135"): "0.72", ("A", "150"): "0.75", ("B", "120"): "0.67", ("B", "135"): "0.52",
              ("B", "150"): "0.60"}
    for r in t.s2[t.s2["ratio_pct"].isin(["120", "135", "150"])].itertuples():
        pcf = float(t.pcs.loc[r.runner, "pc_field_spm"])
        t2, dc2 = r.bpm_played / pcf * 100, (r.cadence_median_spm / pcf - 1) * 100
        sh.add(f"탐색: 실험 2 {r.runner} {r.ratio_pct}% 단계 따라간 비율 R", dc2 / (t2 - 100), r.dC_pct / (r.tempo_ratio_pct - 100),
               r2_ref[(r.runner, r.ratio_pct)], formula=f_r + ". 현장 PC 기준", status=explore,
               inputs=f"T {t2:.2f}%, ΔC% {dc2:+.2f}% (튼 BPM {r.bpm_played:.0f}, 센서 케이던스 {r.cadence_median_spm:.2f}, 현장 PC {pcf:.2f}). "
                      "코드 값은 results/exp2_summary.csv의 dC_pct ÷ (tempo_ratio_pct − 100)")
    for p, ref in (("A", "0.48"), ("B", "0.53"), ("C", "0.22")):
        d = music[music["participant"] == p]
        keep = ~((t_hand[d.index] >= r_lo) & (t_hand[d.index] <= r_hi))
        src = (f"곡 구간 {len(d)}개 가운데 T가 {r_lo:.0f}–{r_hi:.0f}%인 {int((~keep).sum())}개를 뺀 {int(keep.sum())}개 "
               "(results/segments.csv: tempo_ratio_pct, dC_pct, R. config/params.toml: sync.r_exclude_low·high)")
        sh.add(f"{p} 곡 구간 평균 R", (dc_hand[d.index][keep] / (t_hand[d.index][keep] - 100)).mean(), d["R"].mean(), ref, inputs=src,
               formula=f_r + ". 남은 곡 구간의 평균")
        sh.add(f"{p} R을 내지 않은 곡 구간 수", int((~keep).sum()), int(d["R"].isna().sum()), inputs=src, formula="센다", nd=0)

    sh.begin("HC-A5", kind, "", "실측", "T와 ΔC%를 각각 순위로 바꾸고(같은 값은 평균 순위) 순위의 피어슨 상관을 낸다")
    near_pct = params["sync.near_pc_pct"]
    for p, ref in (("A", "+0.64"), ("B", "−0.17"), ("C", "+0.12")):
        d = music[music["participant"] == p]
        h = _hyp(t, "H1", p)
        src = f"곡 구간 {len(d)}개의 T와 ΔC% (results/segments.csv: tempo_ratio_pct, dC_pct)"
        sh.add(f"{p} ρ(T, ΔC%)", spearman(d["tempo_ratio_pct"], d["dC_pct"]), h["value"], ref, inputs=src)
        sh.add(f"{p} 곡 구간 수", len(d), h["n"], inputs=src, formula="센다", nd=0)
        pc = float(base.loc[p, "pc_spm"])
        near = (d["bpm"] - pc).abs() <= near_pct / 100 * pc
        for name, mask in ((f"PC ±{near_pct:.0f}% 곡", near), ("그 밖의 곡", ~near)):
            sh.add(f"{p} {name}의 S3 평균 (%)", d.loc[mask, "sync3_pct"].mean(), None, nd=1,
                   inputs=f"곡 구간 {int(mask.sum())}개의 S3 (results/segments.csv: sync3_pct, bpm), PC {pc:.2f}",
                   formula=f"|BPM − PC| ≤ PC의 {near_pct:.0f}%인 구간과 그 밖 구간의 S3 평균")
    d = music[music["participant"] == "A"]
    rho_simple, d2 = spearman_no_ties(d["tempo_ratio_pct"], d["dC_pct"])
    sh.add("A 순위 차 제곱의 합 Σd²", d2, None, nd=1, formula="Σ(T 순위 − ΔC% 순위)²")
    sh.add("A 같은 값이 없을 때의 식으로 낸 값", rho_simple, None, nd=4,
           formula="1 − 6Σd² ÷ (n(n² − 1)). 같은 T가 있어 ρ와 조금 다르다")
    for p, p_ref in (("A", "0.0006"), ("B", "0.2458"), ("C", "0.6866")):
        h = _hyp(t, "H1", p)
        sh.add(f"{p} 가설 1의 p(참고, 손계산하지 않음)", None, _note_number(h["note"], r"p=([0-9.]+)"), p_ref,
               inputs="results/hypotheses.csv: note. 같은 회차의 곡 구간은 서로 독립이 아니라 참고다", formula="읽은 값")
    h = _hyp(t, "H1", "A")
    src = "results/hypotheses.csv: ci_low, ci_high (회차 단위로 다시 뽑아 낸 95% 구간, D-34)"
    sh.add("A ρ의 회차 단위 신뢰구간, 아래", None, h["ci_low"], "−0.07", inputs=src, formula="읽은 값")
    sh.add("A ρ의 회차 단위 신뢰구간, 위", None, h["ci_high"], "+0.87", inputs=src, formula="읽은 값")
    need80 = params["exp2.h1_2_min_sync_frac"] * 100
    b80 = music[(music["participant"] == "B") & (music["sync3_pct"] >= need80)]["sync3_pct"].sort_values(ascending=False)
    src = "B의 곡 구간 S3 (results/segments.csv: sync3_pct). 지시 없이 들은 실험 1의 값"
    sh.add(f"B S3가 {need80:.0f}% 이상인 곡 구간 수", len(b80), None, "2", inputs=src, formula="센다")
    for k, ref in enumerate(("87", "81")):
        if k < len(b80):
            sh.add(f"B S3가 {need80:.0f}% 이상인 곡 구간 {k + 1}의 S3 (%)", None, b80.iloc[k], ref, inputs=src, formula="읽은 값")

    if steps:
        tol = params["sync.tol_pct"]
        lo, hi = params["exp2.min_interval_s"], params["steps.max_interval_s"]
        sh.begin("HC-A6", kind, "", "실측",
                 f"c_i = 60 ÷ 걸음 간격, |c_i − BPM| ≤ BPM의 {tol:.0f}%이면 동조, S3 = 동조 간격 수 ÷ 유효 간격 수 × 100")
        st = t.st2.set_index("trial_id")
        vals = []
        for tid in ("E2_A_100_1", "E2_A_100_2"):
            r = st.loc[tid]
            n_steps, n_valid, n_in, s3 = sync_count(steps[tid], r["window_t0_s"], r["window_t1_s"], r["bpm_played"], tol,
                                                    lo, hi)
            vals.append(s3)
            src = (f"걸음 시각(zip을 패키지의 걸음 검출로 읽음), 분석 창 {r['window_t0_s']:.2f}–{r['window_t1_s']:.2f} s "
                   f"(results/exp2_stages.csv: window_t0_s, window_t1_s), BPM {r['bpm_played']:.0f}, "
                   f"허용 범위 {r['bpm_played'] * (1 - tol / 100):.2f}–{r['bpm_played'] * (1 + tol / 100):.2f} 걸음/분, "
                   f"유효 간격 {lo:.2f}–{hi:.2f} s")
            sh.add(f"{tid} 분석 창 안 걸음 수", n_steps, r["n_steps_window"], inputs=src, formula="센다", nd=0)
            sh.add(f"{tid} 유효 간격 수", n_valid, r["n_valid_intervals"], inputs=src, formula="센다", nd=0)
            sh.add(f"{tid} 동조 간격 수", n_in, None, inputs=src, formula="센다", nd=0)
            sh.add(f"{tid} S3 (%)", s3, r["sync3_pct"], inputs=src, nd=1)
        sh.add("A 100% 단계 S3 (%)", sum(vals) / len(vals), _stage(t, "A", "100")["sync3_pct"], "69.3",
               inputs=f"두 시행의 S3 {lst(vals, 2)}%", formula="두 시행의 평균")

    sh.begin("HC-A7", kind, "", "실측", "HC-A5와 같은 순위 상관")
    for p, ref in (("A", "+0.40"), ("B", "+0.06"), ("C", "−0.56")):
        d = music[(music["participant"] == p) & music["impact_g"].notna()]
        h = _hyp(t, "H2_impact", p)
        src = f"곡 구간 {len(d)}개의 T와 충격 (results/segments.csv: tempo_ratio_pct, impact_g)"
        sh.add(f"{p} ρ(T, 충격)", spearman(d["tempo_ratio_pct"], d["impact_g"]), h["value"], ref, inputs=src)
        sh.add(f"{p} 충격을 낸 곡 구간 수", len(d), h["n"], inputs=src, formula="센다", nd=0)
    for p, ref in (("A", "+0.59"), ("B", ""), ("C", "−0.22")):
        d = music[(music["participant"] == p) & music["speed_ms"].notna()
                  & ~music["flags"].fillna("").str.contains("gps_sparse")]
        h = _hyp(t, "H2_speed", p)
        src = (f"속도가 있는 곡 구간 {len(d)}개 (results/segments.csv: tempo_ratio_pct, speed_ms, step_length_m. "
               "위치 기록이 드문 구간(gps_sparse)은 뺀다)")
        sh.add(f"{p} 속도가 있는 곡 구간 수", len(d), h["n"], inputs=src, formula="센다", nd=0)
        if len(d) >= params["stats.min_n_for_corr"]:
            sh.add(f"{p} ρ(T, 속도)", spearman(d["tempo_ratio_pct"], d["speed_ms"]), h["value"], ref, inputs=src)
            d2 = d[d["step_length_m"].notna()]
            sh.add(f"{p} ρ(T, 보폭)", spearman(d2["tempo_ratio_pct"], d2["step_length_m"]),
                   _hyp(t, "H2_step_length", p)["value"], inputs=src, nd=2)
    sh.add("B 충격 상관의 p(참고, 손계산하지 않음)", None, _note_number(_hyp(t, "H2_impact", "B")["note"], r"p=([0-9.]+)"), "0.71",
           inputs="results/hypotheses.csv: note", formula="읽은 값")
    # 변동성: 걸음 간격 CV를 걸음 목록에서 다시 낸다(실험 1은 results/steps, 실험 2는 다시 읽은 걸음 시각)
    same = params["stats.same_tempo_pct"]
    lo2, hi2 = params["exp2.min_interval_s"], params["steps.max_interval_s"]
    f_cv = "CV = 걸음 간격의 표본 SD ÷ 평균 × 100(유효 간격만)"
    stx = t.st2.set_index("trial_id")
    cv_ref = {"A": ("3.33", "4.24"), "B": ("3.55", "2.40")}
    pairs_by = {}
    for q in variability_pairs(t, params):
        cv1 = []
        for s in q.segs.itertuples():
            st1 = pd.read_csv(t.steps_dir / f"{s.walk_id}_steps.csv")
            cv1.append(interval_cv(st1[st1["valid"] & (st1["song_idx"] == s.song_idx)]["interval_s"]))
        src1 = (f"T가 실험 2 {q.ratio}% 단계와 ±{same:.0f}%p 안인 실험 1 곡 구간 {len(cv1)}개의 걸음 간격 "
                "(results/steps/<회차>_steps.csv: interval_s, valid, song_idx)")
        sh.add(f"{q.p} {q.ratio}% 단계와 짝지은 실험 1 곡 구간의 CV 평균 (%)", sum(cv1) / len(cv1), q.segs["cv_pct"].mean(), inputs=src1,
               formula=f_cv + ". 곡 구간마다 내고 평균한다", nd=2)
        cv2 = []
        tids = list(t.st2[(t.st2["runner"] == q.p) & (t.st2["ratio_pct"] == q.ratio)]["trial_id"])
        if steps and all(x in steps for x in tids):
            for tid in tids:
                r = stx.loc[tid]
                ts = steps[tid][(steps[tid] >= r["window_t0_s"] - 1e-9) & (steps[tid] <= r["window_t1_s"] + 1e-9)]
                iv = np.diff(ts)
                cv2.append(interval_cv(iv[(iv >= lo2) & (iv <= hi2)]))
                sh.add(f"{tid} 걸음 간격 CV (%)", cv2[-1], r["cv_pct"], formula=f_cv, nd=2,
                       inputs=f"걸음 시각(zip을 패키지의 걸음 검출로 읽음), 분석 창 {r['window_t0_s']:.2f}–{r['window_t1_s']:.2f} s, "
                              f"유효 간격 {lo2:.2f}–{hi2:.2f} s")
            stage_cv = sum(cv2) / len(cv2)
            sh.add(f"{q.p} {q.ratio}% 단계 걸음 간격 CV (%)", stage_cv, q.cv2, inputs=f"두 시행의 CV {lst(cv2, 2)}%", formula="두 시행의 평균",
                   nd=2)
        else:
            stage_cv = q.cv2
        pairs_by.setdefault(q.p, []).append((q.ratio, stage_cv, sum(cv1) / len(cv1)))
    for p, pairs in pairs_by.items():
        h = _hyp(t, "H2_variability", p)
        a, b = sum(x[1] for x in pairs) / len(pairs), sum(x[2] for x in pairs) / len(pairs)
        src = (f"실험 2 단계 {', '.join(x[0] + '%' for x in pairs)}의 걸음 간격 CV {lst([x[1] for x in pairs], 2)}%, "
               f"T가 ±{same:.0f}%p 안인 실험 1 곡 구간의 CV 평균 {lst([x[2] for x in pairs], 2)}% (위의 줄)")
        f = f"실험 2 단계마다 T가 ±{same:.0f}%p 안인 실험 1 곡 구간을 짝짓고, 두 쪽 CV 평균의 차를 낸다"
        sh.add(f"{p} 변동성: 짝지은 단계 수", len(pairs), h["n"], inputs=src, formula="센다", nd=0)
        sh.add(f"{p} 변동성: 실험 2 CV 평균 (%)", a, None, cv_ref[p][0], inputs=src, formula=f)
        sh.add(f"{p} 변동성: 실험 1 CV 평균 (%)", b, None, cv_ref[p][1], inputs=src, formula=f)
        sh.add(f"{p} 변동성: 실험 2 − 실험 1 (%p)", a - b, h["value"], inputs=src, formula=f, nd=2)

    sh.begin("HC-A8", kind, "11주차 구심가속도(p60)", "실측(A·B)", "Fr = v² ÷ (g L)")
    for p, r, ref in (("A", "150", "0.398"), ("A", "180", "1.191"), ("B", "150", "0.551"), ("B", "180", "")):
        row, leg = _stage(t, p, r), float(t.body.loc[p, "leg_length_m"])
        sh.add(f"{p} {r}% 단계 Fr", row["v_ms"] ** 2 / (G * leg), row["fr"], ref, nd=3,
               inputs=f"v {row['v_ms']:.3f} m/s (results/exp2_summary.csv: v_ms), 다리 길이 {leg:.2f} m "
                      "(data/participants.csv: leg_length_m)")

    kl, dl = params["pendulum.k_over_L"], params["pendulum.d_over_L"]
    good = _used(t.sw)
    sh.begin("HC-A9", kind, "12주차 τ = Iα(p39, p41–43)·관성모멘트(p22–30). 주기 식은 교안 밖", "실측",
             f"C_pend = 120 ÷ P, P_model = 2π√(({kl:.3f}L)² ÷ (g × {dl:.3f}L)), 오차 = (P − P_model) ÷ P_model × 100")
    errs = []
    for p, cp, pm, err in (("A", "78.38", "1.680", "−8.89"), ("B", "83.40", "1.620", "−11.20")):
        gs = good[(good["runner"] == p) & (good["knee"] == "straight")]["swing_period_s"]
        per, leg = float(gs.median()), float(t.body.loc[p, "leg_length_m"])
        model = whole_leg_period(leg, kl, dl)
        errs.append(abs((per - model) / model * 100))
        src = (f"곧은 다리 주기 P {per:.4f} s (HC-A10), 다리 길이 {leg:.2f} m (data/participants.csv: leg_length_m), "
               f"PC {t.base.loc[p, 'pc_spm']:.2f} 걸음/분")
        sh.add(f"{p} C_pend (걸음/분)", 120 / per, t.p3.loc[p, "cadence_pend_spm"], cp, inputs=src)
        sh.add(f"{p} 다리 전체 모델 주기 P_model (s)", model, t.p3.loc[p, "period_model_s"], pm, inputs=src)
        sh.add(f"{p} 모델 오차 (%)", (per - model) / model * 100, t.p3.loc[p, "period_error_pct"], err, inputs=src)
    sh.add("평균 |오차| (%)", sum(errs) / len(errs), _hyp(t, "H4_model", "ALL")["value"], "10.04",
           inputs=f"A·B의 |오차| {lst(errs, 2)}%. 기준은 {params['pendulum.valid_error_pct']:.0f}% 이내",
           formula="두 사람 |오차|의 평균")

    sh.begin("HC-A10", kind, "", "실측", "10주기 이상 이어진 시행의 중앙값(조건마다 2회라 평균과 같다)")
    fr = _fractions(params)
    for p, ref_p, ref_k, ref_r, ref_pct in (("A", "1.53095", "1.42665", "0.932", "−6.8"),
                                            ("B", "1.4389", "1.2531", "0.871", "−12.9")):
        gs = good[(good["runner"] == p) & (good["knee"] == "straight")]
        gb = good[(good["runner"] == p) & (good["knee"] == "bent")]
        ps, pb = float(gs["swing_period_s"].median()), float(gb["swing_period_s"].median())
        src = (f"쓴 시행의 주기: 곧은 다리 {', '.join(gs['trial_id'])} = {lst(gs['swing_period_s'], 4)} s, 굽힌 다리 "
               f"{', '.join(gb['trial_id'])} = {lst(gb['swing_period_s'], 4)} s (results/exp3_swings.csv: swing_period_s)")
        sh.add(f"{p} 곧은 다리 주기 P (s)", ps, t.p3.loc[p, "swing_period_s"], ref_p, inputs=src)
        sh.add(f"{p} 굽힌 다리 주기 P_K (s)", pb, t.p3.loc[p, "swing_period_bent_s"], ref_k, inputs=src)
        sh.add(f"{p} P_K ÷ P", pb / ps, t.p3.loc[p, "period_ratio_bent"], ref_r, inputs=src, formula="P_K ÷ P")
        sh.add(f"{p} 주기 변화 (%)", (pb / ps - 1) * 100, None, ref_pct, inputs=src, formula="(P_K ÷ P − 1) × 100")
    note = segment_model(60.0, 1.70 * params["pendulum.fallback_thigh_over_H"],
                         1.70 * params["pendulum.fallback_shank_over_H"], 0, fr).P
    a_tr = t.sw.set_index("trial_id").loc[["E3_A_1", "E3_A_3"]]
    four = list(a_tr["swing_period_s"]) + list(a_tr["video_period_s"])
    gaps = [abs(float(x) - note) for x in four]
    src = (f"A 곧은 다리 두 시행의 폰 주기 {lst(a_tr['swing_period_s'], 4)} s와 영상 주기 {lst(a_tr['video_period_s'], 4)} s "
           "(results/exp3_swings.csv: swing_period_s, video_period_s)")
    sh.add("참고: 손계산 노트 예시 입력(60 kg, 키 1.70 m)의 분절 모델 주기 (s)", note, None, "1.5305",
           inputs="예시 입력: 체중 60 kg, 허벅지 0.4165 m, 정강이 0.4182 m (docs/HANDCALC.md 7번)",
           formula="P = 2π√(I ÷ mgd), 두 분절 모델")
    sh.add("참고: A 시행 값 넷과 예시의 차, 최소 (s)", min(gaps), None, "0.019", inputs=src, formula="|시행 값 − 예시|")
    sh.add("참고: A 시행 값 넷과 예시의 차, 최대 (s)", max(gaps), None, "0.026", inputs=src, formula="|시행 값 − 예시|")
    sh.add("참고: A 같은 두 시행의 영상 주기 중앙값 (s)", float(a_tr["video_period_s"].median()), None, "1.5305",
           inputs=src, formula="두 값의 중앙값")

    tol = params["sync.tol_pct"]
    sh.begin("HC-A11", kind, "", "실측",
             "하한 = 평균 ΔC%가 +SESOI를 넘은 플레이리스트 중 평균 T가 가장 낮은 것(T ≤ 100%는 뺀다). "
             f"상한 = T 순서로 처음 평균 동조(|케이던스 ÷ BPM − 1| ≤ {tol:.0f}%)가 깨진 단계의 바로 앞 단계 T")
    summ = t.pres[t.pres["row_type"] == "summary"].set_index("participant")
    for p, ref_t, ref_b in (("A", "102.9", "102.6"), ("B", "105.1", "103.0"), ("C", "", "")):
        d = music[music["participant"] == p]
        pc, ses = float(base.loc[p, "pc_spm"]), float(base.loc[p, "sesoi_pct"])
        pl = pd.DataFrame(dict(t=t_hand[d.index].groupby(d["playlist"]).mean(),
                               dc=dc_hand[d.index].groupby(d["playlist"]).mean()))
        ok = pl[(pl["dc"] > ses) & (pl["t"] > 100)]
        src = ("플레이리스트 평균 (T %, ΔC %): " + ", ".join(f"{k} ({r.t:.1f}, {r.dc:+.1f})" for k, r in pl.iterrows())
               + f". SESOI {ses:.2f}%, PC {pc:.2f} 걸음/분 (HC-A1–A4)")
        if len(ok):
            low = float(ok["t"].min())
            sh.add(f"{p} 하한 T (일상 PC 대비 %)", low, summ.loc[p, "t_low_pct"], ref_t, inputs=src)
            sh.add(f"{p} 하한 BPM", low / 100 * pc, summ.loc[p, "bpm_low"], ref_b, inputs=src, formula="하한 T ÷ 100 × PC")
        else:
            sh.add(f"{p} 하한이 있는가(있으면 1, 없으면 0)", 0, int(pd.notna(summ.loc[p, "t_low_pct"])), inputs=src,
                   formula="조건을 채운 플레이리스트가 하나라도 있는가", nd=0)
    num = t.s2[t.s2["ratio_pct"].str.isdigit()]
    for p, offs, ref_t, ref_b in (("A", {"100": "+0.48", "120": "−4.24"}, "104.3", "105.0"), ("B", {"100": "+5.91"}, "", "")):
        s = num[num["runner"] == p].copy()
        pcf = float(t.pcs.loc[p, "pc_field_spm"])
        s["t_hand"] = s["bpm_played"] / pcf * 100
        s = s.sort_values("t_hand")
        s["off"] = (s["cadence_median_spm"] / s["bpm_played"] - 1) * 100
        for r in s.itertuples():
            if r.ratio_pct in offs:
                sh.add(f"{p} {r.ratio_pct}% 단계 평균 동조 어긋남 (%)", r.off, None, offs[r.ratio_pct],
                       inputs=f"센서 케이던스 {r.cadence_median_spm:.2f} 걸음/분, 튼 BPM {r.bpm_played:.0f} "
                              "(results/exp2_summary.csv: cadence_median_spm, bpm_played)",
                       formula="(케이던스 ÷ BPM − 1) × 100")
        okk = (s["off"].abs() <= tol).to_numpy()
        n_ok = int(np.argmin(okk)) if not okk.all() else len(okk)
        src = ("단계별 (T %, 어긋남 %): " + ", ".join(f"{r.ratio_pct}% ({r.t_hand:.1f}, {r.off:+.2f})" for r in s.itertuples())
               + f". 현장 PC {pcf:.2f} 걸음/분 (results/exp2_pc.csv: pc_field_spm)")
        if n_ok:
            high = float(s["t_hand"].iloc[n_ok - 1])
            sh.add(f"{p} 상한 T (현장 PC 대비 %)", high, summ.loc[p, "t_high_pct"], ref_t, inputs=src)
            sh.add(f"{p} 상한 BPM", high / 100 * pcf, summ.loc[p, "bpm_high"], ref_b, inputs=src,
                   formula="상한 T ÷ 100 × 현장 PC")
        else:
            sh.add(f"{p} 평균 동조 기준 상한이 있는가(있으면 1, 없으면 0)", 0, int(pd.notna(summ.loc[p, "t_high_pct"])),
                   inputs=src, formula="첫 단계부터 깨지면 상한이 없다", nd=0)
        need = params["exp2.h1_2_min_sync_frac"] * 100
        first = s.iloc[0]
        sh.add(f"{p} S3 기준({need:.0f}% 이상) 상한이 있는가(있으면 1, 없으면 0)", int(first["sync3_pct"] >= need),
               int(pd.notna(summ.loc[p, "t_high_s3_pct"])), nd=0,
               inputs=f"첫 단계({first['ratio_pct']}%) S3 {first['sync3_pct']:.1f}% (results/exp2_summary.csv: sync3_pct)",
               formula=f"첫 단계의 S3가 {need:.0f}% 미만이면 상한이 없다")
    # 민감도(D-89): 동조 기준을 ±5%로 넓혔을 때 A의 상한
    s = num[num["runner"] == "A"].copy()
    pcf = float(t.pcs.loc["A", "pc_field_spm"])
    s["t_hand"] = s["bpm_played"] / pcf * 100
    s = s.sort_values("t_hand")
    ok5 = (((s["cadence_median_spm"] / s["bpm_played"] - 1) * 100).abs() <= 5.0).to_numpy()
    n5 = int(np.argmin(ok5)) if not ok5.all() else len(ok5)
    v5 = t.sens[(t.sens["variant"] == "sync_tol_5pct") & (t.sens["metric"] == "t_high_pct") & (t.sens["participant"] == "A")]
    sh.add("민감도: 동조 기준을 ±5%로 넓히면 A 상한 T (현장 PC 대비 %)", float(s["t_hand"].iloc[n5 - 1]) if n5 else None,
           v5.iloc[0]["value_variant"] if len(v5) else None, "124.1",
           inputs="A 단계별 평균 동조 어긋남(위의 줄), results/sensitivity.csv: sync_tol_5pct의 t_high_pct",
           formula="기준만 ±5%로 바꿔 같은 방법으로 낸다. 기본 결과는 그대로다")

    sh.begin("HC-A12", kind, "5주차 평균 속도(p35–38)", "실측(A·C)",
             "Δln v = Δln 보폭 + Δln 케이던스(무음 대비). 속도 표는 속도가 있는 곡 구간의 평균이고 보폭 = v ÷ (케이던스 ÷ 60)")
    table_ref = {("A", SILENT): ("2", "", "1.247", "0.750"), ("A", "P1"): ("6", "103.3", "1.304", "0.768"),
                 ("A", "P2"): ("6", "110.3", "1.389", "0.780"), ("A", "P3"): ("6", "119.7", "1.424", "0.794"),
                 ("A", "P4"): ("6", "131.4", "1.431", "0.799"), ("C", SILENT): ("1", "", "1.703", "0.862"),
                 ("C", "P1"): ("4", "86.3", "1.476", "0.759"), ("C", "P2"): ("3", "92.8", "1.533", "0.809"),
                 ("C", "P3"): ("3", "100.7", "1.461", "0.744"), ("C", "P4"): ("3", "110.5", "1.427", "0.732")}
    src_tab = ("속도가 있는 곡 구간 (results/segments.csv: speed_ms, cadence_median_spm, tempo_ratio_pct. "
               "gps_sparse·few_steps 구간은 뺀다)")
    for (p, cond), (n_ref, t_ref, v_ref, sl_ref) in table_ref.items():
        x, name = tab[(p, cond)], "무음" if cond == SILENT else cond
        sh.add(f"속도 표: {p} {name} 구간 수", x.n, None, n_ref, inputs=src_tab, formula="센다")
        if t_ref:
            sh.add(f"속도 표: {p} {name} 평균 T (%)", x.t, None, t_ref, inputs=src_tab, formula="구간 평균")
        sh.add(f"속도 표: {p} {name} v (m/s)", x.v, None, v_ref, inputs=src_tab, formula="구간 평균")
        sh.add(f"속도 표: {p} {name} 보폭 (m)", x.sl, None, sl_ref, inputs=src_tab, formula="v ÷ (평균 케이던스 ÷ 60)")
    dec = {("A", "P1"): "0.0447 0.0237 0.0210 47", ("A", "P2"): "0.1078 0.0392 0.0686 64",
           ("A", "P3"): "0.1327 0.0570 0.0757 57", ("A", "P4"): "0.1376 0.0633 0.0743 54",
           ("C", "P1"): "−0.1431 −0.1273 −0.0158 89", ("C", "P2"): "−0.1052 −0.0635 −0.0417 60",
           ("C", "P3"): "−0.1533 −0.1472 −0.0061 96", ("C", "P4"): "−0.1768 −0.1635 −0.0133 92"}
    for (p, pl), txt in dec.items():
        x0, x1 = tab[(p, SILENT)], tab[(p, pl)]
        dv, dc, dsl = math.log(x1.v / x0.v), math.log(x1.c / x0.c), math.log(x1.sl / x0.sl)
        a, b, c, share = txt.split()
        src = (f"속도 표: 무음 v {x0.v:.3f} m/s·보폭 {x0.sl:.3f} m·케이던스 {x0.c:.2f}, {pl} v {x1.v:.3f}·보폭 {x1.sl:.3f}·"
               f"케이던스 {x1.c:.2f}")
        sh.add(f"{p} {pl} Δln v", dv, None, a, inputs=src, formula="ln(v ÷ 무음 v)")
        sh.add(f"{p} {pl} Δln 보폭", dsl, None, b, inputs=src, formula="ln(보폭 ÷ 무음 보폭)")
        sh.add(f"{p} {pl} Δln 케이던스", dc, None, c, inputs=src, formula="ln(케이던스 ÷ 무음 케이던스)")
        if p == "A":
            sh.add(f"{p} {pl} 속도 변화 중 케이던스 몫 (%)", dc / dv * 100, None, share, inputs=src,
                   formula="Δln 케이던스 ÷ Δln v × 100")
        else:
            sh.add(f"{p} {pl} 줄어든 속도 중 보폭 몫 (%)", dsl / dv * 100, None, share, inputs=src,
                   formula="Δln 보폭 ÷ Δln v × 100")

    sh.begin("HC-A13", kind, "5주차 t = d ÷ v(p35–36)", "실측(A·C)", "Δt = d ÷ v_조건 − d ÷ v_무음, d = 1.5 km(예시 거리)")
    com = {("A", SILENT): "1,202.9", ("A", "P1"): "−52.6", ("A", "P2"): "−123.0", ("A", "P3"): "−149.5",
           ("A", "P4"): "−154.7", ("C", SILENT): "880.8", ("C", "P1"): "+135.5", ("C", "P2"): "+97.7",
           ("C", "P3"): "+145.9", ("C", "P4"): "+170.4"}
    for (p, pl), ref in com.items():
        v0 = tab[(p, SILENT)].v
        if pl == SILENT:
            sh.add(f"{p} 무음으로 1.5 km 걷는 시간 (s)", 1500 / v0, None, ref, inputs=f"속도 표: 무음 v {v0:.3f} m/s",
                   formula="1500 ÷ v_무음")
        else:
            v1 = tab[(p, pl)].v
            sh.add(f"{p} {pl} 시간 차 (s)", 1500 / v1 - 1500 / v0, None, ref,
                   inputs=f"속도 표: 무음 v {v0:.3f} m/s, {pl} v {v1:.3f} m/s")

    sh.begin("HC-A14", kind, "", "실측", "차 = 첫째 방법 − 둘째 방법. 평균, 표본 SD, 95% 일치 한계 = 평균 ± 1.96 SD")

    def agreement(label, unit, a, b, measure, who, src, refs=None, pair_refs=None, names=None):
        ba = bland_altman(a, b)
        v = t.val[(t.val["measure"] == measure) & (t.val["participant"] == who)].iloc[0]
        refs = refs or {}
        for k, x in enumerate(ba.diffs):
            if pair_refs:
                sh.add(f"{label}: 짝 {names[k]}의 차 ({unit})", x, None, pair_refs[k], inputs=src)
        sh.add(f"{label}: 짝 수", ba.n, v["n"], refs.get("n", ""), inputs=src, formula="센다", nd=0)
        sh.add(f"{label}: 차의 평균 ({unit})", ba.mean, v["bias"], refs.get("mean", ""), inputs=src, nd=4)
        sh.add(f"{label}: 차의 평균 (%)", ba.mean / ba.mean_b * 100, v["bias"] / v["mean_b"] * 100, refs.get("pct", ""),
               inputs=src, formula="차의 평균 ÷ 둘째 방법의 평균 × 100", nd=1)
        if ba.n > 1 and pd.notna(v["loa_low"]):
            sh.add(f"{label}: 차의 표본 SD ({unit})", ba.sd, (v["loa_high"] - v["bias"]) / 1.96, refs.get("sd", ""),
                   inputs=src, nd=4)
            sh.add(f"{label}: 일치 한계 아래 ({unit})", ba.low, v["loa_low"], refs.get("low", ""), inputs=src, nd=4)
            sh.add(f"{label}: 일치 한계 위 ({unit})", ba.high, v["loa_high"], refs.get("high", ""), inputs=src, nd=4)

    pv = t.sw[t.sw["video_period_s"].notna()]
    agreement("진자 주기(폰 − 영상)", "s", pv["swing_period_s"], pv["video_period_s"], "swing_period", "ALL",
              "results/exp3_swings.csv: swing_period_s(폰), video_period_s(영상 10번 흔들림 ÷ 10)",
              dict(n="8", mean="+0.0043", pct="+0.28", sd="0.0142", low="−0.0235", high="+0.0322"),
              "+0.0073 −0.0064 −0.0120 +0.0216 −0.0112 −0.0025 +0.0213 +0.0167".split(), list(pv["trial_id"]))
    sh.add("진자 주기: 영상 ÷ 폰 − 1의 평균 (%)", ((pv["video_period_s"] / pv["swing_period_s"] - 1) * 100).mean(), None, "−0.3",
           inputs="results/exp3_swings.csv: swing_period_s, video_period_s", formula="같은 8짝을 영상 기준 비율로 본 값(부호가 반대다)")
    jv = t.jumps[t.jumps["flight_time_video_s"].notna()]
    jnames = [f"{r.trial_id} 점프 {int(r.jump_no)}" for r in jv.itertuples()]
    src_j = ("results/jumps.csv: flight_time_s(폰), flight_time_video_s(영상). E2_A_J_2는 영상이 있는 A의 낮 기록이고 "
             "검증에만 쓴다(D-87). 점프 표의 A 값은 영상이 없는 저녁 기록 E2_A_J_1이다")
    for name, r, ref in zip(jnames, jv.itertuples(), ("0.564", "0.555", "0.529", "0.523", "0.500")):
        sh.add(f"점프 체공(폰 − 240 fps 영상): {name}의 폰 체공 (s)", None, r.flight_time_s, ref, inputs=src_j, formula="읽은 값")
    agreement("점프 체공(폰 − 240 fps 영상)", "s", jv["flight_time_s"], jv["flight_time_video_s"], "jump_flight", "ALL", src_j,
              dict(n="5", mean="+0.026", pct="+5.1"), "+0.048 +0.044 +0.031 +0.016 −0.009".split(), jnames)
    jj = _used(t.jumps)
    agreement("점프 이륙 속도(체공 − 가속도 적분)", "m/s", jj["takeoff_v_flight_ms"], jj["takeoff_v_int_ms"],
              "jump_takeoff_velocity", "ALL", "results/jumps.csv: takeoff_v_flight_ms, takeoff_v_int_ms",
              dict(n="6", mean="+0.307", pct="+14.0"))
    sa = segs[(segs["participant"] == "A") & segs["step_length_zh_m"].notna() & segs["step_length_m"].notna()]
    agreement("보폭(역진자 − GPS, A)", "m", sa["step_length_zh_m"], sa["step_length_m"], "step_length", "A",
              "results/segments.csv: step_length_zh_m, step_length_m (A의 곡 구간)", dict(n="26", mean="−0.130", pct="−16.6"))
    agreement("실험 2 케이던스(영상 걸음 수 ÷ 시간 − 센서)", "걸음/분", t.st2["cadence_record_spm"],
              t.st2["cadence_median_spm"], "exp2_cadence", "ALL",
              "results/exp2_stages.csv: cadence_record_spm(영상 걸음 수 ÷ t30 × 60), cadence_median_spm(센서)",
              dict(n="30", mean="+0.077", pct="+0.1"))
    vint = t.vexp2.set_index("trial_id")["cadence_interval_spm"]
    sen = t.st2.set_index("trial_id")["cadence_median_spm"]
    rel = ((vint / sen - 1) * 100).dropna()
    src = ("data/video_exp2.csv: cadence_interval_spm(영상의 디딤 간격으로 낸 케이던스), results/exp2_stages.csv: "
           "cadence_median_spm(센서). 위의 '걸음 수 ÷ 시간'과 다른 방법이다")
    sh.add("실험 2 케이던스(영상 디딤 간격 ÷ 센서 − 1): 시행 수", len(rel), None, "30", inputs=src, formula="센다")
    sh.add("실험 2 케이던스(영상 디딤 간격 ÷ 센서 − 1): 평균 (%)", rel.mean(), None, "+0.6", inputs=src)
    sh.add("실험 2 케이던스(영상 디딤 간격 ÷ 센서 − 1): 표본 SD (%)", rel.std(ddof=1), None, "1.8", inputs=src)
    sh.add("실험 2 케이던스(영상 디딤 간격 ÷ 센서 − 1): 2% 안인 시행 수", int((rel.abs() <= 2).sum()), None, "27", inputs=src, formula="센다")
    v100 = t.val[t.val["measure"] == "steps_100"]
    if len(v100):
        sh.add("사전 점검: 직접 센 100걸음을 검출한 걸음 수", None, v100.iloc[0]["mean_a"], "102",
               inputs="results/validation.csv: steps_100", formula="읽은 값")
    wa = t.walks[(t.walks["participant"] == "A") & t.walks["section_gps_m"].notna()]
    map_m = float(t.body.loc["A", "section_distance_m"])
    agreement("측정 구간 거리(GPS − 지도, A)", "m", wa["section_gps_m"], [map_m] * len(wa), "section_distance", "A",
              f"results/walks.csv: section_gps_m, 지도 거리 {map_m:.1f} m (data/participants.csv: section_distance_m)",
              dict(n="10", mean="+6.569", pct="+2.5"))
    wd = wa[wa["speed_doppler_section_ms"].notna() & wa["speed_section_ms"].notna()]
    agreement("측정 구간 속도(Doppler − 지도 거리 ÷ 통과 시간, A)", "m/s", wd["speed_doppler_section_ms"],
              wd["speed_section_ms"], "section_speed_doppler", "A",
              "results/walks.csv: speed_doppler_section_ms, speed_section_ms", dict(n="8", mean="−0.190", pct="−14.2"))


# ---------------------------------------------------------------- 교안 예제 짝 손계산 (HC-B1–B20)과 연결표의 값
def rows_pairs(sh: Sheet, t, params) -> None:
    kind, base, body, mod = "교안 짝", t.base, t.body, models(t, params)
    mg = {p: float(body.loc[p, "mass_kg"]) * G for p in ("A", "B")}
    si = base["silent_impact_g"]
    jj = _used(t.jumps).sort_values(["runner", "jump_no"]).reset_index(drop=True)
    tr = t.sw.set_index("trial_id")
    good = _used(t.sw)
    amp = {p: float(good[(good["runner"] == p) & (good["knee"] == "straight")]["amp_deg"].mean()) for p in ("A", "B")}
    tau = {p: mod[p].s.m * G * mod[p].s.d * math.sin(math.radians(amp[p])) for p in ("A", "B")}
    period = {p: float(t.p3.loc[p, "swing_period_s"]) for p in ("A", "B")}
    tab = speed_table(t)
    src_body = "data/participants.csv: mass_kg, leg_length_m, thigh_length_m, shank_length_m"

    sh.begin("HC-B1", kind, "10주차 p11 예제 1; 9주차 p19 F = ma, p26 질량중심, p28 W = mg, p30 지면반력", "실측",
             "거꾸로 풀기 F = m(g + a). 충격(BW) = (g + a) ÷ g")
    for p, ref_bw, ref_a, ref_f in (("A", "1.60", "5.89", "1,099"), ("B", "1.58", "", "960")):
        src = (f"무음 걷기의 발 디딤 충격 {si[p]:.4f} BW (results/participants.csv: silent_impact_g), "
               f"체중 {body.loc[p, 'mass_kg']:.0f} kg")
        sh.add(f"{p} 발 디딤 충격 (BW)", None, si[p], ref_bw, inputs=src, formula="읽은 값")
        sh.add(f"{p} 중력을 뺀 수직 가속도 a (m/s²)", (si[p] - 1) * G, None, ref_a, inputs=src, formula="a = (충격 − 1) × g",
               nd=2)
        sh.add(f"{p} 지면반력 F (N)", si[p] * mg[p], None, ref_f, inputs=src, formula="F = 충격 × m × g")

    sh.begin("HC-B2", kind, "10주차 p8–10 정적 분석 ΣF = 0; 2주차 p24; 9주차 p17", "실측",
             "등속 보행이면 한 걸음 동안 ∫(F − mg)dt = 0 → 수직 가속도의 평균 = 1 g. 읽은 값")
    okw = t.walks[t.walks["mean_av_g"].notna()]
    for p, lo, hi in (("A", "1.0014", "1.0067"), ("B", "1.0000", "1.0002"), ("C", "1.0069", "1.0079")):
        d = okw[okw["participant"] == p]["mean_av_g"]
        src = f"회차 {len(d)}개의 평균 수직 가속도 (results/walks.csv: mean_av_g)"
        sh.add(f"{p} 회차 평균 수직 가속도, 최소 (g)", None, d.min(), lo, inputs=src)
        sh.add(f"{p} 회차 평균 수직 가속도, 최대 (g)", None, d.max(), hi, inputs=src)

    lim = params["stats.froude_walk_run"]
    sh.begin("HC-B3", kind, "11주차 p60 예제 3", "실측(A·B)", "a_c = v² ÷ L ≤ g → v ≤ √(gL). Fr = v² ÷ (gL)")
    for p, a, b in (("A", "3.132", "2.215"), ("B", "3.020", "2.136")):
        leg = float(body.loc[p, "leg_length_m"])
        src = f"다리 길이 {leg:.2f} m (data/participants.csv: leg_length_m)"
        sh.add(f"{p} 걷기의 한계 속도 √(gL) (m/s)", math.sqrt(G * leg), None, a, inputs=src, formula="√(g L)")
        sh.add(f"{p} Fr {lim:.1f}가 되는 속도 (m/s)", math.sqrt(lim * G * leg), None, b, inputs=src,
               formula=f"√({lim:.1f} g L)")

    run = t.s2[t.s2["flight_time_median_s"].notna() & t.s2["contact_time_s"].notna()]
    ref4 = {("A", "180"): ("0.564", "9.36", "0.393", "1.62", "9"), ("B", "180"): ("0.304", "5.26", "0.205", "0.47", ""),
            ("B", "195"): ("0.366", "5.37", "0.290", "0.68", "17")}
    ref15 = {("A", "180"): ("3.46", "9.4"), ("B", "180"): ("3.32", "5.3"), ("B", "195"): ("3.91", "5.4")}
    ref6 = {("A", "180"): ("1,579", "2.30", "6.49", "15.88", "24.3", "9.9", "51.3"),
            ("B", "180"): ("1,171", "1.92", "5.20", "17.05", "22.5", "6.9", "30.4"),
            ("B", "195"): ("1,251", "2.06", "4.75", "17.45", "26.3", "7.2", "29.7")}
    sh.begin("HC-B4", kind, "7주차 p23–24, p29–30 축구공 킥; 처음 각 p20–22", "참고값",
             "v_y = g t_f ÷ 2, θ = arctan(v_y ÷ v), 공중 거리 = v t_f, 상승 = g t_f² ÷ 8")
    for r in run.itertuples():
        key, tf, tc, v = (r.runner, r.ratio_pct), float(r.flight_time_median_s), float(r.contact_time_s), float(r.v_ms)
        vy_ref, th_ref, dist_ref, rise_ref, shake_ref = ref4[key]
        from_cad = "tf_from_cadence" in str(r.flags)
        src = (f"체공 t_f {tf:.4f} s, 접촉 t_c {tc:.4f} s, v {v:.3f} m/s (results/exp2_summary.csv: flight_time_median_s, "
               f"contact_time_s, v_ms. 발 카메라에서 읽은 접촉 {int(r.n_contacts_video)}개)")
        name = f"{r.runner} {r.ratio_pct}%"
        if from_cad:
            sh.add(f"{name} 체공 t_f = 걸음 간격 − 접촉 시간 (s)", 60 / r.cadence_median_spm - tc, tf, inputs=src, nd=4,
                   formula="60 ÷ 센서 케이던스 − t_c")
            sh.add(f"{name} 접촉이 10 ms 달라지면 체공이 달라지는 크기 (%)", 0.010 / tf * 100, None, shake_ref, inputs=src,
                   formula="10 ms ÷ t_f × 100", nd=1)
        sh.add(f"{name} 수직 이륙 속도 v_y (m/s)", G * tf / 2, None, vy_ref, inputs=src, formula="g t_f ÷ 2")
        sh.add(f"{name} 이륙 각 θ (°)", math.degrees(math.atan(G * tf / 2 / v)), r.takeoff_angle_deg, th_ref, inputs=src,
               formula="arctan(v_y ÷ v)")
        sh.add(f"{name} 공중 거리 (m)", v * tf, None, dist_ref, inputs=src, formula="v t_f")
        sh.add(f"{name} 몸 중심 상승 (cm)", G * tf ** 2 / 8 * 100, r.rise_height_m * 100, rise_ref, inputs=src,
               formula="g t_f² ÷ 8")
    fast = t.s2[t.s2["ratio_pct"].isin(["165", "180", "195"])]
    for p, lo_ref, hi_ref in (("A", "2", "2"), ("B", "2", "5")):
        f = fast[fast["runner"] == p]["flight_step_frac"] * 100
        src = (f"{p}의 165% 이상 단계에서 폰이 체공을 잡은 걸음의 비율 {lst(f, 1)}% (results/exp2_summary.csv: flight_step_frac). "
               "그래서 체공은 발 카메라에서 읽었다")
        sh.add(f"{p} 폰이 체공을 잡은 걸음 비율, 최소 (%)", None, f.min(), lo_ref, inputs=src, formula="읽은 값")
        sh.add(f"{p} 폰이 체공을 잡은 걸음 비율, 최대 (%)", None, f.max(), hi_ref, inputs=src, formula="읽은 값")

    sh.begin("HC-B5", kind, "10주차 p17 예제 5; 9주차 p45 힘–시간 곡선 아래 넓이 = 충격량, p53 에너지 보존", "실측",
             "h = g t_f² ÷ 8, 체공 v = g t_f ÷ 2, J = m × 체공 v, ½ m v², 밀기 평균 지면반력 = 1 + 적분 v ÷ (g t_push)")
    for r in jj.itertuples():
        m, name = float(body.loc[r.runner, "mass_kg"]), f"{r.runner} 점프 {r.jump_no}"
        src = (f"체공 t_f {r.flight_time_s:.4f} s, 적분 v {r.takeoff_v_int_ms:.3f} m/s, 밀기 시간 {r.pushoff_time_s:.3f} s "
               f"(results/jumps.csv: flight_time_s, takeoff_v_int_ms, pushoff_time_s), 체중 {m:.0f} kg")
        vf = G * r.flight_time_s / 2
        sh.add(f"{name} 높이 h (cm)", G * r.flight_time_s ** 2 / 8 * 100, r.height_m * 100, inputs=src, nd=1,
               formula="g t_f² ÷ 8")
        sh.add(f"{name} 체공 v (m/s)", vf, r.takeoff_v_flight_ms, inputs=src, formula="g t_f ÷ 2", nd=3)
        sh.add(f"{name} 충격량 J (N·s)", m * vf, r.impulse_ns, inputs=src, formula="m × 체공 v", nd=1)
        sh.add(f"{name} 운동에너지 ½mv² (J)", 0.5 * m * vf ** 2, r.kinetic_energy_j, inputs=src, formula="½ m (체공 v)²",
               nd=1)
        sh.add(f"{name} 밀기 평균 지면반력 (BW)", 1 + r.takeoff_v_int_ms / (G * r.pushoff_time_s), r.mean_grf_push_bw,
               inputs=src, formula="1 + 적분 v ÷ (g t_push)", nd=2)
    a1 = jj[jj["runner"] == "A"].iloc[0]
    src = (f"A 점프 1: 밀기 평균 지면반력 {a1.mean_grf_push_bw:.4f} BW, 밀기 시간 {a1.pushoff_time_s:.4f} s, 체공 v "
           f"{a1.takeoff_v_flight_ms:.4f} m/s (results/jumps.csv), 체중 70 kg")
    sh.add("주의: A 점프 1의 (평균 지면반력 − 체중) × 밀기 시간 (N·s)", (a1.mean_grf_push_bw - 1) * mg["A"] * a1.pushoff_time_s,
           None, "160", inputs=src, formula="(F̄ − mg) × t_push = m × 적분 v")
    sh.add("주의: A 점프 1의 J = m × 체공 v (N·s)", 70.0 * a1.takeoff_v_flight_ms, a1.impulse_ns, "181", inputs=src,
           formula="m × 체공 v")
    vj = t.val[(t.val["measure"] == "jump_flight") & (t.val["participant"] == "ALL")].iloc[0]
    longer = vj["bias"] / vj["mean_b"]
    sh.add("주의: 폰 체공이 영상보다 긴 만큼 높이가 커지는 크기 (%)", ((1 + longer) ** 2 - 1) * 100, None, "10",
           inputs=f"폰 − 영상 체공 +{longer * 100:.1f}% (HC-A14)", formula="((1 + 차 %)² − 1) × 100. h는 t_f²에 비례")

    sh.begin("HC-B6", kind, "9주차 p39 탄성력 F = kΔs, p51 탄성에너지 SE = ½kΔx². F_max 식은 Morin 외(2005), 교안 밖",
             "참고값", "F_max = m g (π ÷ 2)(t_f ÷ t_c + 1), Δy = F_max t_c² ÷ (m π²) − g t_c² ÷ 8, "
             "ΔL = L − √(L² − (v t_c ÷ 2)²) + Δy, k_vert = F_max ÷ Δy, k_leg = F_max ÷ ΔL, 탄성에너지 = ½ F_max Δy")
    shake = []
    for r in run.itertuples():
        key = (r.runner, r.ratio_pct)
        m, leg = float(body.loc[r.runner, "mass_kg"]), float(body.loc[r.runner, "leg_length_m"])
        tf, tc, v = float(r.flight_time_median_s), float(r.contact_time_s), float(r.v_ms)
        s = spring(m, leg, v, tc, tf)
        src = (f"t_c {tc:.4f} s, t_f {tf:.4f} s, v {v:.3f} m/s (results/exp2_summary.csv), 체중 {m:.0f} kg, 다리 {leg:.2f} m. "
               f"접촉 {int(r.n_contacts_video)}개")
        name, rf = f"{r.runner} {r.ratio_pct}%", ref6[key]
        sh.add(f"{name} F_max (N)", s.fmax, None, rf[0], inputs=src)
        sh.add(f"{name} F_max (BW)", s.bw, r.fmax_bw, rf[1], inputs=src)
        sh.add(f"{name} 몸 중심 하강 Δy (cm)", s.dy * 100, r.delta_y_m * 100, rf[2], inputs=src)
        sh.add(f"{name} 다리 압축 ΔL (cm)", s.dl * 100, r.delta_l_m * 100, rf[3], inputs=src)
        sh.add(f"{name} k_vert (kN/m)", s.kvert, r.kvert_kn_m, rf[4], inputs=src)
        sh.add(f"{name} k_leg (kN/m)", s.kleg, r.kleg_kn_m, rf[5], inputs=src)
        sh.add(f"{name} 탄성에너지 (J)", s.energy, r.elastic_energy_j, rf[6], inputs=src)
        for dtc in (-0.010, 0.010):
            tc2 = tc + dtc
            tf2 = 60 / r.cadence_median_spm - tc2 if "tf_from_cadence" in str(r.flags) else tf
            shake.append(abs(spring(m, leg, v, tc2, tf2).fmax / s.fmax - 1) * 100)
    sh.add("주의: 접촉이 10 ms 달라질 때 F_max 변화의 최대 크기 (%)", max(shake), None, "4",
           inputs="세 단계의 t_c를 ±10 ms 바꿔 F_max를 다시 낸다(체공을 걸음 간격에서 뺀 단계는 체공도 같이 바뀐다)",
           formula="|F_max' ÷ F_max − 1| × 100의 최댓값", nd=1)

    sh.begin("HC-B7", kind, "12주차 p21 피겨, p22 질량 분포, p27 회전반경, p28 무릎 굽힘 → I↓, p30 평행축, p44 예제 3. "
             "주기 식은 교안 밖", "실측(90° 아님)", "I = Σ m(k² + r²)(엉덩관절 기준, 평행축 정리), P = 2π√(I ÷ m g d)")
    bent = t.sw[t.sw["knee"] == "bent"].copy()
    fr = _fractions(params)
    bent["model"] = [segment_model(float(body.loc[r.runner, "mass_kg"]), float(body.loc[r.runner, "thigh_length_m"]),
                                   float(body.loc[r.runner, "shank_length_m"]), r.knee_deg, fr).P for r in bent.itertuples()]
    ref7 = {"A": ("11.27", "3.322", "0.445", "1.632", "72.6", "2.591", "−22.0", "2.279", "−31.4", "6.6", "0.932"),
            "B": ("9.982", "2.379", "0.398", "1.553", "66.5", "1.906", "−19.9", "1.593", "−33.0", "7.9", "0.871")}
    for p, rf in ref7.items():
        x = mod[p]
        src = (f"체중 {x.M:.0f} kg, 허벅지 {x.lt:.2f} m, 정강이 {x.ls:.2f} m ({src_body}). 분절 비율은 config/params.toml "
               "[pendulum] seg_*(Winter·Dempster, 교안 밖)")
        sh.add(f"{p} 두 분절 질량 m (kg)", x.s.m, None, rf[0], inputs=src, formula="(0.100 + 0.061) × 체중")
        sh.add(f"{p} 곧은 다리 I (kg·m²)", x.s.I, None, rf[1], inputs=src)
        sh.add(f"{p} 곧은 다리 질량중심 거리 d (m)", x.s.d, None, rf[2], inputs=src, formula="두 분절 질량중심의 가중 평균")
        sh.add(f"{p} 곧은 다리 모델 주기 (s)", x.s.P, t.p3.loc[p, "period_model_seg_s"], rf[3], inputs=src)
        sh.add(f"{p} 잰 무릎 각 (°)", None, x.knee, rf[4], formula="읽은 값(영상 마커, HC-B10)",
               inputs="results/exp3_summary.csv: knee_deg")
        sh.add(f"{p} 잰 각에서 I (kg·m²)", x.k.I, None, rf[5], inputs=src + f", 무릎 각 {x.knee:.1f}°")
        sh.add(f"{p} 잰 각에서 I 변화 (%)", (x.k.I / x.s.I - 1) * 100, None, rf[6], inputs=src, formula="(I ÷ 곧은 다리 I − 1) × 100")
        sh.add(f"{p} 90°에서 I (kg·m²)", x.r.I, None, rf[7], inputs=src + ", 무릎 각 90°")
        sh.add(f"{p} 90°에서 I 변화 (%)", (x.r.I / x.s.I - 1) * 100, None, rf[8], inputs=src, formula="(I ÷ 곧은 다리 I − 1) × 100")
        ub = _used(bent)
        sh.add(f"{p} 굽힌 다리 모델 주기 (s)", float(ub[ub["runner"] == p]["model"].median()),
               t.p3.loc[p, "period_model_seg_bent_s"], inputs=src + ". 쓴 굽힌 시행의 무릎 각 (results/exp3_swings.csv: knee_deg)",
               formula="시행마다 그 시행의 무릎 각으로 모델 주기를 내고 중앙값을 쓴다", nd=3)
        sh.add(f"{p} 모델 주기가 실측보다 긴 크기 (%)", (x.s.P / period[p] - 1) * 100, None, rf[9],
               inputs=f"곧은 다리 모델 주기 {x.s.P:.4f} s, 실측 P {period[p]:.4f} s (HC-A10)", formula="(모델 ÷ 실측 − 1) × 100")
        sh.add(f"{p} 실측 P_K ÷ P", float(t.p3.loc[p, "swing_period_bent_s"]) / period[p], t.p3.loc[p, "period_ratio_bent"],
               rf[10], inputs="HC-A10의 P, P_K", formula="P_K ÷ P")
        ratio_ref = {"A": ("0.937", "0.906"), "B": ("0.945", "0.902")}[p]
        sh.add(f"{p} 모델의 굽힌 ÷ 곧은 주기 비, 잰 각", float(ub[ub["runner"] == p]["model"].median()) / x.s.P,
               t.p3.loc[p, "period_ratio_model"], ratio_ref[0], inputs=src, formula="굽힌 다리 모델 주기 ÷ 곧은 다리 모델 주기")
        sh.add(f"{p} 모델의 굽힌 ÷ 곧은 주기 비, 90°", x.r.P / x.s.P, t.p3.loc[p, "period_ratio_model_nominal"], ratio_ref[1],
               inputs=src, formula="무릎 90° 모델 주기 ÷ 곧은 다리 모델 주기")

    sh.begin("HC-B8", kind, "12주차 p42 예제 1, p43 예제 2; 모멘트 팔 p13·p16, p18, p53", "계산만",
             "τ = m g d sin θ, α = τ ÷ I (잰 진폭 평균). 실측 주기로는 α = (2π ÷ P)² sin θ")
    for p, rf in (("A", ("15.5", "13.16", "3.96", "4.50")), ("B", ("25.3", "16.67", "7.01", "8.16"))):
        s = mod[p].s
        src = (f"곧은 다리 쓴 시행의 진폭 평균 {amp[p]:.2f}° (results/exp3_swings.csv: amp_deg), 모델 m {s.m:.3f} kg·d {s.d:.4f} m·"
               f"I {s.I:.4f} kg·m² (HC-B7), 실측 P {period[p]:.4f} s")
        sh.add(f"{p} 진폭 평균 (°)", amp[p], None, rf[0], inputs=src, formula="쓴 시행 진폭의 평균")
        sh.add(f"{p} 중력 토크 τ (N·m)", tau[p], None, rf[1], inputs=src, formula="m g d sin θ")
        sh.add(f"{p} 각가속도 α (rad/s²)", tau[p] / s.I, None, rf[2], inputs=src, formula="τ ÷ I")
        sh.add(f"{p} 실측 주기로 낸 α (rad/s²)", (2 * math.pi / period[p]) ** 2 * math.sin(math.radians(amp[p])), None,
               rf[3], inputs=src, formula="(2π ÷ P)² sin θ")

    sh.begin("HC-B9", kind, "10주차 p22 예제 9; 12주차 p69 각에너지, p70 각 일–에너지 정리", "실측(I·d는 모델)",
             "m g d (1 − cos θ) = ½ I ω² → 예측 ω = √(2 m g d (1 − cos θ) ÷ I)")
    ref9 = {"E3_A_1": ("1.071", "1.235", "1.15", "1.07"), "E3_A_3": ("1.005", "1.083", "1.08", "1.02"),
            "E3_B_1": ("1.755", "2.105", "1.20", "1.11"), "E3_B_2": ("1.794", "1.918", "1.07", "0.99")}
    for tid, rf in ref9.items():
        r = tr.loc[tid]
        s, th = mod[r.runner].s, math.radians(r.amp_deg)
        pred = math.sqrt(2 * s.m * G * s.d * (1 - math.cos(th)) / s.I)
        src = (f"진폭 {r.amp_deg:.2f}°, 자이로 최대 ω {r.omega_peak_rad_s:.4f} rad/s, 주기 {r.swing_period_s:.4f} s "
               f"(results/exp3_swings.csv: amp_deg, omega_peak_rad_s, swing_period_s), 모델 m·d·I (HC-B7)")
        sh.add(f"{tid} 예측 최대 각속도 (rad/s)", pred, r.omega_pred_rad_s, rf[0], inputs=src)
        sh.add(f"{tid} 잰 최대 각속도 (rad/s)", None, r.omega_peak_rad_s, rf[1], inputs=src, formula="읽은 값(자이로)")
        sh.add(f"{tid} 잰 ÷ 예측", r.omega_peak_rad_s / pred, None, rf[2], inputs=src, formula="잰 ω ÷ 예측 ω")
        sh.add(f"{tid} 잰 ÷ 실측 주기로 낸 예측", r.omega_peak_rad_s / (2 * (2 * math.pi / r.swing_period_s) * math.sin(th / 2)),
               None, rf[3], inputs=src, formula="예측 ω = 2 (2π ÷ P) sin(θ ÷ 2)")

    mk = t.markers
    pts = [((r.hip_x, r.hip_y), (r.knee_x, r.knee_y), (r.ankle_x, r.ankle_y)) for r in mk.itertuples()]
    mk = mk.assign(flex=[knee_cosine(*q)[1] for q in pts])
    fr0 = mk[(mk["trial_id"] == "E3_A_K_1") & (mk["event_no"] == 1)].iloc[0]
    q0 = ((fr0.hip_x, fr0.hip_y), (fr0.knee_x, fr0.knee_y), (fr0.ankle_x, fr0.ankle_y))
    src0 = (f"굽힌 진자 한 프레임(E3_A_K_1, 프레임 {int(fr0.frame_no)})의 픽셀 좌표: 엉덩 ({q0[0][0]:.1f}, {q0[0][1]:.1f}), "
            f"무릎 ({q0[1][0]:.1f}, {q0[1][1]:.1f}), 발목 ({q0[2][0]:.1f}, {q0[2][1]:.1f}) (data/video_markers.csv)")
    sh.begin("HC-B10", kind, "11주차 p25–28 예제 1 코사인 법칙; 절대각 풀이 p20–21", "실측(장면이 착지 → 진자로 바뀜)",
             "a² = b² + c² − 2bc cos θ (a 엉덩–발목, b 엉덩–무릎, c 무릎–발목), 굽힘 = 180° − θ")
    inner, flex = knee_cosine(*q0)
    sh.add("한 프레임의 무릎 안쪽 각 (°)", inner, None, "108.33", inputs=src0)
    sh.add("한 프레임의 무릎 굽힘 각 (°)", flex, None, "71.67", inputs=src0)
    for tid, ref in (("E3_A_K_1", "74.8"), ("E3_A_K_2", "70.4"), ("E3_B_K_1", "71.3"), ("E3_B_K_2", "68.6"),
                     ("E3_B_K_3", "59.6")):
        f = mk[mk["trial_id"] == tid]["flex"]
        sh.add(f"{tid} 시행 평균 무릎 굽힘 각 (°)", f.mean(), tr.loc[tid, "knee_deg"], ref,
               inputs=f"마커 {len(f)}프레임의 좌표 (data/video_markers.csv)", formula="프레임마다 코사인 법칙으로 낸 굽힘 각의 평균")

    sh.begin("HC-B11", kind, "5주차 p6–8 보폭, p47 적분; 6주차 p11 적분·미분. 보폭 식은 Zijlstra & Hof(2003), 교안 밖",
             "실측(A만)", "역진자 보폭 = 2√(2 l h − h²), GPS 보폭 = v ÷ (케이던스 ÷ 60)")
    sa = t.segs[(t.segs["participant"] == "A") & t.segs["step_length_zh_m"].notna() & t.segs["step_length_m"].notna()]
    leg_a = float(body.loc["A", "leg_length_m"])
    zh = 2 * (2 * leg_a * sa["com_vertical_m"] - sa["com_vertical_m"] ** 2) ** 0.5
    gps = sa["speed_ms"] / (sa["cadence_median_spm"] / 60)
    ratio = zh / gps
    ex = (("4.95", "0.621", "0.752", "0.83"), ("5.15", "0.634", "0.809", "0.78"), ("5.41", "0.649", "0.743", "0.87"))
    for k, (i, rf) in enumerate(zip((0, len(sa) // 2, len(sa) - 1), ex), 1):
        r = sa.iloc[i]
        src = (f"A 곡 구간 {r.walk_id} {int(r.song_idx)}번 곡: 몸 중심 수직 변위 h {r.com_vertical_m * 100:.2f} cm, v {r.speed_ms:.3f} m/s, "
               f"케이던스 {r.cadence_median_spm:.2f} (results/segments.csv: com_vertical_m, speed_ms, cadence_median_spm), 다리 {leg_a:.2f} m")
        sh.add(f"구간 예 {k}: h (cm)", None, r.com_vertical_m * 100, rf[0], inputs=src, formula="읽은 값")
        sh.add(f"구간 예 {k}: 역진자 보폭 (m)", zh.iloc[i], r.step_length_zh_m, rf[1], inputs=src, formula="2√(2 l h − h²)")
        sh.add(f"구간 예 {k}: GPS 보폭 (m)", gps.iloc[i], r.step_length_m, rf[2], inputs=src, formula="v ÷ (케이던스 ÷ 60)")
        sh.add(f"구간 예 {k}: 역진자 ÷ GPS", ratio.iloc[i], None, rf[3], inputs=src, formula="역진자 보폭 ÷ GPS 보폭")
    src = f"A의 곡 구간 {len(sa)}개 (results/segments.csv)"
    sh.add("역진자 ÷ GPS, 구간 평균", ratio.mean(), None, "0.83", inputs=src, formula="구간별 비의 평균")
    sh.add("역진자 ÷ GPS, 최소", ratio.min(), None, "0.78", inputs=src, formula="구간별 비의 최소")
    sh.add("역진자 ÷ GPS, 최대", ratio.max(), None, "0.92", inputs=src, formula="구간별 비의 최대")

    sh.begin("HC-B12", kind, "7주차 p3, p7, p9 공기저항 무시", "계산만", "F = ½ ρ C_d A v², ρ 1.2 kg/m³, C_d A 0.5 m²(크게 잡은 가정)")
    for p, r, f_ref, pct_ref in (("A", "S", "0.48", "0.07"), ("A", "180", "3.50", "0.51"), ("B", "S", "0.68", "0.11"),
                                 ("B", "195", "4.54", "0.75")):
        v = float(_stage(t, p, r)["v_ms"])
        drag = 0.5 * 1.2 * 0.5 * v ** 2
        name = "무음" if r == "S" else f"{r}%"
        src = f"{p} {name} 단계 v {v:.3f} m/s (results/exp2_summary.csv: v_ms), 체중 {mg[p]:.1f} N"
        sh.add(f"{p} {name} 공기저항 (N)", drag, None, f_ref, inputs=src)
        sh.add(f"{p} {name} 공기저항 ÷ 체중 (%)", drag / mg[p] * 100, None, pct_ref, inputs=src, formula="F ÷ (m g) × 100")

    sh.begin("HC-B13", kind, "6주차 p27 예제 8", "계산만", "정지에서 5 m 안에 v에 이른다고 보면 a = v² ÷ (2 × 5), t = v ÷ a")
    for p, r, a_ref, t_ref in (("A", "150", "0.390", "5.06"), ("A", "180", "1.168", "2.93"), ("B", "150", "0.503", "4.46"),
                               ("B", "195", "1.515", "2.57")):
        v = float(_stage(t, p, r)["v_ms"])
        src = f"{p} {r}% 단계 v {v:.3f} m/s (results/exp2_summary.csv: v_ms. 가운데 30 m 평균 속도). 가속 구간 5 m는 재지 않았다"
        sh.add(f"{p} {r}% 가속도 (m/s²)", v ** 2 / 10, None, a_ref, inputs=src, formula="v² ÷ (2 × 5)")
        sh.add(f"{p} {r}% 걸리는 시간 (s)", 10 / v, None, t_ref, inputs=src, formula="v ÷ a = 10 ÷ v")

    sh.begin("HC-B14", kind, "2주차 p16–17 거리·변위, 속력·속도", "실측",
             "속력 = 경로 길이 ÷ 시간. 점프 체공에서 평균 속력 = 2h ÷ t_f, 평균 속도 = 0(변위 0)")
    for p, s_ref, lo, hi in (("A", "1.247", "1.304", "1.431"), ("C", "1.703", "1.427", "1.533")):
        vs = [x.v for (q, cond), x in tab.items() if q == p and cond != SILENT]
        src = "HC-A12의 속도 표(GPS 경로 거리 ÷ 시간)"
        sh.add(f"실험 1 {p} 무음 속력 (m/s)", tab[(p, SILENT)].v, None, s_ref, inputs=src, formula="속도 표의 값")
        sh.add(f"실험 1 {p} 음악 조건 속력, 최소 (m/s)", min(vs), None, lo, inputs=src, formula="P1–P4 중 최소")
        sh.add(f"실험 1 {p} 음악 조건 속력, 최대 (m/s)", max(vs), None, hi, inputs=src, formula="P1–P4 중 최대")
    ref16 = {"A": ("1.16", "1.29", "2.31", "2.59"), "B": ("1.23", "1.30", "2.45", "2.60")}
    for p, rf in ref16.items():
        d = jj[jj["runner"] == p]
        sp = 2 * d["height_m"] / d["flight_time_s"]
        src = f"{p} 점프 3회의 높이와 체공 (results/jumps.csv: height_m, flight_time_s)"
        sh.add(f"{p} 점프 체공 평균 속력, 최소 (m/s)", sp.min(), None, rf[0], inputs=src, formula="2h ÷ t_f")
        sh.add(f"{p} 점프 체공 평균 속력, 최대 (m/s)", sp.max(), None, rf[1], inputs=src, formula="2h ÷ t_f")

    sh.begin("HC-B15", kind, "5주차 p29 예제 3; 방향 기준 p26", "참고값", "크기 = √(v² + v_y²), 방향 = arctan(v_y ÷ v)")
    for r in run.itertuples():
        v, vy = float(r.v_ms), G * float(r.flight_time_median_s) / 2
        rf, name = ref15[(r.runner, r.ratio_pct)], f"{r.runner} {r.ratio_pct}%"
        src = f"수평 v {v:.3f} m/s(30 m 평균), 수직 v_y {vy:.3f} m/s (HC-B4)"
        sh.add(f"{name} 이륙 속도의 크기 (m/s)", math.hypot(v, vy), None, rf[0], inputs=src)
        sh.add(f"{name} 이륙 속도의 방향 (°)", math.degrees(math.atan2(vy, v)), None, rf[1], inputs=src)

    sh.begin("HC-B16", kind, "5주차 p38 평균 vs 순간 속도", "실측",
             "이륙 순간 v = g t_f ÷ 2, 꼭대기 순간 v = 0, 올라가는 동안 평균 = h ÷ (t_f ÷ 2) = v ÷ 2")
    for p, rf in ref16.items():
        d = jj[jj["runner"] == p]
        up = d["height_m"] / (d["flight_time_s"] / 2)
        v0 = G * d["flight_time_s"] / 2
        src = f"{p} 점프 3회 (results/jumps.csv: flight_time_s, height_m)"
        sh.add(f"{p} 이륙 순간 속도, 최소 (m/s)", v0.min(), d["takeoff_v_flight_ms"].min(), rf[2], inputs=src, formula="g t_f ÷ 2")
        sh.add(f"{p} 이륙 순간 속도, 최대 (m/s)", v0.max(), d["takeoff_v_flight_ms"].max(), rf[3], inputs=src, formula="g t_f ÷ 2")
        sh.add(f"{p} 올라가는 동안 평균 속도, 최소 (m/s)", up.min(), None, rf[0], inputs=src, formula="h ÷ (t_f ÷ 2)")
        sh.add(f"{p} 올라가는 동안 평균 속도, 최대 (m/s)", up.max(), None, rf[1], inputs=src, formula="h ÷ (t_f ÷ 2)")

    sh.begin("HC-B17", kind, "6주차 p20 예제 1, p25 예제 6, p29 예제 10(프레임 ÷ fps)", "실측",
             "t30 = 화면에서 읽은 통과 시간 ÷ k(시차 보정, k = 1 − d ÷ D), v = 30 ÷ t30, 단계 v = 두 시행 v의 평균")
    vx = t.vexp2.set_index("trial_id")
    fps = t.trials.set_index("trial_id")["video_fps"]
    cite = {("A", "S"): ("1.259", "23.83", "1,430"), ("A", "180"): ("3.418", "8.78", "527"),
            ("B", "S"): ("1.510", "19.87", "1,192"), ("B", "195"): ("3.892", "7.71", "462")}
    for r in t.st2.itertuples():
        q = vx.loc[r.trial_id]
        src = (f"화면상 통과 시각 {q.t_in_app_s:.3f}–{q.t_out_app_s:.3f} s, 차 {q.dt_app_s:.3f} s, k {q.k:.2f} "
               f"(data/video_exp2.csv: t_in_app_s, t_out_app_s, dt_app_s, k), 영상 {fps[r.trial_id]:.2f} fps")
        t30 = round(q.dt_app_s / q.k, 2)
        sh.add(f"{r.trial_id} 통과 시간 t30 (s)", t30, r.t30_s, inputs=src, formula="화면상 시간 ÷ k, 0.01 s로 반올림", nd=2)
        sh.add(f"{r.trial_id} v (m/s)", 30 / t30, r.v_ms, inputs=src, formula="30 ÷ t30", nd=3)
        if (r.runner, r.ratio_pct) in cite:
            sh.add(f"{r.trial_id} 화면상 통과 시간의 프레임 수", q.dt_app_s * fps[r.trial_id], None, inputs=src,
                   formula="화면상 시간 × fps", nd=0)
    for r in t.s2.itertuples():
        tr2 = t.st2[(t.st2["runner"] == r.runner) & (t.st2["ratio_pct"] == r.ratio_pct)]
        name = "무음" if r.ratio_pct == "S" else f"{r.ratio_pct}%"
        rf = cite.get((r.runner, r.ratio_pct), ("", "", ""))
        src = f"두 시행의 v {lst(tr2['v_ms'], 3)} m/s (t30 {lst(tr2['t30_s'], 2)} s)"
        sh.add(f"{r.runner} {name} 단계 v (m/s)", (30 / tr2["t30_s"]).mean(), r.v_ms, rf[0], inputs=src, formula="두 시행 v의 평균",
               nd=3)
        if rf[1]:
            sh.add(f"{r.runner} {name} 30 ÷ 단계 v (s)", 30 / r.v_ms, None, rf[1], inputs=src,
                   formula="30 ÷ 단계 v. 검산 기준의 통과 시간은 이렇게 v에서 거꾸로 낸 값이다")
            sh.add(f"{r.runner} {name} 30 ÷ 단계 v × 60 (프레임)", 30 / r.v_ms * 60, None, rf[2], inputs=src,
                   formula="거꾸로 낸 통과 시간 × 60. 실제 프레임 수는 시행별 줄에 있다")
    sl_ref = {"A": "0.76 0.75 0.76 0.81 0.84 1.01 1.24".split(), "B": "0.77 0.82 0.85 0.83 0.89 0.95 1.07 1.23".split()}
    for p, refs_ in sl_ref.items():
        for r, ref in zip(t.s2[t.s2["runner"] == p].itertuples(), refs_):
            name = "무음" if r.ratio_pct == "S" else f"{r.ratio_pct}%"
            sh.add(f"{p} {name} 단계 보폭 (m)", r.v_ms / (r.cadence_median_spm / 60), None, ref,
                   inputs=f"단계 v {r.v_ms:.3f} m/s, 센서 케이던스 {r.cadence_median_spm:.2f} 걸음/분 (results/exp2_summary.csv: v_ms, "
                          "cadence_median_spm)", formula="보폭 = v ÷ (케이던스 ÷ 60)")
        sh.add(f"{p} 실험 2 시행 수", int((t.st2["runner"] == p).sum()), None, {"A": "14", "B": "16"}[p],
               inputs="results/exp2_stages.csv", formula="센다")

    sh.begin("HC-B18", kind, "9주차 p46–49 일·파워, p48 양의 일, p52 일–에너지 정리; 10주차 p21 예제 8, p23 예제 10, p24 예제 11",
             "실측", "밀기 거리 d = 적분 v × t_push ÷ 2, W = 평균 지면반력 × d, P = W ÷ t_push (밀 때 힘이 일정하다고 본 근사)")
    dist = jj["takeoff_v_int_ms"] * jj["pushoff_time_s"] / 2
    force = jj["mean_grf_push_bw"] * jj["runner"].map(mg)
    work = force * dist
    power = work / jj["pushoff_time_s"]
    alt = 0.5 * jj["runner"].map(lambda p: mg[p] / G) * jj["takeoff_v_int_ms"] ** 2 + jj["runner"].map(mg) * dist
    for p, rf in (("A", ("385", "438", "1,077", "1,351")), ("B", ("352", "408", "1,006", "1,282"))):
        i = jj.index[jj["runner"] == p]
        src = (f"{p} 점프 3회: 적분 v {lst(jj.loc[i, 'takeoff_v_int_ms'], 3)} m/s, 밀기 시간 {lst(jj.loc[i, 'pushoff_time_s'], 3)} s, "
               f"밀기 평균 지면반력 {lst(jj.loc[i, 'mean_grf_push_bw'], 2)} BW (results/jumps.csv), 체중 {mg[p]:.1f} N")
        sh.add(f"{p} 밀기 일, 최소 (J)", work[i].min(), None, rf[0], inputs=src)
        sh.add(f"{p} 밀기 일, 최대 (J)", work[i].max(), None, rf[1], inputs=src)
        sh.add(f"{p} 밀기 파워, 최소 (W)", power[i].min(), None, rf[2], inputs=src)
        sh.add(f"{p} 밀기 파워, 최대 (W)", power[i].max(), None, rf[3], inputs=src)
    sh.add("일–에너지 정리로 낸 값과의 최대 차 (J)", float((work - alt).abs().max()), None, nd=6,
           inputs="점프 6회", formula="|F̄ d − (½ m 적분 v² + m g d)|의 최댓값. 0이어야 한다")

    sh.begin("HC-B19", kind, "11주차 p18–19 절대각, p20–22 계산·사분면 보정, p30 분절각 vs 관절각, p31, p33 예제 3", "실측",
             "절대각 = arctan(Δy ÷ Δx)(오른쪽 수평에서 반시계, 아래 끝점 기준, 영상 y축은 위로 뒤집음), 무릎 = 허벅지 − 정강이")
    thigh, shank = absolute_angles(*q0, image_y_down=True)
    sh.add("한 프레임의 허벅지 절대각 (°)", thigh, None, "93.96", inputs=src0)
    sh.add("한 프레임의 정강이 절대각 (°)", shank, None, "22.29", inputs=src0)
    sh.add("한 프레임의 무릎 각 = 허벅지 − 정강이 (°)", thigh - shank, None, "71.67", inputs=src0)

    sh.begin("HC-B20", kind, "11주차 p40 예제 5, p41 예제 6; 라디안·도 p12·p16", "실측",
             "반 주기 동안 Δθ = 2 × 진폭, t = P ÷ 2 → 평균 각속도 = 2 × 진폭 ÷ (P ÷ 2)")
    ref20 = dict(E3_A_1=("42.3", "0.74", "1.67"), E3_A_3=("38.7", "0.68", "1.60"), E3_A_K_1=("55.9", "", ""),
                 E3_A_K_2=("46.5", "", ""), E3_B_1=("69.7", "1.22", "1.73"), E3_B_2=("71.1", "1.24", "1.55"),
                 E3_B_K_4=("42.1", "", ""), E3_B_K_6=("54.2", "", ""))
    for r in good.itertuples():
        rf = ref20[r.trial_id]
        w = 2 * r.amp_deg / (r.swing_period_s / 2)
        src = (f"진폭 {r.amp_deg:.2f}°, 주기 {r.swing_period_s:.4f} s, 자이로 최대 ω {r.omega_peak_rad_s:.4f} rad/s "
               "(results/exp3_swings.csv: amp_deg, swing_period_s, omega_peak_rad_s)")
        sh.add(f"{r.trial_id} 반 주기 평균 각속도 (°/s)", w, None, rf[0], inputs=src)
        if rf[1]:
            sh.add(f"{r.trial_id} 반 주기 평균 각속도 (rad/s)", math.radians(w), None, rf[1], inputs=src, formula="°/s × π ÷ 180")
            sh.add(f"{r.trial_id} 자이로 최대 ÷ 평균", r.omega_peak_rad_s / math.radians(w), None, rf[2], inputs=src,
                   formula="최대 ω ÷ 평균 ω. 사인 운동이면 π ÷ 2 = 1.57")

    # ---- 연결표(5장)에만 있는 값. id는 짝 번호다
    def pair(no, lecture, status, formula=""):
        sh.begin(f"#{no}", kind, lecture, status, formula)

    pair(4, "3주차 p27 뼈에 걸리는 하중, p25 점탄성", "실측(하중 크기만)", "읽은 값: 단계 충격의 범위")
    for gait, name, lo, hi in (("walk", "걷기", "1.52", "1.91"), ("run", "뛰기", "2.70", "3.78")):
        d = t.s2[t.s2["gait_video"] == gait]["impact_g"]
        src = f"영상 판정이 {name}인 단계 {len(d)}개의 충격 (results/exp2_summary.csv: impact_g, gait_video)"
        sh.add(f"{name} 단계 충격, 최소 (BW)", None, d.min(), lo, inputs=src)
        sh.add(f"{name} 단계 충격, 최대 (BW)", None, d.max(), hi, inputs=src)

    pair(8, "5주차 p6–8 보·보폭·케이던스", "실측", "한 걸음 주기(같은 발이 다시 닿을 때까지) = 120 ÷ PC")
    for p, ref in (("A", "1.20"), ("B", "1.22"), ("C", "1.01")):
        sh.add(f"{p} 한 걸음 주기 (s)", 120 / base.loc[p, "pc_spm"], None, ref, inputs=f"PC {base.loc[p, 'pc_spm']:.2f} 걸음/분 (HC-A1)")

    pair(12, "5·9주차 위치·운동에너지(9주차 p50–53)", "계산만", "ΔPE = m g h")
    h0 = float(sa.iloc[0]["com_vertical_m"])
    sh.add("A 몸 중심이 한 걸음에 오르내리는 위치에너지 (J)", 70.0 * G * h0, None, "34.0",
           inputs=f"A 체중 70 kg, 몸 중심 수직 변위 h {h0 * 100:.2f} cm (HC-B11 구간 예 1). ΔKE는 값이 없다")

    pair(19, "7주차 p15–17 위로 던지기", "실측", "올라가는 시간 = v ÷ g, 높이 = g t_f² ÷ 8")
    hts = jj["height_m"] * 100
    sh.add("점프 높이, 최소 (cm)", None, hts.min(), "27.2", inputs="점프 6회 (results/jumps.csv: height_m)", formula="읽은 값")
    sh.add("점프 높이, 최대 (cm)", None, hts.max(), "34.3", inputs="점프 6회 (results/jumps.csv: height_m)", formula="읽은 값")
    sh.add("A 점프 1 올라가는 시간 (s)", a1.takeoff_v_flight_ms / G, None, "0.264",
           inputs=f"A 점프 1 체공 v {a1.takeoff_v_flight_ms:.3f} m/s (HC-B5)", formula="v ÷ g = t_f ÷ 2")

    pair(31, "11주차 p36–41 각속도; 라디안·도 p12, p16", "실측", "읽은 값: 자이로 최대 각속도")
    w = good[good["knee"] == "straight"]["omega_peak_rad_s"]
    sh.add("곧은 다리 쓴 시행의 최대 각속도, 최소 (rad/s)", None, w.min(), "1.08", inputs="results/exp3_swings.csv: omega_peak_rad_s")
    sh.add("곧은 다리 쓴 시행의 최대 각속도, 최대 (rad/s)", None, w.max(), "2.11", inputs="results/exp3_swings.csv: omega_peak_rad_s")

    pair(32, "11주차 p50–52 v = rω(예제 1·2), p58 예제 1", "계산만", "v = r ω, r = 허벅지 + 정강이 길이")
    for p, tid, w_ref, r_ref, v_ref in (("A", "E3_A_1", "1.24", "0.92", "1.14"), ("B", "E3_B_1", "2.11", "0.84", "1.77")):
        om, rr = float(tr.loc[tid, "omega_peak_rad_s"]), mod[p].lt + mod[p].ls
        src = f"{tid} 자이로 최대 ω {om:.4f} rad/s, 허벅지 {mod[p].lt:.2f} m + 정강이 {mod[p].ls:.2f} m"
        sh.add(f"{p} 진자 최대 각속도 (rad/s)", None, om, w_ref, inputs=src, formula="읽은 값")
        sh.add(f"{p} 허벅지 + 정강이 (m)", rr, None, r_ref, inputs=src, formula="더한다")
        sh.add(f"{p} 진자 발끝 속도 (m/s)", rr * om, None, v_ref, inputs=src)

    pair(40, "3-2주차 p31 수축 유형(동심성·원심성)", "실측(몸 전체 값)", "밀기 동안 몸 중심이 오른 거리 d = 적분 v × t_push ÷ 2")
    sh.add("점프 밀기에서 몸 중심이 오른 거리, 최소 (m)", dist.min(), None, "0.32", inputs="점프 6회 (HC-B18)")
    sh.add("점프 밀기에서 몸 중심이 오른 거리, 최대 (m)", dist.max(), None, "0.39", inputs="점프 6회 (HC-B18)")
    for p, lo, hi in (("A", "0.324", "0.357"), ("B", "0.288", "0.372")):
        d = jj[jj["runner"] == p]["pushoff_time_s"]
        sh.add(f"{p} 밀기 시간, 최소 (s)", None, d.min(), lo, inputs="results/jumps.csv: pushoff_time_s", formula="읽은 값")
        sh.add(f"{p} 밀기 시간, 최대 (s)", None, d.max(), hi, inputs="results/jumps.csv: pushoff_time_s", formula="읽은 값")

    pair(41, "4주차 p34 자료 수집 기법; 5주차 p9 운동학 자료 수집", "실측(방법)", "한 프레임 = 1 ÷ fps")
    ta, tb = 30 / float(_stage(t, "A", "S")["v_ms"]), 30 / float(_stage(t, "A", "180")["v_ms"])
    sh.add("240 fps 한 프레임 (ms)", 1000 / 240, None, "4.17", inputs="슬로모션 240 fps")
    sh.add("240 fps 한 프레임이 점프 높이에서 차지하는 크기 (cm)", G * 0.5 * (1 / 240) / 4 * 100, None, "0.51",
           inputs="t_f 약 0.5 s", formula="dh = g t_f dt ÷ 4")
    fm = float(fps["E2_A_S_1"])
    src = f"메인 영상 {fm:.2f} fps (data/exp2_trials.csv: video_fps). 검산 기준값은 60 fps로 낸 값"
    sh.add("메인 영상 한 프레임 (ms)", 1000 / fm, None, "16.7", inputs=src)
    sh.add("메인 영상 한 프레임 ÷ A 무음 통과 시간 (%)", 1 / fm / ta * 100, None, "0.07",
           inputs=f"{src}, A 무음 30 ÷ 단계 v = {ta:.2f} s")
    sh.add("메인 영상 한 프레임 ÷ A 180% 통과 시간 (%)", 1 / fm / tb * 100, None, "0.19",
           inputs=f"{src}, A 180% 30 ÷ 단계 v = {tb:.2f} s")

    pair(42, "5주차 p44 평균 vs 순간 가속도", "실측", "순간 최대 = (충격 − 1) × g, 한 걸음 평균 = (회차 평균 수직 가속도 − 1) × g")
    for p, ref in (("A", "+5.89"), ("B", "+5.69")):
        sh.add(f"{p} 발 디딤 순간 최대 가속도 (m/s²)", (si[p] - 1) * G, None, ref, nd=2,
               inputs=f"무음 걷기 충격 {si[p]:.4f} BW (results/participants.csv: silent_impact_g)")
    for p, lo, hi in (("A", "+0.014", "+0.066"), ("B", "+0.000", "+0.002"), ("C", "+0.068", "+0.077")):
        d = okw[okw["participant"] == p]["mean_av_g"]
        src = f"회차 평균 수직 가속도 {d.min():.4f}–{d.max():.4f} g (results/walks.csv: mean_av_g)"
        sh.add(f"{p} 한 걸음 평균 가속도, 최소 (m/s²)", (d.min() - 1) * G, None, lo, inputs=src)
        sh.add(f"{p} 한 걸음 평균 가속도, 최대 (m/s²)", (d.max() - 1) * G, None, hi, inputs=src)

    pair(44, "6주차 p23 예제 4 평균 가속도 a = Δv ÷ Δt", "실측", "밀기 평균 가속도 = 적분 v ÷ t_push = (평균 지면반력 − 1) × g")
    for r, ref in zip(jj.itertuples(), ("7.06", "5.60", "6.08", "7.78", "7.51", "5.65")):
        sh.add(f"{r.runner} 점프 {r.jump_no} 밀기 평균 가속도 (m/s²)", r.takeoff_v_int_ms / r.pushoff_time_s,
               (r.mean_grf_push_bw - 1) * G, ref,
               inputs=f"적분 v {r.takeoff_v_int_ms:.4f} m/s, 밀기 시간 {r.pushoff_time_s:.4f} s (results/jumps.csv). "
                      "코드 값은 mean_grf_push_bw에서 (값 − 1) × g로 낸 것")

    pair(45, "6주차 p11 적분·미분", "실측", "읽은 값: 가속도를 적분해 낸 이륙 속도")
    for r, ref in zip(jj.itertuples(), ("2.288", "1.998", "2.093", "2.242", "2.388", "2.100")):
        sh.add(f"{r.runner} 점프 {r.jump_no} 적분 v (m/s)", None, r.takeoff_v_int_ms, ref, inputs="results/jumps.csv: takeoff_v_int_ms")

    pair(46, "9주차 p28 무게 W = mg", "실측", "W = m g")
    for p, ref in (("A", "686.7"), ("B", "608.2")):
        sh.add(f"{p} 체중 (N)", mg[p], None, ref, inputs=f"질량 {body.loc[p, 'mass_kg']:.0f} kg (data/participants.csv: mass_kg)")

    pair(47, "10주차 p5–7 자유물체도, p12 예제 2", "실측", "위로 지면반력, 아래로 체중 → 알짜 힘 = 지면반력 − 체중, a = 알짜 힘 ÷ m")
    src = f"A 점프 1 밀기 평균 지면반력 {a1.mean_grf_push_bw:.4f} BW (results/jumps.csv: mean_grf_push_bw), 체중 {mg['A']:.1f} N"
    sh.add("A 점프 1 밀기: 위로 (N)", a1.mean_grf_push_bw * mg["A"], None, "1,181", inputs=src)
    sh.add("A 아래로(체중) (N)", mg["A"], None, "687", inputs=src)
    sh.add("A 점프 1 밀기: 알짜 힘 (N)", (a1.mean_grf_push_bw - 1) * mg["A"], None, "494", inputs=src)
    sh.add("A 점프 1 밀기: 가속도 (m/s²)", (a1.mean_grf_push_bw - 1) * G, None, "7.06", inputs=src)
    src = f"A 무음 걷기 충격 {si['A']:.4f} BW (results/participants.csv: silent_impact_g), 체중 {mg['A']:.1f} N"
    sh.add("A 발 디딤: 위로 (N)", si["A"] * mg["A"], None, "1,099", inputs=src)
    sh.add("A 발 디딤: 알짜 힘 (N)", (si["A"] - 1) * mg["A"], None, "412", inputs=src)
    sh.add("A 발 디딤: 가속도 (m/s²)", (si["A"] - 1) * G, None, "5.89", inputs=src)

    pair(48, "11주차 p35 각위치·각거리·각변위", "실측", "한 주기 각거리 = 4 × 진폭, 한 주기 각변위 = 0")
    pair50 = {}
    for tid, ref48, ref_v, ref_ac in (("E3_A_1", "64.0", "1.14", "1.40"), ("E3_A_3", "60.0", "1.00", "1.08"),
                                      ("E3_B_1", "100.0", "1.77", "3.72"), ("E3_B_2", "102.4", "1.61", "3.09")):
        r = tr.loc[tid]
        sh.add(f"{tid} 한 주기 각거리 (°)", 4 * r.amp_deg, None, ref48, inputs=f"진폭 {r.amp_deg:.2f}° (results/exp3_swings.csv: amp_deg)")
        pair50[tid] = (r, ref_v, ref_ac)

    pair(49, "11주차 p39 각가속도, p53 접선 가속도 a_T = rα", "계산만", "흔들림 끝에서 a_T = r α, α = (2π ÷ P)² sin θ, r = 허벅지 + 정강이")
    for p, ref in (("A", "4.14"), ("B", "6.85")):
        al, rr = (2 * math.pi / period[p]) ** 2 * math.sin(math.radians(amp[p])), mod[p].lt + mod[p].ls
        sh.add(f"{p} 발목의 접선 가속도 (m/s²)", rr * al, None, ref, inputs=f"α {al:.3f} rad/s² (HC-B8), r {rr:.2f} m")

    pair(50, "11주차 p54–55 구심 가속도 a_C = rω², p62 예제 5", "실측(자이로 ω, 테이프 길이)", "흔들림 바닥에서 v = r ω, a_C = r ω²")
    for tid, (r, ref_v, ref_ac) in pair50.items():
        rr = mod[r.runner].lt + mod[r.runner].ls
        src = f"자이로 최대 ω {r.omega_peak_rad_s:.4f} rad/s (results/exp3_swings.csv: omega_peak_rad_s), r {rr:.2f} m"
        sh.add(f"{tid} 발목 속도 (m/s)", rr * r.omega_peak_rad_s, None, ref_v, inputs=src, formula="r ω")
        sh.add(f"{tid} 발목 구심 가속도 (m/s²)", rr * r.omega_peak_rad_s ** 2, None, ref_ac, inputs=src, formula="r ω²")

    pair(51, "12주차 p13·p16 모멘트 팔, p53 몸에 작용하는 토크", "계산만", "r⊥ = d sin θ, τ = m g r⊥")
    for p, arm_ref, tau_ref in (("A", "0.119", "13.15"), ("B", "0.170", "16.66")):
        s = mod[p].s
        src = f"모델 d {s.d:.4f} m, m {s.m:.3f} kg (HC-B7), 진폭 평균 {amp[p]:.2f}°"
        sh.add(f"{p} 중력 토크의 모멘트 팔 (m)", s.d * math.sin(math.radians(amp[p])), None, arm_ref, inputs=src, formula="d sin θ")
        sh.add(f"{p} 중력 토크 (N·m)", tau[p], None, tau_ref, inputs=src, formula="m g r⊥. HC-B8의 τ와 같은 값")

    pair(52, "12주차 p45 예제 4 '질량이 늘면 I는?'", "계산만(모델 값)", "I = m k² → I 비 = 질량 비 × k² 비, k = √(I ÷ m)")
    sa_, sb_ = mod["A"].s, mod["B"].s
    src = f"A I {sa_.I:.4f} kg·m²·m {sa_.m:.3f} kg, B I {sb_.I:.4f}·m {sb_.m:.3f} (HC-B7)"
    sh.add("A ÷ B: I 비", sa_.I / sb_.I, None, "1.396", inputs=src)
    sh.add("A ÷ B: 질량 비", sa_.m / sb_.m, None, "1.129", inputs=src)
    sh.add("A ÷ B: k² 비", (sa_.I / sa_.m) / (sb_.I / sb_.m), None, "1.237", inputs=src)
    sh.add("A 회전반경 k (m)", math.sqrt(sa_.I / sa_.m), None, "0.543", inputs=src, formula="√(I ÷ m)")
    sh.add("B 회전반경 k (m)", math.sqrt(sb_.I / sb_.m), None, "0.488", inputs=src, formula="√(I ÷ m)")


# ---------------------------------------------------------------- 교안 예제 50개 (원본 입력 → 우리 풀이)
def lecture_examples(a1=None) -> list[SimpleNamespace]:
    """교안 예제의 원본 입력과 우리 풀이. a1은 A 점프 1의 줄(E29에 붙이는 우리 값). 없으면 그 값만 뺀다."""
    def cosd(x):
        return math.cos(math.radians(x))

    def sind(x):
        return math.sin(math.radians(x))

    def atand(y, x):
        return math.degrees(math.atan2(y, x))

    out = []

    def ex(no, cite, given, ask, answer, values, link, src):
        out.append(SimpleNamespace(no=no, cite=cite, given=given, ask=ask, answer=answer, values=values, link=link, src=src,
                                   figure="그림 읽기" in src))

    v = []
    for k, (mag, ang, rx, ry, unit) in enumerate(((240, 331, "209.9", "−116.4", "N"), (34, 210, "−29.4", "−17.0", "m/s"),
                                                  (15, 12, "14.67", "3.12", "m"), (20, 90, "0", "20", "m/s²")), 1):
        v += [(f"벡터 {k} x 성분 ({unit})", "크기 × cos(각)", mag * cosd(ang), rx),
              (f"벡터 {k} y 성분 ({unit})", "크기 × sin(각)", mag * sind(ang), ry)]
    ex(1, "5주차 p27 예제 1", "240 N at 331°, 34 m/s at 210°, 15 m at 12°, 20 m/s² at 90°", "x·y 성분",
       "({0}, {1}), ({2}, {3}), ({4}, {5}), ({6}, {7})", v, "#13", "새로")
    v = []
    for k, (x, y, rm, ra, unit) in enumerate(((345, 120, "365.3", "19.2", "N"), (8, 31, "32.0", "75.5", "m/s"),
                                              (-15, 12, "19.2", "141.3", "m/s²")), 1):
        v += [(f"합 {k}의 크기 ({unit})", "√(x² + y²)", math.hypot(x, y), rm), (f"합 {k}의 방향 (°)", "arctan(y ÷ x), 사분면 보정", atand(y, x), ra)]
    ex(2, "5주차 p28 예제 2", "(Fx 345, Fy 120 N), (vx 8, vy 31 m/s), (ax −15, ay 12 m/s²)", "합의 크기·방향",
       "{0} N, {1}° / {2} m/s, {3}° / {4} m/s², {5}°", v, "#13", "새로")
    ex(3, "5주차 p29 예제 3", "수평 11.3, 수직 3.5 m/s", "크기·방향", "{0} m/s, {1}°",
       [("크기 (m/s)", "√(11.3² + 3.5²)", math.hypot(11.3, 3.5), "11.83"), ("방향 (°)", "arctan(3.5 ÷ 11.3)", atand(3.5, 11.3), "17.2")],
       "#13, HC-B15", "v1")
    sx = 450 * cosd(20) + 25 * cosd(270) + 230 * cosd(70)
    sy = 450 * sind(20) + 25 * sind(270) + 230 * sind(70)
    ex(4, "5주차 p30 예제 4", "450 N at 20°, 25 N at 270°, 230 N at 70°", "합의 크기·방향", "{0} N, {1}°",
       [("합의 크기 (N)", "성분끼리 더한 뒤 √(x² + y²)", math.hypot(sx, sy), "608.8"), ("합의 방향 (°)", "arctan(y ÷ x)", atand(sy, sx), "34.5")],
       "#13", "새로")
    ex(5, "5주차 p34 예제 5", "한 변 180 m 블록, 그림의 경로(동쪽 4블록, 남쪽 2블록으로 읽음)", "변위 크기", "거리 {0} m, 변위 {1} m",
       [("거리 (m)", "6 × 180", 6 * 180, "1,080"), ("변위 (m)", "√(720² + 360²)", math.hypot(720, 360), "805")], "#3, HC-B14",
       "새로·그림 읽기")
    ex(6, "6주차 p20 예제 1", "50 m를 7.5 s", "속력", "{0} m/s", [("속력 (m/s)", "50 ÷ 7.5", 50 / 7.5, "6.67")], "#16, HC-B17", "v1")
    ex(7, "6주차 p21 예제 2", "20 km를 89분", "평균 속력", "{0} m/s", [("평균 속력 (m/s)", "20,000 ÷ (89 × 60)", 20000 / (89 * 60), "3.745")],
       "#11, HC-A13", "새로")
    ex(8, "6주차 p22 예제 3", "3 s에 +3 m/s, 4 s 뒤 −5 m/s", "v_i, v_f", "{0}, {1} m/s",
       [("v_i (m/s)", "읽는다", 3, "+3"), ("v_f (m/s)", "읽는다", -5, "−5")], "#44, HC-B20(부호)", "새로")
    ex(9, "6주차 p23 예제 4", "예제 3과 같음", "가속도", "(−5 − 3) ÷ 4 = {0} m/s²", [("가속도 (m/s²)", "(v_f − v_i) ÷ Δt", (-5 - 3) / 4, "−2.0")],
       "#44", "새로")
    ex(10, "6주차 p24 예제 5", "평균 −3.2 m/s, 3 s", "이동", "{0} m", [("이동 (m)", "v × t", -3.2 * 3, "−9.6")], "—", "새로")
    ex(11, "6주차 p25 예제 6", "등속, 10 m → 30 m, 5 s", "속도", "{0} m/s", [("속도 (m/s)", "(30 − 10) ÷ 5", (30 - 10) / 5, "4.0")],
       "#16, HC-B17", "새로")
    ex(12, "6주차 p26 예제 7", "정지에서 3 m/s², 3.5 s", "속력", "{0} m/s", [("속력 (m/s)", "a t", 3 * 3.5, "10.5")], "#15, HC-B13", "새로")
    ex(13, "6주차 p27 예제 8", "1.65 m/s², 9.2 m/s, 처음 속도 0", "시간", "{0} s", [("시간 (s)", "v ÷ a", 9.2 / 1.65, "5.58")], "#15, HC-B13", "v1")
    ex(14, "6주차 p28 예제 9", "a −0.5 m/s², v_i 6 m/s, 3 s", "v_f", "{0} m/s", [("v_f (m/s)", "v_i + a t", 6 - 0.5 * 3, "4.5")], "G-12", "새로")
    ex(15, "6주차 p29 예제 10", "20–30 m 구간을 60프레임, 50 fps", "속도", "{0} s, {1} m/s",
       [("시간 (s)", "프레임 ÷ fps", 60 / 50, "1.2"), ("속도 (m/s)", "10 ÷ 시간", 10 / (60 / 50), "8.33")], "#16, HC-B17", "v1")
    ex(16, "7주차 p15–17 위로 던지기", "v_i 2 m/s, s_i 0", "시간, 높이", "올라가는 시간 {0} s, 전체 {1} s, 높이 {2} m",
       [("올라가는 시간 (s)", "v_i ÷ g", 2 / G, "0.204"), ("전체 시간 (s)", "2 v_i ÷ g", 4 / G, "0.408"), ("높이 (m)", "v_i² ÷ (2g)", 4 / (2 * G), "0.204")],
       "#18, #19", "새로")
    ex(17, "7주차 p18–30 축구공 킥", "수평 15, 수직 10 m/s", "거리", "{0} s, {1} m(최고 높이 {2} m는 우리가 더 푼 값)",
       [("체공 (s)", "2 v_y ÷ g", 20 / G, "2.04"), ("거리 (m)", "v_x × 체공", 15 * 20 / G, "30.6"), ("최고 높이 (m), 우리가 더 푼 값", "v_y² ÷ (2g)", 100 / (2 * G), "5.10")],
       "#17, HC-B4", "v1")
    ay = 1800 / 52 - G
    ex(18, "10주차 p11 예제 1", "52 kg, 5 m/s, 수직 1800 N, 제동 300 N(그림 W 510 N)", "수직 가속도",
       "{0} m/s²({1} g). a_x {2} m/s²는 우리가 더 푼 값",
       [("수직 가속도 (m/s²)", "(1800 − 52 × 9.81) ÷ 52", ay, "24.81"), ("수직 가속도 (g)", "÷ 9.81", ay / G, "2.53"),
        ("수평 가속도 a_x (m/s²), 우리가 더 푼 값", "−300 ÷ 52", -300 / 52, "−5.77"), ("그림의 W (N)", "52 × 9.81", 52 * G, "510")], "#26, HC-B1", "v1")
    ex(19, "10주차 p12 예제 2", "1 kg 공, 수평 5.0 m/s², 수직 가속도 0", "수평·수직 힘", "{0} N, {1} N",
       [("수평 힘 (N)", "m a", 1 * 5.0, "5.0"), ("수직 힘 (N)", "m g", 1 * G, "9.81")], "#47", "새로")
    ex(20, "10주차 p14 예제 3", "평행 380 N, 수직 555 N, μ 0.66", "마찰력", "0.66 × 555 = {0} N(380 N이 더 커서 미끄러짐. 주어진 μ 하나로 계산)",
       [("마찰력 (N)", "μ N", 0.66 * 555, "366.3")], "G-11", "v1")
    fx, fn = 100 * cosd(45), 10 * G + 100 * sind(45)
    ex(21, "10주차 p15 예제 4", "10 kg, μ 0.68, 100 N을 45°로 비스듬히 아래로", "움직이나",
       "수평 100 cos 45° = {0} N, 수직력 98.1 + 100 sin 45° = {1} N, 최대 마찰력 0.68 × {1} = {2} N > {0} N → 움직이지 않음",
       [("수평 (N)", "100 cos 45°", fx, "70.71"), ("수직력 (N)", "m g + 100 sin 45°", fn, "168.81"), ("최대 마찰력 (N)", "μ × 수직력", 0.68 * fn, "114.79")],
       "G-11", "v1(원본에 70.7·114.79)")
    ex(22, "10주차 p17 예제 5", "65 kg, 처음 0, 이륙 3.4 m/s", "이륙 충격량", "{0} N·s", [("충격량 (N·s)", "m Δv", 65 * 3.4, "221")], "#28, HC-B5", "v1")
    ex(23, "10주차 p18 예제 6", "5 kg 볼링공, 8.0 m/s, 2.0 s, 마찰 0", "평균 힘", "{0} N(공이 오는 반대 방향)",
       [("평균 힘 (N)", "m Δv ÷ Δt", 5 * 8.0 / 2.0, "20")], "G-12", "v1(답만 있던 것)")
    ex(24, "10주차 p19 예제 7", "150 kg, 11.1 m/s, 2.0 s", "멈추는 힘", "{0} N", [("멈추는 힘 (N)", "m Δv ÷ Δt", 150 * 11.1 / 2.0, "832.5")], "G-12",
       "v1(답만 있던 것)")
    ex(25, "10주차 p21 예제 8", "10 kg, 40 N, 5 m, 10 s / 30°", "일, 파워", "{0} J, {1} W / {2} J, {3} W",
       [("일 (J)", "F s", 200, "200"), ("파워 (W)", "W ÷ t", 20, "20"), ("30°일 때 일 (J)", "F cos 30° s", 200 * cosd(30), "173.2"),
        ("30°일 때 파워 (W)", "W ÷ t", 20 * cosd(30), "17.3")], "#25, HC-B18", "v1")
    ex(26, "10주차 p22 예제 9", "50 kg, 1 m/s, 3.5 m", "총에너지", "{0} J", [("총에너지 (J)", "½ m v² + m g h", 0.5 * 50 * 1 + 50 * G * 3.5, "1,741.8")],
       "#29, HC-B9", "v1")
    w27 = 50 * cosd(30) * 5
    ex(27, "10주차 p23 예제 10", "25 kg, 50 N 위 30°, 5 m, 정지에서", "일, 속력", "{0} J, {1} m/s(마찰 없다고 봄)",
       [("일 (J)", "F cos 30° s", w27, "216.5"), ("속력 (m/s)", "√(2 W ÷ m)", math.sqrt(2 * w27 / 25), "4.16")], "#25, HC-B18", "새로")
    ex(28, "10주차 p24 예제 11", "0.15 kg, 평균 60 N, 2.0 m, 정지에서", "일, 부호, 속력", "{0} J, 양의 일, {1} m/s",
       [("일 (J)", "F s", 60 * 2.0, "120"), ("속력 (m/s)", "√(2 W ÷ m)", math.sqrt(2 * 120 / 0.15), "40.0")], "#25, HC-B18", "새로")
    v = [("처음 위치에너지 (J)", "m g h", 10 * G * 5, "490.5"), ("바닥 속력 (m/s)", "√(2 g h)", math.sqrt(2 * G * 5), "9.90")]
    answer = "처음 PE {0} J, KE 0 → 바닥 v {1} m/s, PE 0, KE {0} J"
    if a1 is not None:
        v += [("우리: A 점프 1 꼭대기 위치에너지 (J)", "m g h (results/jumps.csv: height_m)", 70.0 * G * a1.height_m, "234.2"),
              ("우리: A 점프 1 착지 직전 운동에너지 (J)", "½ m v² (results/jumps.csv: kinetic_energy_j)", a1.kinetic_energy_j, "234.3")]
        answer += ". 우리: A 점프 1 꼭대기 PE {2} J → 착지 직전 ½mv² {3} J"
    ex(29, "10주차 p25 예제 12", "10 kg, 5 m, 정지에서", "PE·KE·v_f", answer, v, "#12, #23", "새로")
    v = []
    for name, (trunk, thigh, shank, foot), refs in (("착지", (90.43, 123.53, 106.65, 200.48), ("33.10", "16.88", "−3.83")),
                                                    ("발끝 떼기", (88.82, 92.29, 34.90, 106.82), ("3.47", "57.39", "18.08"))):
        v += [(f"{name} 엉덩 (°)", "허벅지 − 몸통", thigh - trunk, refs[0]), (f"{name} 무릎 (°)", "허벅지 − 정강이", thigh - shank, refs[1]),
              (f"{name} 발목 (°)", "정강이 − 발 + 90", shank - foot + 90, refs[2])]
    ex(30, "11주차 p23 보행 분석 표", "착지: 몸통 90.43°, 허벅지 123.53°, 정강이 106.65°, 발 200.48°. 발끝 떼기: 88.82°, 92.29°, 34.90°, 106.82°",
       "관절각(p31 식)", "착지 엉덩 {0}°, 무릎 {1}°, 발목 {2}°(바닥 쪽 굽힘). 발끝 떼기 {3}°, {4}°, {5}°(발등 굽힘)", v,
       "#33(교안 쪽 값), HC-B19, G-13", "새로")
    hip, knee, ank = (1.14, 0.80), (1.22, 0.51), (1.09, 0.09)
    inner, flex = knee_cosine(hip, knee, ank)
    th, shk = absolute_angles(hip, knee, ank)
    ex(31, "11주차 p28 예제 1", "엉덩 (1.14, 0.80), 무릎 (1.22, 0.51), 발목 (1.09, 0.09)", "무릎 상대각",
       "{3}°(안쪽) = 굽힘 {4}°. p20–21의 {5}°, {6}°는 원본에 찍힘",
       [("a 엉덩–발목 (m)", "두 점 사이 거리", math.dist(hip, ank), "0.7118"), ("b 엉덩–무릎 (m)", "두 점 사이 거리", math.dist(hip, knee), "0.3008"),
        ("c 무릎–발목 (m)", "두 점 사이 거리", math.dist(knee, ank), "0.4397"), ("무릎 안쪽 각 (°)", "a² = b² + c² − 2bc cos θ", inner, "147.4"),
        ("굽힘 각 (°)", "180 − θ", flex, "32.6"), ("정강이 절대각 (°)", "arctan(0.42 ÷ 0.13)", shk, "72.8"),
        ("허벅지 절대각 (°)", "arctan(0.29 ÷ −0.08) + 180", th, "105.4"), ("절대각의 차 (°)", "허벅지 − 정강이", th - shk, "32.6")],
       "#33, HC-B10", "새로(v1은 숫자 없음)")
    ex(32, "11주차 p32 예제 2", "허벅지 120°, 몸통 80°", "엉덩 각", "{0}°, 굽힘", [("엉덩 각 (°)", "허벅지 − 몸통", 120 - 80, "40")], "G-13", "새로")
    ex(33, "11주차 p33 예제 3", "정강이 30°, 허벅지 80°", "무릎 각", "{0}°, 굽힘", [("무릎 각 (°)", "허벅지 − 정강이", 80 - 30, "50")], "#34, HC-B19", "v1")
    ex(34, "11주차 p34 예제 4", "정강이 45°, 발 133°", "발목 각", "45 − 133 + 90 = {0}°, 발등 굽힘", [("발목 각 (°)", "정강이 − 발 + 90", 45 - 133 + 90, "2")],
       "G-13", "새로")
    ex(35, "11주차 p40 예제 5", "30° → 120°, 2 s", "각변위, 평균 각속도", "{0}°, {1}°/s",
       [("각변위 (°)", "θ_f − θ_i", 120 - 30, "90"), ("평균 각속도 (°/s)", "Δθ ÷ Δt", (120 - 30) / 2, "45")], "#35, HC-B20", "v1")
    ex(36, "11주차 p41 예제 6", "30° → −85°, 0.05 s", "각변위, 평균 각속도", "{0}°, {1}°/s",
       [("각변위 (°)", "θ_f − θ_i", -85 - 30, "−115"), ("평균 각속도 (°/s)", "Δθ ÷ Δt", (-85 - 30) / 0.05, "−2,300")], "#35, HC-B20", "v1")
    ex(37, "11주차 p51 예제 1", "팔 1 m + 골프채 1.3 m, 3000°/s", "채 끝 선속도", "v = rω(2π ÷ 360°) = 2.3 × {0} = {1} m/s",
       [("각속도 (rad/s)", "3000 × 2π ÷ 360", math.radians(3000), "52.36"), ("채 끝 선속도 (m/s)", "r ω", 2.3 * math.radians(3000), "120.4")], "#32",
       "v1(답만 있던 것)")
    ex(38, "11주차 p52 예제 2", "팔 0.97 m, 놓는 순간 2350°/s", "공 선속도", "{0} m/s", [("공 선속도 (m/s)", "r ω", 0.97 * math.radians(2350), "39.8")],
       "#32", "v1(답만 있던 것)")
    ex(39, "11주차 p58 예제 1", "스위트 스폿 80 cm, 40 m/s", "각속도", "{0} rad/s({1}°/s)",
       [("각속도 (rad/s)", "v ÷ r", 40 / 0.80, "50"), ("각속도 (°/s)", "× 180 ÷ π", math.degrees(40 / 0.80), "2,865")], "#32", "새로")
    ex(40, "11주차 p59 예제 2", "802°/s, 0.16 s, θ_i 0, α 0", "각변위", "{0}°", [("각변위 (°)", "ω t", 802 * 0.16, "128.3")], "#35, HC-B20", "새로")
    ex(41, "11주차 p60 예제 3", "반지름 17 m, 6.64 m/s", "구심 가속도", "{0} m/s²({1} g)",
       [("구심 가속도 (m/s²)", "v² ÷ r", 6.64 ** 2 / 17, "2.59"), ("구심 가속도 (g)", "÷ 9.81", 6.64 ** 2 / 17 / G, "0.26")], "#30, HC-B3", "v1")
    ex(42, "11주차 p61 예제 4", "ω_f 400°/s, α 501°/s², θ_i 0, ω_i 0", "회전한 각", "400² ÷ (2 × 501) = {0}°",
       [("회전한 각 (°)", "ω_f² ÷ (2α)", 400 ** 2 / (2 * 501), "159.7")], "#35", "새로")
    ex(43, "11주차 p62 예제 5", "1200°/s, r 1.2 m", "선속도, 구심 가속도", "{0} m/s, {1} m/s²",
       [("선속도 (m/s)", "r ω", 1.2 * math.radians(1200), "25.13"), ("구심 가속도 (m/s²)", "r ω²", 1.2 * math.radians(1200) ** 2, "526.4")], "#50", "새로")
    ex(44, "12주차 p42 예제 1", "300 N, 축에서 1.3 m, α 309 rad/s²", "문의 I", "{0} ÷ 309 = {1} kg·m²",
       [("토크 (N·m)", "F r", 300 * 1.3, "390"), ("관성모멘트 I (kg·m²)", "τ ÷ α", 300 * 1.3 / 309, "1.262")], "#38, HC-B8", "v1(답만 있던 것)")
    ex(45, "12주차 p43 예제 2", "토크 5 N·m, 2 kg, 회전반경 10 cm", "α", "I {0} kg·m², α {1} rad/s²",
       [("관성모멘트 I (kg·m²)", "m k²", 2 * 0.10 ** 2, "0.020"), ("각가속도 (rad/s²)", "τ ÷ I", 5 / (2 * 0.10 ** 2), "250")], "#38, HC-B8",
       "v1(답만 있던 것)")
    ex(46, "12주차 p44 예제 3", "회전반경 2(단위 없음)에서 20 rad/s, 펴서 회전반경 2배", "착지 직전 ω", "20 × (2 ÷ 4)² = {0} rad/s",
       [("착지 직전 각속도 (rad/s)", "ω₁ (k₁ ÷ k₂)²(각운동량 보존)", 20 * (2 / 4) ** 2, "5")], "#36, HC-B7", "v1('2배' 조건 보탬)")
    ex(47, "12주차 p45 예제 4", "—", "질량이 늘면 I는?", "I = mk²라 k가 같으면 질량에 비례해 커진다", [], "#52", "새로(말로 답)")
    ex(48, "12주차 p59 예제 1", "아래팔·손 45 N(팔꿈치에서 0.15 m), 바벨 420 N(0.4 m), 굽힘근 모멘트 팔 0.05 m", "평형에 필요한 근육 모멘트",
       "{0} + {1} = {2} N·m(근육 힘 {3} N은 우리가 더 푼 값)",
       [("아래팔·손의 모멘트 (N·m)", "45 × 0.15", 45 * 0.15, "6.75"), ("바벨의 모멘트 (N·m)", "420 × 0.4", 420 * 0.4, "168"),
        ("근육 모멘트 (N·m)", "두 모멘트의 합", 45 * 0.15 + 420 * 0.4, "174.75"), ("근육 힘 (N), 우리가 더 푼 값", "모멘트 ÷ 0.05", (45 * 0.15 + 420 * 0.4) / 0.05, "3,495")],
       "G-15", "v1(답만 있던 것)")
    ex(49, "12주차 p60 예제 2", "예제 1에서 팔을 수평 아래 25°로, 근육 작용선은 축에서 0.05 m", "필요한 근육 토크",
       "174.75 × cos 25° = {0} N·m(근육 힘 {1} N)",
       [("근육 토크 (N·m)", "174.75 × cos 25°", 174.75 * cosd(25), "158.4"), ("근육 힘 (N)", "토크 ÷ 0.05", 174.75 * cosd(25) / 0.05, "3,168")], "G-15",
       "v1(답만 있던 것)")
    ia, rxr = 0.0096 * -14.66, (-0.07) * 20.3 - 0.07 * (-1.57)
    ex(50, "12주차 p65 예제 3", "발: R_x −1.57 N, R_y 20.3 N, I 0.0096 kg·m², α −14.66 rad/s², 발 질량중심을 축으로. "
       "그림에서 발목 관절은 질량중심의 위 0.07 m, 뒤 0.07 m", "발목 토크", "ΣT = Iα: T_ankle = Iα − (r × R) = {0} − ({1}) = {2} N·m(반시계)",
       [("Iα (N·m)", "0.0096 × −14.66", ia, "−0.141"), ("r × R (N·m)", "r_x R_y − r_y R_x, r = (−0.07, 0.07)", rxr, "−1.311"),
        ("발목 토크 (N·m)", "Iα − (r × R)", ia - rxr, "1.17")], "G-16", "새로·그림 읽기")
    return out


def rows_lecture(sh: Sheet, t) -> None:
    jj = _used(t.jumps).sort_values(["runner", "jump_no"])
    for e in lecture_examples(jj[jj["runner"] == "A"].iloc[0]):
        status = "교안 예제 · 그림 읽기" if e.figure else "교안 예제"
        sh.begin(f"E{e.no}", "교안 예제", e.cite, status, inputs=f"교안 문제의 입력: {e.given}")
        if not e.values:
            sh.add(f"묻는 것: {e.ask} → {e.answer}", formula="I = m k²")
        for item, formula, value, ref in e.values:
            ours = item.startswith("우리:")
            sh.add(item, value, None, ref, formula=formula, status="실측" if ours else None,
                   inputs="A 점프 1 (results/jumps.csv), 체중 70 kg" if ours else None)


# ---------------------------------------------------------------- 가정 예시 (G-1–G-18)
def rows_assumption(sh: Sheet, t, params) -> None:
    kind, st, base, body, mod = "가정 예시", "가정 예시", t.base, t.body, models(t, params)
    mg = {p: float(body.loc[p, "mass_kg"]) * G for p in ("A", "B")}
    m_a = float(body.loc["A", "mass_kg"])
    si = float(base.loc["A", "silent_impact_g"])
    s180, s_sil, s150, b195 = _stage(t, "A", "180"), _stage(t, "A", "S"), _stage(t, "A", "150"), _stage(t, "B", "195")
    f_walk, f_run = si * mg["A"], float(s180["impact_g"]) * mg["A"]
    jj = _used(t.jumps).sort_values(["runner", "jump_no"])
    a1 = jj[jj["runner"] == "A"].iloc[0]
    v1 = float(a1.takeoff_v_flight_ms)
    tr = t.sw.set_index("trial_id")
    good = _used(t.sw)
    amp = {p: float(good[(good["runner"] == p) & (good["knee"] == "straight")]["amp_deg"].mean()) for p in ("A", "B")}
    tau = {p: mod[p].s.m * G * mod[p].s.d * math.sin(math.radians(amp[p])) for p in ("A", "B")}
    fr = _fractions(params)

    sh.begin("G-1", kind, "3주차 p6 σ = F/A, p8 ε = ΔL/L, p10 E = σ/ε, p15, p25(극한 응력 그림)", st,
             "σ = F ÷ A, ε = σ ÷ E, ΔL = ε × 정강이 길이",
             f"실측: A 발 디딤 충격 {si:.2f} BW(걷기 무음), {float(s180['impact_g']):.2f} BW(180% 뛰기), 정강이 {mod['A'].ls:.2f} m. "
             "가정: 정강뼈가 지면반력만 받는다, 단면적 3.0 cm²(가정), E 18,000 MPa(교안 p10 표의 뼈 값. 표에 단위가 없어 MPa로 봄), 연골 E 20")
    sh.add("걷기 힘 (N)", f_walk, None, "1,099")
    sh.add("뛰기 힘 (N)", f_run, None, "2,596")
    for name, f, rf in (("걷기", f_walk, ("3.66", "0.020", "0.073", "18.3", "55", "37")),
                        ("뛰기", f_run, ("8.65", "0.048", "0.173", "43.3", "23", "16"))):
        sig = f / 3.0e-4 / 1e6
        sh.add(f"{name} 응력 (MPa)", sig, None, rf[0])
        sh.add(f"{name} 변형률 (%)", sig / 18000 * 100, None, rf[1])
        sh.add(f"{name} 정강뼈가 줄어드는 길이 (mm)", sig / 18000 * mod["A"].ls * 1000, None, rf[2])
        sh.add(f"{name} 같은 응력에서 연골의 변형률 (%)", sig / 20 * 100, None, rf[3])
        sh.add(f"{name} 압축 극한 응력 200 MPa ÷ 응력 (배)", 200 / sig, None, rf[4], formula="교안 p25 그림에서 읽은 200 MPa ÷ σ",
               status="가정 예시 · 그림 읽기")
        sh.add(f"{name} 인장 극한 응력 135 MPa ÷ 응력 (배)", 135 / sig, None, rf[5], formula="교안 p25 그림에서 읽은 135 MPa ÷ σ",
               status="가정 예시 · 그림 읽기")

    sh.begin("G-2", kind, "3주차 p25–26 점탄성과 하중률", st, "하중률 = 충격 ÷ 정점까지 걸리는 시간",
             f"실측: G-1의 두 충격({si:.2f}, {float(s180['impact_g']):.2f} BW). 가정: 정점까지 걷기 0.10 s, 뛰기 0.03 s")
    sh.add("걷기 하중률 (BW/s)", si / 0.10, None, "16")
    sh.add("걷기 하중률 (kN/s)", f_walk / 0.10 / 1000, None, "11.0")
    sh.add("뛰기 하중률 (BW/s)", float(s180["impact_g"]) / 0.03, None, "126")
    sh.add("뛰기 하중률 (kN/s)", f_run / 0.03 / 1000, None, "86.5")
    sh.add("뛰기 ÷ 걷기 (배)", (f_run / 0.03) / (f_walk / 0.10), None, "7.9")

    sh.begin("G-3", kind, "3주차 p27–28 하중 종류", st, "", "값 없이 잇는다")
    sh.add("걷기·점프에서 정강뼈는 압축, 진자에서 엉덩관절은 흔드는 다리를 끌어당기는 인장을 받는다(G-10의 관절반력)")

    work = a1.mean_grf_push_bw * mg["A"] * a1.takeoff_v_int_ms * a1.pushoff_time_s / 2
    sh.begin("G-4", kind, "3-2주차 p31 원심성에서 최대 힘, p35 힘-속도 곡선", st,
             "흡수할 에너지 = ½ m v² + m g n, 평균 지면반력 = m(g + v² ÷ 2n)",
             f"실측: A 점프 1 이륙 속도 {v1:.3f} m/s, 밀기 일 {work:.1f} J(HC-B18). 가정: 착지 때 몸 중심이 n = 0.30 m(뻣뻣하면 0.10 m) 내려가며 멈춘다")
    sh.add("A 점프 1 밀기 일 (J)", work, None, "437.8", formula="HC-B18의 W")
    sh.add("착지 직전 운동에너지 (J)", 0.5 * m_a * v1 ** 2, None, "234.2", formula="½ m v²")
    sh.add("n 0.30 m: 내려가며 잃는 위치에너지 (J)", mg["A"] * 0.30, None, "206.0", formula="m g n")
    sh.add("n 0.30 m: 흡수할 에너지 (J)", 0.5 * m_a * v1 ** 2 + mg["A"] * 0.30, None, "440.2")
    sh.add("n 0.30 m: 평균 지면반력 (N)", m_a * (G + v1 ** 2 / 0.6), None, "1,467")
    sh.add("n 0.30 m: 평균 지면반력 (BW)", (G + v1 ** 2 / 0.6) / G, None, "2.14")
    sh.add("n 0.10 m: 흡수할 에너지 (J)", 0.5 * m_a * v1 ** 2 + mg["A"] * 0.10, None, "302.9")
    sh.add("n 0.10 m: 평균 지면반력 (N)", m_a * (G + v1 ** 2 / 0.2), None, "3,029")
    sh.add("n 0.10 m: 평균 지면반력 (BW)", (G + v1 ** 2 / 0.2) / G, None, "4.41")
    sh.add("0.10 m ÷ 0.30 m 평균 지면반력의 비 (배)", (G + v1 ** 2 / 0.2) / (G + v1 ** 2 / 0.6), None, nd=2)

    sh.begin("G-5", kind, "3-2주차 p14 MV = m ÷ ρ", st, "근육 부피 = 근육 질량 ÷ 밀도",
             f"모델: A 허벅지 분절 질량 = {fr['thigh_mass']:.3f} × {m_a:.0f} kg. 교안 밖 가정: 근육 비율 0.6, 밀도 1.06 g/cm³")
    sh.add("A 허벅지 분절 질량 (kg)", fr["thigh_mass"] * m_a, None, "7.0")
    sh.add("A 허벅지 근육 부피 (cm³)", fr["thigh_mass"] * m_a * 1000 * 0.6 / 1.06, None, "3,962")

    tc = float(s180["contact_time_s"])
    sh.begin("G-6", kind, "4주차 p16 수축 시간, p18–19 크기 원리·발화빈도", st, "수축 시간 ÷ 접촉 시간 × 100",
             f"실측: A 180% 접촉 {tc:.4f} s(참고값), 충격 무음 {float(s_sil['impact_g']):.2f} → 180% {float(s180['impact_g']):.2f} BW. "
             "교안 값: Type I 수축 시간 70 ms 초과, Type IIb 30–40 ms")
    sh.add("A 180% 접촉 시간 (s)", None, tc, "0.2475", formula="읽은 값")
    sh.add("충격이 커진 배수 (배)", float(s180["impact_g"]) / float(s_sil["impact_g"]), None, "2.49", formula="180% 충격 ÷ 무음 충격")
    sh.add("Type I(70 ms)이 접촉 시간에서 차지하는 몫 (%)", 70 / (tc * 1000) * 100, None, "28")
    sh.add("Type IIb(30 ms)의 몫 (%)", 30 / (tc * 1000) * 100, None, "12")
    sh.add("Type IIb(40 ms)의 몫 (%)", 40 / (tc * 1000) * 100, None, "16")

    iv_a = 60 / float(base.loc["A", "pc_spm"]) * 1000
    iv_a180, iv_b195 = 60 / float(s180["cadence_median_spm"]) * 1000, 60 / float(b195["cadence_median_spm"]) * 1000
    ra, rb = 2 * mod["A"].L / 60 * 1000, 2 * mod["B"].L / 60 * 1000
    sh.begin("G-7", kind, "4주차 p20–22 신장반사, p28 근방추", st, "반사 시간 = 왕복 경로 ÷ 전도 속도, 걸음 간격 = 60 ÷ 케이던스",
             f"실측: A PC, A 180%·B 195% 단계 케이던스, 다리 길이 A {mod['A'].L:.2f} m·B {mod['B'].L:.2f} m. "
             "교안 밖 가정: 신경 전도 속도 60 m/s, 척수까지 왕복 경로 = 다리 길이 × 2")
    for name, value, ref in (("A 평소 걸음 간격 (ms)", iv_a, "602"), ("A 180% 걸음 간격 (ms)", iv_a180, "362"),
                             ("B 195% 걸음 간격 (ms)", iv_b195, "316"), ("A 반사 시간 (ms)", ra, "33"),
                             ("A 반사 시간 ÷ 평소 걸음 간격 (%)", ra / iv_a * 100, "5.5"), ("A 반사 시간 ÷ 180% 걸음 간격 (%)", ra / iv_a180 * 100, "9.2"),
                             ("B 반사 시간 (ms)", rb, "31"), ("B 반사 시간 ÷ 195% 걸음 간격 (%)", rb / iv_b195 * 100, "9.8")):
        sh.add(name, value, None, ref)

    sh.begin("G-8", kind, "4주차 p35–36 근전도", st, "EMG 진폭이 힘에 비례한다면 늘어난 비율이 같다",
             f"실측: A 충격 무음 {float(s_sil['impact_g']):.2f} → 150% {float(s150['impact_g']):.2f} BW. 가정: 대퇴사두근 EMG 진폭이 힘에 비례한다")
    sh.add("A 충격이 늘어난 크기 = EMG 진폭이 커졌을 크기 (%)", (float(s150["impact_g"]) / float(s_sil["impact_g"]) - 1) * 100, None, "+26")

    ref_g = {"A": ("E3_A_1", "0.123", "1.98", "118.2", "110.6", "1.07", "4.103", "1.584", "+28.2", "1.800", "+45.8", "20.5", "10.3",
                   "1.905", "0.378", "5.04"),
             "B": ("E3_B_1", "0.168", "2.71", "115.5", "97.9", "1.18", "5.008", "2.627", "+24.8", "3.144", "+49.4", "25.0", "12.5",
                   "3.664", "0.359", "10.19")}
    calc = {}
    for p, rf in ref_g.items():
        r, s = tr.loc[rf[0]], mod[p].s
        th, w = math.radians(r.amp_deg), float(r.omega_peak_rad_s)
        calc[p] = SimpleNamespace(r=r, s=s, th=th, w=w, H=s.I * w, W=s.m * G * s.d * (1 - math.cos(th)), rf=rf)

    sh.begin("G-9", kind, "9주차 p32 압력중심; 몸 중심은 12주차 p48, p51", st,
             "다리 질량중심의 앞뒤 이동 = d sin θ, 몸 전체 질량중심 이동 = 그 값 × 다리 질량 ÷ 체중",
             "실측·모델: 시행 A_1·B_1의 진폭, 흔드는 다리의 모델 질량과 d(HC-B7). 가정: 서 있는 몸이 움직이지 않고 정적 균형을 지킨다")
    for p, c in calc.items():
        sh.add(f"{p} 다리 질량중심 이동(가운데에서 한쪽 끝까지) (m)", c.s.d * math.sin(c.th), None, c.rf[1])
        sh.add(f"{p} 몸 전체 질량중심 이동(가운데에서 한쪽 끝까지) (cm)", c.s.d * math.sin(c.th) * c.s.m / mod[p].M * 100, None, c.rf[2])

    sh.begin("G-10", kind, "9주차 p34 관절반력", "가정 예시 · 계산만", "흔들림 바닥에서 R = m(g + ω² d)",
             "실측: 시행 A_1·B_1의 자이로 최대 ω. 모델: 다리 질량 m, 질량중심 거리 d(HC-B7)")
    for p, c in calc.items():
        sh.add(f"{p} 엉덩관절 반력 (N)", c.s.m * (G + c.w ** 2 * c.s.d), None, c.rf[3])
        sh.add(f"{p} 다리 무게 (N)", c.s.m * G, None, c.rf[4])
        sh.add(f"{p} 반력 ÷ 다리 무게 (배)", (G + c.w ** 2 * c.s.d) / G, None, c.rf[5])

    fmax = float(s180["fmax_bw"]) * mg["A"]
    fp = 482 / 688 * f_walk
    sh.begin("G-11", kind, "9주차 p41–43 F_f = μN, p31 지면반력 곡선(그림); 10주차 p14 예제 3, p15 예제 4", st,
             "수평력 = 비 × 수직력, 최대 마찰력 = μ × 수직력. 수평력이 더 크면 미끄러진다",
             f"실측: A 걷기 수직력 {f_walk:.0f} N, 180% 뛰기 F_max {fmax:.0f} N(참고값). 교안 그림 값(9주차 p31, 교안 속 한 사람의 걷기, 그림 읽기): "
             "수평 ÷ 수직이 첫 봉우리 0.20, 앞으로 미는 힘이 가장 클 때 0.35(수직 482 N, 앞뒤 169 N), 첫 봉우리 수직 688 N. "
             "가정: A의 걷기 모양이 교안 그림과 같다. 교안 밖 가정: 뛰기의 비 0.25, 바닥 μ 마른 바닥 0.6·젖은 바닥 0.3·얼음 0.1")
    for name, value, ref in (("걷기 첫 봉우리: 수평력 (N)", 0.20 * f_walk, "220"), ("걷기 첫 봉우리: 최대 마찰력, 마른 바닥 (N)", 0.6 * f_walk, "659"),
                             ("걷기 첫 봉우리: 최대 마찰력, 젖은 바닥 (N)", 0.3 * f_walk, "330"), ("걷기 첫 봉우리: 최대 마찰력, 얼음 (N)", 0.1 * f_walk, "110"),
                             ("교안 그림: 앞으로 미는 순간의 수평 ÷ 수직", 169 / 482, "0.35"), ("교안 그림: 앞으로 미는 순간 수직력 ÷ 첫 봉우리 수직력", 482 / 688, "0.70"),
                             ("걷기 앞으로 미는 순간: 수직력 (N)", fp, "770"), ("걷기 앞으로 미는 순간: 수평력 (N)", 0.35 * fp, "270"),
                             ("걷기 앞으로 미는 순간: 최대 마찰력, 마른 바닥 (N)", 0.6 * fp, "462"), ("걷기 앞으로 미는 순간: 최대 마찰력, 젖은 바닥 (N)", 0.3 * fp, "231"),
                             ("걷기 앞으로 미는 순간: 최대 마찰력, 얼음 (N)", 0.1 * fp, "77"), ("뛰기 F_max (N)", fmax, "1,579"),
                             ("뛰기: 수평력 (N)", 0.25 * fmax, "395"), ("뛰기: 최대 마찰력, 마른 바닥 (N)", 0.6 * fmax, "947"),
                             ("뛰기: 최대 마찰력, 젖은 바닥 (N)", 0.3 * fmax, "474"), ("뛰기: 최대 마찰력, 얼음 (N)", 0.1 * fmax, "158")):
        sh.add(name, value, None, ref, status="가정 예시 · 그림 읽기" if "교안 그림" in name or "앞으로 미는" in name or "첫 봉우리" in name else None)

    v180 = float(s180["v_ms"])
    sh.begin("G-12", kind, "9주차 p23 F = Δp ÷ Δt, p44 충격량으로 멈추기; 10주차 p18 예제 6, p19 예제 7", st,
             "멈추는 평균 힘 = m v ÷ Δt, 착지 평균 지면반력 = m v ÷ Δt + m g",
             f"실측: A 180% 속도 {v180:.3f} m/s, 점프 1 착지 속도 {v1:.3f} m/s(이륙과 같다고 봄), {m_a:.0f} kg. 가정: 멈추는 데 1.0 s 또는 0.5 s, 착지는 0.10 s 또는 0.30 s")
    for name, value, ref in (("1.0 s에 멈출 때 평균 힘 (N)", m_a * v180 / 1.0, "239"), ("1.0 s에 멈출 때 평균 힘 (BW)", v180 / 1.0 / G, "0.35"),
                             ("0.5 s에 멈출 때 평균 힘 (N)", m_a * v180 / 0.5, "479"), ("0.5 s에 멈출 때 평균 힘 (BW)", v180 / 0.5 / G, "0.70"),
                             ("착지 0.10 s: 충격량 몫 (N)", m_a * v1 / 0.10, "1,811"), ("체중 (N)", mg["A"], "687"),
                             ("착지 0.10 s: 평균 지면반력 (N)", m_a * v1 / 0.10 + mg["A"], "2,498"), ("착지 0.10 s: 평균 지면반력 (BW)", v1 / 0.10 / G + 1, "3.64"),
                             ("착지 0.30 s: 평균 지면반력 (N)", m_a * v1 / 0.30 + mg["A"], "1,290"), ("착지 0.30 s: 평균 지면반력 (BW)", v1 / 0.30 / G + 1, "1.88")):
        sh.add(name, value, None, ref)

    fr0 = t.markers[(t.markers["trial_id"] == "E3_A_K_1") & (t.markers["event_no"] == 1)].iloc[0]
    thigh, shank = absolute_angles((fr0.hip_x, fr0.hip_y), (fr0.knee_x, fr0.knee_y), (fr0.ankle_x, fr0.ankle_y), image_y_down=True)
    sh.begin("G-13", kind, "11주차 p32 예제 2, p34 예제 4", st, "엉덩 = 허벅지 − 몸통, 발목 = 정강이 − 발 + 90",
             f"실측: 진자 한 프레임의 허벅지 {thigh:.2f}°, 정강이 {shank:.2f}°(HC-B19). 가정: 몸통 절대각 90°(곧게 섬) 또는 80°, 발 절대각은 교안 예제 4의 133°")
    sh.add("엉덩 굽힘, 몸통 90° (°)", thigh - 90, None, "3.96")
    sh.add("엉덩 굽힘, 몸통 80° (°)", thigh - 80, None, "13.96")
    sh.add("발목, 발 133° (°)", shank - 133 + 90, None, "−20.71")

    sh.begin("G-14", kind, "12주차 p31–38 각운동량, p44 예제 3", st, "H = I ω, 접은 뒤 ω' = H ÷ I'",
             "실측·모델: 시행 A_1·B_1의 자이로 최대 ω, 곧은 다리·잰 각·90°의 모델 I(HC-B7). "
             "가정: 다리가 중력 토크 없이 자유롭게 돈다(실제 진자는 중력 토크가 있어 보존되지 않는다)")
    for p, c in calc.items():
        sh.add(f"{p} 각운동량 H (kg·m²/s)", c.H, None, c.rf[6])
        sh.add(f"{p} 잰 각까지 접으면 각속도 (rad/s)", c.H / mod[p].k.I, None, c.rf[7])
        sh.add(f"{p} 잰 각까지 접으면 각속도 변화 (%)", (c.s.I / mod[p].k.I - 1) * 100, None, c.rf[8])
        sh.add(f"{p} 90°까지 접으면 각속도 (rad/s)", c.H / mod[p].r.I, None, c.rf[9])
        sh.add(f"{p} 90°까지 접으면 각속도 변화 (%)", (c.s.I / mod[p].r.I - 1) * 100, None, c.rf[10])

    period = {p: float(t.p3.loc[p, "swing_period_s"]) for p in ("A", "B")}
    ref15 = {"A": ("13.16", "263", "0.38", "49.25", "985", "1.43", "1.531", "1.203", "1.619", "62", "8.1"),
             "B": ("16.67", "333", "0.55", "38.95", "779", "1.28", "1.439", "1.224", "1.381", "38", "6.3")}
    sh.begin("G-15", kind, "12주차 p56 정적 평형, p59 예제 1, p60 예제 2; 9주차 p38", st, "근육 모멘트 = 중력 토크, 근육 힘 = 모멘트 ÷ 모멘트 팔",
             f"실측·모델: 놓기 직전 다리를 잰 진폭(A {amp['A']:.1f}°, B {amp['B']:.1f}°)에 붙잡고 있다, 모델 m·d(HC-B7). "
             "가정: 엉덩관절 굽힘근의 모멘트 팔 0.05 m(교안 예제 1의 팔꿈치 값을 빌림)")
    for p, rf in ref15.items():
        s = mod[p].s
        hz = s.m * G * s.d
        sh.add(f"{p} 필요한 모멘트 (N·m)", tau[p], None, rf[0])
        sh.add(f"{p} 근육 힘 (N)", tau[p] / 0.05, None, rf[1])
        sh.add(f"{p} 근육 힘 (BW)", tau[p] / 0.05 / mg[p], None, rf[2])
        sh.add(f"{p} 다리를 수평으로 들 때 모멘트 (N·m)", hz, None, rf[3], formula="m g d")
        sh.add(f"{p} 다리를 수평으로 들 때 근육 힘 (N)", hz / 0.05, None, rf[4])
        sh.add(f"{p} 다리를 수평으로 들 때 근육 힘 (BW)", hz / 0.05 / mg[p], None, rf[5])

    sh.begin("G-16", kind, "12주차 p55, p63 ΣT = Iα, p65 예제 3; 9주차 p38", st,
             "필요한 되돌림 토크 = 중력 토크 × (P ÷ 걸음 왕복 시간)². 근육이 더 내는 몫 = 그 배수 − 1",
             "실측: 진자 주기 P(HC-A10), PC(HC-A1) → 걸을 때 다리 한 번 왕복 = 120 ÷ PC. 가정: 걸을 때도 같은 진폭으로 단순 조화 운동처럼 흔든다")
    for p, rf in ref15.items():
        cyc = 120 / float(base.loc[p, "pc_spm"])
        k = (period[p] / cyc) ** 2
        sh.add(f"{p} 진자 주기 P (s)", None, period[p], rf[6], formula="읽은 값")
        sh.add(f"{p} 걸을 때 다리 한 번 왕복 (s)", cyc, None, rf[7], formula="120 ÷ PC")
        sh.add(f"{p} 필요한 되돌림 토크 ÷ 중력 토크 (배)", k, None, rf[8])
        sh.add(f"{p} 근육이 더 내는 몫 (%)", (k - 1) * 100, None, rf[9])
        sh.add(f"{p} 근육이 더 내는 토크, 잰 진폭에서 (N·m)", tau[p] * (k - 1), None, rf[10])

    sh.begin("G-17", kind, "12주차 p66 각충격량 T Δt = Iω_f − Iω_i", st, "각충격량 = I ω, 평균 토크 = I ω ÷ Δt",
             "실측·모델: 시행 A_1·B_1의 자이로 최대 ω, 곧은 다리 모델 I. 가정: 정지한 다리를 근육으로 0.2 s 또는 0.4 s 만에 그 ω까지 휘두른다")
    for p, c in calc.items():
        sh.add(f"{p} 각충격량 (N·m·s)", c.H, None, c.rf[6])
        sh.add(f"{p} 평균 토크, 0.2 s (N·m)", c.H / 0.2, None, c.rf[11])
        sh.add(f"{p} 평균 토크, 0.4 s (N·m)", c.H / 0.4, None, c.rf[12])

    sh.begin("G-18", kind, "12주차 p67 W = TΔθ, p68 P = Tω, p70 각 일–에너지 정리", "가정 예시 · 계산만",
             "끝에서 바닥까지 중력이 하는 일 = m g d (1 − cos θ), 평균 각파워 = 일 ÷ (P ÷ 4)",
             "실측·모델: 시행 A_1·B_1의 진폭과 주기, 모델 m·d(HC-B7)")
    for p, c in calc.items():
        sh.add(f"{p} 중력이 하는 일 (J)", c.W, None, c.rf[13])
        sh.add(f"{p} 끝에서 바닥까지 시간 P ÷ 4 (s)", c.r.swing_period_s / 4, None, c.rf[14])
        sh.add(f"{p} 평균 각파워 (W)", c.W / (c.r.swing_period_s / 4), None, c.rf[15])


# ---------------------------------------------------------------- 묶기, 쓰기, 요약
def build_sheet(t, params, steps: dict | None = None) -> Sheet:
    sh = Sheet()
    rows_conclusion(sh, t, params, steps)
    rows_pairs(sh, t, params)
    rows_lecture(sh, t)
    rows_assumption(sh, t, params)
    return sh


def write_csv(sh: Sheet, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in sh.rows:
            w.writerow(r.cells())


def summary(sh: Sheet) -> pd.DataFrame:
    """구분마다: 손계산 수, 값 줄 수, 코드 값과 견준 줄, 일치, 기준값이 있는 줄, 기준값과 다른 줄."""
    out = []
    for kind in KINDS:
        rows = [r for r in sh.rows if r.kind == kind]
        out.append(dict(구분=kind, 손계산=len({r.id for r in rows}), 줄=len(rows), 손계산값=sum(r.hand is not None for r in rows),
                        코드와견줌=sum(r.match != "" for r in rows), 일치=sum(r.match == "일치" for r in rows),
                        불일치=sum(r.match == "불일치" for r in rows), 기준값있음=sum(r.ref_match != "" for r in rows),
                        기준값과다름=sum(r.ref_match == "다름" for r in rows)))
    df = pd.DataFrame(out)
    total = {"구분": "합계", **{c: int(df[c].sum()) for c in df.columns if c != "구분"}}
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "총정리본_검산표.csv")
    ap.add_argument("--no-steps", action="store_true", help="zip을 읽지 않는다(HC-A6을 뺀다)")
    args = ap.parse_args(argv)
    t, params = load_tables(), load_params()
    steps = None if args.no_steps else detect_exp2_steps(step_trials(t, params))
    sh = build_sheet(t, params, steps)
    write_csv(sh, args.out)
    print(f"검산표: {args.out} ({len(sh.rows)}줄)")
    print(summary(sh).to_string(index=False))
    for r in sh.rows:
        if r.match == "불일치":
            print(f"  코드와 불일치: {r.id} | {r.item}: 손계산 {r.hand:.10g}, 코드 {r.code:.10g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
