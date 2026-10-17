#!/usr/bin/env python3
"""Check a diff for tests it weakens (ADR 0002: Python 3 stdlib only, JSON-only stdout).

Reads a unified diff and reports each place where it makes the test suite prove
less: a test (or a test file) deleted, a test skipped, an assertion removed, or
an assertion loosened. Each finding carries a file, a line, the diff line as
detail and its consequence. Findings are review input, so a scan exits 0
whatever it finds.

Usage:
    python3 test_integrity.py <repo> [--range=A..B | --staged | --stdin]

With no source flag the scan reads the uncommitted change (staged and unstaged)
against HEAD; --range diffs two revisions (commits or tree objects), --staged the
index against HEAD, and --stdin reads a unified diff such as `gh pr diff` prints.
A git diff holds only the files git tracks: a file the change creates and git has
not seen yet is not in it, so a caller that creates files compares two tree
objects with --range. The diff is limited to <repo> and names paths from it. A
folder that is not inside a git work tree is not an error: nothing could be
checked, so the answer has no findings and a warning says so. A repository git
refuses to open (a .git entry at or above the folder that git will not read) is
an error.

Output: {"ok", "mode": "test-integrity", "source", "files_scanned", "findings":
[{"file", "line", "language", "kind", "detail", "consequence"}], "unsupported",
"warnings", "next_action"}, with kind one of deleted-test (a deleted test file, or
one renamed to a path that is not a test file, is one finding at line 1),
skipped-test, removed-assertion or loosened-assertion. A
usage error, or a diff git cannot produce, prints {"ok": false, "mode", "error",
"next_action"} and exits 2, the code detect.py uses.

The check reads changed lines, not syntax trees, through per-language patterns
(TEST_PATTERNS). A line whose text is added again elsewhere in the diff moved, so
it is not a removal; a removed test or assertion that an added one of its kind
rewrites in the same file, in the same run of changed lines or keeping most of the
words that name it, was rewritten, which the review rubric judges, so it is not a
removal either; an unrelated addition elsewhere in the file rewrites nothing. A
skip inside a test the same diff adds skips nothing that
ran before, so it is not a finding, unless the file also removes a test or a Python
class (which added test a removed one became is a guess); one that focuses on some
tests (.only, fit) skips the others, so it still is. A line number is the old file's for something
removed and the new file's for something added. Changed files in a language
detect.py knows but TEST_PATTERNS does not are listed under "unsupported", never
passed silently.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Container
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import groupby
from pathlib import Path, PurePosixPath

# Isolated mode (python3 -I) leaves this script's folder off sys.path, so detect.py is
# found by location: the kit keeps one table of language extensions.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from detect import LANGUAGE_EXTENSIONS  # noqa: E402

MODE = "test-integrity"
USAGE = "Use: test_integrity.py <repo> [--range=A..B | --staged | --stdin]."
GIT_NEXT_ACTION = (
    "Point the scan at a git repository and name revisions it has, such as main...HEAD."
)
NOT_A_REPOSITORY_NEXT_ACTION = (
    "Run the scan inside a git repository, or pipe a unified diff in with --stdin."
)
ERROR_EXIT_CODE = 2
GIT_TIMEOUT_SECONDS = 60
TOKEN_CACHE_SIZE = 4096
# Fixed flags keep the diff independent of the user's git config: no colour, no
# external diff tool or text conversion, a/ and b/ prefixes, renames followed, and
# non-ASCII paths unquoted. --relative limits the diff to the scanned folder and names
# paths from it.
GIT_DIFF = [
    "-c",
    "core.quotePath=false",
    "diff",
    "-U0",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "-M",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--relative",
]
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NODE_TEST_NAME = re.compile(r"\.(?:test|spec)\.\w+$")
TOKEN = re.compile(r"\w+|[^\w\s]")
# The words of a name or a line, with snake_case and camelCase split apart.
WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
# An added test or assertion rewrote a removed one of its role outside their run of
# changed lines only when more than this share of the words that name them is shared.
REWRITE_SIMILARITY = 0.5
NO_HEADERS_WARNING = "The input has text but no unified diff file headers, so nothing was checked."
NOT_A_REPOSITORY_WARNING = "The folder is not inside a git work tree, so nothing was checked."

# Five roles per language: "test" starts a test, "skip" skips tests, "assertion" is a
# check, "exact" marks a check that pins an expected value, and "weak" marks a check
# that pins none (truthy, not null, any exception, greater than). A check that pinned
# a value, replaced in place by a weak one that pins none, is a loosened assertion.
# A line that only opens a multi-line expression (formatter reflow) pins nothing, so
# it is not weak.
TEST_PATTERNS: dict[str, dict[str, re.Pattern[str]]] = {
    "python": {
        "test": re.compile(r"^\s*(?:async\s+)?def\s+test\w*\s*\("),
        "skip": re.compile(
            r"^\s*@(?:pytest\.mark\.(?:skip|skipif|xfail)|unittest\.(?:skip\w*|expectedFailure))\b"
            r"|\bpytest\.(?:skip|xfail)\s*\(|\bself\.skipTest\s*\("
        ),
        "assertion": re.compile(
            r"^\s*assert\b|\bself\.(?:assert\w*|fail)\s*\(|\bpytest\.(?:raises|warns|fail)\s*\("
            r"|\bassert_\w+\s*\("
        ),
        "exact": re.compile(
            r"==|\bassert(?!Not)\w*Equal\s*\(|\bassertIs\s*\(|\bassert_\w*(?:equal|_with)\s*\("
            r"|\b(?:isclose|approx)\s*\(|\bmatch\s*="
            r"|\b(?:pytest\.raises|assertRaises\w*)\s*\(\s*(?!(?:Base)?Exception\b)\w"
        ),
        "weak": re.compile(
            r"^\s*assert\b(?!.*==)(?!.*[(\[{]\s*$)"
            r"|\b(?:assertTrue|assertFalse|assertIsNotNone|assertIsInstance"
            r"|assertIn|assertGreater\w*|assertLess\w*)\s*\(|\bassert_(?:called|awaited)\s*\("
            r"|\b(?:pytest\.raises|assertRaises)\s*\(\s*(?:Base)?Exception\s*[,)]"
        ),
    },
    "node": {
        "test": re.compile(r"^\s*[xf]?(?:it|test)(?:\.\w+)*\s*\(\s*['\"`]"),
        "skip": re.compile(
            r"\b(?:it|test|describe|suite|context)\.(?:skip\w*|only)\b"
            r"|(?<![\w.])(?:xit|xtest|xdescribe|xcontext|fit|fdescribe)\s*\("
        ),
        "assertion": re.compile(r"\b(?:expect|assert)(?:\.\w+)*\s*\(|\.should\b"),
        "exact": re.compile(
            r"\.(?:toBe|toEqual|toStrictEqual|toMatchObject|toHaveBeenCalledWith"
            r"|toHaveBeenNthCalledWith|toHaveBeenLastCalledWith|toHaveBeenCalledTimes|toHaveLength"
            r"|toThrow|toThrowError|toMatchInlineSnapshot|equal|equals|eql|strictEqual|deepEqual"
            r"|deepStrictEqual|include|members)\s*\(\s*[^)\s]"
        ),
        "weak": re.compile(
            r"\.(?:toBeTruthy|toBeFalsy|toBeDefined|toBeInstanceOf|toBeGreaterThan\w*|toBeLessThan\w*"
            r"|toContain\w*|toHaveBeenCalled|toMatch)\b|\.toThrow(?:Error)?\s*\(\s*\)"
            r"|\.not\.toBe(?:Null|Undefined|NaN)\b|\bexpect\.any(?:thing)?\s*\("
            r"|\bassert(?:\.ok)?\s*\(|\.to\.(?:be\.)?(?:ok|exist|true)\b"
        ),
    },
    "go": {
        "test": re.compile(r"^\s*func\s+(?:Test|Fuzz)\w*\s*\(|\bt\.Run\s*\("),
        "skip": re.compile(r"\b(?:t|b|f|tb)\.Skip(?:f|Now)?\s*\("),
        "assertion": re.compile(
            r"\b(?:t|b|f|tb)\.(?:Error|Errorf|Fatal|Fatalf|Fail|FailNow)\s*\("
            r"|\b(?:assert|require)\.\w+\s*\("
        ),
        "exact": re.compile(
            r"\b(?:assert|require)\.(?:Equal|Exactly|ElementsMatch|JSONEq|YAMLEq|ErrorIs"
            r"|ErrorContains)\w*\s*\("
        ),
        "weak": re.compile(
            r"\b(?:assert|require)\.(?:NotNil|NoError|Error|True|False|NotEmpty|NotZero|Greater"
            r"|GreaterOrEqual|Less|LessOrEqual|Positive|Contains|NotEqual)\s*\("
        ),
    },
    "rust": {
        "test": re.compile(r"^\s*#\[(?:\w+::)*(?:rs)?test\b"),
        "skip": re.compile(r"^\s*#\[ignore\b"),
        "assertion": re.compile(r"\b(?:debug_)?assert(?:_eq|_ne)?!\s*[(\[{]|^\s*#\[should_panic\b"),
        "exact": re.compile(r"\b(?:debug_)?assert_eq!|==|#\[should_panic\s*\("),
        "weak": re.compile(r"\b(?:debug_)?assert(?:_ne)?!\s*[(\[{](?!\s*$)|#\[should_panic\]"),
    },
}
# Rust keeps unit tests inline under #[cfg(test)], so a removed #[test] or an added
# #[ignore] counts in any Rust file; assertions count only in test files, because
# assert! also guards production code.
INLINE_TEST_LANGUAGES = {"rust"}
# Which test an added skip belongs to, to leave out a skip inside a test the diff adds.
# A decorator or attribute marks the test it sits on: a Rust test attribute in the same
# block, or the Python def or class below it.
MARKER = re.compile(r"^\s*(?:@|#\[)")
PYTHON_DEF = re.compile(r"^\s*(?:async\s+)?def\s")
PYTHON_CLASS = re.compile(r"^\s*class\s")
# A Python or Go call that skips belongs to the nearest test above it, unless another
# definition starts between them. Node's skips that are not a test's own line skip a
# group (describe.skip), so they belong to no single test.
DEFINITIONS = {
    "python": re.compile(r"^\s*(?:(?:async\s+)?def|class)\s|^\s*@"),
    "go": re.compile(r"^\s*func\s"),
}
# The name a test line gives its test, per language: what a moved test keeps.
TEST_NAMES = {
    "python": re.compile(r"\bdef\s+(\w+)"),
    "node": re.compile(r"""\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)"""),
    "go": re.compile(r'\bfunc\s+(\w+)|\bt\.Run\s*\(\s*"([^"]*)"'),
    "rust": re.compile(r"\bfn\s+(\w+)"),
}
# A skip that focuses on some tests skips every other one, so it is always a finding.
FOCUS = re.compile(r"\.only\b|(?<![\w.])(?:fit|fdescribe)\s*\(")
CONSEQUENCES = {
    "deleted-test": "A deleted test no longer runs, so what it covered is unchecked.",
    "skipped-test": "Skipped tests no longer run, so a failure in what they cover goes unnoticed.",
    "removed-assertion": "The test no longer checks this, so it can pass while this is wrong.",
    "loosened-assertion": "The check now accepts more answers, so a wrong result can still pass.",
}

Line = tuple[int, str]


class UsageError(Exception):
    """Raised when the command line does not match the JSON-only contract."""


class DiffError(Exception):
    """Raised when git cannot produce the diff the arguments name."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


@dataclass
class Hunk:
    """One run of changed lines in an @@ block: (line, text) pairs, old numbering when
    removed, new when added. A context line ends a run, so a context diff's @@ block
    holds a run per change, as a -U0 diff's does."""

    removed: list[Line] = field(default_factory=list)
    added: list[Line] = field(default_factory=list)


@dataclass
class FileDiff:
    """One file of a unified diff; a path is None on the side where the file does not exist."""

    old_path: str | None = None
    new_path: str | None = None
    deleted: bool = False
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def removed(self) -> list[Line]:
        return [line for hunk in self.hunks for line in hunk.removed]

    @property
    def added(self) -> list[Line]:
        return [line for hunk in self.hunks for line in hunk.added]


class _Elsewhere:
    """The lines the other files of a diff changed: counts over every file minus this file's own."""

    def __init__(self, counts: Counter[str], own: set[str]) -> None:
        self.counts = counts
        self.own = own

    def __contains__(self, key: object) -> bool:
        return self.counts[key] - (1 if key in self.own else 0) > 0


def fail(error: str, next_action: str = USAGE) -> int:
    print(json.dumps({"ok": False, "mode": MODE, "error": error, "next_action": next_action}))
    return ERROR_EXIT_CODE


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run git in the repository; raise DiffError only when git itself cannot run."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise DiffError("git is not installed") from None
    except subprocess.TimeoutExpired:
        raise DiffError(f"git took longer than {GIT_TIMEOUT_SECONDS} seconds") from None


def _git(repo: Path, args: list[str]) -> str:
    """Run git in the repository and return its stdout; raise DiffError with git's own words."""
    proc = _run_git(repo, args)
    if proc.returncode != 0:
        lines = proc.stderr.strip().splitlines()
        raise DiffError(lines[0] if lines else f"git exited {proc.returncode}")
    return proc.stdout


def _in_git_work_tree(repo: Path) -> bool:
    """Whether git finds a repository at or above the folder.

    False only when no folder at or above holds a .git entry. A repository git refuses
    to open (unsafe ownership, a broken .git) is an error, not a clean answer.
    """
    proc = _run_git(repo, ["rev-parse", "--git-dir"])
    if proc.returncode == 0:
        return True
    here = repo.resolve()
    if any((folder / ".git").exists() for folder in (here, *here.parents)):
        lines = proc.stderr.strip().splitlines()
        raise DiffError(lines[0] if lines else f"git exited {proc.returncode}")
    return False


def _worktree_base(repo: Path) -> str:
    """HEAD, or the empty tree in a repository with no commit yet, where nothing can be lost."""
    if _run_git(repo, ["rev-parse", "--verify", "--quiet", "HEAD"]).returncode == 0:
        return "HEAD"
    return _git(repo, ["hash-object", "-t", "tree", "--stdin"]).strip()


def read_diff(repo: Path, source: str, range_: str = "") -> str:
    """The unified diff a source names: stdin, or git's diff of the repository."""
    if source == "stdin":
        # Bytes, decoded here: a diff with a Latin-1 file in it must not crash the scan.
        return sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if source == "range":
        revision = range_
    elif source == "staged":
        revision = "--cached"
    else:
        revision = _worktree_base(repo)
    return _git(repo, [*GIT_DIFF, revision, "--"])


def _diff_path(value: str, prefixed: bool = True) -> str | None:
    path = value.split("\t", 1)[0].rstrip("\r")
    if path == "/dev/null":
        return None
    if len(path) > 1 and path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    if prefixed and path[:2] in ("a/", "b/"):
        path = path[2:]
    return path


def parse_unified_diff(text: str) -> list[FileDiff]:
    """Split a unified diff (git's or diff -u's, any context size) into files and hunks."""
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    in_header = False
    old_line = new_line = old_left = new_left = 0
    for raw in text.split("\n"):
        if hunk is not None and (old_left > 0 or new_left > 0):
            marker, body = raw[:1], raw[1:]
            if marker == "-":
                hunk.removed.append((old_line, body))
                old_line, old_left = old_line + 1, old_left - 1
                continue
            if marker == "+":
                hunk.added.append((new_line, body))
                new_line, new_left = new_line + 1, new_left - 1
                continue
            if marker in (" ", ""):
                if hunk.removed or hunk.added:
                    hunk = Hunk()
                    current.hunks.append(hunk)
                old_line, new_line = old_line + 1, new_line + 1
                old_left, new_left = old_left - 1, new_left - 1
                continue
            if marker == "\\":
                continue
            # A hunk shorter than its header claimed: read this line as a header.
            old_left = new_left = 0
        if raw.startswith("diff --git "):
            current = FileDiff()
            files.append(current)
            hunk, in_header = None, True
            continue
        if raw.startswith("--- "):
            if current is None or not in_header:
                current = FileDiff()
                files.append(current)
                hunk, in_header = None, True
            current.old_path = _diff_path(raw[len("--- ") :])
            continue
        if current is None:
            continue
        match = HUNK.match(raw)
        if match:
            hunk = Hunk()
            current.hunks.append(hunk)
            in_header = False
            old_line, new_line = int(match[1]), int(match[3])
            old_left = int(match[2]) if match[2] is not None else 1
            new_left = int(match[4]) if match[4] is not None else 1
            continue
        if not in_header:
            continue
        if raw.startswith("+++ "):
            current.new_path = _diff_path(raw[len("+++ ") :])
            current.deleted = current.new_path is None
        elif raw.startswith("rename from "):
            current.old_path = _diff_path(raw[len("rename from ") :], prefixed=False)
        elif raw.startswith("rename to "):
            current.new_path = _diff_path(raw[len("rename to ") :], prefixed=False)
        elif raw.startswith("deleted file mode "):
            current.deleted = True
    return files


def language_of(path: str) -> str | None:
    """The language detect.py gives the path's extension, or None for any other file."""
    suffix = PurePosixPath(path).suffix.lower()
    for language, extensions in LANGUAGE_EXTENSIONS.items():
        if suffix in extensions:
            return language
    return None


def is_test_file(path: str, language: str) -> bool:
    """Whether the path holds tests by the language's naming rules (Python's as test_quality.py)."""
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    name, folders = parts[-1], set(parts[:-1])
    if language == "python":
        return name.startswith("test_") or name.endswith("_test.py") or "tests" in folders
    if language == "node":
        return bool(NODE_TEST_NAME.search(name)) or bool(folders & {"test", "tests", "__tests__"})
    if language == "go":
        return name.endswith("_test.go")
    if language == "rust":
        return "tests" in folders or name == "tests.rs"
    return False


def _norm(text: str) -> str:
    return " ".join(text.split())


@lru_cache(maxsize=TOKEN_CACHE_SIZE)
def _tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN.findall(text))


def _similarity(first: str, second: str) -> float:
    """Shared tokens (names, numbers, symbols) over all tokens of the two lines."""
    union = _tokens(first) | _tokens(second)
    return len(_tokens(first) & _tokens(second)) / len(union) if union else 1.0


def _most_like(items: list[Line], text: str) -> Line:
    return max(items, key=lambda item: _similarity(item[1], text))


def _entries(lines: list[Line]) -> list[Line]:
    """Each line, with a Rust attribute joined to the line after it, which names the test."""
    by_number = dict(lines)
    entries = []
    for number, text in lines:
        following = by_number.get(number + 1)
        if text.lstrip().startswith("#[") and following is not None:
            text = f"{text.strip()} {following.strip()}"
        entries.append((number, text))
    return entries


def _matching(lines: list[Line], pattern: re.Pattern[str]) -> list[Line]:
    return [(number, text) for number, text in _entries(lines) if pattern.search(text)]


def _keys(lines: list[Line]) -> set[str]:
    return {_norm(text) for _, text in lines} | {_norm(text) for _, text in _entries(lines)}


def _unmoved(
    lines: list[Line], counterparts: list[Line], elsewhere: Container[str]
) -> tuple[list[Line], list[Line]]:
    """Set aside the lines that only moved.

    A line whose text (whitespace aside) is among its counterparts in this file, or in
    another file of the diff, moved or was re-indented. Returns the lines that did not
    move and the counterparts that no line used.
    """
    spare: dict[str, list[Line]] = {}
    for item in counterparts:
        spare.setdefault(_norm(item[1]), []).append(item)
    changed = []
    for item in lines:
        key = _norm(item[1])
        if spare.get(key):
            spare[key].pop(0)
        elif key not in elsewhere:
            changed.append(item)
    return changed, sorted(item for items in spare.values() for item in items)


def _unreplaced(removed: list[Line], added: list[Line]) -> list[Line]:
    """Removed lines left once each added line of the same role replaced the one most like it."""
    if len(added) >= len(removed):
        return []
    left = list(removed)
    for _, text in added:
        left.remove(_most_like(left, text))
    return left


def _words(text: str, role: str, language: str) -> frozenset[str]:
    """The words that name a test (those of its name) or an assertion (those of its line)."""
    if role == "test":
        match = TEST_NAMES[language].search(text)
        if match:
            text = next(group for group in match.groups() if group is not None)
    return frozenset(word.lower() for word in WORD.findall(text))


def _alike(old: str, new: str, role: str, language: str) -> bool:
    """Whether more than REWRITE_SIMILARITY of the words naming the two lines is shared."""
    first, second = _words(old, role, language), _words(new, role, language)
    union = first | second
    return bool(union) and len(first & second) / len(union) > REWRITE_SIMILARITY


def _unrewritten(
    fd: FileDiff, removed: list[Line], added: list[Line], role: str, language: str
) -> list[Line]:
    """The removed lines of a role that no added line of that role rewrote. An added line
    rewrites the removed line most like it among those in its own run of changed lines
    (an edit in place) and those it is _alike (an edit that also moved it); any other
    addition, such as a new check elsewhere in the file, leaves the removal standing."""
    old_run = {number: index for index, hunk in enumerate(fd.hunks) for number, _ in hunk.removed}
    new_run = {number: index for index, hunk in enumerate(fd.hunks) for number, _ in hunk.added}
    left = list(removed)
    for number, text in added:
        candidates = [
            item
            for item in left
            if old_run.get(item[0], -1) == new_run.get(number, -2)
            or _alike(item[1], text, role, language)
        ]
        if candidates:
            left.remove(_most_like(candidates, text))
    return left


def _inside(fd: FileDiff, tests: list[Line]) -> set[int]:
    """Old line numbers that went with a deleted test: the rest of its run of removed lines.

    A run is consecutive old lines, so a context diff that also holds a change elsewhere in
    the same hunk keeps that change as its own finding.
    """
    starts = {number for number, _ in tests}
    inside: set[int] = set()
    for hunk in fd.hunks:
        for _, group in groupby(enumerate(hunk.removed), key=lambda pair: pair[1][0] - pair[0]):
            run = [line[0] for _, line in group]
            first = next((number for number in run if number in starts), None)
            if first is not None:
                inside.update(number for number in run if number > first)
    return inside


def _loosened(
    removed: list[Line], added: list[Line], patterns: dict[str, re.Pattern[str]]
) -> list[tuple[Line, Line]]:
    """The (old, new) checks of one hunk where a check that pinned a value became a weak one.

    Exact checks the hunk adds first replace the removed exact checks most like them, so a
    hunk loosens at most as many checks as it loses exact ones.
    """
    exact, weak = patterns["exact"], patterns["weak"]
    lost = _unreplaced(
        [line for line in removed if exact.search(line[1])],
        [line for line in added if exact.search(line[1])],
    )
    spare = [line for line in added if weak.search(line[1]) and not exact.search(line[1])]
    pairs = []
    for old in lost:
        if not spare:
            break
        new = _most_like(spare, old[1])
        spare.remove(new)
        pairs.append((old, new))
    return pairs


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip())


def _marked_test(run: list[Line], at: int, language: str) -> int | None:
    """The test a decorator or attribute at run[at] marks: a test attribute in the same
    Rust attribute block, or the Python def below when it is a test, or the first test
    of the Python class below. None for a Rust or Node attribute with nothing below it
    in the run: the item it marks is an existing one outside the diff."""
    test = TEST_PATTERNS[language]["test"]
    end = at
    while end + 1 < len(run) and MARKER.match(run[end + 1][1]):
        end += 1
    if language != "python" and end + 1 >= len(run):
        return None  # the item the attributes mark is not in the diff
    for number, text in reversed(run[:at]):
        if not MARKER.match(text):
            break
        if test.search(text):
            return number
    in_class = False
    for number, text in run[at + 1 :]:
        if test.search(text):
            return number
        if language != "python":
            if not MARKER.match(text):
                return None
        elif PYTHON_CLASS.match(text):
            in_class = True
        elif PYTHON_DEF.match(text) and not in_class:
            return None
    return None


def _skip_owner(run: list[Line], at: int, language: str) -> int | None:
    """The line of the test that the skip at run[at] belongs to, within its run of
    consecutive added lines, or None when it belongs to no test there."""
    test = TEST_PATTERNS[language]["test"]
    number, text = run[at]
    if test.search(text):
        return number
    if MARKER.match(text):
        return _marked_test(run, at, language)
    definition = DEFINITIONS.get(language)
    if definition is None:
        return None
    shallowest = _indent(text)
    for above, line in reversed(run[:at]):
        if not line.strip():
            continue
        if test.search(line):
            # A call belongs to a test only when everything from the header to it is
            # indented inside the header: a dedent between them closed the test.
            return above if _indent(line) < shallowest else None
        if definition.search(line):
            return None
        shallowest = min(shallowest, _indent(line))
    return None


def _new_tests(
    fd: FileDiff,
    patterns: dict[str, re.Pattern[str]],
    removed_tests: list[Line],
    removed_elsewhere: Container[str],
) -> set[int]:
    """New line numbers of the tests the diff adds: not moved from this file or another.
    A file that also removes a test (`removed_tests`, the removed tests that did not
    move) or a Python class adds none: which added test a removed one became is a
    guess, so a skip beside them is reported rather than excused."""
    if removed_tests or any(PYTHON_CLASS.match(text) for _, text in fd.removed):
        # Which added test a removed one became (a rename) is a guess, so none is new.
        return set()
    fresh, _ = _unmoved(
        _matching(fd.added, patterns["test"]),
        _matching(fd.removed, patterns["test"]),
        removed_elsewhere,
    )
    return {number for number, _ in fresh}


def _in_new_tests(fd: FileDiff, language: str, skips: list[Line], new_tests: set[int]) -> set[int]:
    """The line numbers of the skips that sit inside a test the diff adds."""
    if not new_tests:
        return set()
    entries = dict(_entries(fd.added))
    wanted = {number for number, text in skips if not FOCUS.search(text)}
    inside = set()
    for hunk in fd.hunks:
        for _, group in groupby(enumerate(hunk.added), key=lambda pair: pair[1][0] - pair[0]):
            run = [(number, entries[number]) for _, (number, _) in group]
            for at, (number, _) in enumerate(run):
                if number in wanted and _skip_owner(run, at, language) in new_tests:
                    inside.add(number)
    return inside


def _finding(path: str, line: int, language: str, kind: str, detail: str) -> dict:
    return {
        "file": path,
        "line": line,
        "language": language,
        "kind": kind,
        "detail": detail,
        "consequence": CONSEQUENCES[kind],
    }


def _assertion_findings(
    fd: FileDiff, language: str, added_elsewhere: Container[str], gone_tests: list[Line]
) -> list[dict]:
    patterns = TEST_PATTERNS[language]
    old_path = fd.old_path or fd.new_path or ""
    new_path = fd.new_path or fd.old_path or ""
    inside = _inside(fd, gone_tests)
    removed = [
        line for line in _matching(fd.removed, patterns["assertion"]) if line[0] not in inside
    ]
    removed, added = _unmoved(removed, _matching(fd.added, patterns["assertion"]), added_elsewhere)
    findings = []
    for hunk in fd.hunks:
        old_numbers = {number for number, _ in hunk.removed}
        new_numbers = {number for number, _ in hunk.added}
        hunk_removed = [line for line in removed if line[0] in old_numbers]
        hunk_added = [line for line in added if line[0] in new_numbers]
        for old, new in _loosened(hunk_removed, hunk_added, patterns):
            removed.remove(old)
            added.remove(new)
            detail = f"-{old[1].strip()} => +{new[1].strip()}"
            findings.append(_finding(new_path, new[0], language, "loosened-assertion", detail))
    for number, text in _unrewritten(fd, removed, added, "assertion", language):
        findings.append(
            _finding(old_path, number, language, "removed-assertion", f"-{text.strip()}")
        )
    return findings


def scan_file(
    fd: FileDiff,
    language: str,
    added_elsewhere: Container[str] = frozenset(),
    removed_elsewhere: Container[str] = frozenset(),
) -> list[dict]:
    """The findings for one changed file in a language TEST_PATTERNS covers."""
    patterns = TEST_PATTERNS[language]
    in_tests = any(is_test_file(path, language) for path in (fd.old_path, fd.new_path) if path)
    if not in_tests and language not in INLINE_TEST_LANGUAGES:
        return []
    old_path = fd.old_path or fd.new_path or ""
    new_path = fd.new_path or fd.old_path or ""
    tests, test_twins = _unmoved(
        _matching(fd.removed, patterns["test"]),
        _matching(fd.added, patterns["test"]),
        added_elsewhere,
    )
    gone_tests = _unrewritten(fd, tests, test_twins, "test", language)
    if fd.deleted and in_tests:
        if not gone_tests:
            return []
        detail = f"file deleted with {len(gone_tests)} test(s), first -{gone_tests[0][1].strip()}"
        return [_finding(old_path, 1, language, "deleted-test", detail)]
    findings = [
        _finding(old_path, number, language, "deleted-test", f"-{text.strip()}")
        for number, text in gone_tests
    ]
    skips, _ = _unmoved(
        _matching(fd.added, patterns["skip"]),
        _matching(fd.removed, patterns["skip"]),
        removed_elsewhere,
    )
    # A skip inside a test the diff adds skips nothing that ran before.
    new_tests = _new_tests(fd, patterns, tests, removed_elsewhere)
    in_new_tests = _in_new_tests(fd, language, skips, new_tests)
    findings += [
        _finding(new_path, number, language, "skipped-test", f"+{text.strip()}")
        for number, text in skips
        if number not in in_new_tests
    ]
    if in_tests:
        findings += _assertion_findings(fd, language, added_elsewhere, gone_tests)
    return findings


def _moved_out_of_tests(fd: FileDiff) -> dict | None:
    """The finding for a test file renamed to a path that is no test file: its tests no
    longer run, whatever its hunks show (a pure rename has none), so it is one finding
    at line 1, as a deleted test file is."""
    if not (fd.old_path and fd.new_path) or fd.old_path == fd.new_path:
        return None
    language = language_of(fd.old_path)
    if language not in TEST_PATTERNS or not is_test_file(fd.old_path, language):
        return None
    if language_of(fd.new_path) == language and is_test_file(fd.new_path, language):
        return None
    detail = f"test file moved out of the test paths to {fd.new_path}"
    return _finding(fd.old_path, 1, language, "deleted-test", detail)


def _next_action(findings: list[dict], files_scanned: int, unsupported: list[str]) -> str:
    unchecked = f"changes in {', '.join(unsupported)} were not checked"
    if findings:
        first = findings[0]
        action = (
            f"Restore or explain the {first['kind'].replace('-', ' ')} at "
            f"{first['file']}:{first['line']} ({len(findings)} finding(s) in all)."
        )
        return f"{action} Also, {unchecked}." if unsupported else action
    if unsupported:
        return f"No test-integrity findings; {unchecked}."
    if files_scanned:
        return "No test-integrity findings in this diff."
    return "Nothing to check: the diff changes no code in a supported language."


def scan(diff_text: str, source: str) -> dict:
    """Check every file of a unified diff and build the one JSON object the CLI prints."""
    files = parse_unified_diff(diff_text)
    added_keys = [_keys(fd.added) for fd in files]
    removed_keys = [_keys(fd.removed) for fd in files]
    added_counts = Counter(key for keys in added_keys for key in keys)
    removed_counts = Counter(key for keys in removed_keys for key in keys)
    findings: list[dict] = []
    unsupported: set[str] = set()
    files_scanned = 0
    for fd, own_added, own_removed in zip(files, added_keys, removed_keys, strict=True):
        moved_out = _moved_out_of_tests(fd)
        if moved_out:
            files_scanned += 1
            findings.append(moved_out)
            continue
        language = language_of(fd.new_path or fd.old_path or "")
        if language is None:
            continue
        if language not in TEST_PATTERNS:
            unsupported.add(language)
            continue
        files_scanned += 1
        findings += scan_file(
            fd,
            language,
            _Elsewhere(added_counts, own_added),
            _Elsewhere(removed_counts, own_removed),
        )
    warnings = [NO_HEADERS_WARNING] if diff_text.strip() and not files else []
    return {
        "ok": True,
        "mode": MODE,
        "source": source,
        "files_scanned": files_scanned,
        "findings": findings,
        "unsupported": sorted(unsupported),
        "warnings": warnings,
        "next_action": _next_action(findings, files_scanned, sorted(unsupported)),
    }


def _outside_a_repository(source: str) -> dict:
    """The answer for a folder git does not cover: nothing could be checked, which is no finding."""
    answer = scan("", source)
    answer["warnings"] = [NOT_A_REPOSITORY_WARNING]
    answer["next_action"] = NOT_A_REPOSITORY_NEXT_ACTION
    return answer


def _source(args: argparse.Namespace) -> str:
    if args.range_ is not None:
        return "range"
    if args.staged:
        return "staged"
    if args.stdin:
        return "stdin"
    return "worktree"


def main(argv: list[str] | None = None) -> int:
    parser = JsonArgumentParser(prog="test_integrity.py", add_help=False)
    parser.add_argument("repo")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--range", dest="range_")
    sources.add_argument("--staged", action="store_true")
    sources.add_argument("--stdin", action="store_true")
    try:
        args = parser.parse_args(argv)
    except UsageError as error:
        return fail(str(error))
    if args.range_ is not None and (".." not in args.range_ or args.range_.startswith("-")):
        return fail("--range needs two revisions such as main...HEAD")
    repo = Path(args.repo)
    if not repo.is_dir():
        return fail(f"not a directory: {args.repo}", "Pass the path of the repository to scan.")
    source = _source(args)
    try:
        if source != "stdin" and not _in_git_work_tree(repo):
            print(json.dumps(_outside_a_repository(source)))
            return 0
        diff_text = read_diff(repo, source, args.range_ or "")
    except DiffError as error:
        return fail(str(error), GIT_NEXT_ACTION)
    print(json.dumps(scan(diff_text, source)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
