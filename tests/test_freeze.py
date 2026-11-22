"""데이터 동결: 복사, SHA256SUMS, 덮어쓰기 거부 (SPEC §7)."""

import hashlib

import pytest

from walkmusic.freeze import freeze_results


def _results(tmp_path):
    res = tmp_path / "results"
    (res / "steps").mkdir(parents=True)
    (res / "figures").mkdir()
    (res / "segments.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (res / "steps" / "w1_steps.csv").write_text("t_s\n0.5\n", encoding="utf-8")
    (res / "run_info.json").write_text("{}", encoding="utf-8")
    (res / "figures" / "fig2.png").write_bytes(b"png")  # 그림은 동결하지 않는다(다시 만들 수 있다)
    return res


def test_freeze_copies_tables_and_writes_checksums(tmp_path):
    res = _results(tmp_path)
    target = freeze_results(res, "1.0")
    assert target == res / "frozen" / "v1.0"
    assert sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()) == [
        "SHA256SUMS", "run_info.json", "segments.csv", "steps/w1_steps.csv"]
    sums = dict(reversed(line.split("  ")) for line in (target / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
    assert sums["segments.csv"] == hashlib.sha256((res / "segments.csv").read_bytes()).hexdigest()
    assert set(sums) == {"run_info.json", "segments.csv", "steps/w1_steps.csv"}


def test_freeze_refuses_to_overwrite_and_skips_earlier_versions(tmp_path):
    res = _results(tmp_path)
    freeze_results(res, "1.0")
    with pytest.raises(FileExistsError):
        freeze_results(res, "1.0")
    second = freeze_results(res, "1.1")  # 앞 판의 동결본은 새 판에 다시 들어가지 않는다
    assert not (second / "frozen").exists() and (second / "segments.csv").exists()


def test_freeze_checks_version_and_empty_folder(tmp_path):
    with pytest.raises(ValueError):
        freeze_results(_results(tmp_path), "final")
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        freeze_results(tmp_path / "empty", "1.0")
