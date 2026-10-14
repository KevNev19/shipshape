"""Tests for the test-integrity diff check: tests a diff deletes, skips or weakens.

Hand-written unified diffs go in on stdin, so most cases need no git; the git
sources (--range, --staged and the default, the uncommitted change) run against a
real temporary repository.
"""

import json
import os
import subprocess
import sys

import pytest
from conftest import SCRIPTS, run_script

SCRIPT = SCRIPTS / "test_integrity.py"
MATH_TESTS = (
    "def test_adds():\n"
    "    assert add(2, 2) == 4\n"
    "    assert add(0, 0) == 0\n"
    "\n"
    "\n"
    "def test_subtracts():\n"
    "    assert sub(3, 1) == 2\n"
)
LOOSENED_MATH_TESTS = MATH_TESTS.replace("assert sub(3, 1) == 2", "assert sub(3, 1)")
NOT_A_REPOSITORY = "The folder is not inside a git work tree, so nothing was checked."
NOT_A_REPOSITORY_NEXT = (
    "Run the scan inside a git repository, or pipe a unified diff in with --stdin."
)


def changed(path: str, *lines: str) -> list[str]:
    return [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", *lines]


def created(path: str, *lines: str) -> list[str]:
    header = [f"diff --git a/{path} b/{path}", "new file mode 100644", "--- /dev/null"]
    return [*header, f"+++ b/{path}", *lines]


def deleted(path: str, *lines: str) -> list[str]:
    header = [f"diff --git a/{path} b/{path}", "deleted file mode 100644", f"--- a/{path}"]
    return [*header, "+++ /dev/null", *lines]


def diff(*sections: list[str]) -> str:
    return "\n".join(line for section in sections for line in section) + "\n"


def scan_diff(tmp_path, text: str) -> dict:
    """run_script passes no stdin, so a diff goes in through its own subprocess."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "--stdin"],
        input=text,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout
    assert proc.stderr == ""
    return json.loads(proc.stdout)


def run_isolated(args: list[str], cwd) -> tuple[int, dict]:
    """How Rook starts the script: python3 -I -B, by absolute path, from another folder."""
    proc = subprocess.run(
        [sys.executable, "-I", "-B", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True
    )
    assert proc.stderr == ""
    return proc.returncode, json.loads(proc.stdout)


def kinds(result: dict) -> list[tuple[str, int, str]]:
    return [(item["file"], item["line"], item["kind"]) for item in result["findings"]]


def git(repo, *args: str) -> None:
    identity = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    hermetic = ["-c", "core.hooksPath=/dev/null"]
    subprocess.run(["git", *identity, *hermetic, *args], cwd=repo, check=True, capture_output=True)


def git_output(repo, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def write(repo, relpath: str, text: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-qb", "main")
    write(repo, "tests/test_math.py", MATH_TESTS)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    return repo


def test_new_test_and_source_change_report_no_findings(tmp_path):
    text = diff(
        changed("src/math.py", "@@ -2 +2 @@", "-    return a - b", "+    return a + b"),
        changed(
            "tests/test_math.py",
            "@@ -7,0 +8,3 @@",
            "+",
            "+def test_adds_negatives():",
            "+    assert add(-1, -1) == -2",
        ),
    )

    assert scan_diff(tmp_path, text) == {
        "ok": True,
        "mode": "test-integrity",
        "source": "stdin",
        "files_scanned": 2,
        "findings": [],
        "unsupported": [],
        "warnings": [],
        "next_action": "No test-integrity findings in this diff.",
    }


def test_deleted_test_is_one_finding_that_covers_its_assertions(tmp_path):
    text = diff(
        changed(
            "tests/test_math.py",
            "@@ -5,3 +4,0 @@",
            "-",
            "-def test_subtracts():",
            "-    assert sub(3, 1) == 2",
        )
    )

    result = scan_diff(tmp_path, text)

    assert result["findings"] == [
        {
            "file": "tests/test_math.py",
            "line": 6,
            "language": "python",
            "kind": "deleted-test",
            "detail": "-def test_subtracts():",
            "consequence": "A deleted test no longer runs, so what it covered is unchecked.",
        }
    ]
    assert result["next_action"] == (
        "Restore or explain the deleted test at tests/test_math.py:6 (1 finding(s) in all)."
    )


def test_context_diff_keeps_an_assertion_removed_beside_a_deleted_test(tmp_path):
    text = diff(
        changed(
            "tests/test_math.py",
            "@@ -10,7 +10,3 @@",
            "-def test_old():",
            "-    assert old() == 1",
            "-",
            " def test_keep():",
            "     x = 1",
            "-    assert keep(x) == 2",
            "     other()",
        )
    )

    assert kinds(scan_diff(tmp_path, text)) == [
        ("tests/test_math.py", 10, "deleted-test"),
        ("tests/test_math.py", 15, "removed-assertion"),
    ]


def test_removed_assertion_is_a_finding(tmp_path):
    text = diff(changed("tests/test_math.py", "@@ -3 +2,0 @@", "-    assert add(0, 0) == 0"))

    result = scan_diff(tmp_path, text)

    assert kinds(result) == [("tests/test_math.py", 3, "removed-assertion")]
    assert result["findings"][0]["detail"] == "-assert add(0, 0) == 0"
    assert result["findings"][0]["consequence"] == (
        "The test no longer checks this, so it can pass while this is wrong."
    )


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        ("tests/test_math.py", "    assert add(2, 2) == 4", "    assert add(2, 2) is not None"),
        (
            "tests/test_math.py",
            "        self.assertEqual(add(2, 2), 4)",
            "        self.assertTrue(add(2, 2))",
        ),
        (
            "tests/test_math.py",
            "    with pytest.raises(ValueError):",
            "    with pytest.raises(Exception):",
        ),
        ("test/math.test.js", "  expect(add(1, 2)).toBe(3)", "  expect(add(1, 2)).toBeTruthy()"),
        ("math_test.go", "\tassert.Equal(t, 3, Add(1, 2))", "\tassert.NotNil(t, Add(1, 2))"),
        ("tests/math.rs", "    assert_eq!(add(1, 2), 3);", "    assert!(add(1, 2) > 0);"),
    ],
)
def test_loosened_assertion_is_a_finding(tmp_path, path, old, new):
    result = scan_diff(tmp_path, diff(changed(path, "@@ -7 +7 @@", f"-{old}", f"+{new}")))

    assert kinds(result) == [(path, 7, "loosened-assertion")]
    assert result["findings"][0]["detail"] == f"-{old.strip()} => +{new.strip()}"


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        (
            "tests/test_math.py",
            "    assert add(2, 2) == expected_total_of_two_and_two",
            [
                "    assert (",
                "        add(2, 2)",
                "        == expected_total_of_two_and_two",
                "    )",
            ],
        ),
        (
            "tests/math.rs",
            "    assert!(add(1, 2) == expected_total_of_one_and_two);",
            ["    assert!(", "        add(1, 2) == expected_total_of_one_and_two", "    );"],
        ),
    ],
)
def test_reflowed_assertion_is_not_a_finding(tmp_path, path, old, new):
    header = f"@@ -7 +7,{len(new)} @@"

    result = scan_diff(tmp_path, diff(changed(path, header, f"-{old}", *[f"+{x}" for x in new])))

    assert result["findings"] == []


def test_changed_expected_value_is_left_to_the_review(tmp_path):
    text = diff(
        changed(
            "tests/test_math.py",
            "@@ -2 +2 @@",
            "-    assert add(2, 2) == 4",
            "+    assert add(2, 2) == 5",
        )
    )

    assert scan_diff(tmp_path, text)["findings"] == []


@pytest.mark.parametrize(
    ("path", "line"),
    [
        ("tests/test_math.py", '@pytest.mark.skip(reason="flaky")'),
        ("tests/test_math.py", "@pytest.mark.xfail"),
        ("tests/test_math.py", '    pytest.skip("later")'),
        ("tests/test_math.py", "        self.skipTest('later')"),
        ("test/math.test.js", "  it.skip('adds two numbers', () => {"),
        ("test/math.test.js", "describe.only('math', () => {"),
        ("test/math.test.js", "  xit('adds two numbers', () => {"),
        ("test/math.test.js", "  fit('adds two numbers', () => {"),
        ("math_test.go", '\tt.Skip("flaky on CI")'),
        ("tests/math.rs", "#[ignore]"),
        ("src/lib.rs", "#[ignore]"),
    ],
)
def test_added_skip_is_a_finding(tmp_path, path, line):
    result = scan_diff(tmp_path, diff(changed(path, "@@ -4,0 +5 @@", f"+{line}")))

    assert kinds(result) == [(path, 5, "skipped-test")]


def test_skipping_a_test_in_place_is_one_finding(tmp_path):
    text = diff(
        changed(
            "test/math.test.js",
            "@@ -3 +3 @@",
            "-  it('adds two numbers', () => {",
            "+  it.skip('adds two numbers', () => {",
        )
    )

    assert kinds(scan_diff(tmp_path, text)) == [("test/math.test.js", 3, "skipped-test")]


def test_skip_marker_moved_to_another_file_is_not_a_finding(tmp_path):
    text = diff(
        changed("tests/test_math.py", "@@ -5 +4,0 @@", "-@pytest.mark.skip"),
        created("tests/test_slow.py", "@@ -0,0 +1 @@", "+@pytest.mark.skip"),
    )

    assert scan_diff(tmp_path, text)["findings"] == []


@pytest.mark.parametrize(
    ("path", "lines", "detail"),
    [
        (
            "math_test.go",
            ["-func TestAdd(t *testing.T) {", "-\tassert.Equal(t, 3, Add(1, 2))", "-}"],
            "-func TestAdd(t *testing.T) {",
        ),
        (
            "test/math.test.js",
            ["-  it('adds two numbers', () => {", "-    expect(add(1, 2)).toBe(3)", "-  })"],
            "-it('adds two numbers', () => {",
        ),
        (
            "src/lib.rs",
            [
                "-    #[test]",
                "-    fn adds_two() {",
                "-        assert_eq!(add(1, 1), 2);",
                "-    }",
            ],
            "-#[test] fn adds_two() {",
        ),
    ],
)
def test_deleted_test_is_a_finding_in_each_language(tmp_path, path, lines, detail):
    header = f"@@ -10,{len(lines)} +9,0 @@"

    result = scan_diff(tmp_path, diff(changed(path, header, *lines)))

    assert kinds(result) == [(path, 10, "deleted-test")]
    assert result["findings"][0]["detail"] == detail


def test_moved_and_reindented_tests_are_not_findings(tmp_path):
    text = diff(
        changed(
            "tests/test_math.py",
            "@@ -1,3 +0,0 @@",
            "-def test_adds():",
            "-    assert add(2, 2) == 4",
            "-    assert add(0, 0) == 0",
            "@@ -6,2 +3,0 @@",
            "-def test_subtracts():",
            "-    assert sub(3, 1) == 2",
            "@@ -7,0 +5,4 @@",
            "+class TestAdd:",
            "+    def test_adds(self):",
            "+        assert add(2, 2) == 4",
            "+        assert add(0, 0) == 0",
        ),
        created(
            "tests/test_sub.py",
            "@@ -0,0 +1,2 @@",
            "+def test_subtracts():",
            "+    assert sub(3, 1) == 2",
        ),
    )

    assert scan_diff(tmp_path, text)["findings"] == []


def test_deleted_test_file_is_one_finding_at_line_one(tmp_path):
    lines = [f"-{line}" for line in MATH_TESTS.splitlines()]
    text = diff(deleted("tests/test_math.py", f"@@ -1,{len(lines)} +0,0 @@", *lines))

    result = scan_diff(tmp_path, text)

    assert kinds(result) == [("tests/test_math.py", 1, "deleted-test")]
    assert result["findings"][0]["detail"] == (
        "file deleted with 2 test(s), first -def test_adds():"
    )


def test_test_file_split_into_others_is_not_a_finding(tmp_path):
    lines = MATH_TESTS.splitlines()
    text = diff(
        deleted("tests/test_math.py", f"@@ -1,{len(lines)} +0,0 @@", *[f"-{x}" for x in lines]),
        created("tests/test_add.py", "@@ -0,0 +1,3 @@", *[f"+{x}" for x in lines[:3]]),
        created("tests/test_sub.py", "@@ -0,0 +1,2 @@", *[f"+{x}" for x in lines[5:]]),
    )

    assert scan_diff(tmp_path, text)["findings"] == []


def test_lines_that_are_not_test_checks_are_ignored(tmp_path):
    text = diff(
        changed("src/math.py", "@@ -2 +1,0 @@", "-    assert a >= 0"),
        changed("src/app.js", "@@ -4 +3,0 @@", "-  assert(total > 0)"),
        changed("src/lib.rs", "@@ -3 +2,0 @@", "-    assert!(n > 0);"),
        changed(
            "math_test.go",
            "@@ -12,2 +11,0 @@",
            '-\t\treturn fmt.Errorf("bad input: %w", err)',
            "-\tlog.Println(err.Error())",
        ),
    )

    result = scan_diff(tmp_path, text)

    assert result["files_scanned"] == 4
    assert result["findings"] == []


@pytest.mark.parametrize(
    ("path", "lines"),
    [
        ("tests/test_quality.py", ["+    source = \"@pytest.mark.skip(reason='later')\""]),
        (
            "test/run.test.ts",
            [
                "-  expect(out.stopped).toBe('cost')",
                "+  expect(out).toMatchObject({ stopped: 'cost', tokens: 1100 })",
            ],
        ),
        (
            "test/gap.test.ts",
            [
                "-  expect(gap(10)).toBe(base + 10)",
                "+  expect(gap(10)).toBe(limit)",
                "+  expect(text.length).toBeGreaterThan(10)",
            ],
        ),
    ],
)
def test_quoted_skips_and_stronger_checks_are_not_findings(tmp_path, path, lines):
    removed = sum(1 for line in lines if line.startswith("-"))
    header = f"@@ -5,{removed} +5,{len(lines) - removed} @@"

    assert scan_diff(tmp_path, diff(changed(path, header, *lines)))["findings"] == []


def test_plain_diff_with_context_and_timestamps_is_read(tmp_path):
    text = diff(
        [
            "--- tests/test_math.py\t2026-10-12 10:00:00",
            "+++ tests/test_math.py\t2026-10-12 10:05:00",
            "@@ -1,3 +1,2 @@",
            " def test_adds():",
            "-    assert add(2, 2) == 4",
            "     assert add(0, 0) == 0",
        ]
    )

    assert kinds(scan_diff(tmp_path, text)) == [("tests/test_math.py", 2, "removed-assertion")]


def test_unsupported_language_is_listed_not_passed(tmp_path):
    text = diff(
        changed(
            "src/test/java/MathTest.java",
            "@@ -9 +8,0 @@",
            "-        assertEquals(4, add(2, 2));",
        )
    )

    result = scan_diff(tmp_path, text)

    assert result["files_scanned"] == 0
    assert result["unsupported"] == ["java"]
    assert result["next_action"] == (
        "No test-integrity findings; changes in java were not checked."
    )


def test_next_action_names_unchecked_languages_beside_findings(tmp_path):
    text = diff(
        changed("tests/test_math.py", "@@ -3 +2,0 @@", "-    assert add(0, 0) == 0"),
        changed(
            "src/test/java/MathTest.java",
            "@@ -9 +8,0 @@",
            "-        assertEquals(4, add(2, 2));",
        ),
    )

    result = scan_diff(tmp_path, text)

    assert result["unsupported"] == ["java"]
    assert result["next_action"].endswith("Also, changes in java were not checked.")


def test_text_that_is_not_a_diff_is_a_warning(tmp_path):
    result = scan_diff(tmp_path, "this is not a diff\n")

    assert result["files_scanned"] == 0
    assert result["findings"] == []
    assert result["warnings"] == [
        "The input has text but no unified diff file headers, so nothing was checked."
    ]


def test_crlf_and_missing_newline_markers_keep_the_finding(tmp_path):
    text = diff(
        changed(
            "tests/test_math.py",
            "@@ -2 +2 @@",
            "-    assert add(2, 2) == 4",
            "\\ No newline at end of file",
            "+    assert add(2, 2)",
            "\\ No newline at end of file",
        )
    ).replace("\n", "\r\n")

    assert kinds(scan_diff(tmp_path, text)) == [("tests/test_math.py", 2, "loosened-assertion")]


def test_diff_bytes_that_are_not_utf8_are_still_scanned(tmp_path):
    text = diff(changed("tests/test_math.py", "@@ -3 +2,0 @@", "-    assert name == 'café'"))
    strict = {**os.environ, "PYTHONIOENCODING": "utf-8:strict"}

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "--stdin"],
        input=text.encode("latin-1"),
        capture_output=True,
        env=strict,
    )

    assert proc.returncode == 0, proc.stderr
    assert kinds(json.loads(proc.stdout)) == [("tests/test_math.py", 3, "removed-assertion")]


def test_default_scan_sees_staged_and_unstaged_work(repo):
    staged = MATH_TESTS.replace("    assert add(0, 0) == 0\n", "")
    write(repo, "tests/test_math.py", staged)
    git(repo, "add", "tests/test_math.py")
    skipped = "@pytest.mark.skip\ndef test_subtracts"
    write(repo, "tests/test_math.py", staged.replace("def test_subtracts", skipped))

    code, result = run_script("test_integrity.py", repo)

    assert code == 0
    assert result["source"] == "worktree"
    assert kinds(result) == [
        ("tests/test_math.py", 5, "skipped-test"),
        ("tests/test_math.py", 3, "removed-assertion"),
    ]


def test_staged_scan_sees_only_the_index(repo):
    staged = MATH_TESTS.replace("    assert add(0, 0) == 0\n", "")
    write(repo, "tests/test_math.py", staged)
    git(repo, "add", "tests/test_math.py")
    skipped = "@pytest.mark.skip\ndef test_subtracts"
    write(repo, "tests/test_math.py", staged.replace("def test_subtracts", skipped))

    code, result = run_script("test_integrity.py", repo, "--staged")

    assert code == 0
    assert result["source"] == "staged"
    assert kinds(result) == [("tests/test_math.py", 3, "removed-assertion")]


def test_range_scan_follows_a_renamed_test_file(repo):
    git(repo, "mv", "tests/test_math.py", "tests/test_arith.py")
    git(repo, "commit", "-qm", "rename")
    write(repo, "tests/test_arith.py", LOOSENED_MATH_TESTS)
    git(repo, "commit", "-qam", "loosen")

    code, result = run_script("test_integrity.py", repo, "--range=HEAD~2..HEAD")

    assert code == 0
    assert result["source"] == "range"
    assert kinds(result) == [("tests/test_arith.py", 7, "loosened-assertion")]


def test_scan_of_a_repository_without_commits_finds_nothing(tmp_path):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    git(fresh, "init", "-qb", "main")
    write(fresh, "tests/test_math.py", MATH_TESTS)
    git(fresh, "add", ".")

    code, result = run_script("test_integrity.py", fresh)

    assert code == 0
    assert result["files_scanned"] == 1
    assert result["findings"] == []


def test_scan_of_a_subfolder_reports_only_its_own_changes_with_paths_from_it(repo):
    write(repo, "app/tests/test_app.py", MATH_TESTS)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "app")
    write(repo, "app/tests/test_app.py", LOOSENED_MATH_TESTS)
    write(repo, "tests/test_math.py", LOOSENED_MATH_TESTS)

    code, result = run_script("test_integrity.py", repo / "app")

    assert code == 0
    assert kinds(result) == [("tests/test_app.py", 7, "loosened-assertion")]


def test_user_git_config_cannot_change_what_a_git_source_reads(repo, tmp_path, monkeypatch):
    write(repo, "tests/test_old.py", "def test_old():\n    assert old() == 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "old")
    git(repo, "rm", "-q", "tests/test_old.py")
    git(repo, "mv", "tests/test_math.py", "tests/test_café.py")
    write(repo, "tests/test_café.py", LOOSENED_MATH_TESTS)
    write(repo, ".gitattributes", "*.py diff=hostile\n")
    config = tmp_path / "gitconfig"
    config.write_text(
        "[core]\n\tquotePath = true\n"
        "[diff]\n\texternal = true\n\tmnemonicPrefix = true\n\trenames = false\n"
        '[diff "hostile"]\n\ttextconv = true\n'
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    code, result = run_script("test_integrity.py", repo)

    assert code == 0
    assert sorted(kinds(result)) == [
        ("tests/test_café.py", 7, "loosened-assertion"),
        ("tests/test_old.py", 1, "deleted-test"),
    ]


def test_isolated_mode_scans_a_repository_with_a_deleted_test(repo, tmp_path):
    """python3 -I leaves the script's own folder off sys.path; detect.py must still load."""
    remaining = MATH_TESTS.replace("\n\ndef test_subtracts():\n    assert sub(3, 1) == 2\n", "")
    write(repo, "tests/test_math.py", remaining)

    code, result = run_isolated([str(repo)], cwd=tmp_path)

    assert code == 0
    assert kinds(result) == [("tests/test_math.py", 6, "deleted-test")]


def test_isolated_mode_scans_a_range_of_two_tree_objects(repo, tmp_path):
    write(repo, "tests/test_math.py", LOOSENED_MATH_TESTS)
    git(repo, "commit", "-qam", "loosen")
    before = git_output(repo, "rev-parse", "HEAD~1^{tree}")
    after = git_output(repo, "rev-parse", "HEAD^{tree}")

    code, result = run_isolated([str(repo), f"--range={before}..{after}"], cwd=tmp_path)

    assert code == 0
    assert result["source"] == "range"
    assert kinds(result) == [("tests/test_math.py", 7, "loosened-assertion")]


def test_isolated_mode_answers_no_findings_for_a_folder_that_is_not_a_repository(
    tmp_path, monkeypatch
):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    code, result = run_isolated([str(plain)], cwd=tmp_path)

    assert code == 0
    assert result == {
        "ok": True,
        "mode": "test-integrity",
        "source": "worktree",
        "files_scanned": 0,
        "findings": [],
        "unsupported": [],
        "warnings": [NOT_A_REPOSITORY],
        "next_action": NOT_A_REPOSITORY_NEXT,
    }


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["{repo}", "--bogus"],
        ["scan", "{repo}"],
        ["{repo}", "--staged", "--stdin"],
        ["{repo}", "--range=--output=leak.txt"],
        ["{repo}", "--range", ""],
        ["{repo}", "--range", "HEAD"],
        ["{missing}", "--stdin"],
        ["{repo}", "--range", "nope..HEAD"],
    ],
)
def test_usage_and_git_errors_are_json_with_exit_two(repo, tmp_path, args):
    values = {"repo": repo, "missing": tmp_path / "missing"}

    code, result = run_script("test_integrity.py", *[arg.format(**values) for arg in args])

    assert code == 2
    assert result["ok"] is False
    assert result["mode"] == "test-integrity"
    assert result["error"]
    assert result["next_action"]
    assert "findings" not in result
    assert not (repo / "leak.txt").exists()
