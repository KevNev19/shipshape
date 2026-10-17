"""Review surfaces keep ADR 0007's verdict and escalation invariants aligned."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_SURFACES = (
    ROOT / "skills" / "shipshape-review" / "references" / "finding-contract.md",
    ROOT / "templates" / "github" / "agents" / "reviewer.md.tmpl",
    ROOT / "templates" / "github" / "copilot-instructions.md.tmpl",
)
REQUIRED_RULES = (
    '"Looks safe to merge"',
    '"Needs attention first: <the one thing>"',
    '"Do not merge: <reason>"',
    'Any secret in the diff is an automatic "Do not merge".',
    'Red checks can never be called "looks safe" — ever.',
)


def test_review_surfaces_share_verdict_and_escalation_rules():
    for surface in REVIEW_SURFACES:
        content = surface.read_text(encoding="utf-8")
        for rule in REQUIRED_RULES:
            assert rule in content, f"{surface.relative_to(ROOT)} is missing: {rule}"


def test_review_skill_reads_the_diff_before_running_another_authors_checks():
    skill = ROOT / "skills" / "shipshape-review" / "SKILL.md"
    text = " ".join(skill.read_text(encoding="utf-8").split())
    assert "On a branch someone else wrote, first read its diff" in text
    for changed in (".sdlc/config.json", "package scripts", ".github/workflows/"):
        assert changed in text
    assert "run them only after the user says yes" in text
