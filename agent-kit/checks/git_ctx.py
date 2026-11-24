"""What the checks need to know about the change under review.

Kept separate from the checks themselves so tests can build a context by hand
instead of creating throwaway git repositories.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class GitContextError(RuntimeError):
    """Git could not read the requested comparison."""


def _git(repo: Path, *args: str, required: bool = False) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        if required:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise GitContextError(detail or f"git {args[0]} failed")
        return ""

    return result.stdout.decode("utf-8", errors="replace")


@dataclass
class Change:
    """One file in the diff."""

    path: str
    lines_before: int
    lines_after: int
    added_lines: list[str] = field(default_factory=list)

    @property
    def grew(self) -> bool:
        return self.lines_after > self.lines_before

    @property
    def is_new(self) -> bool:
        return self.lines_before == 0


@dataclass
class Context:
    """Everything a check is allowed to look at."""

    repo_root: Path
    commit_message: str
    changes: list[Change]
    branch: str = ""
    # True when `head` has two or more parents. A merge commit carries git's
    # own message ("Merge branch 'x'"), so the checks that read the head
    # message alone (ticket-key, rule3) skip it; the merged commits were
    # checked on their own branch. Found wiring the local gate.
    is_merge: bool = False

    def paths(self) -> list[str]:
        return [c.path for c in self.changes]


def _count_lines(repo: Path, rev: str, path: str) -> int:
    blob = _git(repo, "show", f"{rev}:{path}")
    if not blob or "\x00" in blob:  # empty, or binary: a binary file has no helper lines
        return 0
    return blob.count("\n")


def _added_lines(repo: Path, base: str, head: str, path: str) -> list[str]:
    diff = _git(repo, "diff", "--unified=0", base, head, "--", path)
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def from_git(repo_root: Path, base: str = "HEAD~1", head: str = "HEAD") -> Context:
    """Build a Context from a real repository range."""
    repo = Path(repo_root).resolve()
    base = _git(
        repo, "rev-parse", "--verify", "--end-of-options",
        f"{base}^{{commit}}", required=True,
    ).strip()
    head = _git(
        repo, "rev-parse", "--verify", "--end-of-options",
        f"{head}^{{commit}}", required=True,
    ).strip()
    message = _git(repo, "log", "-1", "--format=%B", head)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    # "<head> <parent>..." -- three or more ids means two or more parents.
    parents = _git(repo, "rev-list", "--parents", "-n", "1", head).split()
    names = _git(repo, "diff", "--name-only", base, head, "--", required=True).split()
    changes = [
        Change(
            path=name,
            lines_before=_count_lines(repo, base, name),
            lines_after=_count_lines(repo, head, name),
            added_lines=_added_lines(repo, base, head, name),
        )
        for name in names
    ]
    return Context(
        repo_root=repo,
        commit_message=message,
        changes=changes,
        branch=branch,
        is_merge=len(parents) > 2,
    )
