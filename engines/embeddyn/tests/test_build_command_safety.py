from pathlib import Path

from embeddyn.build import compose_west_args, compose_west_command


def test_west_build_uses_argv_boundaries_for_untrusted_paths(tmp_path: Path):
    app = tmp_path / "app;touch SHOULD_NOT_RUN"
    build = tmp_path / "build dir"
    board_root = tmp_path / "boards $(echo nope)"

    args = compose_west_args("board;echo nope", app, build, board_root)

    assert args[:3] == ["west", "build", "-p"]
    assert args[args.index("-b") + 1] == "board;echo nope"
    assert str(app) in args
    assert str(build) in args
    assert f"-DBOARD_ROOT={board_root.absolute()}" in args
    assert "touch" not in args

    display = compose_west_command("board;echo nope", app, build, board_root)
    assert "'board;echo nope'" in display
    assert "'" in display
