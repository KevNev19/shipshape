"""Offline tests for verification-cost aggregation."""

import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verification_cost  # noqa: E402

FIXED_NOW = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)


def test_happy_path_aggregates_runs_and_merged_changes(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path == "repos/owner/repo":
            return {"default_branch": "main"}
        if "/commits?" in path:
            return [{"sha": "a"}, {"sha": "b"}]
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-10T10:00:00Z",
                        "updated_at": "2026-08-10T10:12:00Z",
                    },
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-11T10:00:00Z",
                        "updated_at": "2026-08-11T10:08:00Z",
                    },
                ]
            }
        return {"total_count": 2}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result == {
        "ok": True,
        "window_days": 30,
        "runs": 2,
        "attempts": 2,
        "retried_runs": 0,
        "minutes": 20,
        "merged_changes": 2,
        "minutes_per_merge": 10,
        "landed_changes": 2,
        "minutes_per_landed_change": 10,
        "estimated_cost": {"status": "unknown", "currency": None, "amount": None},
        "warnings": [],
        "next_action": "Review verification minutes and retries for avoidable CI work.",
    }


def test_retried_run_counts_all_attempts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 3,
                        "run_started_at": "2026-08-12T10:00:00Z",
                        "updated_at": "2026-08-12T10:15:00Z",
                    }
                ]
            }
        return {"total_count": 0}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["runs"] == 1
    assert result["attempts"] == 3
    assert result["retried_runs"] == 1
    assert result["minutes_per_merge"] is None


def test_missing_token_fails_without_network(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def unexpected_fetch(_path):
        raise AssertionError("network fetch should not run without a token")

    monkeypatch.setattr(verification_cost, "fetch_json", unexpected_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is False
    assert result["estimated_cost"]["status"] == "unknown"
    assert "Set GITHUB_TOKEN" in result["next_action"]


def test_malformed_run_attempt_is_graceful(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": "not-a-number",
                        "run_started_at": "2026-08-12T10:00:00Z",
                        "updated_at": "2026-08-12T10:05:00Z",
                    }
                ]
            }
        return {"total_count": 1}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is True
    assert result["runs"] == 1
    assert result["attempts"] == 1
    assert result["retried_runs"] == 0
    assert result["warnings"]


def test_malformed_pagination_timestamp_is_graceful(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    malformed = {
        "run_attempt": 1,
        "run_started_at": "not-a-timestamp",
        "updated_at": "2026-08-12T10:05:00Z",
    }
    batch = [
        {
            "run_attempt": 1,
            "run_started_at": "2026-08-12T10:00:00Z",
            "updated_at": "2026-08-12T10:05:00Z",
        }
        for _ in range(99)
    ] + [malformed]

    def fake_fetch(path):
        if path.endswith("&page=1"):
            return {"workflow_runs": batch}
        if path.startswith("repos/"):
            return {"workflow_runs": []}
        return {"total_count": 1}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is True
    assert result["runs"] == 99
    assert result["warnings"]


def test_run_at_exact_cutoff_is_included(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)

    def fake_fetch(path):
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-10T12:00:00Z",
                        "updated_at": "2026-08-10T12:01:00Z",
                    }
                ]
            }
        query = urllib.parse.unquote(path.split("q=", 1)[1].split("&", 1)[0])
        assert query == ("repo:owner/repo is:pr is:merged merged:>=2026-08-10T12:00:00+00:00")
        return {"total_count": 1}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=now)

    assert result["runs"] == 1
    assert result["minutes"] == 1


def test_trunk_pushes_count_when_no_pull_request_merged(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path == "repos/owner/repo":
            return {"default_branch": "main"}
        if "/commits?" in path:
            return [{"sha": "1"}, {"sha": "2"}, {"sha": "3"}, {"sha": "4"}]
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-12T10:00:00Z",
                        "updated_at": "2026-08-12T10:10:00Z",
                    }
                ]
            }
        return {"total_count": 0}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is True
    assert result["merged_changes"] == 0
    assert result["minutes_per_merge"] is None
    assert result["landed_changes"] == 4
    assert result["minutes_per_landed_change"] == 2.5
    assert result["estimated_cost"]["status"] == "unknown"
    assert result["warnings"] == []


def test_unreadable_default_branch_stays_unknown(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path == "repos/owner/repo":
            return {"default_branch": "not a branch"}
        if "/commits?" in path:
            raise AssertionError("commits must not be read when the branch name is unusable")
        if path.startswith("repos/"):
            return {"workflow_runs": []}
        return {"total_count": 0}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is True
    assert result["landed_changes"] is None
    assert result["minutes_per_landed_change"] is None
    assert result["warnings"]


def test_non_ascii_and_plus_branch_names_are_counted(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path, branch):
        if path == "repos/owner/repo":
            return {"default_branch": branch}
        if "/commits?" in path:
            assert urllib.parse.quote(branch, safe="") in path
            return [{"sha": "abc"}]
        if path.startswith("repos/"):
            return {"workflow_runs": []}
        return {"total_count": 0}

    for branch in ("développement", "release+stable"):
        monkeypatch.setattr(
            verification_cost,
            "fetch_json",
            lambda path, branch=branch: fake_fetch(path, branch),
        )
        result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)
        assert result["landed_changes"] == 1, branch
        assert result["minutes_per_landed_change"] is None or result["minutes"] == 0


def test_truncated_commit_count_stays_unknown(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_fetch(path):
        if path == "repos/owner/repo":
            return {"default_branch": "main"}
        if "/commits?" in path:
            return [{"sha": str(i)} for i in range(100)]
        if path.startswith("repos/"):
            return {"workflow_runs": []}
        return {"total_count": 0}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=FIXED_NOW)

    assert result["ok"] is True
    assert result["landed_changes"] is None
    assert result["minutes_per_landed_change"] is None
    assert any("truncated" in warning for warning in result["warnings"])


def test_cost_instructions_stop_when_the_summary_failed():
    skill = (
        Path(__file__).resolve().parent.parent / "skills" / "shipshape-doctor" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "If `ok` is false" in skill
    assert "were not measured" in skill


def test_run_just_outside_cutoff_is_excluded(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)

    def fake_fetch(path):
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-10T11:59:59.999999Z",
                        "updated_at": "2026-08-10T12:01:00Z",
                    }
                ]
            }
        return {"total_count": 0}

    monkeypatch.setattr(verification_cost, "fetch_json", fake_fetch)

    result = verification_cost.summarize("owner/repo", 30, now=now)

    assert result["runs"] == 0
    assert result["minutes"] == 0
