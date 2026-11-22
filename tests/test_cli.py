"""명령줄 옵션 (SPEC §10)."""

from walkmusic.cli import _build_parser


def test_exp23_command_options():
    a = _build_parser().parse_args(["exp23", "--links", "--date", "2026-11-21"])
    assert (a.command, a.links, a.date, a.synthetic, a.allow_unfrozen) == ("exp23", True, "2026-11-21", False, False)


def test_report_and_freeze_command_options():
    p = _build_parser()
    for name in ("validation", "sensitivity", "figures"):
        a = p.parse_args([name, "--synthetic"])
        assert (a.command, a.synthetic, a.allow_unfrozen) == (name, True, False)
    assert p.parse_args(["freeze", "--version", "1.0"]).version == "1.0"
