"""config 읽기와 문서·params.toml 키 일치."""

import re

import pytest

from walkmusic.config import ROOT, load_params

DOCS = ["docs/SPEC.md", "docs/QA_CHECKLIST.md", "docs/DECISIONS.md", "docs/PROTOCOL.md", "docs/DATA_FACTS.md"]


def test_load_and_types():
    p = load_params()
    assert isinstance(p["qa.min_fs_hz"], float)
    lo, hi = p["steps.detect_band_hz"]
    assert 0 < lo < hi
    assert p["cadence.primary"] in ("median", "rate")
    assert p["steps.signal"] in ("magnitude", "vertical")
    assert p["time.timezone"] == "Asia/Seoul"


def test_missing_key_raises():
    p = load_params()
    with pytest.raises(KeyError):
        p["qa.no_such_key"]
    with pytest.raises(KeyError):
        p["nosection"]


def test_doc_keys_exist_in_params():
    """문서에 `섹션.키`로 적힌 파라미터가 모두 params.toml에 있어야 한다."""
    p = load_params()
    sections = set(p.sections())
    missing = []
    for doc in DOCS:
        text = (ROOT / doc).read_text(encoding="utf-8")
        for sec, key in re.findall(r"`([a-z0-9_]+)\.([A-Za-z0-9_]+)`", text):
            if sec in sections and key not in {"csv", "md", "json", "toml", "png", "zip"} and f"{sec}.{key}" not in p:
                missing.append(f"{doc}: {sec}.{key}")
    assert not missing, missing
