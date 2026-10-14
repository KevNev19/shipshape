# Finding contract

Every review first chooses its profile (section 0); the report then follows
the order of sections 1 to 5. The reviewer reads the full diff internally but
does not narrate it file by file. Findings-first changes what the human reads,
not what the reviewer inspects.

## 0. Artefact profile

Every review uses exactly one profile: specification, plan, documentation, or code.
The profile decides which lenses (the questions a review works through) apply
and what a finding's evidence points at. Sections 1 to 5 keep their order and
wording under every profile.

| Profile | Fits | Evidence for a finding |
| --- | --- | --- |
| `specification` | specifications, design and decision records, change intent | the file and line of the requirement, and the line it contradicts or the acceptance check it lacks |
| `plan` | implementation plans | the file and line of the step, and the dependency, definition or verification it lacks |
| `documentation` | other Markdown, MDX, reStructuredText and AsciiDoc | the file and line of the statement, and the code, command or link that shows it wrong |
| `code` | everything else | a check result, or an exact file and line |

[profiles.json](profiles.json) holds each profile's path patterns and its
lenses, most important first. In a pattern, `*` matches within one folder and
`**` matches any number of folders; neither matches a name that starts with a
dot, so files under `.github/` or `.claude/` are code.

A changed file fits the first profile in the table above whose patterns match its path; a file that matches no pattern fits `code`.

Use the profile that fits the most changed files when that is at least half of them,
the earlier one in that list on a tie; otherwise review the change as code.
A changed file that fits another profile is still reviewed for what that profile looks for; its findings join the same report.
In the Intent part, name the profile and how many of the changed files fit it.

Security is checked under every profile.
The verdict and its two automatic escalations are the same under every profile.

## 1. Intent

Say whether an intent artifact (a written record of what the change is meant
to do) is available. Look for intent artifacts under `docs/changes/`. Link the
artifact or originating issue (the task that led to the change) when one
exists. When neither exists, say: "No intent artifact was found. This review
judged the change on its own terms."

## 2. Verified findings

Report verified findings in severity order. Each finding has:

- evidence: a check result, or an exact file and line;
- the consequence in plain language; and
- exactly one next action.

If there are none, say "No verified findings." Do not invent a finding to
fill the section.

## 3. Intent conformance (match to the request)

Say whether the change does what was asked, and only that. Name any
unrequested functionality: behaviour beyond the stated intent.

## 4. Material uncertainties (important things that could not be verified)

State what could not be verified. "No verified findings" never means "no
risk." Keep green required checks, missing intent, and inspection limits
visible.

## 5. Verdict

End on exactly one verdict: "Looks safe to merge", "Needs attention first: <the one thing>",
or "Do not merge: <reason>".

Any secret in the diff is an automatic "Do not merge".
Red checks can never be called "looks safe" — ever.
