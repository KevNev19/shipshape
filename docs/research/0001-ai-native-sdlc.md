# Challenging the traditional SDLC: does it survive AI-native development?

- Status: Living research document (v1.1, 2026-08-10 — every cited URL
  fetched and checked against its claim; quotes verified verbatim against
  primaries; misattributions and one cost-math error from v1 corrected)
- Purpose: working document for stress-testing traditional SDLC and CI/CD
  orthodoxy against how software is actually built in 2026, and sketching
  what an AI-native lifecycle could look like. Opinionated by design;
  every external claim carries a source. Where evidence is vendor-tainted
  or contested, it says so inline.
- Relationship to this repo: shipshape installs a conventional SDLC
  (CI, CodeQL, review gates, trunk-based flow). This document asks which
  of those conventions are durable and which are transitional. Kit policy
  lives in [docs/agents/harness.md](../agents/harness.md); nothing here
  changes policy — a superseding ADR would.

---

## 1. Framing: what actually changed

Traditional SDLC — phased delivery, sprint ceremonies, code review as the
quality gate, CI/CD as the delivery backbone — was built around one
economic fact: **human coding time is scarce and expensive**. Its
ceremonies schedule scarce human attention, while its gates assume that
work is produced slowly enough for people to inspect it.

AI changes that economic foundation. The important shift is not simply
that "AI writes code now." It is that **the marginal cost of producing
code is collapsing toward zero while the cost of verifying,
understanding, and trusting code is rising**. Pedro Tavares gave the
canonical account in June 2025: "The marginal cost of adding new
software is approaching zero, especially with LLMs. But what is the price
of understanding, testing, and trusting that code? Higher than ever."
([ordep.dev](https://ordep.dev/posts/writing-code-was-never-the-bottleneck))
Robert Laszczak sharpened the asymmetry in 2026: "The biggest
bottleneck of implementation quietly shifted from producing code to
reading code" — writing accelerated, review didn't.
([threedots.tech](https://threedots.tech/post/understanding-code-is-bottleneck/))

That shift has two structural consequences, and the rest of this document
works through them:

1. **Every SDLC stage that meters human writing effort is optimizing a
   solved problem.** Estimation, sprint capacity, story points, velocity —
   all denominated in human coding hours.
2. **Every stage that meters human comprehension is now the constraint.**
   Review, testing strategy, architecture coherence, incident response,
   onboarding.

Sonya Siderova offers the honest one-line summary — "Agile isn't dead.
It's optimizing a constraint that moved." — the constraint having moved
from the mechanics of human collaboration to decision-making and
validation.
([InfoQ, Feb 2026](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate))

That distinction matters. Before deciding which practices should change,
we need to recover what those practices were meant to accomplish.

## 2. Steelman: what traditional SDLC was actually for

Traditional practices were not arbitrary ceremony. Each solved a real
coordination, quality, or delivery problem, and most of those problems
still exist even if their original implementation no longer fits.

| Practice | What it actually optimized | Does the problem still exist? |
|---|---|---|
| Requirements/specs | Shared intent before expensive build | Yes — arguably more (see §6) |
| Sprints, estimation | Scheduling scarce human coding time; forecasting | Mostly no — the scarce resource moved |
| Standups/ceremonies | Synchronizing human mental models | Transformed — agents don't attend, but humans still drift |
| Code review | Defect detection + knowledge transfer + accountability | Yes, but the mechanism is breaking (§4, §5) |
| Testing | Catching human error patterns | Yes, but AI error patterns differ (§4) |
| CI | Bounding integration pain (superlinear in batch size) | Yes — more than ever |
| CD/small batches | Fast feedback, small blast radius | Yes — more than ever |
| Branch/PR workflow | Serializing changes through human judgment | Under the most strain of anything on this list |

Two heavyweight witnesses argue for continuity from *inside* the Agile
canon, and any "Agile is dead" claim has to answer them. Kent Beck (XP,
TDD, Manifesto signatory) describes his own practice as "augmented
coding": "The value system in augmented coding is similar to hand coding
— tidy code that works. It's just that I don't type much of that code."
What changes is *where* judgment goes: "I make more consequential
programming decisions per hour, fewer boring vanilla decisions."
([newsletter.kentbeck.com](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes))

Martin Fowler & Unmesh Joshi make a deeper objection to
generate-then-review. Stable abstractions are *discovered through the act
of coding*, not specified upfront. In Joshi's words, "Reviewing
LLM-generated code is rarely enough — you miss the deep thinking that
happens when you are coding yourself."
([martinfowler.com](https://martinfowler.com/articles/convo-llm-abstractions.html))

The counterposition is real but contested. Steve Jones of Capgemini says
"Agentic SDLCs are too fast for Agile": apps built in hours make
two-week sprints the wrong unit, while documentation and architectural
planning become "more critical than ever" because agents need written
intent. Yet Forrester 2025 found 95% of professionals affirming Agile's
continued relevance.
([InfoQ debate](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate))

Our working position follows: the *values* — feedback, small steps,
working software, adaptation — survive. The *ceremonies* were
implementations tuned to a constraint that moved. We should critique the
implementations, not the values, by tracing the pressure through each
phase of delivery.

## 3. Pressure points, phase by phase

Once we separate enduring goals from inherited mechanisms, the pattern is
consistent across the lifecycle: intent and feedback become more
important, while practices that ration human production or depend on
unlimited human review capacity begin to fail.

### Requirements & planning

Intent capture holds and matters more than ever: an agent will happily
build the wrong thing fast. AWS guidance therefore replaces "sprint planning"
with "intent design" — constrain the executor's state space,
but don't script its path
([via InfoQ](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate)).

Estimation, by contrast, breaks. Story points encode human effort,
fatigue, and uncertainty. Simon Willison notes that these habits were
built around the now-collapsed constraint of expensive coding time.
Paraphrasing his framing, the question shifts from justifying development
time to deciding which problems are worth solving.
([simonw.substack.com](https://simonw.substack.com/p/agentic-engineering-patterns))

Casey West's verification→validation shift completes the inversion.
Agents are increasingly good at checking conformance-to-spec; the
expensive human residue is deciding whether the spec was *right*
([via InfoQ](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate)).
Planning therefore moves away from effort accounting and toward durable,
testable intent.

### Implementation

Implementation is the phase that shrank, although not uniformly. As §5
details, individual task completion rises ~20–26% in the credible RCTs,
but gains collapse as codebase complexity and maturity increase. For
high-complexity brownfield work, they fall to 0–10% and turn negative once
rework is netted out — a category that describes much of production
engineering (Stanford, ~100k developers; slides only, not yet
peer-reviewed —
[slides](https://aiconference.com/wp-content/uploads/2025/09/Yegor-Denisov-Blanch-Will-AI-Replace-Software-Engineers_-.pptx.pdf)).

The craft has not disappeared; it has moved into **harness engineering**
(§6). The durable artifact is increasingly the environment that makes
agents reliable, rather than the individual diff. That transfer puts
immediate pressure on the gate that still expects people to inspect every
line.

### Code review — the gate under the most strain

Code review is where production and comprehension rates collide most
visibly. Bryan Finster, Minimum CD author and ex-Walmart CD lead, frames
this as a sampling-rate problem: human reviewers catch defects effectively
up to ~400 LOC and degrade sharply beyond, while a single AI feature can
blow past that limit. "Adding more human reviewers to a blocking queue does not fix
  this... automate feedback so the sampling rate matches the production
  rate." His conclusion is that humans should review agent
*findings*, not raw diffs.
([bryanfinster.substack.com](https://bryanfinster.substack.com/p/ai-broke-your-code-review-heres-how))

The data agrees that the queue is where review breaks. LinearB's dataset
of 8.1M PRs from 4,800 teams in 42 countries shows that AI PRs wait
~4.6–5.3x longer for reviewer pickup, with agentic PRs at the high end
(>16 hours vs ~200 minutes). At p75 they are ~2.5x larger, 400+ vs 157 LOC,
and they merge at 32.7% vs 84.5% for human-authored PRs. Once review
*starts*, AI code is reviewed faster. The delay is queueing rather than
reading, and LinearB interprets those fast reviews as superficial
validation.

The full benchmarks report adds a seniority split: seniors spend 38 min
reviewing AI PRs and accept 23.7%, while juniors spend 15 min and accept
31.9%. Scrutiny and acceptance move in opposite directions.
([linearb.io](https://linearb.io/blog/8-million-prs-engineering-productivity),
[full report](https://linearb.io/resources/software-engineering-benchmarks-report),
vendor telemetry)

Rubber-stamping is also a documented belief. A CMU qualitative study of
~3,100 practitioner opinions records superficial approval under volume,
comprehension difficulty undermining feedback, and review itself becoming
the bottleneck
([arXiv 2607.07980](https://arxiv.org/pdf/2607.07980) — evidence about
the discourse, not measured defect rates). A related claim — that AI
code's idiomatic polish itself disarms reviewer suspicion — circulates
only in secondary outlets with no traced primary; it is plausible but
unverified.

The deeper problem is that comprehension used to be a byproduct of
friction. Armin Ronacher, Flask creator and agentic-coding *adopter*,
argues that modifying someone else's code once forced reading, questions,
and negotiation. That "waste" was the knowledge-transfer mechanism.
"Agents remove much of that friction...
  The tower does not fall, and so we do not notice what was lost."
([lucumr.pocoo.org](https://lucumr.pocoo.org/2026/7/13/the-tower-keeps-rising/))

Open source offers a natural experiment because its review capacity
cannot simply be bought. curl announced in January 2026 that it was
ending its bug bounty, effective Feb 1, after AI-assisted reports reached
~20% of volume while only ~5% of submissions identified genuine
vulnerabilities. Stenberg's own phrase was "death by a thousand AI slops"
([RedMonk](https://redmonk.com/kholterhoff/2026/02/03/ai-slopageddon-and-the-oss-maintainers/),
[BleepingComputer](https://www.bleepingcomputer.com/news/security/curl-ending-bug-bounty-program-after-flood-of-ai-slop-reports/)).
curl then [returned to HackerOne in March](https://daniel.haxx.se/blog/2026/02/25/curl-security-moves-again/),
so this was not a clean death. Jazzband, with 84 projects and >150M
downloads/month, [shut down](https://jazzband.co/news/2026/03/14/sunsetting-jazzband).
Ghostty and tldraw restricted external PRs (RedMonk, above), as did
[Ladybird and openai/codex](https://codenote.net/en/posts/oss-external-pr-shutdown-2026/).
Each case has confounds; the pattern is real.

### Testing

Testing remains essential, but familiar signals can now point in the
wrong direction. AI-generated suites can achieve high line coverage while
killing few mutants, producing "perpetually green" tests. Mutation
testing is therefore being revived as a meta-gate on test quality
([Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/mutation-testing)),
with property-based testing as the complementary technique: assert
invariants rather than examples
([arXiv 2307.04346](https://arxiv.org/pdf/2307.04346)).

The reason is not merely more errors, but different errors. Human-shaped
tests catch typos and off-by-ones; AI code fails differently. Apiiro
reports trivial syntax errors *down* while privilege-escalation paths and
architectural design flaws are *up*: the errors moved from shallow to
deep
([The Register coverage](https://www.theregister.com/2025/09/05/ai_code_assistants_security_problems/),
which itself cautions that "security findings" ≠ exploitable
vulnerabilities; a dispute of Apiiro's multipliers attributed to Contrast
Security's CTO circulates but is untraced to a primary).

The security base rates reinforce that concern. Veracode's 2025 report,
covering 100+ LLMs and 80 tasks, found that 45% of generations introduce
known security flaws, with Java worst at ~72% failure
([2025 report](https://www.veracode.com/resources/analyst-reports/2025-genai-code-security-report/)).
Its Spring 2026 update, covering 150+ LLMs, finds security pass rates
stuck at ~55%, and **model scale doesn't fix it**: models from 20B to 400B
params cluster at the same mark
([Spring 2026](https://www.veracode.com/blog/spring-2026-genai-code-security/)).
Both are adversarial benchmarks, not observed production code.
Observational GitHub analysis instead finds ~12% of AI-attributed files
with identifiable CWEs
([arXiv 2510.26103](https://arxiv.org/abs/2510.26103)).

AI also creates genuinely new attack surface through package
hallucination, or slopsquatting. Across 16 LLMs in 2025, 19.7% of
suggested packages did not exist, and 43% of hallucinated names repeated
consistently, making them pre-registerable by attackers
([socket.dev](https://socket.dev/blog/slopsquatting-how-ai-hallucinations-are-fueling-a-new-class-of-supply-chain-attacks)).
Frontier models improved to ~4.6–6.1% in an Oct 2025–Mar 2026
re-evaluation ([arXiv 2605.17062](https://arxiv.org/pdf/2605.17062)).
The remaining risk shifts more responsibility toward release-time and
runtime controls.

### Release & operations

As change volume grows, progressive delivery — flags, canaries, automated
rollback — is promoted from a nice-to-have toward the primary safety net.
We should be honest about the evidence, however: "flags + rollback replace pre-merge review"
is asserted by flag vendors and **measured by nobody**.
No controlled data exists on change-failure rate at 10x change volume.

The quiet damage appears in maintenance. Across 623M changes from
2023–2026, GitClear reports that refactoring fell from 21% of changed
lines in 2022 to 3.8% in 2026; cross-file reuse fell −35%; legacy
maintenance fell −74%; duplication rose +81%; and developers became ~5x
likelier to copy/paste than refactor.
([gitclear.com](https://www.gitclear.com/the_ai_code_quality_maintainability_gap),
vendor telemetry, correlational, but the longest baseline anyone has)

That maintenance burden is not only technical. It also changes how people
learn, decide, and sustain attention.

### People & skills (cross-cutting)

Skill formation is the first concern. An RCT with n=52 found that
AI-assisted learners scored 17% lower on comprehension, with debugging
hit hardest. There was no task speedup, so the skill cost bought nothing
([arXiv 2601.20245](https://arxiv.org/html/2601.20245v1); one-hour study
of a months-scale phenomenon; Anthropic-affiliated — authored by Shen via
the Anthropic Fellows Program and Tamkin at Anthropic).

Judgment can weaken alongside comprehension. A Microsoft/CMU study (CHI
2025, n=319) found that higher confidence in AI led to less critical
evaluation. According to the paper, participants who felt underqualified
showed disproportionate trust even while knowing the AI errs
([microsoft.com](https://www.microsoft.com/en-us/research/publication/the-impact-of-generative-ai-on-critical-thinking-self-reported-reductions-in-cognitive-effort-and-confidence-effects-from-a-survey-of-knowledge-workers/),
self-reported).

The effect on juniors remains unresolved. Stanford's Digital Economy Lab
reports employment for developers 22–25 down ~20% since late 2022 while
older cohorts grew
([Canaries in the Coal Mine](https://digitaleconomy.stanford.edu/publication/canaries-in-the-coal-mine-six-facts-about-the-recent-employment-effects-of-artificial-intelligence/)).
The result is confounded by the tech correction; causality is not
established. Yegge's "juniors win" thesis
([Sourcegraph](https://sourcegraph.com/blog/revenge-of-the-junior-developer))
directly contradicts the employment data.

Finally, attention does not parallelize. Adam Tornhill writes that
"agentic coding is
  mentally expensive"; decision density exhausts
developers in hours, cutting against the fleet-management vision
([Fowler fragments](https://martinfowler.com/fragments/2026-05-27.html)).
That matches Faros AI's cognitive-load telemetry from 22k devs — vendor
telemetry frequently misattributed to DORA — which records +67.4% PR
contexts/day, +13.8% work restarts, and 26% more tasks idle 7+ days
([faros.ai](https://www.faros.ai/research/ai-acceleration-whiplash)).

Across phases, then, the old lifecycle does not fail uniformly. Its
automated feedback mechanisms become more valuable, while its assumptions
about human-paced production and review become less credible. CI/CD needs
the same separation of mechanism from purpose.

## 4. Is traditional CI/CD still valid?

Traditional CI/CD remains valid, but only after separating its automated
feedback loop from the human-paced assumptions wrapped around it. We can
do that by decomposing CI/CD into the founding assumptions behind Fowler's
*Continuous Integration* and Humble & Farley's *Continuous Delivery*,
then checking each one.

**The four load-bearing assumptions:**
1. Change arrival rate is bounded by human speed (the "ten-minute build"
   is calibrated to human commit cadence).
2. The author understands their change.
3. Reviewer comprehension is cheap relative to the change.
4. The pipeline has spare capacity relative to arrival rate.

**Verdict per assumption:**

| Assumption | Status | Evidence |
|---|---|---|
| Integration pain superlinear in batch size | **Holds — stronger than ever** | DORA's mechanism for the 2024 instability finding was exactly "AI enables larger batches" ([dora.dev](https://dora.dev/research/2024/dora-report/)) |
| Fast feedback loops | **Holds** | DORA 2025: teams with strong automated testing and fast feedback capture AI gains; weak teams get punished harder ([DORA 2025](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report)) |
| Human-paced arrival rate | **Broken** | Merge-queue math explodes nonlinearly under agent arrival rates; flaky-test retries become self-inflicted DoS ([tianpan.co](https://tianpan.co/blog/2026-07-02-the-merge-queue-is-the-new-bottleneck)) |
| Author understands the change | **Broken** | Werner Vogels' "verification debt"; Sonar survey: 96% don't fully trust AI code, only 48% verify before committing ([Sonar press release](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/), vendor survey) |
| Reviewer comprehension is cheap | **Broken** | LinearB queueing data, Finster's sampling-rate argument (§3) |
| Humans are the error source automation protects against | **Inverted** | CI must now be hardened *against the automation*: microVM/syscall sandboxing (Kata Containers, gVisor) via the kubernetes-sigs Agent Sandbox project — the working assumption being that agent-written code will eventually do something it shouldn't ([agent-sandbox.sigs.k8s.io](https://agent-sandbox.sigs.k8s.io/)) |

The evidence creates a tension that we need to hold rather than resolve
away. DORA 2025, the strongest source at ~5,000 respondents, finds that
"AI doesn't fix a team; it amplifies what's already there." CI/CD
discipline became *more* decisive, not less. The instability finding
isn't "CI is obsolete"; it's "teams with weak CI get punished harder."

LinearB, meanwhile, provides the strongest dataset at 8.1M PRs and shows
that the *human-judgment gate* inside the pipeline is precisely where AI
volume piles up. Both findings can be true at once: **the automated
pipeline holds; the human gate embedded in it doesn't scale.** That is a
more defensible thesis than "CI/CD is obsolete," and it is the thesis
this document adopts.

The source incentives are also worth naming. A large share of the louder
"coding agents will break
your CI/CD" content traces to a single vendor,
Signadot, selling the ephemeral-environment fix through editorial placed
across multiple outlets
([example](https://dev.to/signadot/why-coding-agents-will-break-your-cicd-pipeline-and-how-to-fix-it-1gbh)).
The problem framing has independent support; the panic level doesn't.

What *is* genuinely new on the pipeline side is its cost model. CI compute
becomes a metered cost of agent operation. GitHub Agent HQ bills Actions
minutes atop Copilot seats
([github.blog](https://github.blog/news-insights/company-news/welcome-home-agents/)),
while Cloudflare's AI review costs $1.19 per review *run* × ~131k
runs/month ≈ $156k/month — ~$3.25 per MR at ~2.7 review passes each.
These costs scale with PR volume, not headcount
([blog.cloudflare.com](https://blog.cloudflare.com/ai-code-review/)).

Provenance also proves less than the pipeline once implied. In the Aug
2026 keyv npm attack, malware shipped with *valid* npm provenance
attestations — Sigstore/OIDC-based and produced by the legitimate GitHub
Actions workflow — while payloads hid in `.claude/` and `.vscode/` config
files that scanners never read. Attestation answers "which pipeline built this,"
never "should this
  change exist."
([Snyk](https://snyk.io/blog/inside-keyv-npm-compromise-preinstall-malware-trusted-provenance-ide-hooks/),
[TechTimes](https://www.techtimes.com/articles/323089/20260805/keyv-npm-supply-chain-attack-hides-malware-ai-agent-files-scanners-never-read.htm))

Dagger argues the conservative response well: keep the pipeline
deterministic and let the agent *repair* it, posting fixes as PR
suggestions that pass through the same developer review as any other
change.
([dagger.io](https://dagger.io/blog/automate-your-ci-fixes-self-healing-pipelines-with-ai-agents/),
vendor)

The EU AI Act is mostly a null result here. AI-generated code usually does
not trigger high-risk obligations, and marking AI-generated code is under
discussion rather than required
([Article 50 overview](https://artificialintelligenceact.eu/transparency-rules-article-50/),
[Kirkland & Ellis analysis](https://www.kirkland.com/publications/kirkland-alert/2026/02/illuminating-ai-the-eus-first-draft-code-of-practice-on-transparency-for-ai)).
It is a watch item, not a driver.

The resulting position is narrower than either celebration or panic:
keep deterministic CI/CD, harden it against automated producers, and stop
assuming that a universal human gate can absorb unlimited change. The
evidence base tells us how confidently we can make each part of that case.

## 5. What the evidence actually supports

The evidence is less contradictory than it first appears. Most of the
disagreement sits on a methodological fault line: **studies measuring
individual task completion find gains; studies measuring system-level
delivery and code health find flat-to-negative results.** Once we separate
those levels of analysis, almost every apparent contradiction dissolves.

**Well-supported (multiple independent sources, different methods):**
1. **Individual task throughput rises ~20–26%.** Three combined field
   experiments at Microsoft, Accenture, and a Fortune 100 firm covered
   4,867 devs and found +26% tasks completed (SE ~10pp — wide CI),
   peer-reviewed in
   *Management Science*
   ([INFORMS](https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00535));
   a Google internal RCT found ~21% faster (p=.086, not significant — the
   widely circulated version omits that;
   [arXiv](https://arxiv.org/pdf/2410.12944)).
2. **Gains collapse with complexity and maturity.** Stanford (~100k
   devs; slides only, not yet peer-reviewed) reports +30–40% for
   greenfield/simple work, falling to 0–10% and becoming negative after
   rework for complex brownfield work — plausibly the modal bucket for
   production work (this doc's inference).
3. **Delivery stability degrades.** This is the most robust system-level
   finding. DORA 2024 found −7.2% stability per 25% AI adoption. That
   finding persisted through DORA 2025's throughput reversal and is
   corroborated by
   [Faros telemetry](https://www.faros.ai/research/ai-acceleration-whiplash)
   (22k devs: incidents +58%, bugs/dev +54%, PRs merged with no review
   +31%, deployment frequency −11.7% — vendor, within-org before/after)
   and [Uplevel](https://uplevelteam.com/blog/ai-for-developer-productivity)
   (+41% bug rate, no throughput gain — vendor, observational).
4. **Self-reported speedup is contradicted in sign by three independent
   datasets.** METR reported felt +20% and measured −19%, then later
   self-downgraded to
   "very weak evidence"; Stanford's self-assessment barely correlates
   with measured productivity, r=0.17, developers misjudging by ~30
   percentile points, slides only; and the NAV IT longitudinal
   replication (perceived gains, no objective change — via
   [ITPro](https://www.itpro.com/software/development/github-says-copilot-improves-code-quality-but-are-ai-coding-tools-actually-producing-results-for-developers)).
   None is individually strong, but no dataset shows self-report
   tracking measured outcomes. Discount *any* "developers report saving
   N hours" finding accordingly, including DX's 3.6 hrs/week
   ([DX](https://getdx.com/blog/ai-assisted-engineering-q4-impact-report-2025/)).
5. **Maintainability erodes on the longest baseline.** GitClear §3 is
   directionally consistent with Faros churn data despite both being
   vendor telemetry.

The METR study deserves a closer, honest reading because it supplies the
most-cited number in the debate. In July 2025, 16 experienced OSS devs
completed 246 tasks on their own mature repos. They were 19% *slower* with
AI while estimating that they were +20% faster.

In Feb 2026, however, METR reported that its follow-up design had broken
down. Developers unwilling to work without AI opted out, 30–50% of
developers said they withheld some tasks, and some ran concurrent agents,
making wall-clock time meaningless. Point estimates flipped positive for
returning participants, and METR called its own data "only very weak evidence."
Citing the 19% in 2026 without this update is misleading; so
is citing the walkback as proof of speedup.
([original](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/),
[update](https://metr.org/blog/2026-02-24-uplift-update/))

**Genuinely contested — don't build on these:**
- Delivery-level throughput direction (DORA 2024 no / 2025 yes / Faros:
  task throughput up but deploy frequency down).
- Whether juniors or seniors benefit more (the Management Science
  experiments: juniors; the
  [*Science* 30M-commit study](https://www.science.org/doi/10.1126/science.adz9311):
  seniors exclusively).
- Whether trust is rising (DORA: distrust 39%→30%) or falling
  ([Stack Overflow](https://survey.stackoverflow.co/2025/ai): trust
  40%→29%) — different populations, not reconcilable.
- Whether engineering maturity protects quality (DORA yes;
  [Faros](https://www.faros.ai/research/ai-acceleration-whiplash):
  "maturity is not a shield").

Some numbers in wide circulation could not be traced to a primary source
and should not be used: "AI PRs contain 1.7x more issues"; "32% faster
merge / 28% fewer defects with AI review"; "2.74x more vulnerabilities
than human code"; the inflated Uber figures (Fortune's sober version:
Uber exhausted its 2026 AI budget in four months and its COO says the
value link "is not there yet" —
[fortune.com](https://fortune.com/2026/05/26/uber-coo-ai-spending-tokens-claude-code/));
Beck's "24→9 months onboarding" number. Separately — **traceable but
unusable as measurement**: Pichai's ">25% of new code" (Alphabet Q3 2024
earnings call, later "well over 30%") and Nadella's "20–30%" (LlamaCon,
Apr 2025) are self-reported figures with undefined denominators — use
the [*Science* study's](https://www.science.org/doi/10.1126/science.adz9311)
~29% of Python functions or
[DX's](https://getdx.com/blog/ai-assisted-engineering-q4-impact-report-2025/)
22% of merged code instead. Also: **no credible independent measurement
of agentic (vs autocomplete) adoption exists** — any specific percentage
is a laundered vendor estimate.

The vendor-incentive map explains part of the remaining disagreement:
who profits from which finding? Tool vendors such as GitHub — whose famous
[55%-faster study](https://github.blog/news-insights/research/research-quantifying-github-copilots-impact-on-developer-productivity-and-happiness/)
was a greenfield HTTP-server task and is never citable as a general
figure — and Google measure task speed and find gains. Analytics vendors
(GitClear, Faros, LinearB, Uplevel, Veracode, Apiiro) measure system
health and find degradation, each selling the finding that makes its
product necessary.

The independent middle — METR, *Science*, and the
[Auckland longitudinal study](https://arxiv.org/abs/2605.23135) — finds
real individual gains, real system costs, and a well-replicated
perception gap. The Management Science experiments sit between camps —
peer-reviewed, but partly authored by Microsoft about Microsoft's tool,
and measuring task count rather than value.

The evidence therefore supports a qualified one-sentence conclusion: AI
increases the rate of code production while degrading system stability
and maintainability, with benefits inversely proportional to codebase
complexity and maturity — and developers' own perception of speedup
repeatedly contradicted in sign. The lifecycle we propose next must
capture the individual gains without pretending those system costs away.

## 6. Toward an AI-native SDLC (v0)

The evidence does not justify abandoning lifecycle discipline. It points
toward redesigning that discipline around verification capacity, durable
intent, and empirical learning. Several emerging practices already supply
the pieces, although none yet proves the whole model.

### What's emerging in the wild

**Spec-driven development** moves the programming surface closer to
intent. [GitHub Spec Kit](https://github.com/github/spec-kit) uses a
constitution→specify→plan→tasks→implement pipeline;
[Amazon Kiro](https://kiro.dev/blog/introducing-kiro/) combines
requirements.md/design.md/tasks.md with event-fired agent hooks; and
[Tessl](https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry/)
treats the spec as source and code as a build output.

Birgitta Böckeler's comparison supplies the honest assessment. Kiro and
Spec Kit are "spec-first only, not spec-anchored over time" (her phrasing):
despite "living
artifact" marketing, their specs are discarded or
branch-scoped after implementation. Only Tessl pursues durability, and it
inherits Model-Driven Development's known failure modes.

The one empirical head-to-head, from Scott Logic, is a sharper warning.
Spec Kit produced 2,500+ lines of markdown and required 3.5 hours of
review for work that plain iterative prompting completed ~10x faster,
with no observed bug reduction. The author asks whether this is "a return to waterfall,"
in markdown (n=1, weight accordingly).
([Böckeler](https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html),
[Scott Logic](https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html))

The test for any SDD claim is therefore: *what happens to the spec after
merge?* Yuval Yeret's defense is still worth keeping: "the spec is
becoming a higher-level programming language... That is not abandoning
agility. That is what agility looks like when the programming surface
moves up a layer."
([yuvalyeret.com](https://yuvalyeret.com/blog/is-spec-driven-development-a-step-forward-or-back-for-product-development/))

**Harness engineering** offers a more durable frame, and it is the one
this repo already practices. Böckeler's structure is Agent = Model +
Harness. The controls split into **guides** — feedforward context files,
constitutions, and steering rules — and **sensors** — feedback from tests,
linters, and review agents. Each can be **computational**, meaning
deterministic and fast, or **inferential**, meaning semantic and
LLM-based.

The model exposes two failure modes. Feedback-only harnesses repeat
mistakes; feed-forward-only harnesses encode rules but never learn whether
they worked. This doc's inference is that teams typically over-weight
guides relative to sensors. A better balance distributes cheap checks
pre-commit and expensive sensors post-integration, monitors drift
*continuously outside* the change lifecycle, and uses steering loops in
which humans improve the harness whenever agents repeat a failure. "A good
harness should not necessarily aim to fully eliminate human input, but
to direct it to where our input is most important."
([martinfowler.com](https://martinfowler.com/articles/harness-engineering.html))

Mitchell Hashimoto gives the empirical version: "each line in that file is based
on a bad agent behavior" — the harness grows from observed failures rather
than being designed upfront. He also finds that "if you give an agent a way to verify its work,
it more often than not fixes its own mistakes and prevents regressions."
([mitchellh.com](https://mitchellh.com/writing/my-ai-adoption-journey))

**Policy-as-file is becoming policy-as-execution.** Four independent
groups converged on the same shape. [Kiro's](https://kiro.dev/blog/introducing-kiro/)
repo-level hooks are inherited on checkout. GitHub Next's `gh aw`
compiles markdown intent into Actions YAML
([Continuous AI](https://githubnext.com/projects/continuous-ai/),
[gh-aw repo](https://github.com/githubnext/gh-aw)). AWS AI-DLC ships its
methodology *as agent steering rules*
([awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows)).
Cognition uses playbooks with explicit postconditions and forbidden actions
(659 Devin PRs merged in one week,
[cognition.com](https://cognition.com/blog/how-cognition-uses-devin-to-build-devin)).
Cross-vendor standards also solidified quickly: AGENTS.md was donated to the
[Linux Foundation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)
in Dec 2025, while Anthropic's SKILL.md spec was
[adopted by ~32 tools](https://www.unite.ai/anthropic-opens-agent-skills-standard-continuing-its-pattern-of-building-industry-infrastructure/)
within months.

The evidence puts an honest brake on all of this. Anthropic's 2026
Agentic Coding Trends report — seen only via
[secondary coverage](https://pathmode.io/blog/orchestration-era-needs-intent);
primary not yet verified — reports developers use AI in ~60% of their
work but can *fully delegate* only 0–20% of tasks; DORA 2025 measures
delivery throughput gains of only ~2–18%
([dora.dev](https://dora.dev/dora-report-2025/)).
The orchestration story is therefore running well ahead of the delegation
evidence. Our model should be read as a direction of travel, not a
claim that the destination has already been validated.

### v0 model: verification-centric lifecycle

The traditional pipeline is a **writing pipeline with checking bolted
on**. The AI-native alternative is a **verification pipeline with writing
as a cheap input**. Its phases are not time-boxes; they are *gates through
which a change flows continuously*:

1. **Intent** (human, durable). Problem statement, constraints,
   non-goals, acceptance criteria. The highest-leverage human artifact —
   but keep it lightweight; the Scott Logic result warns against ceremony
   for its own sake. Lives in the repo, versioned, agent-readable.
2. **Harness** (human-curated, grown empirically). Policy files, skills,
   steering rules, forbidden actions — every line traceable to an
   observed failure. This *is* the team process now; new agents and new
   humans onboard from the same files.
3. **Generation** (agent, cheap, parallel, disposable). Multiple
   candidates are fine; code is no longer precious. Sandboxed by default
   — assume the generator can be prompt-injected.
4. **Mechanical verification** (computational sensors, deterministic).
   Tests (mutation-scored, not coverage-scored), types, lint, secret
   scan, SAST, property-based invariants, frozen fixtures as ground
   truth. Red is a stop sign. This layer scales with compute, so pour the
   growth here.
5. **Semantic verification** (inferential sensors). AI review tiered by
   risk: comment-only → suggest-and-approve → auto-merge for low-risk
   globs; adversarial/multi-agent review for critical paths; a
   calibrated judge — "a broken judge is worse than no judge, because you
   trust it"
   ([Pragmatic Engineer on evals](https://newsletter.pragmaticengineer.com/p/evals)).
6. **Human judgment** (the scarce resource, spent deliberately). Humans
   review *findings and intent-conformance*, not raw diffs (Finster).
   Human attention goes to: architecture coherence, security-sensitive
   paths, the spec being right, and steering-loop improvements to layer
   2. Beck's tripwires name what to watch for: loops, unrequested
   functionality, cheating.
7. **Progressive release** (runtime verification). Flags, canaries,
   automated rollback — acknowledging pre-merge gates can't catch
   everything at volume. (Evidence gap flagged in §3: this layer's
   sufficiency is asserted, not measured.)
8. **Continuous stewardship** (background agents + drift sensors).
   Scheduled maintenance agents, drift monitoring outside the change
   lifecycle, comprehension debt paid down deliberately — Ronacher's
   tower problem doesn't announce itself, so something must go looking.

This model *keeps* trunk-based flow, small batches, fast deterministic
feedback, and red-is-a-stop-sign from traditional CI/CD. It *demotes*
human review as the default universal gate, coverage as a quality signal,
and estimation as a planning input. It *adds* the harness as a first-class
artifact, verification economics through per-review cost budgets, agent
sandboxing, provenance labeling, and comprehension as a maintained asset.

That abstract model becomes more useful when applied to shipshape's
existing choices.

### Testing shipshape's own stance

Applied to shipshape, the model mostly strengthens existing policy
rather than overturning it. The keepers are the practices that turn
observed failures into durable, deterministic controls; the gaps are on
the sensor side of the harness.

- **"Automation proposes, CI checks, a human merges"** — keeper for now,
  with a horizon. It's exactly the LinearB failure mode (human gate
  queues under volume) — but shipshape targets small teams and
  non-engineers, where Tornhill's attention limit binds long before
  merge-queue math does. The v0 evolution isn't removing the human; it's
  Finster's move: present the human with verified findings and an
  intent-conformance summary rather than a raw diff. A tiered-authority
  future (auto-merge for docs/deps behind green gates) is plausible ADR
  material, not policy yet.
- **Frozen fixtures as ground truth** — keeper, and quietly ahead of the
  curve. "Never regenerate to make a regression pass" is precisely the
  anti-reward-hacking control the harness-engineering literature calls a
  computational sensor with teeth (Beck's "cheating" tripwire,
  operationalized).
- **Red CI is a stop sign** — keeper; DORA 2025 says this discipline is
  what determines whether AI amplifies you upward or downward.
- **Every bug leaves a dated regression test** — keeper; it's a steering
  loop in miniature (observed failure → permanent sensor).
- **Security guardrails on by default, disabling requires hearing the
  consequence** — keeper; the Veracode/slopsquatting base rates say the
  default-on posture is the correct prior for agent-generated code.
- **Model-neutral harness doc mirrored by thin adapters** (ADR 0004) —
  keeper; this is the AGENTS.md/SKILL.md convergence arriving
  independently.
- **Gap worth an eventual ADR:** shipshape's kit has no *sensor* for test
  quality (mutation score), and no scheduled drift/health monitoring
  beyond the weekly CodeQL scan its templates ship — doctor, the kit's
  drift sensor, runs on invocation only. Both sit in the sensor half of
  Böckeler's 2x2, the side her feed-forward-only failure mode warns
  about.

This leaves the project with a direction but not a finished doctrine. The
remaining uncertainties are specific enough to investigate rather than
paper over.

## 7. Open questions / next digs

The next round of research should focus on the claims that would most
change shipshape's design or the proposed lifecycle. These are open
questions, not conclusions waiting to be confirmed:

1. **Mutation testing in practice** — is there a stdlib-only-compatible
   way for shipshape to score test quality, or at least detect
   assertion-free tests? (mutmut/cosmic-ray survey; cost at CI scale.)
2. **Tiered review authority** — design what auto-merge-behind-green-gates
   would need (path globs, risk classes, break-glass audit) before
   deciding whether to ever propose it.
   [Cloudflare's](https://blog.cloudflare.com/ai-code-review/) 0.6%
   break-glass rate is the benchmark.
3. **The deployment evidence gap** — track for controlled data on
   change-failure rate under high change volume with flags/rollback as
   primary safety net. Currently vendor assertion only.
4. **Fetch primaries** still outstanding: The New Stack's skeptical
   ["AI hasn't shifted the bottleneck"](https://thenewstack.io/ai-code-bottleneck-myth/)
   piece; the FSE '26
   ["Fast and Spurious"](https://arxiv.org/pdf/2510.24265) quantitative
   tables; the Anthropic 2026 Agentic Coding Trends report behind the
   delegation-gap figure. (Sonar's primary was located and is now cited
   in §4.)
5. **Comprehension debt metrics** — can Ronacher's tower problem be
   measured? (Candidate proxies: bus factor tooling, knowledge-map drift,
   time-to-explain in incident reviews.)
6. **DORA 2026** — not yet published as of Aug 2026; revisit when it
   lands, especially whether the stability penalty finally closes.
7. **Where does shipshape sit** on the guides/sensors balance? Audit the
   kit's templates against Böckeler's 2x2 and consider whether v0.3
   should ship any inferential sensor at all.

---

*Document maintained as ongoing research. Supersede conclusions by
editing with dated notes; if any conclusion hardens into a decision,
record it as an ADR and link back here.*
