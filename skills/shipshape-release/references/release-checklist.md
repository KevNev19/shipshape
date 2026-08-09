# Release checklist

Before proposing a version:

1. Working tree clean; on the default branch; CI green on the release commit.
2. Commits since the last tag reviewed — nothing half-finished going out.
3. Version bump matches the content (patch = fixes only, minor = new
   features, major = something breaks for existing users). When torn
   between two, pick the bigger bump — surprising users is worse than an
   inflated number.

After tagging:

4. Tag pushed; release workflow succeeded (`gh run list --workflow=release.yml -L 1`).
5. Release notes read sensibly to someone who didn't write the code.
6. If the release workflow failed: the tag exists but no release — fix the
   workflow and re-run it (`gh run rerun`), don't delete the tag.

First release of a project: suggest v0.1.0 ("early but usable"), not v1.0.0.
v1.0.0 is a promise of stability — suggest it only when the user says the
project is ready to be relied on.
