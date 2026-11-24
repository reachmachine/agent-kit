"""Tests for the kit checks.

Each test builds a Context by hand, so no throwaway git repository is needed and
the suite runs anywhere in well under a second.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHECKS))

import check_duplicate_helpers  # noqa: E402
import check_file_growth  # noqa: E402
import check_rule3  # noqa: E402
import check_ticket_key  # noqa: E402
import run_all  # noqa: E402
from git_ctx import Change, Context, from_git  # noqa: E402
from kit_config import Config, ConfigError  # noqa: E402


def ctx(message: str = "fix: something", changes=None, root: Path | None = None, is_merge=False):
    return Context(
        repo_root=root or Path("/tmp"),
        commit_message=message,
        changes=list(changes or []),
        is_merge=is_merge,
    )


def cfg(**overrides):
    data = {
        "tracker": {"ticket_pattern": r"\bABC-\d+\b"},
        "limits": {"max_file_lines": 300, "file_size_exempt": []},
        "commands": {"lint": "ruff check ."},
    }
    data.update(overrides)
    return Config(data, Path("/tmp/project.yml"))


# ---------------------------------------------------------------- Rule 3


def test_rule3_flags_a_test_change_with_no_red():
    problems = check_rule3.run(ctx(changes=[Change("backend/tests/test_a.py", 10, 40)]))
    assert len(problems) == 1
    assert "Rule 3" in problems[0]


def test_rule3_accepts_pasted_red_output():
    message = "fix(api): guard null user\n\nRemoved the guard -> 3 tests RED; restored -> 41 passed."
    assert check_rule3.run(ctx(message, [Change("tests/test_a.py", 10, 40)])) == []


def test_rule3_accepts_an_explicit_exemption():
    message = "test: pin dependency floor\n\nRule3-Exempt: version floor has no runtime branch to break"
    assert check_rule3.run(ctx(message, [Change("tests/test_a.py", 0, 12)])) == []


def test_rule3_ignores_a_commit_that_touches_no_tests():
    assert check_rule3.run(ctx(changes=[Change("backend/app/main.py", 10, 40)])) == []


@pytest.mark.parametrize("word", ["credits", "required", "redis", "rendered"])
def test_rule3_is_not_fooled_by_words_containing_red(word):
    """Case-insensitive matching would pass these; that bug was measured live."""
    message = f"fix(api): handle {word} correctly"
    assert check_rule3.run(ctx(message, [Change("tests/test_a.py", 1, 9)])) != []


def test_rule3_skips_a_merge_commit():
    """git writes the merge message; each merged commit carried its own RED."""
    merged = ctx("Merge branch 'feature'", [Change("tests/test_a.py", 10, 40)], is_merge=True)
    assert check_rule3.run(merged) == []


def test_rule3_does_not_treat_a_note_named_test_as_a_test():
    """Memory notes with "test" in the file name were flagged on the first live run."""
    change = Change(".claude/agent-memory/executor/reference_local_test_env.md", 10, 20)
    assert check_rule3.run(ctx(changes=[change])) == []


# ------------------------------------------------------------ ticket key


def test_ticket_key_flags_a_fix_with_no_ticket():
    assert check_ticket_key.run(ctx("fix(api): stop the crash"), cfg()) != []


def test_ticket_key_accepts_a_named_ticket():
    assert check_ticket_key.run(ctx("fix(api): stop the crash (ABC-12)"), cfg()) == []


def test_ticket_key_accepts_a_stated_reason():
    message = "fix(api): stop the crash\n\nNo-Ticket: one-line typo found while reading"
    assert check_ticket_key.run(ctx(message), cfg()) == []


def test_ticket_key_ignores_docs_commits():
    assert check_ticket_key.run(ctx("docs: fix a typo"), cfg()) == []


def test_ticket_key_skips_a_merge_commit():
    assert check_ticket_key.run(ctx("Merge branch 'feature'", is_merge=True), cfg()) == []


def test_ticket_key_reports_a_missing_pattern_rather_than_passing():
    bare = Config({"tracker": {}}, Path("/tmp/project.yml"))
    with pytest.raises(ConfigError):
        check_ticket_key.run(ctx("fix(api): x"), bare)


# ----------------------------------------------------------- file growth


def test_file_growth_flags_an_oversized_file_that_grew():
    problems = check_file_growth.run(ctx(changes=[Change("app/big.py", 900, 940)]), cfg())
    assert len(problems) == 1
    assert "940" in problems[0]


def test_file_growth_allows_shrinking_an_oversized_file():
    """Splitting a big file must never be blocked by the size check itself."""
    assert check_file_growth.run(ctx(changes=[Change("app/big.py", 900, 420)]), cfg()) == []


def test_file_growth_flags_a_new_oversized_file():
    problems = check_file_growth.run(ctx(changes=[Change("app/new.py", 0, 480)]), cfg())
    assert "NEW file" in problems[0]


def test_file_growth_ignores_generated_files():
    changes = [Change("frontend/src/lib/api-types.gen.ts", 2000, 2600)]
    assert check_file_growth.run(ctx(changes=changes), cfg()) == []


def test_file_growth_honours_the_configured_exemption_list():
    config = cfg(limits={"max_file_lines": 300, "file_size_exempt": ["tests/contract/*"]})
    changes = [Change("tests/contract/test_x.py", 800, 900)]
    assert check_file_growth.run(ctx(changes=changes), config) == []


# ------------------------------------------------------ duplicate helpers


def test_duplicate_helper_is_flagged(tmp_path):
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("def _now():\n    return 1\n")
    change = Change("new_module.py", 0, 3, added_lines=["def _now():"])
    problems = check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path))
    assert len(problems) == 1
    assert "_now" in problems[0]


def test_a_genuinely_new_helper_is_allowed(tmp_path):
    (tmp_path / "a.py").write_text("def _now():\n    return 1\n")
    change = Change("new_module.py", 0, 3, added_lines=["def _unique_thing():"])
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path)) == []


def test_shared_modules_may_hold_the_canonical_copy(tmp_path):
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("def _now():\n    return 1\n")
    change = Change("services/shared/time.py", 0, 3, added_lines=["def _now():"])
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path)) == []


def test_a_helper_added_to_a_test_file_is_not_flagged(tmp_path):
    """Tests are not owners, so they are not subjects either."""
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("def _run():\n    return 1\n")
    change = Change("tests/test_new.py", 0, 3, added_lines=["def _run():"])
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path)) == []


def test_a_new_method_is_not_a_helper(tmp_path):
    """Only module-level defs count: a method cannot be imported instead."""
    (tmp_path / "pkg").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "pkg" / name).write_text("def add(x):\n    return x\n")
    method = Change("pkg/report.py", 0, 3, added_lines=["    def add(self, test):"])
    assert check_duplicate_helpers.run(ctx(changes=[method], root=tmp_path)) == []
    top = Change("pkg/report.py", 0, 3, added_lines=["def add(x):"])
    assert check_duplicate_helpers.run(ctx(changes=[top], root=tmp_path)) != []


def test_nested_functions_are_not_existing_owners(tmp_path):
    """A name that exists only as nested defs elsewhere is still new at module level."""
    (tmp_path / "scripts").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "scripts" / name).write_text("def outer():\n    def _read():\n        return 1\n    return _read\n")
    change = Change("scripts/new.py", 0, 3, added_lines=["def _read():"])
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path)) == []


def test_a_copy_in_another_top_level_folder_is_not_an_owner(tmp_path):
    """A script cannot import from the app, so an app function with the same name is not a copy."""
    (tmp_path / "backend").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "backend" / name).write_text("def classify(x):\n    return x\n")
    script = Change("scripts/checks/check-new.py", 0, 3, added_lines=["def classify(line):"])
    assert check_duplicate_helpers.run(ctx(changes=[script], root=tmp_path)) == []
    app = Change("backend/new_module.py", 0, 3, added_lines=["def classify(x):"])
    assert check_duplicate_helpers.run(ctx(changes=[app], root=tmp_path)) != []


def test_project_yml_can_allow_an_entry_point_name(tmp_path):
    """`check` is every scripts/checks/check-*.py's entry point, like `main`."""
    (tmp_path / "scripts").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "scripts" / name).write_text("def check():\n    return 1\n")
    change = Change("scripts/checks/check-new.py", 0, 3, added_lines=["def check():"])
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path)) != []
    allowing = cfg(limits={"max_file_lines": 300, "file_size_exempt": [], "helper_names_allowed": ["check"]})
    assert check_duplicate_helpers.run(ctx(changes=[change], root=tmp_path), allowing) == []


# ------------------------------------------------------------------ run_all


def test_only_runs_the_named_checks_and_skips_the_rest(tmp_path):
    """A repository that already runs its own ticket/rule3/size checks runs one kit check."""
    change = Change("tests/test_a.py", 1, 9)
    no_key = ctx("fix: no key here", [change], root=tmp_path)
    assert set(run_all.collect(no_key, cfg())) == set(run_all.CHECKS)
    only = run_all.collect(no_key, cfg(), only=["duplicate-helpers"])
    assert list(only) == ["duplicate-helpers"], "--only must skip the others, not report them"
    assert only["duplicate-helpers"] == []


# ------------------------------------------------------------ config lookup


@pytest.mark.parametrize(
    "layout",
    ["project.yml", "agent-kit/project.yml", ".claude/agent-kit/project.yml"],
)
def test_config_is_found_in_every_supported_layout(tmp_path, layout):
    """Install puts the kit at the repo root OR under .claude/. Both must work.

    The root layout was missed at first, so a correctly installed kit reported
    'misconfigured' for every check. Found by running the kit in a fresh repo.
    """
    target = tmp_path / layout
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("tracker:\n  ticket_pattern: '\\bZZZ-\\d+\\b'\n")
    loaded = Config.load(tmp_path)
    assert loaded.ticket_pattern == r"\bZZZ-\d+\b"


def test_a_missing_config_raises_rather_than_defaulting(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path)


def test_a_null_command_raises_naming_the_key(tmp_path):
    config = Config({"commands": {"lint": None}}, tmp_path / "project.yml")
    with pytest.raises(ConfigError, match="commands.lint"):
        config.command("lint")


def test_a_binary_file_in_the_diff_does_not_crash(tmp_path):

    def git(*a):
        subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *a],
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "one")
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\x90\x00\xff\xfe\x80")
    git("add", ".")
    git("commit", "-qm", "two")
    context = from_git(tmp_path, "HEAD~1", "HEAD")
    image = next(c for c in context.changes if c.path == "img.png")
    assert image.lines_after == 0
    assert run_all.collect(context, cfg(), only=["duplicate-helpers"]) == {"duplicate-helpers": []}
@pytest.mark.parametrize(
    ("base", "head", "expected_exit"),
    [
        ("missing-base", "HEAD", 2),
        ("HEAD", "missing-head", 2),
        ("HEAD", "HEAD", 0),
    ],
)
def test_git_range_exit_status(tmp_path, monkeypatch, capsys, base, head, expected_exit):
    git = [
        "git", "-C", str(tmp_path),
        "-c", "user.name=Test",
        "-c", "user.email=test@example.com",
    ]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "commit", "--allow-empty", "-qm", "baseline"], check=True)

    config = tmp_path / "project.yml"
    config.write_text("tracker: {ticket_pattern: '#[0-9]+'}\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_KIT_CONFIG", str(config))

    result = run_all.main(["--repo", str(tmp_path), "--base", base, "--head", head])
    output = capsys.readouterr()

    assert result == expected_exit
    if expected_exit == 2:
        assert base in output.err and head in output.err
        assert "nothing to check" not in output.out
    else:
        assert "nothing to check" in output.out