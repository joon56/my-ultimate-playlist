"""논문·발표용 핵심 그림 4장 (SPEC §8): 그림 2 템포 지도, 3b 동조율, 6 속도·체공·Froude 수, 7 진자.

이미 계산된 결과 표만 읽는다(실험 1: segments·participants·prescription, 실험 2·3: exp2_summary·exp3_summary·exp2_pc).
그림마다 같은 이름의 `.json`에 그려진 값과 params 해시를 남긴다. 300 dpi, 폭 6.5–8 inch, 사람마다 같은 색.
한글 글꼴(D-18)이 없으면 영어 라벨로 그린다. 합성 자료 그림에는 SYNTHETIC 워터마크를 넣는다. 좌표는 쓰지 않는다.
템포에 따른 그림의 가로축 T는 실험 1은 일상 PC, 실험 2는 현장 PC 기준이다(D-04).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from walkmusic.config import Params
from walkmusic.stats import _sha, require_freeze

NAN = float("nan")
FONTS = ("Pretendard", "Noto Sans CJK KR", "NanumGothic", "Malgun Gothic", "AppleGothic")  # D-18
COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}  # 색각 이상에서도 구분되는 세 색(검사함), 사람마다 고정
OTHER, INK, MUTED, GRID = "#5f6b65", "#17201c", "#5f6b65", "#d9dedb"
GAIT_MARK = {"walk": "o", "run": "^", "mixed": "^", "": "D"}
TEXT = {  # 한글, 영어(한글 글꼴이 없을 때)
    "t_axis": ("템포 비율 T (%)", "Tempo ratio T (%)"),
    "cad_axis": ("케이던스 ÷ PC (%)", "Cadence / PC (%)"),
    "s3_axis": ("동조율 S3 (%)", "Synchronisation S3 (%)"),
    "v_axis": ("속도 v (m/s)", "Speed v (m/s)"),
    "fr_axis": ("Froude 수 Fr", "Froude number Fr"),
    "tf_axis": ("체공 시간 (s)", "Flight time (s)"),
    "c_axis": ("케이던스 (걸음/분)", "Cadence (steps/min)"),
    "stage_axis": ("단계의 템포 비율 T (%)", "Stage tempo ratio T (%)"),
    "exp1_seg": ("실험 1 곡 구간(듣기만 함)", "Exp. 1 song segments (listening only)"),
    "exp1_mean": ("실험 1 플레이리스트 평균", "Exp. 1 playlist mean"),
    "exp2_walk": ("실험 2 단계: 걷기(영상 판정)", "Exp. 2 stage: walking (video)"),
    "exp2_run": ("실험 2 단계: 뛰기(영상 판정)", "Exp. 2 stage: running (video)"),
    "exp2_unknown": ("실험 2 단계: 판정하지 못함", "Exp. 2 stage: undetermined"),
    "diag": ("y = x (박자와 같은 케이던스)", "y = x (cadence equals tempo)"),
    "band": ("평소 흔들리는 폭(100 ± SESOI %)", "Usual variation (100 ± SESOI %)"),
    "pend_straight": ("진자 예측: 곧은 다리", "Pendulum: straight leg"),
    "pend_bent": ("진자 예측: 굽힌 다리", "Pendulum: bent knee"),
    "first_run": ("처음 뛴 단계", "First running stage"),
    "rx": ("처방 범위", "Prescription range"),
    "rx_low": ("처방 범위 하한(상한 없음)", "Prescription lower bound (no upper bound)"),
    "near_pc": ("PC ±10% 템포", "Tempo within PC ±10%"),
    "h12": ("가설 1-2 기준 {x:.0f}%", "Hypothesis 1-2 criterion {x:.0f}%"),
    "fr_half": ("Fr = {x:g}", "Fr = {x:g}"),
    "tf_phone": ("폰으로 잰 체공", "Flight time by phone"),
    "tf_video": ("발 카메라 프레임으로 읽은 체공(참고값)", "Flight time from foot-camera frames (reference)"),
    "tf_none": ("폰이 체공을 일부 걸음에서만 잡아 값 없음", "No value: phone caught flight in few steps"),
    "model": ("모델 예측", "Model prediction"),
    "measured": ("흔들림 실측으로 낸 값", "From measured swing period"),
    "straight": ("곧은 다리", "Straight leg"),
    "bent": ("굽힌 다리", "Bent knee"),
    "pc_daily": ("실측 PC(일상, 실험 1)", "Measured PC (daily, Exp. 1)"),
    "pc_field": ("현장 PC(실험 2 무음)", "Field PC (Exp. 2 silent)"),
    "panel": ("{p} · PC {pc:.1f} 걸음/분", "{p} · PC {pc:.1f} steps/min"),
    "panel2": ("{p} · PC {pc:.1f}, 현장 {pcf:.1f} 걸음/분", "{p} · PC {pc:.1f}, field {pcf:.1f} steps/min"),
    "fig2": ("템포 비율과 케이던스", "Tempo ratio and cadence"),
    "fig3b": ("템포 비율과 동조율: 실험 1 곡 구간과 실험 2 단계", "Tempo ratio and synchronisation: Exp. 1 and Exp. 2"),
    "fig6": ("단계별 속도, Froude 수, 체공 시간", "Speed, Froude number and flight time by stage"),
    "fig7": ("진자 예측 케이던스와 실측 평소 케이던스", "Pendulum-predicted cadence and measured usual cadence"),
    "basis": ("T는 실험 1은 일상 PC, 실험 2는 현장 PC 기준", "T uses daily PC for Exp. 1 and field PC for Exp. 2"),
}


def korean_font() -> str | None:
    """D-18의 순서로 찾은 첫 한글 글꼴 이름. 없으면 None(영어 라벨)."""
    have = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in FONTS if n in have), None)


def style(font: str | None) -> dict:
    """그림 공통 rcParams."""
    rc = {"axes.unicode_minus": False, "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
          "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5, "axes.edgecolor": MUTED,
          "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
          "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
          "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 100,
          "savefig.dpi": 300, "figure.facecolor": "white", "axes.facecolor": "white"}
    if font:
        rc["font.family"] = font
    return rc


@dataclass
class FigureData:
    """그림에 쓰는 결과 표들."""

    segments: pd.DataFrame      # 실험 1 곡 구간(T, ΔC%, S3)
    base: pd.DataFrame          # 사람마다 PC·SESOI(실험 1)
    prescription: pd.DataFrame  # 처방 범위(요약 줄)
    summary: pd.DataFrame       # 실험 2 단계
    pendulum: pd.DataFrame      # 실험 3 사람 요약
    field_pc: pd.DataFrame      # 실험 2 현장 PC
    korean: bool = True
    synthetic: bool = False

    def tr(self, key: str, **kw) -> str:
        return TEXT[key][0 if self.korean else 1].format(**kw)

    def people(self) -> list[str]:
        ids = set(self.base.get("participant", [])) | set(self.summary.get("runner", []))
        return sorted(ids)

    def color(self, person: str) -> str:
        return COLORS.get(person, OTHER)

    def pc(self, person: str) -> float:
        b = self.base[self.base["participant"] == person] if len(self.base) else self.base
        return float(b["pc_spm"].iloc[0]) if len(b) else NAN

    def sesoi(self, person: str) -> float:
        b = self.base[self.base["participant"] == person] if len(self.base) else self.base
        return float(b["sesoi_pct"].iloc[0]) if len(b) and "sesoi_pct" in b else NAN

    def pc_field(self, person: str) -> float:
        f = self.field_pc[self.field_pc["runner"] == person] if len(self.field_pc) else self.field_pc
        return float(f["pc_field_spm"].iloc[0]) if len(f) else NAN

    def panel_title(self, person: str) -> str:
        pc, pcf = self.pc(person), self.pc_field(person)
        if np.isfinite(pc) and np.isfinite(pcf):
            return self.tr("panel2", p=person, pc=pc, pcf=pcf)
        return self.tr("panel", p=person, pc=pc) if np.isfinite(pc) else person


def music_segments(data: FigureData, person: str) -> pd.DataFrame:
    """그 사람의 음악 곡 구간 가운데 T와 값이 있는 줄."""
    s = data.segments
    if not len(s):
        return pd.DataFrame(columns=["tempo_ratio_pct", "dC_pct", "sync3_pct", "playlist"])
    s = s[(s["participant"] == person) & (s["condition"] != "S")]
    return s[np.isfinite(pd.to_numeric(s["tempo_ratio_pct"], errors="coerce"))
             & np.isfinite(pd.to_numeric(s["dC_pct"], errors="coerce"))]  # 걸음이 모자란 구간(D-08)은 값이 없다


def stages(data: FigureData, person: str) -> pd.DataFrame:
    """그 사람의 실험 2 단계(무음 제외)를 T 순서로. gait는 walk·run·mixed 또는 빈칸(판정하지 못함)."""
    s = data.summary
    if not len(s):
        return pd.DataFrame(columns=["tempo_ratio_pct"])
    s = s[(s["runner"] == person) & s["ratio_pct"].astype(str).str.replace(".", "", 1).str.isdigit()].copy()
    s["gait"] = s["gait_video"].fillna("").astype(str) if "gait_video" in s else ""
    return s[np.isfinite(s["tempo_ratio_pct"].astype(float))].sort_values("tempo_ratio_pct").reset_index(drop=True)


def first_run_t(st: pd.DataFrame) -> float:
    """영상 판정이 처음 뛰기(또는 섞임)인 단계의 T. 없으면 NaN."""
    run = st[st["gait"].isin(["run", "mixed"])] if len(st) else st
    return float(run["tempo_ratio_pct"].iloc[0]) if len(run) else NAN


def _rx(data: FigureData, person: str) -> tuple[float, float]:
    p = data.prescription
    if not len(p):
        return NAN, NAN
    p = p[(p["participant"] == person) & (p["row_type"] == "summary")]
    if not len(p):
        return NAN, NAN
    return float(p["t_low_pct"].iloc[0]), float(p["t_high_pct"].iloc[0])


def _pend(data: FigureData, person: str) -> dict:
    p = data.pendulum[data.pendulum["runner"] == person] if len(data.pendulum) else data.pendulum
    return p.iloc[0].to_dict() if len(p) else {}


def _panels(fig: Figure, n: int):
    axes = fig.subplots(1, max(n, 1), sharex=True, sharey=True, squeeze=False)[0]
    for ax in axes[1:]:
        ax.tick_params(labelleft=False)
    return axes


def _xlim(ax, values: list[float], lo: float, hi: float) -> None:
    """가로축 범위: 끝 눈금 글자가 옆 패널과 겹치지 않게 양쪽에 조금 여유를 둔다."""
    a, b = _span(values, lo, hi, 10)
    ax.set_xlim(a - 4, b + 4)


def _stage_marks(ax, st: pd.DataFrame, y: str, color: str) -> None:
    """실험 2 단계: 굵은 선 + 걸음새별 표식(걷기 ●, 뛰기 ▲, 판정하지 못함 ◇)."""
    ax.plot(st["tempo_ratio_pct"], st[y], color=color, lw=2.0, zorder=3)
    for gait, mark in (("walk", "o"), ("run", "^"), ("mixed", "^"), ("", "D")):
        d = st[st["gait"] == gait]
        ax.scatter(d["tempo_ratio_pct"], d[y], marker=mark, s=34, zorder=4, linewidths=1.2, edgecolors=color,
                   facecolors="white" if gait == "" else color)


def _stage_handles(data: FigureData, sts: list[pd.DataFrame]) -> list:
    gaits = {g for s in sts for g in s.get("gait", [])}
    out = []
    for key, gs, mark, hollow in (("exp2_walk", {"walk"}, "o", False), ("exp2_run", {"run", "mixed"}, "^", False),
                                  ("exp2_unknown", {""}, "D", True)):
        if gaits & gs:
            out.append(Line2D([], [], color=OTHER, lw=2.0, marker=mark, ms=5.5, mfc="white" if hollow else OTHER,
                              mec=OTHER, label=data.tr(key)))
    return out


def fig2_tempo_map(data: FigureData) -> tuple[Figure, dict]:
    """그림 2 '템포 지도': 1인 1패널. 실험 1 곡 구간은 점, 실험 2 단계는 선."""
    people = data.people()
    fig = Figure(figsize=(8.0, 3.9))
    axes = _panels(fig, len(people))
    summary, sts, flags = {}, [], set()
    for ax, p in zip(axes, people, strict=False):
        c, pc, ses = data.color(p), data.pc(p), data.sesoi(p)
        seg, st = music_segments(data, p), stages(data, p)
        sts.append(st)
        ax.plot([0, 400], [0, 400], color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
        if np.isfinite(ses):
            ax.axhspan(100 - ses, 100 + ses, color="#c9cfcc", alpha=0.7, lw=0, zorder=0)
            flags.add("band")
        if len(seg):
            ax.scatter(seg["tempo_ratio_pct"], 100 + seg["dC_pct"].astype(float), s=12, color=c, alpha=0.55, lw=0,
                       zorder=2)
            flags.add("seg")
        if len(st):
            st = st.assign(y=100 + st["dC_pct"].astype(float))
            _stage_marks(ax, st, "y", c)
        pend = _pend(data, p)
        lines = {}
        for key, col, ls in (("pend_straight", "cadence_pend_spm", (0, (1, 2))), ("pend_bent", "cadence_pend_bent_spm",
                                                                                (0, (3, 1, 1, 1)))):
            v = float(pend.get(col, NAN))
            if np.isfinite(v) and np.isfinite(pc):
                ax.axhline(v / pc * 100, color=INK, lw=1.0, ls=ls, zorder=1)
                lines[key] = v / pc * 100
                flags.add(key)
        t_run = first_run_t(st)
        if np.isfinite(t_run):
            ax.axvline(t_run, color=INK, lw=0.9, ls="-", zorder=1)
            flags.add("first_run")
        lo, hi = _rx(data, p)
        if np.isfinite(lo) and np.isfinite(hi) and hi >= lo:
            ax.axvspan(lo, hi, ymin=0, ymax=0.06, color=INK, lw=0, zorder=5)
            flags.add("rx")
        elif np.isfinite(lo):
            ax.plot([lo], [0.03], marker="^", ms=6, color=INK, transform=ax.get_xaxis_transform(), clip_on=False,
                    zorder=5)
            flags.add("rx_low")
        ax.set_title(data.panel_title(p), loc="left")
        ax.set_xlabel(data.tr("t_axis"))
        summary[p] = dict(pc_spm=pc, pc_field_spm=data.pc_field(p), sesoi_pct=ses, n_segments=len(seg),
                          segments_t_pct=_r(seg["tempo_ratio_pct"]), segments_cadence_pct=_r(100 + seg["dC_pct"]),
                          stages_t_pct=_r(st.get("tempo_ratio_pct", [])), stages_cadence_pct=_r(st.get("y", [])),
                          stages_gait=list(st.get("gait", [])), pendulum_pct=lines, first_run_t_pct=t_run,
                          prescription_t_pct=[lo, hi])
    xs = [x for s in summary.values() for x in s["segments_t_pct"] + s["stages_t_pct"]]
    ys = [y for s in summary.values() for y in s["segments_cadence_pct"] + s["stages_cadence_pct"]
          + list(s["pendulum_pct"].values())]
    _xlim(axes[0], xs, 80, 200)
    lo_y, hi_y = _span(ys, 70, 180, 10)
    axes[0].set_ylim(lo_y, hi_y + 5)
    axes[0].set_ylabel(data.tr("cad_axis"))
    handles = []
    if "seg" in flags:
        handles.append(Line2D([], [], color=OTHER, lw=0, marker="o", ms=4, alpha=0.6, label=data.tr("exp1_seg")))
    handles += _stage_handles(data, sts)
    handles.append(Line2D([], [], color=MUTED, lw=0.8, ls=(0, (4, 3)), label=data.tr("diag")))
    if "band" in flags:
        handles.append(Patch(color="#c9cfcc", alpha=0.7, lw=0, label=data.tr("band")))
    for key, ls in (("pend_straight", (0, (1, 2))), ("pend_bent", (0, (3, 1, 1, 1)))):
        if key in flags:
            handles.append(Line2D([], [], color=INK, lw=1.0, ls=ls, label=data.tr(key)))
    if "first_run" in flags:
        handles.append(Line2D([], [], color=INK, lw=0.9, label=data.tr("first_run")))
    if "rx" in flags:
        handles.append(Patch(color=INK, lw=0, label=data.tr("rx")))
    if "rx_low" in flags:
        handles.append(Line2D([], [], color=INK, lw=0, marker="^", ms=5, label=data.tr("rx_low")))
    _finish(fig, data, "fig2", handles, bottom=0.31, note=data.tr("basis"))
    return fig, summary


def fig3b_sync(data: FigureData, params: Params) -> tuple[Figure, dict]:
    """그림 3b: 실험 1 곡 구간(점, 플레이리스트 평균은 가는 선)과 실험 2 단계(굵은 선)의 동조율을 T로 나란히."""
    people = data.people()
    fig = Figure(figsize=(8.0, 3.7))
    axes = _panels(fig, len(people))
    near, need = params["sync.near_pc_pct"], params["exp2.h1_2_min_sync_frac"] * 100
    summary, sts, flags = {}, [], set()
    for ax, p in zip(axes, people, strict=False):
        c = data.color(p)
        seg, st = music_segments(data, p), stages(data, p)
        seg = seg[np.isfinite(pd.to_numeric(seg["sync3_pct"], errors="coerce"))] if len(seg) else seg
        st = st[np.isfinite(st["sync3_pct"].astype(float))] if len(st) else st
        sts.append(st)
        ax.axvspan(100 - near, 100 + near, color="#e6e9e7", lw=0, zorder=0)
        ax.axhline(need, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
        means = pd.DataFrame(columns=["t", "s3"])
        if len(seg):
            ax.scatter(seg["tempo_ratio_pct"], seg["sync3_pct"], s=12, color=c, alpha=0.55, lw=0, zorder=2)
            means = (seg.groupby("playlist").agg(t=("tempo_ratio_pct", "mean"), s3=("sync3_pct", "mean"))
                     .sort_values("t"))
            ax.plot(means["t"], means["s3"], color=c, lw=1.0, marker="s", ms=4.5, mfc="white", mec=c, zorder=3)
            flags.add("seg")
        if len(st):
            _stage_marks(ax, st, "sync3_pct", c)
        ax.set_title(data.panel_title(p), loc="left")
        ax.set_xlabel(data.tr("t_axis"))
        summary[p] = dict(n_segments=len(seg), segments_t_pct=_r(seg.get("tempo_ratio_pct", [])),
                          segments_s3_pct=_r(seg.get("sync3_pct", [])), playlist_mean_t_pct=_r(means["t"]),
                          playlist_mean_s3_pct=_r(means["s3"]), stages_t_pct=_r(st.get("tempo_ratio_pct", [])),
                          stages_s3_pct=_r(st.get("sync3_pct", [])), stages_gait=list(st.get("gait", [])))
    xs = [x for s in summary.values() for x in s["segments_t_pct"] + s["stages_t_pct"]]
    _xlim(axes[0], xs, 80, 200)
    axes[0].set_ylim(-3, 103)
    axes[0].set_ylabel(data.tr("s3_axis"))
    handles = []
    if "seg" in flags:
        handles += [Line2D([], [], color=OTHER, lw=0, marker="o", ms=4, alpha=0.6, label=data.tr("exp1_seg")),
                    Line2D([], [], color=OTHER, lw=1.0, marker="s", ms=4.5, mfc="white", label=data.tr("exp1_mean"))]
    handles += _stage_handles(data, sts)
    handles += [Line2D([], [], color=MUTED, lw=0.8, ls=(0, (4, 3)), label=data.tr("h12", x=need)),
                Patch(color="#e6e9e7", lw=0, label=data.tr("near_pc"))]
    _finish(fig, data, "fig3b", handles, bottom=0.29, note=data.tr("basis"))
    return fig, dict(panels=summary, h12_criterion_pct=need, near_pc_pct=near)


def fig6_speed_flight(data: FigureData, params: Params) -> tuple[Figure, dict]:
    """그림 6: 위는 단계별 속도(선)와 Froude 수(같은 축의 오른쪽 눈금), 아래는 체공 시간(막대)."""
    people = [p for p in data.people() if len(stages(data, p))]
    fig = Figure(figsize=(7.2, 5.6))
    n = max(len(people), 1)
    axes = fig.subplots(2, n, sharex=True, sharey="row", squeeze=False, gridspec_kw=dict(height_ratios=[3, 2]))
    lim, g = params["stats.froude_walk_run"], params["constants.g"]
    summary, sts, flags = {}, [], set()
    for k, p in enumerate(people):
        top, low = axes[0][k], axes[1][k]
        c = data.color(p)
        st = stages(data, p)
        sts.append(st)
        _stage_marks(top, st, "v_ms", c)
        ok = st[np.isfinite(st["fr"].astype(float)) & (st["fr"].astype(float) > 0)]
        leg = float((ok["v_ms"] ** 2 / (g * ok["fr"])).median()) if len(ok) else NAN  # Fr = v² ÷ (g L)
        v_half = math.sqrt(lim * g * leg) if np.isfinite(leg) else NAN
        if np.isfinite(leg):
            top.axhline(v_half, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
            sec = top.secondary_yaxis("right", functions=(lambda v, L=leg: np.asarray(v) ** 2 / (g * L),
                                                          lambda f, L=leg: np.sqrt(np.clip(f, 0, None) * g * L)))
            sec.set_ticks([0.1, 0.25, 0.5, 1.0, 1.5, 2.0], ["0.1", "0.25", "0.5", "1.0", "1.5", "2.0"])
            sec.tick_params(labelsize=7.5, colors=MUTED)
            sec.set_ylabel(data.tr("fr_axis"), color=INK)
        tf = st["flight_time_median_s"].astype(float)
        video = st.get("phase_source", pd.Series("", index=st.index)).fillna("").astype(str) == "video"
        frac = st.get("flight_step_frac", pd.Series(NAN, index=st.index)).astype(float)
        for src, hatch, key in ((~video, None, "tf_phone"), (video, "////", "tf_video")):
            d = st[src & np.isfinite(tf)]
            if len(d):
                low.bar(d["tempo_ratio_pct"], d["flight_time_median_s"], width=8, color=c, edgecolor="white", lw=1.0,
                        hatch=hatch, zorder=3)
                flags.add(key)
        none = st[~np.isfinite(tf) & (frac > 0)]
        if len(none):
            low.scatter(none["tempo_ratio_pct"], np.zeros(len(none)), marker="x", s=30, color=INK, lw=1.2, zorder=4,
                        clip_on=False)
            flags.add("tf_none")
        top.set_title(data.panel_title(p), loc="left")
        low.set_xlabel(data.tr("stage_axis"))
        summary[p] = dict(stages_t_pct=_r(st["tempo_ratio_pct"]), speed_ms=_r(st["v_ms"], 3), froude=_r(st["fr"], 3),
                          gait=list(st["gait"]), leg_length_m=leg, speed_at_fr_limit_ms=v_half,
                          flight_time_s=_r(tf, 3), flight_source=list(st.get("phase_source", pd.Series(
                              "", index=st.index)).fillna("")), flight_step_frac=_r(frac, 3))
    axes[0][0].set_ylabel(data.tr("v_axis"))
    axes[1][0].set_ylabel(data.tr("tf_axis"))
    tfs = [x for s in summary.values() for x in s["flight_time_s"] if np.isfinite(x)]
    axes[1][0].set_ylim(0, max(0.15, max(tfs, default=0) * 1.25))
    xs = [x for s in summary.values() for x in s["stages_t_pct"]]
    _xlim(axes[1][0], xs, 90, 200)
    handles = _stage_handles(data, sts) + [Line2D([], [], color=MUTED, lw=0.8, ls=(0, (4, 3)),
                                                  label=data.tr("fr_half", x=lim))]
    if "tf_phone" in flags:
        handles.append(Patch(facecolor=OTHER, edgecolor="white", label=data.tr("tf_phone")))
    if "tf_video" in flags:
        handles.append(Patch(facecolor=OTHER, edgecolor="white", hatch="////", label=data.tr("tf_video")))
    if "tf_none" in flags:
        handles.append(Line2D([], [], color=INK, lw=0, marker="x", ms=5, label=data.tr("tf_none")))
    _finish(fig, data, "fig6", handles, bottom=0.18, top=0.9, wspace=0.36)
    return fig, dict(panels=summary, froude_walk_run=lim)


def fig7_pendulum(data: FigureData) -> tuple[Figure, dict]:
    """그림 7: 사람마다 곧은 다리 막대 2개(모델, 흔들림 실측)와 굽힌 다리 막대 2개, 실측 PC는 가로선."""
    people = [p for p in data.people() if _pend(data, p)]
    fig = Figure(figsize=(6.8, 4.2))
    ax = fig.subplots()
    ax.grid(axis="x", visible=False)
    summary, ticks, labels, tops = {}, [], [], []
    width, has_field = 0.8, False
    for k, p in enumerate(people):
        c, pend, x0 = data.color(p), _pend(data, p), k * 5.2
        bars = [("straight", "model", 120 / float(pend.get("period_model_s", NAN))),
                ("straight", "measured", float(pend.get("cadence_pend_spm", NAN))),
                ("bent", "model", 120 / float(pend.get("period_model_seg_bent_s", NAN))),
                ("bent", "measured", float(pend.get("cadence_pend_bent_spm", NAN)))]
        xs = [x0, x0 + 0.9, x0 + 2.3, x0 + 3.2]
        for x, (_, kind, v) in zip(xs, bars, strict=True):
            if not np.isfinite(v):
                continue
            ax.bar(x, v, width=width, color=c, alpha=0.38 if kind == "model" else 1.0, edgecolor="white", lw=1.0,
                   zorder=3)
            ax.text(x, v - 3, f"{v:.1f}", ha="center", va="top", fontsize=7.5, color=INK, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.9))
            tops.append(v)
        pc, pcf = data.pc(p), data.pc_field(p)
        span = (x0 - 0.6, x0 + 3.8)
        # 두 PC가 가까우면 글자가 겹친다: 큰 쪽은 선 위에, 작은 쪽은 선 아래에 적는다
        upper = "field" if np.isfinite(pcf) and (not np.isfinite(pc) or pcf >= pc) else "daily"
        for name, v, lw, ls in (("daily", pc, 1.6, "-"), ("field", pcf, 1.0, (0, (4, 3)))):
            if not np.isfinite(v):
                continue
            ax.plot(span, [v, v], color=INK, lw=lw, ls=ls, zorder=4)
            ax.text(span[1] + 0.08, v, f"{v:.1f}", ha="left", va="bottom" if name == upper else "top", fontsize=7.5,
                    color=INK)
            tops.append(v)
            has_field = has_field or name == "field"
        knee = float(pend.get("knee_deg", NAN))
        ticks += [x0 + 0.45, x0 + 2.75]
        labels += [f"{p}\n{data.tr('straight')}",
                   f"{p}\n{data.tr('bent')}" + (f" {knee:.0f}°" if np.isfinite(knee) else "")]
        summary[p] = dict(bars_spm={f"{leg}_{kind}": v for leg, kind, v in bars}, pc_spm=pc, pc_field_spm=pcf,
                          knee_deg=float(pend.get("knee_deg", NAN)))
    ax.set_xticks(ticks, labels)
    ax.set_xlim(-1.0, max(len(people), 1) * 5.2 - 0.6)
    ax.set_ylim(0, max(tops, default=100) * 1.12)
    ax.set_ylabel(data.tr("c_axis"))
    handles = [Patch(facecolor=OTHER, alpha=0.38, edgecolor="white", label=data.tr("model")),
               Patch(facecolor=OTHER, edgecolor="white", label=data.tr("measured")),
               Line2D([], [], color=INK, lw=1.6, label=data.tr("pc_daily"))]
    if has_field:
        handles.append(Line2D([], [], color=INK, lw=1.0, ls=(0, (4, 3)), label=data.tr("pc_field")))
    _finish(fig, data, "fig7", handles, bottom=0.25, top=0.9)
    return fig, dict(panels=summary)


def _r(values, nd: int = 2) -> list[float]:
    return [round(float(x), nd) for x in np.asarray(list(values), dtype=float)]


def _span(values: list[float], lo: float, hi: float, step: float) -> tuple[float, float]:
    """값을 모두 담는 축 범위(step 단위로 넓힌다). 값이 없으면 (lo, hi)."""
    v = [x for x in values if np.isfinite(x)]
    if not v:
        return lo, hi
    return math.floor((min(v) - 0.3 * step) / step) * step, math.ceil((max(v) + 0.3 * step) / step) * step


def _finish(fig: Figure, data: FigureData, key: str, handles: list, bottom: float, note: str = "", top: float = 0.86,
            wspace: float = 0.12) -> None:
    """제목, 범례(그림 아래), 주석(제목 줄 오른쪽), 합성 자료 워터마크."""
    fig.suptitle(data.tr(key), x=0.01, y=0.975, ha="left", va="top", fontsize=10, fontweight="bold")
    fig.subplots_adjust(left=0.085, right=0.93, top=top, bottom=bottom, wspace=wspace, hspace=0.12)
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.01, 0.0), ncol=3, columnspacing=1.6,
               handlelength=2.2)
    if note:
        fig.text(0.99, 0.968, note, ha="right", va="top", fontsize=7.5, color=MUTED)
    if data.synthetic:
        fig.text(0.5, 0.5, "SYNTHETIC", ha="center", va="center", rotation=30, fontsize=64, color="#888888",
                 alpha=0.25, zorder=10)


FILES = {"fig2": "fig2_cadence_vs_tempo", "fig3b": "fig3b_sync_exp1_vs_exp2", "fig6": "fig6_speed_flight_froude",
         "fig7": "fig7_pendulum"}


def render_all(data: FigureData, out: Path, params: Params) -> dict[str, dict]:
    """그림 4장을 out에 PNG로, 그려진 값을 같은 이름의 JSON으로 쓴다. {그림: 요약}을 돌려준다."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    font = korean_font() if data.korean else None
    data.korean = font is not None
    done = {}
    with matplotlib.rc_context(style(font)):
        for key, make in (("fig2", lambda: fig2_tempo_map(data)), ("fig3b", lambda: fig3b_sync(data, params)),
                          ("fig6", lambda: fig6_speed_flight(data, params)), ("fig7", lambda: fig7_pendulum(data))):
            fig, summary = make()
            fig.savefig(out / f"{FILES[key]}.png", dpi=300)
            info = dict(figure=FILES[key], title=data.tr(key), synthetic=data.synthetic, font=font or "(영어 라벨)",
                        params_sha256=_sha(params.path) if params.path else "", values=summary)
            (out / f"{FILES[key]}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=_json),
                                                    encoding="utf-8")
            done[key] = info
    return done


def _json(x):
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return str(x)


def load_data(exp1_results: Path, exp23_results: Path, synthetic: bool = False) -> FigureData:
    """결과 폴더에서 그림용 표를 읽는다(없는 표는 빈 표)."""
    def table(folder: Path, name: str, **kw) -> pd.DataFrame:
        p = Path(folder) / name
        return pd.read_csv(p, **kw) if p.exists() and p.stat().st_size > 1 else pd.DataFrame()

    pres = table(exp23_results, "prescription.csv")
    return FigureData(segments=table(exp1_results, "segments.csv"), base=table(exp1_results, "participants.csv"),
                      prescription=pres if len(pres) else table(exp1_results, "prescription.csv"),
                      summary=table(exp23_results, "exp2_summary.csv", dtype={"ratio_pct": str}),
                      pendulum=table(exp23_results, "exp3_summary.csv"), field_pc=table(exp23_results, "exp2_pc.csv"),
                      synthetic=synthetic)


def make_figures(exp1_results: Path, exp23_results: Path, out: Path, params: Params, real: bool,
                 allow_unfrozen: bool = False) -> dict[str, dict]:
    """결과 폴더의 표로 핵심 그림 4장을 그린다. 실제 데이터는 분석 고정 태그가 있어야 한다(D-35)."""
    require_freeze(real, allow_unfrozen, params["freeze.tag"])
    return render_all(load_data(exp1_results, exp23_results, synthetic=not real), out, params)
