"""tools/assign.py가 data/assignment.csv를 그대로 다시 만드는지(SPEC §9 끝)."""

import csv
import importlib.util

from walkmusic.config import ROOT


def test_assignment_reproduces():
    spec = importlib.util.spec_from_file_location("assign", ROOT / "tools" / "assign.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = [tuple(str(x) for x in r) for r in mod.rows()]
    with open(ROOT / "data" / "assignment.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["participant", "walk_no", "condition", "start_song"]
    assert got == [tuple(r) for r in rows[1:]]
