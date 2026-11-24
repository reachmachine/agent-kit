# agent-kit

**Four AI coding agent roles, and the checks that make their rules stick.**

[![tests](https://github.com/reachmachine/agent-kit/actions/workflows/tests.yml/badge.svg?branch=agent-reuse)](https://github.com/reachmachine/agent-kit/actions/workflows/tests.yml)

You wrote the rule down. Your coding agent read it. Then it skipped it.

This kit is our answer to that. It gives you four agent roles (architect,
executor, reviewer, retro), and it turns the rules that matter into small
scripts that fail a commit. A rule in a prompt is a suggestion. A script that
turns the build red is a rule.

Open source, MIT licence. One folder to copy, one config file to fill in.

## Why we built it

We ran this pattern on one real project for six weeks: 3,275 commits, 1,374
agent sessions, 1,114 tickets closed. Then we measured what the agents did
against what the rules said.

| What we measured | Result |
|---|---|
| The one rule that had a script behind it | held on **100%** of commits |
| The prose rules beside it | held on **58%** |
| Unreviewed commits on the deploy branch | **71** |
| Safety refusals worked around within three tool calls | **90%** |
| Changes that self-review passed | **94%** |
| Of those, later recorded as a miss by the same author | **21%** |
| Modules holding their own copy of one helper, `_now` | **22** |

Two findings shaped everything in this repository:

1. **Rules with a script behind them held. Rules written as prose did not.**
   So a rule that matters becomes a check, and the charter keeps only what no
   script can express.
2. **The author cannot grade their own work.** So the reviewer never sees the
   plan. It gets the ticket, the diff and the commit messages, and nothing else.

> These numbers come from our own audit of one private codebase. The data
> behind them is not public. Read them as one team's measurement, not a
> benchmark.

## What you get

The kit lives in the `agent-kit/` folder.

| Piece | What it is |
|---|---|
| `agents/architect.md` | Designs, decides and writes the spec. Never writes implementation code. |
| `agents/executor.md` | Builds one spec end to end in its own worktree, with its tests. |
| `agents/reviewer.md` | Judges the diff cold. Never sees the author's reasoning. |
| `agents/retro.md` | Meant to run weekly. Turns recorded mistakes into new checks. Never merges its own pull request. |
| `charter-core.md` | The rules that are true in any codebase. 131 lines, inside a 150-line budget. |
| `project.example.yml` | The one file you fill in per project: names, branches, commands. |
| `checks/` | Four checks, one runner, 36 tests. |
| `defects/` | The record format the retro role learns from. |

The checks are plain Python and git. They read commits, so they work the same
whether a person or an agent wrote the change.

Also in this repository:

| Piece | What it is |
|---|---|
| `requirements.txt` | The one package the checks need: PyYAML. |
| `requirements-dev.txt` | That, plus pytest for the tests. |
| [`TOOLS.md`](TOOLS.md) | How to set up Serena and graphify, two code-search tools, next to the kit. |
| `tools/codemap/` | An early library that will map where data is read and written. Storage layer only, with no command to run yet. |

## See it catch something

This is real output from a trial repository. First, a commit whose message is
`fix: add subtraction`:

```
$ python3 .claude/agent-kit/checks/run_all.py
[FAIL] ticket-key
        - No ticket named. Put the ticket id in the commit subject (pattern '\\bABC-\\d+\\b'), or add a line 'No-Ticket: <reason>' so the choice is on the record.
[  ok] rule3
[  ok] file-growth
[  ok] duplicate-helpers

1 of 4 checks failed.
```

Change the message to `fix: add subtraction (ABC-12)` and the same command
prints `All 4 checks passed.`

The other three checks, each from its own run in the same trial:

```
[FAIL] rule3
        - Rule 3: this commit changes tests but shows no failing run. Files: tests/test_app.py. Break the code the test covers, paste the RED output into the commit message, restore it and confirm GREEN. If the behaviour genuinely cannot be broken, add a 'Rule3-Exempt: <reason>' line saying why.

[FAIL] file-growth
        - big.py is a NEW file of 320 lines, over the 300-line limit. Split it before committing.

[FAIL] duplicate-helpers
        - svc/c.py adds '_now', which already exists in 2+ modules (svc/b.py, svc/a.py). Import the existing one, or move it to a shared module — do not write a third copy.
```

## Install

You need Python 3.10 or newer, git, and one package, PyYAML.

```bash
# 1. Get the kit, next to your repository, and install PyYAML
git clone https://github.com/reachmachine/agent-kit.git
python3 -m pip install -r agent-kit/requirements.txt

# 2. From the root of your repository
cd your-repo
mkdir -p .claude/agents
cp -r ../agent-kit/agent-kit .claude/agent-kit
cp .claude/agent-kit/agents/*.md .claude/agents/
cp .claude/agent-kit/project.example.yml .claude/agent-kit/project.yml

# 3. Check the install
python3 .claude/agent-kit/checks/run_all.py --list
```

If pip stops with an `externally-managed-environment` error, as the system
Python on recent Debian and Ubuntu does, make a virtual environment first and
run the commands on this page inside it:

```bash
python3 -m venv .venv
. .venv/bin/activate
```

If `python3 -m venv` fails too, its error message names the system package
that is missing. On our test box that was `python3-venv`.

Step 2 overwrites any file named `architect.md`, `executor.md`, `reviewer.md`
or `retro.md` that is already in `.claude/agents/`. Move yours aside first.

Step 3 prints the config file it found and the four check names.

**4. Fill in `.claude/agent-kit/project.yml`.** Set `tracker.ticket_pattern` at
least. It is a regular expression that a commit message must match:

```yaml
tracker:
  ticket_pattern: '\bABC-\d+\b'   # tickets like ABC-123
  # ticket_pattern: '#\d+'        # GitHub issues like #123
```

While it is still `null`, a run on a commit that needs a ticket stops with exit
code 2 and names the missing key. It does not pass. Every other value may stay
`null`: the role files tell the agents to report **NOT RUN** for that step,
with the reason, and not to invent a command.

**5. Commit the kit.** It brings its own test file, so its own `rule3` check
asks for proof on that commit. Say why there is none:

```bash
git add .claude
git commit -m "chore: add the agent kit" -m "Rule3-Exempt: the kit arrives with its own tests, unchanged"
python3 .claude/agent-kit/checks/run_all.py
```

That prints `All 4 checks passed.`

The kit also works from the repository root (`agent-kit/` in place of
`.claude/agent-kit/`). The runner finds `project.yml` in both places.

The folder has its own short README. Its commands are written relative to the
folder that holds `agent-kit/`. The commands on this page are run from your
repository root, and they are the ones this page was tested with.

## Run it in CI

```bash
python3 .claude/agent-kit/checks/run_all.py --base origin/main --head HEAD
```

| Exit code | Meaning |
|---|---|
| 0 | clean, or nothing in the range to check |
| 1 | at least one check failed |
| 2 | The kit could not run because of a configuration error or an invalid Git comparison. |

**Give the job the full git history.** In GitHub Actions that is
`fetch-depth: 0` on the checkout step. "Honest limits" below says what happens
without it.

Already run some of these checks your own way? Run one and skip the rest:

```bash
python3 .claude/agent-kit/checks/run_all.py --only duplicate-helpers
```

## The four checks

| Check | Fails a change when | The way out, on the record |
|---|---|---|
| `ticket-key` | its last commit names no ticket, and is not a `docs`, `chore`, `style`, `ci`, `build`, `revert` or `merge` commit | a `No-Ticket: <reason>` line |
| `rule3` | it touches a test file and the last commit message shows no failing run (the word `RED`) | a `Rule3-Exempt: <reason>` line |
| `file-growth` | a file ends over the size limit and grew in this change (a new file counts) | a glob in `limits.file_size_exempt` |
| `duplicate-helpers` | it adds a Python helper whose name already exists in two or more modules | a name in `limits.helper_names_allowed` (add the key yourself; the example file does not list it) |

Every way out is a line someone can read later.

## How a lesson becomes permanent

**A lesson is learned only when it is a check that can fail.** Every recorded
mistake sits on one of four rungs:

1. **A note** in memory. Weakest. It relies on someone reading it.
2. **A line in a checklist** the role must tick, with its evidence.
3. **A script** that fails the commit or the pull request.
4. **A setting** the agent cannot bypass at all.

A mistake that repeats three times in 30 days moves up one rung (three is the
default; you set it). That is the retro role's job: one pull request per new
check, approved by a person. A check that has blocked nothing in 90 days is
proposed for deletion, so the rulebook shrinks as well as grows.

## Honest limits

- **Built for Claude Code.** The role files are markdown with a YAML header,
  made for the `.claude/agents/` folder. The headers ask for project memory
  and, for the executor, its own worktree. Whether your tool honours those
  depends on the tool and its version. With another agent tool, use the text
  as the system prompt.
- **The role files are short on purpose.** 45 to 69 lines each. Our own
  working copies are longer and full of project detail. These are the parts
  that carry over to any codebase.
- **Charter path.** The role files name the charter as
  `agent-kit/charter-core.md`. Installed under `.claude/`, the real path is
  `.claude/agent-kit/charter-core.md`. If your agent does not find it, fix the
  `agent-kit/` paths in the four role files (7 lines).
- **Last commit only.** `ticket-key` and `rule3` read the message of the last
  commit in the range, and skip a merge commit. `file-growth` and
  `duplicate-helpers` read every changed file in the range.
- - **An unavailable revision exits 2.** If Git cannot resolve the base or head
  commit, the runner reports the requested comparison and exits 2. A valid
  comparison with no changed files still exits 0.
- **`rule3` checks the words, not the run.** It looks for `RED` or
  `Rule3-Exempt:` in the message. It cannot tell whether the failing run was
  real. That is the reviewer's job.
- **`duplicate-helpers` reads Python only.** It compares module-level `def`
  names in `.py` files inside the same top-level folder.
- **No tracker client and no scheduler.** The role files tell agents to claim
  work in your tracker, and the retro role is written to run weekly. The kit
  ships no code that talks to a tracker or starts an agent. The checks only
  match `ticket_pattern` against commit messages.
- **Tested on Linux only.** The tests run in CI on Python 3.10 to 3.13.
- **Serena and graphify are not wired in.** The role files and the charter do
  not mention either tool. [TOOLS.md](TOOLS.md) shows the setup we ran and
  what we did not test.
- **`tools/codemap/` is not usable yet.** It is a library and its tests, with
  no command to run.

## Run the tests

From the root of this repository:

```bash
python3 -m pip install -r requirements-dev.txt
(cd agent-kit/checks && python3 -m pytest tests/ -q)
(cd tools/codemap && python3 -m pytest -q)
```

36 kit tests and 49 codemap tests. Each kit test builds its case by hand, so
that suite needs no network. The codemap tests run `git`, `bash` and `tar` in
temp folders.

## Contributing

One rule: a check must be able to fail. Break it on purpose, show its tests go
red, restore it, show green, and paste both into the pull request. The details
are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT. See [LICENSE](LICENSE). Built by Reach Machine.
