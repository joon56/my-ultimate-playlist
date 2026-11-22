"""점프·진자 영상 판독 도구(tools/video, D-84)를 합성 신호로 확인한다(영상 없이)."""

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("PIL")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "video"))
import apply_pendulum_jump as apj  # noqa: E402
import jump_read as jr  # noqa: E402
import knee_read as kr  # noqa: E402
import marker_track as mt  # noqa: E402
import swing_read as sr  # noqa: E402


def test_hinge_finds_break_between_frames():
    fps = 240.0
    t = np.arange(23) / fps
    tb = 12.4 / fps  # 12번과 13번 프레임 사이
    # 닿아 있는 동안 느리게, 뜬 뒤 빠르게 올라간다
    y = np.where(t < tb, 1596.0 - 100 * (t - tb), 1596.0 - 1300 * (t - tb))
    par = (np.arange(23) % 2).astype(float)
    h = jr.hinge(t, y + 0.8 * par, par)
    assert h["tb"] == pytest.approx(tb, abs=0.25 / fps)
    assert h["parity"] == pytest.approx(0.8, abs=0.05)
    assert h["s1"] == pytest.approx(-100, abs=30) and h["s2"] == pytest.approx(-1300, abs=30)


def test_flight_time_of_synthetic_jump():
    fps, level, rise, t0, tf = 240.0, 1600.0, 250.0, 1.5021, 0.5
    t = np.arange(int(4 * fps)) / fps
    y = np.full_like(t, level)
    up = (t >= t0) & (t <= t0 + tf)
    y[up] = level - 4 * rise * (t[up] - t0) * (t0 + tf - t[up]) / tf**2  # 포물선
    res, _ = jr.flights(t, y)
    assert len(res) == 1
    assert res[0]["takeoff_s"] == pytest.approx(t0, abs=1 / fps)
    assert res[0]["flight_s"] == pytest.approx(tf, abs=1 / fps)


def test_short_hop_is_not_a_jump():
    fps = 240.0
    t = np.arange(int(4 * fps)) / fps
    y = np.full_like(t, 1600.0)
    up = (t >= 1.5) & (t <= 1.6)  # 0.1 s짜리(체공 0.20 s 미만)
    y[up] = 1600.0 - 4 * 130.0 * (t[up] - 1.5) * (1.6 - t[up]) / 0.1**2
    assert jr.flights(t, y)[0] == []


def _swing_markers(period=1.42, knee_deg=75.0, fps=60.0):
    """엉덩관절 (900, 100), 허벅지 420 px, 무릎에서 정강이 쪽 70 px에 파랑, 350 px에 노랑(y는 아래쪽이 +)."""
    t = np.arange(int(26 * fps)) / fps
    amp = np.where((t >= 2) & (t <= 22), 30.0 * np.exp(-(t - 2) / 25), 0.0)
    th = np.radians(amp * np.cos(2 * np.pi * (t - 2) / period))
    hip = np.array([900.0, 100.0])
    knee = hip + 420 * np.column_stack([np.sin(th), np.cos(th)])
    us = np.column_stack([np.sin(th - np.radians(knee_deg)), np.cos(th - np.radians(knee_deg))])
    return dict(t=t, yellow=knee + 350 * us, blue=knee + 70 * us, red=np.tile(hip + [0, -90], (len(t), 1)))


def test_swing10_is_ten_periods():
    z = _swing_markers(period=1.42)
    t, s = sr.series(z)
    for sign in (1, -1):
        tp = sr.chain(sr.extremes(t, s, sign))
        value, used = sr.swing10(tp)
        assert len(tp) >= 12 and used == (1, 11)
        assert value == pytest.approx(14.2, abs=0.03)


def test_swing10_needs_eleven_extremes():
    assert sr.swing10(np.arange(10) * 1.4) == (None, None)
    value, used = sr.swing10(np.arange(11) * 1.4)
    assert value == pytest.approx(14.0) and used == (0, 10)


def test_chain_drops_irregular_start():
    tp = np.array([0.0, 3.0, 4.4, 5.8, 7.2, 8.6, 10.0])
    assert sr.chain(tp) == pytest.approx([3.0, 4.4, 5.8, 7.2, 8.6, 10.0])


def test_knee_flexion_with_tape_below_the_joint(tmp_path):
    np.savez(tmp_path / "bent_markers.npz", **_swing_markers(knee_deg=75.0))
    # 올림 비율 = 관절~파랑 ÷ 파랑~노랑, 내림 비율 = 빨강~엉덩관절 ÷ 파랑~노랑
    info, rows, _ = kr.analyse(tmp_path, "bent", 70 / 280, 90 / 280)
    assert info["hip_center"] == pytest.approx([900.0, 100.0], abs=1.0)
    assert info["circle_center"] == pytest.approx([900.0, 100.0], abs=1.0)
    assert info["thigh_radius_px"] == pytest.approx(420.0, abs=1.0)
    assert info["flexion_mean_of_cycles"] == pytest.approx(75.0, abs=0.3)
    assert len(rows) >= 6 * info["n_cycles"] - 2 and all(r["flexion"] == pytest.approx(75.0, abs=0.5) for r in rows)
    # 테이프를 그대로 무릎으로 쓰면(올림 0) 각이 작게 나온다
    assert kr.analyse(tmp_path, "bent", 0.0, 90 / 280)[0]["flexion_mean_of_cycles"] < 70.0
    # 좌우 대칭으로 흔들면 엉덩관절 높이를 잘못 잡아도(내림 0) 평균 각은 거의 같다
    info_red, _, _ = kr.analyse(tmp_path, "bent", 70 / 280, 0.0, "red")
    assert info_red["flexion_mean_of_cycles"] == pytest.approx(75.0, abs=0.5)


def test_marker_masks_and_blobs():
    a = np.full((120, 160, 3), (120, 118, 110), np.uint8)
    a[20:40, 30:50] = (228, 220, 130)   # 노랑 테이프
    a[60:80, 90:120] = (70, 105, 195)   # 파랑 테이프
    a[90:110, 20:60] = (215, 80, 90)    # 빨강 테이프
    a[0:10, 100:140] = (235, 236, 240)  # 흰 신발(어느 색도 아니다)
    m = mt.masks(a)
    assert (int(m["yellow"].sum()), int(m["blue"].sum()), int(m["red"].sum())) == (400, 600, 800)
    ((x, y, area),) = mt.blobs(m["blue"], 100)
    assert (x, y, area) == pytest.approx((104.5, 69.5, 600.0))
    assert mt.blobs(m["blue"], 700) == []


def _write_lines(path, lines):
    path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def test_apply_keeps_rows_entered_by_people(tmp_path, monkeypatch):
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    out.mkdir()
    _write_lines(data / "exp2_trials.csv", ["trial_id,runner,ratio_pct,video_file,video_fps",
                                            "E2_B_J_1,B,J,B-JUMP.MOV,240"])
    _write_lines(data / "exp3_swings.csv", ["trial_id,runner,knee,video_file,video_fps",
                                            "E3_A_1,A,straight,A-STRAIGHT-1.MOV,60", "E3_A_K_1,A,bent,A-90-1.MOV,60"])
    _write_lines(data / "video_checks.csv", [",".join(apj.CHECK_COLS),
                                             "E3_B_1,swing_10,1,B-STRAIGHT-1.MOV,60,,14.4,B,스톱워치",
                                             f"E3_A_1,swing_10,1,A-STRAIGHT-1.MOV,60,,99.0,{apj.MEASURER},옛 값"])
    jump = dict(jump_no=1, flight_s=0.4979, takeoff_s=12.1683, landing_s=12.6662)
    (out / "B-JUMP_jumps.json").write_text(json.dumps(dict(jumps=[jump])), encoding="utf-8")
    ext = dict(n_extremes=17, swing10_s=15.066, used=[1, 11])
    few = dict(n_extremes=9, swing10_s=None, used=None)
    swings = [dict(stem="A-STRAIGHT-1", swing10_s=15.043, max=ext, min=dict(ext, swing10_s=15.021)),
              dict(stem="A-90-1", swing10_s=None, max=few, min=few)]
    (out / "swing_results.json").write_text(json.dumps(swings), encoding="utf-8")
    row = dict(event_no=1, frame_no=400, t=6.5, hip=[854.0, 112.0], knee=[800.2, 530.4], ankle=[498.0, 629.0],
               blue=[758.0, 550.0], flexion=76.0)
    knee = {"A-90-1": dict(info=dict(delta_px=71.0, drop_px=79.0), rows=[row])}
    (out / "knee_results_0.25.json").write_text(json.dumps(knee), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["apply_pendulum_jump.py", str(out)])
    apj.main()
    checks = list(csv.DictReader(open(data / "video_checks.csv", encoding="utf-8")))
    assert [(r["trial_id"], r["kind"], r["value_s"], r["measurer"]) for r in checks] == [
        ("E3_B_1", "swing_10", "14.4", "B"),
        ("E2_B_J_1", "jump_flight", "0.498", apj.MEASURER),
        ("E3_A_1", "swing_10", "15.043", apj.MEASURER)]
    marks = list(csv.DictReader(open(data / "video_markers.csv", encoding="utf-8")))
    assert len(marks) == 1 and marks[0]["trial_id"] == "E3_A_K_1" and marks[0]["event"] == "pendulum_bent"
    assert (marks[0]["hip_x"], marks[0]["knee_y"], marks[0]["ankle_x"]) == ("854.0", "530.4", "498.0")


def test_apply_numbers_jumps_by_sensor_pairing(tmp_path, monkeypatch):
    # D-87: 센서가 세지 않은 점프와 읽지 못한 점프는 줄을 만들지 않고, 번호는 센서의 점프 번호를 따른다
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    out.mkdir()
    _write_lines(data / "exp2_trials.csv", ["trial_id,runner,ratio_pct,video_file,video_fps",
                                            "E2_A_J_2,A,J,A-JUMP.MOV,240"])
    _write_lines(data / "exp3_swings.csv", ["trial_id,runner,knee,video_file,video_fps"])
    flights = ((1, 0.53), (2, 0.60), (3, 0.51))
    jumps = [dict(jump_no=k, flight_s=v, takeoff_s=10.0 * k, landing_s=10.0 * k + v) for k, v in flights]
    (out / "A-JUMP_jumps.json").write_text(json.dumps(dict(jumps=jumps)), encoding="utf-8")
    pairing = dict(pairs={"2": 1, "3": 2}, unread={"2": "착지 꺾이는 점을 찾지 못함"}, note="이륙 간격으로 짝지음")
    (out / "A-JUMP_pairing.json").write_text(json.dumps(pairing, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["apply_pendulum_jump.py", str(out)])
    apj.main()
    checks = list(csv.DictReader(open(data / "video_checks.csv", encoding="utf-8")))
    assert [(r["trial_id"], r["event_no"], r["value_s"]) for r in checks] == [("E2_A_J_2", "2", "0.510")]
    assert "영상의 3번째 점프" in checks[0]["notes"] and "이륙 간격으로 짝지음" in checks[0]["notes"]
