# Release checklist

## Candidate evidence

The helper's `local` result is the completion criterion before proposing a
version. `ok: true` means all of these refer to one exact SHA:

- the working tree is clean and checked out on GitHub's actual default branch;
- local HEAD, origin's default-branch ref, and GitHub's default-branch head
  agree;
- the candidate's configuration identifies enabled security workflows;
- the exact release workflow is registered and active, and its default-branch
  `.sdlc/scripts/release-preflight.py` helper exists; neither needs a prior tag
  run;
- the exact-path CI workflow and enabled Secret scan and CodeQL workflows have
  an unambiguously latest applicable `push` attempt for that SHA and branch,
  ordered by the current attempt's UTC `run_started_at`;
- each applicable run completed successfully and every returned job succeeded.
- when CodeQL applies, the candidate is still the current default-branch tip;
  the uniquely latest CodeQL analysis for that SHA, ref, and expected workflow
  category was created no earlier than the selected Actions attempt and has an
  empty `error`; and the candidate has no open high, critical, or error-level
  CodeQL alert.

An unrelated workflow, a same-named workflow at another path, an earlier green
attempt before a failed rerun, or a skipped job supplies no evidence. API,
authentication, pagination, missing/malformed/tied attempt chronology, and
incomplete-response errors all stop publication. A local-only repository is not
GitHub-release-ready: connect and push its intended GitHub origin first.

A successful CodeQL Actions workflow and `analyze` job prove execution, not a
successful analysis upload or clean findings. The helper paginates
`code-scanning/analyses` for the default ref and filters client-side because
GitHub does not reliably honor the endpoint's SHA filter. It requires the exact
candidate SHA, default ref, `CodeQL` tool, expected
`.github/workflows/codeql.yml:analyze` key and category, empty `error`, and a
unique latest `created_at` at or after the selected Actions attempt.

The helper separately paginates open `CodeQL` alerts on the default ref. An
alert blocks release when its latest instance is the candidate and its security
severity is high or critical, or its rule severity is error. Reports contain
only alert numbers and GitHub URLs, never finding messages or source snippets.
An open alert whose latest instance is not the exact candidate is unknown and
also stops publication. Missing, stale, ambiguous, malformed, or unavailable
analysis or alert evidence stops publication. The release token needs
`security-events: read`; denied or unavailable code-scanning APIs are not
treated as clean.

GitHub exposes an alert's most recent instance on a branch, not an immutable
historical alert snapshot for an older commit. Therefore every CodeQL-enabled
`local`, `publish`, and `verify-release` check requires the candidate to remain
the current default-branch tip. If the branch advances after tagging, create a
new candidate and version instead of treating the older tag as proven clean.

GitHub generally does not start workflow runs for events created with the
built-in Actions credential
([documented behavior](https://docs.github.com/en/actions/concepts/security/github_token)),
so a bot merge may have no post-merge `push` run. Neither pushing an unchanged ref
nor `workflow_dispatch` satisfies this push-only policy. The bounded recovery is a
separately approved release/version commit pushed with normal human or appropriately
authorized app credentials: restart preflight for that new SHA, whose evidence does
not transfer to the bot-merged SHA. A continuous bot-merge release path remains a
separate feature.

## Version and approval

Review every commit since the last tag. Patch means fixes only, minor includes
new features, and major breaks existing users. When torn between two, choose
the larger bump. First releases normally start at v0.1.0; v1.0.0 is a promise
of stability.

Show the exact SHA and proposed tag at the publication approval boundary. Once
approved, the helper proves the candidate again before tag creation and proves
the local tag plus remote absence immediately before push. Existing local and
remote tags remain immutable; a correction uses a new patch tag.

## Publication evidence

At run start, the rendered workflow asks GitHub for the repository's current
default branch and loads `.sdlc/scripts/release-preflight.py` from that branch.
It does not check out or execute the candidate's helper. This is current trusted
policy, not an immutable default-branch snapshot. The workflow creates a
release only after `publish` verifies the remote tag's exact commit,
default-branch ancestry, enabled workflow identities, latest attempts, and
jobs. Its JSON output records the SHA and supporting run URLs.

After the tag push, `verify-release` must identify the same immutable tag and
SHA, the exact `.github/workflows/release.yml` push run for that tag, and the
non-draft release URL. Wait for a pending run. An external transient or a bug
in the current default-branch helper can be fixed before rerunning the same tag;
the existing approval still covers that unchanged exact tag and SHA. A bug in
the tagged release workflow cannot be fixed by rerunning because its immutable
commit retains the old workflow code. Land that fix on the default branch,
prove a new candidate, choose a new version tag, and obtain approval for the
new exact tag and SHA. Never delete or move the old tag.

## Trust limit

This policy trusts administrators allowed to change the default-branch setting,
the helper fetched from that branch, or release workflow code. A trusted
administrator can therefore replace current or future release policy; this
design does not claim an immutable policy snapshot when the branch moves.
GitHub API availability and the token's read access to Actions and code-scanning
evidence are also required; neither condition is silently skipped.
