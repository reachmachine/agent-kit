#!/usr/bin/env python3
"""Run every kit check against a commit range and report what failed.

Usage:
    python run_all.py                 # check HEAD against its parent
    python run_all.py --base origin/main --head HEAD
    python run_all.py --list          # show which checks are active and why
    python run_all.py --only duplicate-helpers   # one check; the rest run elsewhere

Exit code 0 = clean, 1 = at least one check failed, 2 = the kit is misconfigured.
A misconfiguration is deliberately NOT a pass: a check that could not run must
never look like a check that ran and found nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_duplicate_helpers  # noqa: E402
import check_file_growth  # noqa: E402
import check_rule3  # noqa: E402
import check_ticket_key  # noqa: E402
import git_ctx  # noqa: E402
from kit_config import Config, ConfigError  # noqa: E402


# Name -> runner. --list prints the names; --only picks from them.
CHECKS = {
    "ticket-key": lambda ctx, config: check_ticket_key.run(ctx, config),
    "rule3": lambda ctx, config: check_rule3.run(ctx),
    "file-growth": lambda ctx, config: check_file_growth.run(ctx, config),
    "duplicate-helpers": lambda ctx, config: check_duplicate_helpers.run(ctx, config),
}


def collect(
    ctx: git_ctx.Context, config: Config, only: list[str] | None = None
) -> dict[str, list[str]]:
    """Run each check, or only the named ones. Key = check name, value = its problems."""
    names = [name for name in CHECKS if only is None or name in only]
    return {name: CHECKS[name](ctx, config) for name in names}


def _report(results: dict[str, list[str]]) -> int:
    failed = {name: items for name, items in results.items() if items}
    for name, items in results.items():
        mark = "FAIL" if items else "ok"
        print(f"[{mark:>4}] {name}")
        for item in items:
            print(f"        - {item}")
    if not failed:
        print(f"\nAll {len(results)} checks passed.")
        return 0
    print(f"\n{len(failed)} of {len(results)} checks failed.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--list", action="store_true", help="show active checks")
    parser.add_argument(
        "--only", action="append", choices=list(CHECKS), metavar="NAME",
        help="run only this check (repeatable). The others are skipped, not passed -- "
        "for a repository that already runs its own copy of them.",
    )
    args = parser.parse_args(argv)

    try:
        config = Config.load(Path(args.repo).resolve())
    except ConfigError as exc:
        print(f"Kit misconfigured: {exc}", file=sys.stderr)
        return 2

    if args.list:
        print(f"config: {config.path}")
        for name in CHECKS:
            print(f"  {name}")
        return 0

    try:
        ctx = git_ctx.from_git(Path(args.repo).resolve(), args.base, args.head)
    except git_ctx.GitContextError as exc:
        print(f"Cannot compare {args.base!r} to {args.head!r}: {exc}", file=sys.stderr)
        return 2
    if not ctx.changes:
        print("No changed files in range; nothing to check.")
        return 0
    try:
        results = collect(ctx, config, args.only)
    except ConfigError as exc:
        print(f"Kit misconfigured: {exc}", file=sys.stderr)
        return 2
    return _report(results)


if __name__ == "__main__":
    raise SystemExit(main())
