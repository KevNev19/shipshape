---
name: shipshape-release
description: Cut a release — pick the right version number, write human-readable notes from the commit history, tag it, and let the release workflow publish it on GitHub. Use when the user says "cut a release", "ship a version", "release this", or "tag v1.2".
disable-model-invocation: true
---

# shipshape-release

Guide the user through a release. A release is a named, tagged version of
the project others can rely on. Follow
[../shipshape-init/references/voice.md](../shipshape-init/references/voice.md);
the full checklist is [references/release-checklist.md](references/release-checklist.md).

## Steps

1. **Preflight.** All three must hold, or explain and stop:
   - clean working tree (`git status --short` empty — nothing half-saved),
   - on the default branch,
   - latest CI on that branch is green (`gh run list --branch <branch> -L 1`
     when a remote exists; skip with a note when not).

2. **What's in this release.** Find the last release tag
   (`git describe --tags --abbrev=0`, or "first release" if none) and list
   the commits since. Summarize them in plain language, grouped as: new
   things, fixes, everything else.

3. **Pick the version.** Semver in one sentence: fixes bump the last number,
   new features the middle, breaking changes the first. Propose the bump the
   commits justify (conventional-commit prefixes are the hint: `fix:` →
   patch, `feat:` → minor). Let the user override.

4. **Confirm once, then tag.** Tagging and pushing publishes the release —
   this is the pause point. On yes:

   ```bash
   git tag -a v<version> -m "v<version>"
   git push origin v<version>
   ```

   The release workflow (`.github/workflows/release.yml`) creates the GitHub
   release with generated notes. If the repo has no remote, create the tag
   and say the GitHub half will happen when the project is pushed.

5. **Verify and report.** `gh release view v<version>` once the workflow
   finishes. Tell the user the release URL and the one next thing (usually:
   nothing — enjoy).

## Don't

- Don't release from a dirty tree or red CI, even if asked to "just ship it"
  — explain what's unfinished first and let them decide with eyes open.
- Don't invent release notes — every line traces to a commit.
- Don't re-tag or move an existing tag; a broken release gets a new patch
  version instead.
- Don't push anything except the release tag.
