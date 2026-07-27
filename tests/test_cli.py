from playwright_locators_forge.cli import build_parser, main


def test_root_argument_before_subcommand():
    args = build_parser().parse_args(["--root", "some/path", "scan"])
    assert args.root == "some/path"


def test_root_argument_after_subcommand():
    args = build_parser().parse_args(["scan", "--root", "some/path"])
    assert args.root == "some/path"


def test_root_argument_defaults_to_cwd():
    args = build_parser().parse_args(["scan"])
    assert args.root == "."


def test_root_argument_after_subcommand_for_every_command():
    for command, extra in [
        ("scan", []),
        ("rank", []),
        ("resolve", ["--page", "x", "--element", "y"]),
        ("check", []),
        ("init", []),
    ]:
        args = build_parser().parse_args([command, "--root", "some/path", *extra])
        assert args.root == "some/path", f"failed for {command}"


def test_scan_and_resolve_end_to_end(tmp_path):
    (tmp_path / "about.tsx").write_text(
        'export function About() { return <button data-testid="submit-btn">Go</button>; }'
    )

    exit_code = main(["--root", str(tmp_path), "scan", "--framework", "react"])
    assert exit_code == 0
    assert (tmp_path / "locators" / "INDEX.md").exists()

    exit_code = main(["--root", str(tmp_path), "resolve", "--page", "about", "--element", "submit-btn"])
    assert exit_code == 0


def test_resolve_missing_element_returns_nonzero(tmp_path):
    (tmp_path / "about.tsx").write_text("export function About() { return <div />; }")
    main(["--root", str(tmp_path), "scan", "--framework", "react"])
    exit_code = main(["--root", str(tmp_path), "resolve", "--page", "about", "--element", "nope"])
    assert exit_code == 1


def test_check_reports_no_drift_on_fresh_scan(tmp_path):
    (tmp_path / "about.tsx").write_text(
        'export function About() { return <button data-testid="go">Go</button>; }'
    )
    main(["--root", str(tmp_path), "scan", "--framework", "react"])
    exit_code = main(["--root", str(tmp_path), "check"])
    assert exit_code == 0


def test_check_without_prior_scan_fails(tmp_path):
    exit_code = main(["--root", str(tmp_path), "check"])
    assert exit_code == 1


def test_init_writes_templates(tmp_path):
    exit_code = main(["--root", str(tmp_path), "init"])
    assert exit_code == 0
    assert (tmp_path / "locator-priority.yaml").exists()
    assert (tmp_path / ".locatorsforge.yaml").exists()
    assert (tmp_path / "AGENTS.forge-snippet.md").exists()


def test_init_does_not_overwrite_without_force(tmp_path):
    (tmp_path / "locator-priority.yaml").write_text("custom content")
    main(["--root", str(tmp_path), "init"])
    assert (tmp_path / "locator-priority.yaml").read_text() == "custom content"


def test_init_overwrites_with_force(tmp_path):
    (tmp_path / "locator-priority.yaml").write_text("custom content")
    main(["--root", str(tmp_path), "init", "--force"])
    assert (tmp_path / "locator-priority.yaml").read_text() != "custom content"


def test_rank_without_prior_scan_fails(tmp_path):
    exit_code = main(["--root", str(tmp_path), "rank"])
    assert exit_code == 1


def test_rank_reranks_without_rescanning_source(tmp_path):
    (tmp_path / "about.tsx").write_text(
        'export function About() { return <button data-testid="go" id="go-id">Go</button>; }'
    )
    main(["--root", str(tmp_path), "scan", "--framework", "react"])

    (tmp_path / "locator-priority.yaml").write_text("priority:\n  1: id\n  2: testId\n")
    # delete source so a rank-triggered rescan (bug) would produce 0 elements
    (tmp_path / "about.tsx").unlink()

    exit_code = main(["--root", str(tmp_path), "rank"])
    assert exit_code == 0
    locator = None
    for line in (tmp_path / "locators" / "about.md").read_text().splitlines():
        if line.startswith("| 1 |"):
            locator = line
            break
    assert locator is not None
    assert "id" in locator.split("|")[2]
