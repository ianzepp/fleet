#!/usr/bin/env python3
"""Rank source files by churn since their last polish commit.

This is a routing helper for the polish skill. It is intentionally read-only:
it inspects git history, recognizes polish commits, and prints candidate files
whose current state has drifted the most since their last polish pass.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# A commit subject counts as polish when it uses the canonical
# `polish:` / `polish(scope):` form, the legacy prose form (`Polish ...`),
# or the reversed `<scope>: polish ...` form. A `Polish-Primary:` trailer is
# authoritative regardless of subject wording (see has_primary_trailer).
POLISH_SUBJECT_RE = re.compile(
    r"^(?:"
    r"polish(?:\([^)]+\))?:"        # canonical polish: / polish(scope):
    r"|[a-z0-9_./-]+:\s*polish\b"   # reversed <scope>: polish ...
    r"|polish\b"                     # legacy prose, e.g. "Polish radix: ..."
    r")",
    re.IGNORECASE,
)
PRIMARY_TRAILER_RE = re.compile(r"^Polish-Primary:\s*(.+?)\s*$")
SUPPORTING_TRAILER_RE = re.compile(r"^Polish-Supporting:\s*(.+?)\s*$")

SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".ex",
    ".exs",
    ".fab",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".zsh",
}

SKIP_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "build",
    "cache",
    "dist",
    "generated",
    "node_modules",
    "target",
    "tmp",
    "vendor",
}

TEST_PARTS = {"fixtures", "fixture", "testdata", "tests", "__tests__"}
TEST_SUFFIXES = (
    "_test.rs",
    "_test.py",
    "_test.go",
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
)


@dataclass(frozen=True)
class PolishCommit:
    commit: str
    epoch: int
    iso_date: str
    subject: str
    source: str


@dataclass(frozen=True)
class Candidate:
    path: str
    score: float
    commits_since: int
    added: int
    deleted: int
    days_since: float | None
    last_polish: PolishCommit | None


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def repo_root(path: Path) -> Path:
    output = run_git(path, ["rev-parse", "--show-toplevel"]).strip()
    return Path(output)


def tracked_files(repo: Path, pathspecs: list[str]) -> list[str]:
    args = ["ls-files"]
    if pathspecs:
        args.extend(["--", *pathspecs])
    return [line for line in run_git(repo, args).splitlines() if line]


def is_test_path(path: str) -> bool:
    parts = set(Path(path).parts)
    name = Path(path).name
    return bool(parts & TEST_PARTS) or name.endswith(TEST_SUFFIXES)


def is_doc_path(path: str) -> bool:
    return path.startswith("docs/") or Path(path).suffix.lower() in {".md", ".mdx", ".rst"}


def is_candidate_path(path: str, include_tests: bool, include_docs: bool, include_all: bool) -> bool:
    if include_all:
        return True
    parts = set(Path(path).parts)
    if parts & SKIP_PARTS:
        return False
    if not include_tests and is_test_path(path):
        return False
    if not include_docs and is_doc_path(path):
        return False
    return Path(path).suffix.lower() in SOURCE_EXTENSIONS


def iter_polish_commits(
    repo: Path,
    all_refs: bool,
    history_limit: int,
) -> Iterable[tuple[str, int, str, str, str]]:
    """Yield (commit, epoch, iso_date, subject, body) for recognized polish commits.

    A commit qualifies when its subject matches ``POLISH_SUBJECT_RE`` or its
    message carries a ``Polish-Primary:`` trailer. The trailer is
    authoritative: a properly-trailered commit counts as polish even when the
    subject wording does not match (for example ``forma: polish ...``).
    """
    args = ["log", "--date=iso-strict", "--format=%H%x1f%ct%x1f%aI%x1f%s%x1f%B%x1e"]
    if all_refs:
        args.insert(1, "--all")
    if history_limit > 0:
        args.insert(1, f"--max-count={history_limit}")

    output = run_git(repo, args)
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x1f", 4)
        if len(parts) != 5:
            continue
        commit, epoch, iso_date, subject, body = parts
        if POLISH_SUBJECT_RE.search(subject) or has_primary_trailer(body):
            yield commit, int(epoch), iso_date, subject, body


def has_primary_trailer(body: str) -> bool:
    """Return True if the commit message carries a `Polish-Primary:` trailer line."""
    return any(PRIMARY_TRAILER_RE.match(line) for line in body.splitlines())


def commit_files(repo: Path, commit: str) -> list[str]:
    return [line for line in run_git(repo, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit]).splitlines() if line]


def trailer_values(body: str, regex: re.Pattern[str]) -> list[str]:
    values: list[str] = []
    for line in body.splitlines():
        match = regex.match(line)
        if match:
            values.append(match.group(1))
    return values


def last_polish_by_file(repo: Path, candidates: set[str], all_refs: bool, history_limit: int) -> dict[str, PolishCommit]:
    result: dict[str, PolishCommit] = {}
    for commit, epoch, iso_date, subject, body in iter_polish_commits(repo, all_refs, history_limit):
        primary = trailer_values(body, PRIMARY_TRAILER_RE)
        supporting = set(trailer_values(body, SUPPORTING_TRAILER_RE))
        touched = commit_files(repo, commit)

        if primary:
            files = primary
            source = "trailer"
        else:
            files = [path for path in touched if path not in supporting]
            source = "touched"

        for path in files:
            if path in candidates and path not in result:
                result[path] = PolishCommit(commit, epoch, iso_date, subject, source)

    return result


def churn_by_file(
    repo: Path,
    candidates: set[str],
    polished: dict[str, PolishCommit],
    history_limit: int,
    window_days: int,
) -> dict[str, tuple[int, int, int]]:
    """Return path -> (commit_count, added, deleted)."""
    cutoff = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=window_days)).timestamp()) if window_days > 0 else 0
    churn: dict[str, dict[str, object]] = {
        path: {"commits": set(), "added": 0, "deleted": 0}
        for path in candidates
    }

    args = ["log", "--numstat", "--format=@@@%H%x1f%ct"]
    if history_limit > 0:
        args.insert(1, f"--max-count={history_limit}")

    current_commit: str | None = None
    current_epoch = 0
    for line in run_git(repo, args).splitlines():
        if line.startswith("@@@"):
            fields = line[3:].split("\x1f", 1)
            if len(fields) == 2:
                current_commit = fields[0]
                current_epoch = int(fields[1])
            else:
                current_commit = None
                current_epoch = 0
            continue

        if current_commit is None:
            continue
        fields = line.split("\t")
        if len(fields) < 3 or fields[0] == "-" or fields[1] == "-":
            continue
        path = fields[2]
        if path not in candidates:
            continue

        last = polished.get(path)
        if last:
            if current_epoch <= last.epoch:
                continue
        elif current_epoch < cutoff:
            continue

        try:
            added = int(fields[0])
            deleted = int(fields[1])
        except ValueError:
            continue

        data = churn[path]
        commits = data["commits"]
        assert isinstance(commits, set)
        commits.add(current_commit)
        data["added"] = int(data["added"]) + added
        data["deleted"] = int(data["deleted"]) + deleted

    return {
        path: (len(data["commits"]), int(data["added"]), int(data["deleted"]))
        for path, data in churn.items()
    }


def score_candidate(
    commits_since: int,
    added: int,
    deleted: int,
    days_since: float | None,
    no_polish_penalty: int,
) -> float:
    score = added + deleted + commits_since * 20
    if days_since is None:
        score += no_polish_penalty
    else:
        score += min(days_since, 365.0) * 0.5
    return score


def build_candidates(
    repo: Path,
    paths: list[str],
    include_tests: bool,
    include_docs: bool,
    include_all: bool,
    all_refs: bool,
    history_limit: int,
    window_days: int,
    no_polish_penalty: int,
) -> list[Candidate]:
    tracked = tracked_files(repo, paths)
    candidates = {
        path
        for path in tracked
        if is_candidate_path(path, include_tests=include_tests, include_docs=include_docs, include_all=include_all)
    }
    polished = last_polish_by_file(repo, candidates, all_refs=all_refs, history_limit=history_limit)
    churn = churn_by_file(repo, candidates, polished, history_limit=history_limit, window_days=window_days)
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    rows: list[Candidate] = []

    for path in sorted(candidates):
        last = polished.get(path)
        commits_since, added, deleted = churn.get(path, (0, 0, 0))
        if last is None and commits_since == 0 and added == 0 and deleted == 0:
            continue
        days_since = ((now - last.epoch) / 86400.0) if last else None
        score = score_candidate(commits_since, added, deleted, days_since, no_polish_penalty)
        if score <= 0:
            continue
        rows.append(
            Candidate(
                path=path,
                score=score,
                commits_since=commits_since,
                added=added,
                deleted=deleted,
                days_since=days_since,
                last_polish=last,
            )
        )

    rows.sort(key=lambda row: (-row.score, row.path))
    return rows


def print_table(rows: list[Candidate], limit: int) -> None:
    selected = rows[:limit] if limit > 0 else rows
    if not selected:
        print("No polish candidates found.")
        return

    print(f"{'score':>7}  {'last polish':<12}  {'commits':>7}  {'added':>7}  {'deleted':>7}  path")
    print(f"{'-' * 7}  {'-' * 12}  {'-' * 7}  {'-' * 7}  {'-' * 7}  {'-' * 40}")
    for row in selected:
        if row.last_polish:
            last = row.last_polish.iso_date[:10]
        else:
            last = "never"
        print(
            f"{row.score:7.1f}  {last:<12}  {row.commits_since:7d}  "
            f"{row.added:7d}  {row.deleted:7d}  {row.path}"
        )


def candidate_to_json(row: Candidate) -> dict[str, object]:
    last = row.last_polish
    return {
        "path": row.path,
        "score": row.score,
        "commits_since_polish": row.commits_since,
        "lines_added_since_polish": row.added,
        "lines_deleted_since_polish": row.deleted,
        "days_since_polish": row.days_since,
        "last_polish": None
        if last is None
        else {
            "commit": last.commit,
            "date": last.iso_date,
            "subject": last.subject,
            "source": last.source,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Git repository to inspect; default: current directory")
    parser.add_argument("--path", action="append", default=[], help="Restrict to a tracked pathspec; may be repeated")
    parser.add_argument("--limit", type=int, default=30, help="Maximum rows to print; use 0 for all")
    parser.add_argument("--history-limit", type=int, default=5000, help="Maximum commits to scan for polish markers; use 0 for all")
    parser.add_argument("--window-days", type=int, default=60, help="Fallback churn window for files with no polish history")
    parser.add_argument("--no-polish-penalty", type=int, default=200, help="Score penalty added to files with no polish history")
    parser.add_argument("--all-refs", action="store_true", help="Scan polish commits from all refs instead of HEAD history only")
    parser.add_argument("--include-tests", action="store_true", help="Include test and fixture paths")
    parser.add_argument("--include-docs", action="store_true", help="Include documentation paths")
    parser.add_argument("--include-all", action="store_true", help="Include every tracked file not restricted by --path")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        repo = repo_root(Path(args.repo).resolve())
        rows = build_candidates(
            repo=repo,
            paths=args.path,
            include_tests=args.include_tests,
            include_docs=args.include_docs,
            include_all=args.include_all,
            all_refs=args.all_refs,
            history_limit=args.history_limit,
            window_days=args.window_days,
            no_polish_penalty=args.no_polish_penalty,
        )
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        selected = rows[: args.limit] if args.limit > 0 else rows
        print(json.dumps([candidate_to_json(row) for row in selected], indent=2, sort_keys=True))
    else:
        print_table(rows, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
