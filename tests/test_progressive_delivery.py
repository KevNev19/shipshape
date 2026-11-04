"""Progressive delivery is an opt-in checklist, not a deploy workflow."""

from conftest import init_repo, run_script

GUIDE = "docs/sdlc/progressive-delivery.md"


def apply(tmp_path, overrides=None):
    repo = init_repo("repo-python", tmp_path, overrides=overrides)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    return repo, set(payload["written"])


def test_progressive_delivery_guide_stays_off_by_default(tmp_path):
    repo, written = apply(tmp_path)
    assert GUIDE not in written
    assert not (repo / GUIDE).exists()
    config = (repo / ".sdlc/config.json").read_text()
    assert '"progressive_delivery": false' in config


def test_progressive_delivery_guide_renders_when_enabled(tmp_path):
    repo, written = apply(tmp_path, ["features.progressive_delivery=true"])
    assert GUIDE in written
    text = (repo / GUIDE).read_text()
    assert "managed-by: shipshape" in text
    assert "{{" not in text
    assert "Feature flag" in text
    assert "Canary" in text
    assert "does not deploy" in text
    assert "does not replace them" in text
    assert "no deploy workflow" in text.lower() or "There is no deploy workflow" in text
    workflows = list((repo / ".github/workflows").glob("deploy*.yml"))
    assert workflows == []


def test_customize_skill_does_not_describe_the_page_as_a_deploy():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    skill = (root / "skills/shipshape-customize/SKILL.md").read_text()
    reference = (root / "skills/shipshape-customize/references/progressive-delivery.md").read_text()
    assert "references/progressive-delivery.md" in skill
    assert "does not deploy" in reference
    assert "features.progressive_delivery" in reference
