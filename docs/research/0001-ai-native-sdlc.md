# Challenging the traditional SDLC: does it survive AI-native development?

- Status: Living research document (v1, 2026-08-10)
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
quality gate, CI/CD as the delivery backbone — was engineered around one
economic fact: **human coding time is scarce and expensive**. Every
ceremony is a scheduling algorithm for scarce human attention; every gate
assumes the thing being checked was produced slowly enough to check.

The shift is not "AI writes code now." It is that **the marginal cost of
producing code is collapsing toward zero while the cost of verifying,
understanding, and trusting code is rising**. Pedro Tavares' June 2025
essay is the canonical statement: "The marginal cost of adding new
software is approaching zero, especially with LLMs. But what is the price
of understanding, testing, and trusting that code? Higher than ever."
([ordep.dev](https://ordep.dev/posts/writing-code-was-never-the-bottleneck))
Robert Laszczak's 2026 restatement sharpens the asymmetry: "The biggest
bottleneck of implementation quietly shifted from producing code to
reading code" — writing accelerated, review didn't.
([threedots.tech](https://threedots.tech/post/understanding-code-is-bottleneck/))

Two structural consequences follow, and most of this document is working
out their implications:

1. **Every SDLC stage that meters human writing effort is optimizing a
   solved problem.** Estimation, sprint capacity, story points, velocity —
   all denominated in human coding hours.
2. **Every stage that meters human comprehension is now the constraint.**
   Review, testing strategy, architecture coherence, incident response,
   onboarding.

Sonya Siderova's framing is the honest one-liner: Agile isn't dead, it's
optimizing a constraint that moved — from the mechanics of human
collaboration to decision-making and validation.
([InfoQ, Feb 2026](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate))

## 2. Steelman: what traditional SDLC was actually for

Before tearing anything down, name what each piece bought us. Most
critiques fail because they treat ceremonies as pure waste rather than as
solutions to real problems that may still exist.

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
canon, and any "Agile is dead" claim has to answer them:

- **Kent Beck** (XP, TDD, Manifesto signatory) frames his own practice as
  "augmented coding": "The value system in augmented coding is similar to
  hand coding — tidy code that works. It's just that I don't type much of
  that code." His change is *where* judgment goes: "I make more
  consequential programming decisions per hour, fewer boring vanilla
  decisions."
  ([newsletter.kentbeck.com](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes))
- **Martin Fowler & Unmesh Joshi** make the deepest objection to
  generate-then-review: stable abstractions are *discovered through the
  act of coding*, not specified upfront — "Reviewing LLM-generated code
  is rarely enough — you miss the deep thinking that happens when you are
  coding yourself."
  ([martinfowler.com](https://martinfowler.com/articles/convo-llm-abstractions.html))

The counterposition (Steve Jones, Capgemini: "Agentic SDLCs are too fast
for Agile" — apps built in hours make two-week sprints the wrong unit;
the Manifesto's deprioritization of documentation *inverts* because agents
need written intent) is real but contested: Forrester 2025 found 95% of
professionals affirming Agile's continued relevance.
([InfoQ debate](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate))

**Working position:** the *values* (feedback, small steps, working
software, adaptation) survive; the *ceremonies* were implementations tuned
to a constraint that moved. Critique implementations, not values.

## 3. Pressure points, phase by phase

### Requirements & planning
- **Holds:** intent capture matters more than ever — an agent will happily
  build the wrong thing fast. AWS guidance replaces "sprint planning" with
  "intent design": constrain the executor's state space, don't script its
  path ([via InfoQ](https://www.infoq.com/news/2026/02/ai-agile-manifesto-debate)).
- **Breaks:** estimation. Story points encode human effort, fatigue, and
  uncertainty. Simon Willison: for agent-native tasks, lengthy estimation
  becomes pointless — the question shifts from "how do we justify
  development time?" to "which problems are worth solving?"
  ([simonw.substack.com](https://simonw.substack.com/p/agentic-engineering-patterns))
- **Inverts:** Casey West's verification→validation shift: checking
  conformance-to-spec is what agents now do well; the expensive human
  residue is judging whether the spec was *right*.

### Implementation
- The phase that shrank. Evidence summary in §5: individual task
  completion rises ~20–26% in the credible RCTs, but gains collapse with
  codebase complexity/maturity — approaching zero for high-complexity
  brownfield work, which is most production engineering (Stanford,
  ~100k developers, [slides](https://aiconference.com/wp-content/uploads/2025/09/Yegor-Denisov-Blanch-Will-AI-Replace-Software-Engineers_-.pptx.pdf)).
- The craft moved into **harness engineering** (§6): the durable artifact
  is the environment that makes agents reliable, not the individual diff.

### Code review — the gate under the most strain
- **The sampling-rate argument** (Bryan Finster, Minimum CD author, ex-
  Walmart CD lead): human reviewers catch defects effectively up to ~400
  LOC and degrade sharply beyond; one AI feature blows past that in a
  shot. "Adding more human reviewers to a blocking queue does not fix
  this... automate feedback so the sampling rate matches the production
  rate." Humans should review agent *findings*, not raw diffs.
  ([bryanfinster.substack.com](https://bryanfinster.substack.com/p/ai-broke-your-code-review-heres-how))
- **The data agrees the queue is where it breaks.** LinearB (8.1M PRs,
  4,800 orgs): AI-assisted PRs wait 2.5–5.3x longer for reviewer pickup,
  are ~2.6x larger at p75, and merge at ~33% vs ~84% for human-authored.
  Once review *starts*, AI code is reviewed faster — the delay is
  queueing, not reading; LinearB reads the fast reviews as superficial
  validation. Seniors spend 38 min and accept 23.7%; juniors spend 15 min
  and accept 31.9% — scrutiny and acceptance move opposite.
  ([linearb.io](https://linearb.io/blog/8-million-prs-engineering-productivity), vendor telemetry)
- **Rubber-stamping is a documented belief, and polish disarms
  reviewers.** CMU qualitative study of ~3,100 practitioner opinions
  documents superficial approval under volume, comprehension difficulty
  undermining feedback, and review itself becoming the bottleneck
  ([arXiv 2607.07980](https://arxiv.org/pdf/2607.07980) — evidence about
  the discourse, not measured defect rates).
- **The deepest cut — comprehension was a byproduct of friction.** Armin
  Ronacher (Flask creator, agentic-coding *adopter*): modifying someone's
  code used to force reading, questions, negotiation — that "waste" was
  the knowledge-transfer mechanism. "Agents remove much of that friction...
  The tower does not fall, and so we do not notice what was lost."
  ([lucumr.pocoo.org](https://lucumr.pocoo.org/2026/7/13/the-tower-keeps-rising/))
- **The OSS natural experiment** — review capacity that can't be bought:
  curl killed its bug bounty Feb 2026 after AI-assisted reports hit ~20%
  of volume while genuine-vuln rates fell below 5% (Stenberg: "AI slop is
  DDoSing open source") — then returned to HackerOne in March, so it's
  not a clean death. Jazzband (84 projects, >150M downloads/month) shut
  down; Ghostty, tldraw, Ladybird, openai/codex restricted external PRs.
  ([RedMonk](https://redmonk.com/kholterhoff/2026/02/03/ai-slopageddon-and-the-oss-maintainers/),
  [Jazzband](https://jazzband.co/news/2026/03/14/sunsetting-jazzband))
  Each case has confounds; the pattern is real.

### Testing
- **Coverage became an actively misleading signal.** AI-generated suites
  hit high line coverage while killing few mutants — "perpetually green"
  tests. Mutation testing is being revived as the meta-gate on test
  quality; property-based testing asserts invariants instead of examples.
  ([Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/mutation-testing))
- **AI error patterns differ from human ones.** Human-shaped tests catch
  typos and off-by-ones; AI code fails differently: Apiiro reports
  trivial syntax errors *down* while privilege-escalation paths and
  architectural design flaws are *up* — errors moved from shallow to deep
  ([The Register coverage](https://www.theregister.com/2025/09/05/ai_code_assistants_security_problems/);
  disputed by Contrast Security's CTO, and findings ≠ exploitable vulns).
- Security base rates: Veracode (100+ LLMs, 80 tasks): 45% of generations
  introduce OWASP Top 10 vulns, Java worst at 72%; **model scale doesn't
  fix it** — 20B to 400B params cluster at the same ~55% pass rate
  ([veracode.com](https://www.veracode.com/blog/spring-2026-genai-code-security/),
  adversarial benchmark, not observed production code — observational
  GitHub analysis finds ~12% of AI-attributed files with identifiable
  CWEs, [arXiv 2510.26103](https://arxiv.org/abs/2510.26103)).
- Genuinely new attack surface: package hallucination / slopsquatting —
  19.7% of suggested packages didn't exist across 16 LLMs (2025), 43% of
  hallucinated names repeat consistently (pre-registerable by attackers);
  frontier models improved to ~5–6% by early 2026.
  ([socket.dev](https://socket.dev/blog/slopsquatting-how-ai-hallucinations-are-fueling-a-new-class-of-supply-chain-attacks))

### Release & operations
- Progressive delivery (flags, canaries, automated rollback) is promoted
  from nice-to-have toward primary safety net as change volume grows —
  but note honestly: "flags + rollback replace pre-merge review" is
  asserted by flag vendors and **measured by nobody**. No controlled data
  exists on change-failure rate at 10x change volume.
- Maintenance is where the quiet damage shows: GitClear (623M changes,
  2023–2026): refactoring 21% of changed lines (2022) → 3.8% (2026);
  cross-file reuse −35%; legacy maintenance −74%; duplication +81%;
  developers now ~5x likelier to copy/paste than refactor.
  ([gitclear.com](https://www.gitclear.com/the_ai_code_quality_maintainability_gap),
  vendor telemetry, correlational, but the longest baseline anyone has)

### People & skills (cross-cutting)
- Skill formation: RCT (n=52) found AI-assisted learners scored 17% lower
  on comprehension with debugging hit hardest — and no task speedup, so
  the skill cost bought nothing ([arXiv 2601.20245](https://arxiv.org/html/2601.20245v1);
  one-hour study of a months-scale phenomenon; sometimes miscited as an
  Anthropic study — it isn't).
- Microsoft/CMU (CHI 2025, n=319): higher confidence in AI → less
  critical evaluation; those least able to catch errors trusted most
  ([microsoft.com](https://www.microsoft.com/en-us/research/publication/the-impact-of-generative-ai-on-critical-thinking-self-reported-reductions-in-cognitive-effort-and-confidence-effects-from-a-survey-of-knowledge-workers/), self-reported).
- Juniors: Stanford HAI reports employment for developers 22–25 down ~20%
  since late 2022 while older cohorts grew — confounded by the tech
  correction; causality not established. Yegge's "juniors win" thesis
  ([Sourcegraph](https://sourcegraph.com/blog/revenge-of-the-junior-developer))
  directly contradicts the employment data; unresolved.
- Attention doesn't parallelize: Adam Tornhill — "agentic coding is
  mentally expensive"; decision density exhausts developers in hours,
  against the fleet-management vision
  ([Fowler fragments](https://martinfowler.com/fragments/2026-05-27.html)).
  Matches DORA 2025's cognitive-load telemetry: +67% PR contexts/day,
  +13.8% work restarts, 26% more tasks idle 7+ days.

## 4. Is traditional CI/CD still valid?

Decompose CI/CD into its founding assumptions (Fowler's *Continuous
Integration*, Humble & Farley's *Continuous Delivery*) and check each.

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
| Author understands the change | **Broken** | Werner Vogels' "verification debt"; Sonar survey: 96% don't fully trust AI code, only 48% verify before committing (secondhand, fetch primary before leaning on it) |
| Reviewer comprehension is cheap | **Broken** | LinearB queueing data, Finster's sampling-rate argument (§3) |
| Humans are the error source automation protects against | **Inverted** | CI must now be hardened *against the automation*: microVM sandboxing (Firecracker/Kata), default-deny egress, K8s Agent Sandbox SIG — "assume agent-written code will eventually do something it shouldn't" ([agent-sandbox.sigs.k8s.io](https://agent-sandbox.sigs.k8s.io/)) |

**The key tension in the evidence — hold both:**
- **DORA 2025** (strongest source, ~5,000 respondents): AI amplifies
  what's already there. CI/CD discipline became *more* decisive, not
  less. The instability finding isn't "CI is obsolete"; it's "teams with
  weak CI get punished harder."
- **LinearB** (strongest dataset, 8.1M PRs): the *human-judgment gate*
  inside the pipeline is precisely where AI volume piles up.

Both are true simultaneously: **the automated pipeline holds; the human
gate embedded in it doesn't scale.** That is a far more defensible thesis
than "CI/CD is obsolete," and it's the thesis this document adopts.

Also worth naming: a large share of the louder "coding agents will break
your CI/CD" content traces to a single vendor (Signadot) selling the
ephemeral-environment fix, placed as editorial across multiple outlets.
The problem framing has independent support; the panic level doesn't.

**What's genuinely new on the pipeline side:**
- CI compute becomes a metered cost of agent operation (GitHub Agent HQ
  bills Actions minutes atop Copilot seats; Cloudflare's AI review costs
  $1.19/review × 48k MRs/month ≈ $57k/month — costs scale with PR volume,
  not headcount).
- Provenance ≠ intent: the Aug 2026 keyv npm attack shipped malware with
  *valid* SLSA/OIDC attestations, hidden in AI agent config files
  scanners never read. Attestation answers "which pipeline built this,"
  never "should this change exist."
  ([techtimes](https://www.techtimes.com/articles/323089/20260805/keyv-npm-supply-chain-attack-hides-malware-ai-agent-files-scanners-never-read.htm))
- The conservative position, well argued by Dagger: the pipeline stays
  fixed, deterministic, and fast; the agent *writes and repairs* the
  pipeline, submitting fixes through the same review lane as any change.
  ([dagger.io](https://dagger.io/deep-dives/agentic-ci/), vendor)
- EU AI Act: mostly a null result — AI-generated code usually does not
  trigger high-risk obligations; marking of AI-generated code is under
  discussion, not required. Watch item, not driver.

## 5. What the evidence actually supports

The literature looks contradictory until you see the methodological fault
line: **studies measuring individual task completion find gains; studies
measuring system-level delivery and code health find flat-to-negative
results.** Almost every apparent contradiction dissolves there.

**Well-supported (multiple independent sources, different methods):**
1. **Individual task throughput rises ~20–26%** — Microsoft/Accenture RCT,
   4,867 devs, +26% tasks completed, peer-reviewed in *Management Science*
   ([INFORMS](https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00535));
   Google internal RCT ~21% faster (p=.086, not significant — the widely
   circulated version omits that).
2. **Gains collapse with complexity and maturity** — Stanford (~100k
   devs): +30–40% greenfield/simple → 0–10% (negative after rework) for
   complex brownfield. Most production work is the latter bucket.
3. **Delivery stability degrades** — the most robust system-level finding.
   DORA 2024 (−7.2% stability per 25% AI adoption), persisted through
   DORA 2025's throughput reversal, corroborated by Faros telemetry
   (22k devs: incidents +58%, bugs/dev +54%, PRs merged with no review
   +31%, deployment frequency −11.7% — vendor, within-org before/after)
   and Uplevel (+41% bug rate, no throughput gain — vendor, observational).
4. **Self-reported speedup is unreliable in sign, not just magnitude** —
   falsified three times independently: METR (felt +20%, measured −19%),
   Stanford (felt +20%, ~−20% after rework), NAV IT longitudinal
   (perceived gains, no objective change). Discount *any* "developers
   report saving N hours" finding accordingly, including DX's 3.6
   hrs/week.
5. **Maintainability erodes on the longest baseline** — GitClear §3;
   directionally consistent with Faros churn data despite both being
   vendor telemetry.

**The METR study deserves its own honest paragraph** because it's the
most-cited number in the debate. July 2025: 16 experienced OSS devs, 246
tasks on their own mature repos — 19% *slower* with AI while estimating
+20% faster. But in Feb 2026 METR reported its follow-up design broke
down (selection bias — devs unwilling to work without AI opted out;
30–50% self-selected tasks; some ran concurrent agents making wall-clock
meaningless), with point estimates flipping positive for returning
participants, and called its own data "only very weak evidence." Citing
the 19% in 2026 without this update is misleading; so is citing the
walkback as proof of speedup.
([original](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/),
[update](https://metr.org/blog/2026-02-24-uplift-update/))

**Genuinely contested — don't build on these:**
- Delivery-level throughput direction (DORA 2024 no / 2025 yes / Faros:
  task throughput up but deploy frequency down).
- Whether juniors or seniors benefit more (Microsoft RCT: juniors;
  *Science* 30M-commit study: seniors exclusively).
- Whether trust is rising (DORA: distrust 39%→30%) or falling (Stack
  Overflow: trust 40%→29%) — different populations, not reconcilable.
- Whether engineering maturity protects quality (DORA yes; Faros
  "maturity is not a shield").

**Numbers in wide circulation that could not be traced to a primary
source — do not use:** "AI PRs contain 1.7x more issues"; "32% faster
merge / 28% fewer defects with AI review"; "2.74x more vulnerabilities
than human code"; the inflated Uber figures (Fortune's sober version:
Uber exhausted its 2026 AI budget in four months and its COO says the
value link "is not there yet"); Beck's "24→9 months onboarding" number;
Google/Microsoft "~30% of our code is AI" earnings-call remarks (use the
*Science* study's ~29% of Python functions or DX's 22% of merged code
instead). Also: **no credible independent measurement of agentic (vs
autocomplete) adoption exists** — any specific percentage is a laundered
vendor estimate.

**Vendor-incentive map** (who profits from which finding): tool vendors
(GitHub, Google) measure task speed and find gains; analytics vendors
(GitClear, Faros, LinearB, Uplevel, Veracode, Apiiro) measure system
health and find degradation — each selling the finding that makes its
product necessary. The independent middle (METR, *Science*, Auckland
longitudinal, Microsoft/MIT RCT): real individual gains, real system
costs, and a well-replicated perception gap.

**One-sentence summary of the evidence:** AI increases the rate of code
production while degrading system stability and maintainability, with
benefits inversely proportional to codebase complexity and maturity — and
developers' own perception of speedup is demonstrably unreliable in sign.

## 6. Toward an AI-native SDLC (v0)

### What's emerging in the wild

**Spec-driven development** (GitHub Spec Kit's constitution→specify→plan→
tasks→implement pipeline; Amazon Kiro's requirements.md/design.md/tasks.md
with event-fired agent hooks; Tessl's spec-as-source where code is a build
output). The honest assessment comes from Birgitta Böckeler's comparison:
Kiro and Spec Kit are *spec-first, not spec-driven* — specs get discarded
or branch-scoped after implementation despite "living artifact" marketing;
only Tessl pursues durability, inheriting Model-Driven Development's known
failure modes. And the one empirical head-to-head (Scott Logic): Spec Kit
produced 2,500+ lines of markdown and 3.5 hours of review for work plain
iterative prompting did ~10x faster with no observed bug reduction —
"waterfall in markdown" (n=1, weight accordingly).
([Böckeler](https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html),
[Scott Logic](https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html))
The test to apply to any SDD claim: *what happens to the spec after
merge?* Yuval Yeret's defense is worth keeping though: "the spec is
becoming a higher-level programming language... This is not abandoning
agility. This is what agility looks like when the programming surface
moves up a layer."
([yuvalyeret.com](https://yuvalyeret.com/blog/is-spec-driven-development-a-step-forward-or-back-for-product-development/))

**Harness engineering** — the more durable frame, and the one this repo
already practices. Böckeler's structure: Agent = Model + Harness; controls
decompose into **guides** (feedforward — context files, constitutions,
steering rules) vs **sensors** (feedback — tests, linters, review agents),
each either **computational** (deterministic, fast) or **inferential**
(semantic, LLM-based). Key strategic claims: most teams over-invest in
guides and under-invest in sensors; distribute cheap checks pre-commit and
expensive sensors post-integration; monitor drift *continuously outside*
the change lifecycle; run steering loops where humans improve the harness
whenever agents repeat a failure. "A good harness should not aim to fully
eliminate human input, but to direct it to where our input is most
important." ([martinfowler.com](https://martinfowler.com/articles/harness-engineering.html))
Mitchell Hashimoto's empirical version: "each line in that file is based
on a bad agent behavior" — the harness is grown from observed failures,
not designed upfront; and "if you give an agent a way to verify its work,
it more often than not fixes its own mistakes."
([mitchellh.com](https://mitchellh.com/writing/my-ai-adoption-journey))

**Policy-as-file becoming policy-as-execution** — four independent groups
converged on the same shape: Kiro's repo-level hooks inherited on
checkout; GitHub Next's `gh aw` compiling markdown intent into Actions
YAML ([Continuous AI](https://githubnext.com/projects/continuous-ai/));
AWS AI-DLC shipping its methodology *as agent steering rules*
([awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows));
Cognition's playbooks with explicit postconditions and forbidden actions
(659 Devin PRs merged in one week,
[cognition.com](https://cognition.com/blog/how-cognition-uses-devin-to-build-devin)).
Cross-vendor standards solidified fast: AGENTS.md donated to the Linux
Foundation Dec 2025; Anthropic's SKILL.md spec adopted by ~32 tools
within months.

**The honest brake on all of it:** Anthropic's own research finds
developers use AI in ~60% of their work but can *fully delegate* only
0–20% of tasks; DORA measures delivery throughput gains of only ~2–18%.
The orchestration story is running well ahead of the delegation evidence.

### v0 model: verification-centric lifecycle

The traditional pipeline is a **writing pipeline with checking bolted
on**. The AI-native pipeline is a **verification pipeline with writing as
a cheap input**. Phases stop being time-boxes and become *gates a change
flows through continuously*:

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
   trust it."
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

What this *keeps* from traditional CI/CD: trunk-based flow, small batches,
fast deterministic feedback, red-is-a-stop-sign. What it *demotes*:
human review as the default universal gate, coverage as a quality signal,
estimation as a planning input. What it *adds*: harness as first-class
artifact, verification economics (per-review cost budgets), agent
sandboxing, provenance labeling, comprehension as a maintained asset.

### Testing shipshape's own stance

- **"Automation proposes, CI checks, a human merges"** — keeper for now,
  with a horizon. It's exactly the LinearB failure mode (human gate
  queues under volume) — but shipshape targets small teams and
  non-engineers, where Tornhill's attention limit binds long before
  merge-queue math does. The v0 evolution isn't removing the human, it's
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
  quality (mutation score) and no drift monitoring outside the change
  lifecycle (doctor runs on invocation, not on schedule). Both are the
  under-invested quadrants in Böckeler's 2x2.

## 7. Open questions / next digs

1. **Mutation testing in practice** — is there a stdlib-only-compatible
   way for shipshape to score test quality, or at least detect
   assertion-free tests? (mutmut/cosmic-ray survey; cost at CI scale.)
2. **Tiered review authority** — design what auto-merge-behind-green-gates
   would need (path globs, risk classes, break-glass audit) before
   deciding whether to ever propose it. Cloudflare's 0.6% break-glass
   rate is the benchmark.
3. **The deployment evidence gap** — track for controlled data on
   change-failure rate under high change volume with flags/rollback as
   primary safety net. Currently vendor assertion only.
4. **Fetch primaries** flagged secondhand: Sonar 2026 State of Code
   survey; The New Stack's skeptical "AI hasn't shifted the bottleneck"
   piece; the FSE '26 "Fast and Spurious" quantitative tables.
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
