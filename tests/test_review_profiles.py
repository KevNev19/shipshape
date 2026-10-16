"""Review profiles (ADR 0013) stay one contract across the files that carry them.

`skills/shipshape-review/references/profiles.json` lists the profiles, their
path patterns and their lenses; the finding contract names the same profiles
in the same order; the contract and both generated GitHub briefings carry the
same profile rules. Patterns use only `*` and `**`: `*` matches within one
folder, `**` matches any number of folders, and neither matches a name that
starts with a dot. A changed file fits the first profile whose patterns match
it, and `code` when none does.
"""

import fnmatch
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REVIEW_SKILL = ROOT / "skills" / "shipshape-review"
PROFILES_FILE = REVIEW_SKILL / "references" / "profiles.json"
CONTRACT = REVIEW_SKILL / "references" / "finding-contract.md"
RUBRIC = REVIEW_SKILL / "references" / "review-rubric.md"
SKILL = REVIEW_SKILL / "SKILL.md"
REVIEW_SURFACES = (
    CONTRACT,
    ROOT / "templates" / "github" / "agents" / "reviewer.md.tmpl",
    ROOT / "templates" / "github" / "copilot-instructions.md.tmpl",
)
PROFILE_NAMES = ["specification", "plan", "documentation", "code"]
PROFILE_RULES = (
    "Every review uses exactly one profile: specification, plan, documentation, or code.",
    "Use the profile that fits the most changed files when that is at least half of them,"
    " the earlier one in that list on a tie; otherwise review the change as code.",
    "A changed file that fits another profile is still reviewed for what that profile looks for;"
    " its findings join the same report.",
    "Security is checked under every profile.",
    "The verdict and its two automatic escalations are the same under every profile.",
)
INTENT_COUNT = "how many of the changed files fit it"
FIT_RULE = (
    "A changed file fits the first profile in the table above whose patterns match its path;"
    " a file that matches no pattern fits `code`."
)
SKILL_FIT_RULE = (
    "taking the first profile in that file whose patterns match (a file that matches none is code)"
)
CONTRACT_SECTIONS = [
    "## 0. Artefact profile",
    "## 1. Intent",
    "## 2. Verified findings",
    "## 3. Intent conformance",
    "## 4. Material uncertainties",
    "## 5. Verdict",
]
PROFILE_SECTION = re.compile(r"^## 0\. Artefact profile$(.*?)^## 1\. Intent$", re.M | re.S)
PROFILE_ROW = re.compile(r"^\| `([a-z]+)` \|", re.M)
LENS_KEY = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
# Python's fnmatch and Node's path.matchesGlob, which callers use, disagree on these.
UNSUPPORTED_GLOB_CHARS = re.compile(r"[?\[\]{}()!]")
MAX_LENS_PROMPT_CHARS = 500
# A tool that runs only a profile's leading lenses must still check security.
SECURITY_LENS_DEPTH = 3
FILE_PROFILES = [
    ("docs/specs/2026-10-01-login-design.md", "specification"),
    ("docs/login-design.md", "specification"),
    ("docs/adr/0013-artefact-review-profiles.md", "specification"),
    ("docs/decisions/0001-use-example.md", "specification"),
    ("docs/changes/2026-10-12-login.md", "specification"),
    ("rfcs/0001-example.md", "specification"),
    ("docs/plans/2026-10-02-login.md", "plan"),
    ("release-plan.md", "plan"),
    ("README.md", "documentation"),
    ("AGENTS.md", "documentation"),
    ("CLAUDE.md", "documentation"),
    ("docs/sdlc/harness.md", "documentation"),
    ("docs/guide/install.rst", "documentation"),
    ("docs/guide/intro.mdx", "documentation"),
    ("docs/guide/intro.adoc", "documentation"),
    ("skills/example/SKILL.md", "documentation"),
    ("src/app.py", "code"),
    ("spec/models/user_spec.rb", "code"),
    ("templates/github/agents/reviewer.md.tmpl", "code"),
    (".github/copilot-instructions.md", "code"),
    (".claude/skills/example/SKILL.md", "code"),
]


def flat(text: str) -> str:
    return " ".join(text.split())


def load_profiles() -> list[dict]:
    return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))["profiles"]


def glob_matches(path: str, pattern: str) -> bool:
    return segments_match(path.split("/"), pattern.split("/"))


def segments_match(parts: list[str], patterns: list[str]) -> bool:
    if not patterns:
        return not parts
    head, rest = patterns[0], patterns[1:]
    if head == "**":
        for skip in range(len(parts) + 1):
            if segments_match(parts[skip:], rest):
                return True
            if skip < len(parts) and parts[skip].startswith("."):
                return False
        return False
    if not parts or (parts[0].startswith(".") and not head.startswith(".")):
        return False
    return fnmatch.fnmatchcase(parts[0], head) and segments_match(parts[1:], rest)


def profile_of(path: str, profiles: list[dict]) -> str:
    for profile in profiles:
        if any(glob_matches(path, pattern) for pattern in profile["paths"]):
            return profile["name"]
    return "code"


def test_review_surfaces_share_the_profile_rules():
    for surface in REVIEW_SURFACES:
        content = flat(surface.read_text(encoding="utf-8"))
        for rule in (*PROFILE_RULES, INTENT_COUNT):
            assert rule in content, f"{surface.relative_to(ROOT)} is missing: {rule}"


def test_contract_says_how_a_changed_file_fits_a_profile():
    assert flat(FIT_RULE) in flat(CONTRACT.read_text(encoding="utf-8"))


def test_profiles_file_lists_the_contract_profiles_in_order():
    section = PROFILE_SECTION.search(CONTRACT.read_text(encoding="utf-8"))
    assert section, "finding-contract.md has no '## 0. Artefact profile' before '## 1. Intent'"
    assert PROFILE_ROW.findall(section.group(1)) == PROFILE_NAMES
    assert [profile["name"] for profile in load_profiles()] == PROFILE_NAMES


def test_profiles_file_has_the_documented_shape():
    text = PROFILES_FILE.read_text(encoding="utf-8")
    data = json.loads(text)
    assert text == json.dumps(data, indent=2) + "\n"
    assert set(data) == {"version", "profiles"}
    assert data["version"] == 1
    for profile in data["profiles"]:
        assert set(profile) == {"name", "paths", "lenses"}, profile
        assert profile["paths"], profile["name"]
        for pattern in profile["paths"]:
            assert isinstance(pattern, str) and pattern, profile["name"]
            assert not UNSUPPORTED_GLOB_CHARS.search(pattern), pattern
        keys = [lens["key"] for lens in profile["lenses"]]
        assert keys and len(keys) == len(set(keys)), profile["name"]
        for lens in profile["lenses"]:
            assert set(lens) == {"key", "prompt"}, lens
            assert LENS_KEY.match(lens["key"]), lens["key"]
            assert 0 < len(lens["prompt"]) <= MAX_LENS_PROMPT_CHARS, lens["key"]


def test_code_profile_comes_last_and_takes_the_rest():
    code = load_profiles()[-1]
    assert code["name"] == "code"
    assert code["paths"] == ["**"]


def test_every_profile_checks_security_among_its_leading_lenses():
    for profile in load_profiles():
        leading = [lens["key"] for lens in profile["lenses"][:SECURITY_LENS_DEPTH]]
        assert "security" in leading, profile["name"]


@pytest.mark.parametrize(("path", "expected"), FILE_PROFILES)
def test_changed_file_takes_the_first_profile_that_fits(path, expected):
    assert profile_of(path, load_profiles()) == expected


def test_contract_puts_the_profile_before_its_five_parts():
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    headings = [line.split(" (")[0] for line in lines if line.startswith("## ")]
    assert headings == CONTRACT_SECTIONS


def test_skill_and_rubric_work_through_the_profile_lenses():
    skill = SKILL.read_text(encoding="utf-8")
    assert "**Classify the artefact.**" in skill
    assert skill.index("**Classify the artefact.**") < skill.index("**Read the whole diff**")
    assert "(references/profiles.json)" in skill
    assert SKILL_FIT_RULE in flat(skill)
    rubric = RUBRIC.read_text(encoding="utf-8")
    assert "## 0. Profile" in rubric
    assert "(profiles.json)" in rubric
