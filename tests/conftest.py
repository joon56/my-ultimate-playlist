"""공통 픽스처: 합성 zip, 실제 파일(있을 때만)."""

from pathlib import Path

import pytest

from walkmusic.config import ROOT, load_params
from walkmusic.synthetic import SynthSpec, write_zip

RAW = ROOT / "data" / "raw"
TRIAL = RAW / "_1271-10-2026-11-07_11-20-44.zip"
PRECHECK = {n: RAW / f"TEST_A_1108_{n}.zip" for n in (1, 2, 3)}


@pytest.fixture(scope="session")
def params():
    return load_params()


@pytest.fixture(scope="session")
def make_synth(tmp_path_factory):
    """SynthSpec → (zip 경로, 정답). 같은 spec은 한 번만 만든다."""
    cache: dict = {}
    base = tmp_path_factory.mktemp("synth")

    def _make(**kw):
        key = tuple(sorted((k, repr(v)) for k, v in kw.items()))
        if key not in cache:
            path = base / f"s{len(cache)}.zip"
            cache[key] = (path, write_zip(path, SynthSpec(**kw)))
        return cache[key]

    return _make


def real(path: Path):
    """실제 파일이 없으면(다른 컴퓨터, git에는 없다) 그 테스트를 건너뛴다."""
    if not path.exists():
        pytest.skip(f"실제 파일 없음: {path.name}")
    return path
