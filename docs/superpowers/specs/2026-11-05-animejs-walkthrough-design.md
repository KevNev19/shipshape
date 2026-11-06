# Design: setup walkthrough and health-check reveals

Date: 2026-11-05
Status: Draft for review. No implementation until this file is accepted.

## Decision

Animate two existing parts of the marketing site, and nothing else:

1. The four-step setup course in `#how`.
2. The watch bill and the example doctor report in `#watch`.

The motion explains the order shipshape already prints. It does not add a step, a flag treatment, sound, or a new film.

## What is on the page today

The course is an ordered list, `ol.course`, with four waypoints. There is no fifth step on the page. The hero's short list uses the same four names and is not part of this work.

| Order | Heading | Body, as published |
| --- | --- | --- |
| 1 | Scan | It reads your project to learn its languages, how it installs packages and how its tests run. It only looks. |
| 2 | A few questions | Five at most, about outcomes: who works on it, how changes should land, how you check it works, what must never leak, and whether it's public. What the scan already knows is only confirmed. |
| 3 | Preview | Every file it will add, one line each, with what it's for. Files you already have are listed apart and left alone unless you say yes to that exact file. |
| 4 | Set up | It writes exactly what you saw and switches on the commit guard. A GitHub rule that protects main is added only if you say yes. |

The cartouche under the list stays still: "Course for `$shipshape-init`. Nothing changes before the preview."

The watch bill is the table captioned "Watch bill". Rows stay in this order:

| When | On watch |
| --- | --- |
| Every commit, on your computer | Secret guard |
| Pushes and pull requests to main | CI |
| Pushes and pull requests to main | Secret scan |
| Pushes, pull requests and weekly | CodeQL |
| Weekly | Dependabot |
| Every Wednesday | Health check |
| You push a version tag | Release |
| Once you say yes | Branch rule |

The health-check reveal is the figure labelled "Example `$shipshape-doctor` report", not the Commands card whose heading is "Health check". That card is out of scope. The report's lines stay in this order:

1. Security group label.
2. FAIL, secret guard installed.
3. FAIL, remote protection.
4. PASS, code scanning (CodeQL).
5. PASS, dependency watch (Dependabot).
6. Setup group label.
7. PASS, automated tests (CI).
8. PASS, managed files.
9. The "Next:" line.

Copy is not rewritten. Status words stay written out (FAIL, PASS). Failures still lead.

## Motion

Two independent timelines. Neither scrubs with scroll, loops, or plays again after it finishes.

**Course.** When at least 60% of `#how` is on screen, and motion is allowed, and the library has loaded: each `.waypoint` goes from opacity 0 and 8px down to opacity 1 and no offset. Duration 450ms. Start each one 180ms after the previous. The whole course finishes in 990ms. Order is 1, 2, 3, 4.

**Watch.** When at least 60% of the watch-bill table is on screen, under the same conditions: each `tbody tr` uses opacity and 8px translateY, duration 280ms, stagger 70ms. Eight rows, seven gaps: 770ms. When at least 60% of the doctor figure is on screen: the two group labels, the six status lines, and the Next line, nine targets, use duration 280ms and stagger 80ms. Eight gaps: 920ms.

Only `opacity` and `translateY`. No `translateX`, no scale that changes layout, no animating `height` or `display`.

## When it plays, and when it does not

Each timeline has its own "already played" flag, kept in memory for the page view.

- First time the target is 60% visible, and motion is allowed, and the library is ready: play once.
- Scrolling away does not rewind it and does not queue a second play.
- Scrolling back shows the finished state.
- There is no replay control. A full reload may play again.
- The hero list, the terminal, the commands grid, the flags, and the film are not targets.

**Library arrives late.** Content is visible while the file loads. If the target has already been 60% visible for 300ms before the module resolves, do not play. A hide-then-reveal of text the visitor is already reading is worse than no motion. If the module resolves before that 300ms, and the target is still at least 60% visible, play once.

**Reduced motion.** If `prefers-reduced-motion: reduce` matches, do not load the library and do not play. The printed page is the final state.

**Preference change.** Anime.js does not turn itself off for reduced motion. The site checks the query.

- Motion allowed, then reduced, while a timeline is running: stop it and leave every target fully visible, with no leftover inline opacity or transform. Do not send the timeline back to the hidden start. Mark it played.
- Reduced, then allowed, after that surface was already shown: do not play.
- Reduced, then allowed, before that surface has played, and it is at least 60% visible: load the module if it is not loaded, then play once.

The documented way to read the query is `createScope({ mediaQueries: { reduceMotion: '(prefers-reduced-motion)' } })`. The official example sets `duration` to 0 when it matches. This design does not use duration 0 as the whole policy, because a duration of 0 is not specified here as a substitute for "never hide the text". The matchMedia listener above is the requirement.

## No JavaScript, and a failed load

Default CSS shows every waypoint, row, and report line. The script may hide a target only in the same turn that it starts that target's timeline.

If the module import rejects, or `createTimeline` throws, remove any inline opacity or transform this script set, and do not try again. The page looks like the no-JavaScript page.

## Semantics and screen readers

Keep the ordered list, the table, and the report list. Do not set `aria-hidden` on them. Do not remove them with `display` or `visibility`. Do not add a live region that announces each step. Someone using a screen reader can read the course and the watch bill before, during, and after the motion. The animation is visual only.

The 8px offset is transform, so it does not move the focus order or the table layout.

## Library

Pin **animejs 4.5.0**, MIT. `package.json` in that version says `"license": "MIT"`. `LICENSE.md` in the tarball is the MIT license, copyright 2025 Julian Garnier. Source headers inside the same tarball say copyright 2026. Ship the tarball's `LICENSE.md` unchanged next to the file.

Self-host this file, and only this build:

| File | Bytes | gzip | sha256 |
| --- | --- | --- | --- |
| `dist/bundles/anime.esm.min.js` | 118678 | 40860 | `a19015a1a92d52025a2fb6703b6d67eadd1cc2aeaf880770e96e04cf6aa07be1` |
| `LICENSE.md` | 1075 | 643 | `3f3e835a9952cfc2a6ca836fb95b3257c981f24fa3ef51249055acb09931897b` |

Measured on 2026-11-05 from `npm pack animejs@4.5.0`. Registry integrity `sha512-NQimYX+lz8WaXonGS9zVVoviCIAjONeJayxacUditaivYLqyXgGjFKjuyl0aUUhFKm5MriX9ty1TGovNzoJQWA==`, shasum `d0f6f5141cff15629ae02ce3c379a0846784e4d1`. gzip is `gzip.compress` of those exact bytes with `mtime=0`.

Place them at:

- `site/assets/vendor/animejs/4.5.0/anime.esm.min.js`
- `site/assets/vendor/animejs/4.5.0/LICENSE.md`

A Node import of that ESM build exposes `createTimeline`, `createScope`, and `stagger` as named exports. The page imports those three from the self-hosted file. It does not import `onScroll`. Scroll-scrubbing would tie the course to scroll position; this design plays once instead.

The unminified closure of `timeline`, `animation`, `scope`, and `utils/stagger.js` is 33 files and 250462 bytes. That is larger than the one minified bundle, so the page uses the bundle. Those 33 files are the measured alternative, not a second copy to commit.

Do not take the library from a CDN at runtime. Do not add a bundler. The site stays static HTML and CSS.

The homepage's "24.50 KB" figure is their summary of the toolbox. It is not the size of the file above. Do not use it as a budget.

## Loading

Dynamic-import the module only when `#how` or the watch section is within 400px of the viewport, and only when reduced motion is off. A first view that never reaches those sections does not download it.

The Lighthouse budgets stay as they are: pessimistic aggregation, performance at least 0.90, accessibility at least 0.95, best practices at least 0.90, cumulative layout shift at most 0.10, first-load transfer at most 800 KiB. This work does not edit those numbers. The implementation pull request runs that check. If the module's parse time pushes a cold run under 0.90, the fix is to keep the import off the first screen, not to lower the floor.

## Tests

- A page test reads `ol.course` and asserts the four headings, in order: Scan, A few questions, Preview, Set up. It fails if a fifth waypoint appears.
- The same test reads the watch-bill body and asserts the eight "On watch" cells in the table order above.
- The same test reads the doctor example and asserts the six status lines in order, failures first.
- The script's source shows a reduced-motion match, a played-once guard per surface, and no `onScroll` import.
- The vendored file's sha256 matches the table above, and `LICENSE.md` is beside it.
- With motion allowed, a headless page that scrolls `#how` to 60% shows waypoint 1 before waypoint 4, and scrolling away and back does not run it again.
- With reduced motion set before load, no timeline runs and every waypoint is visible.
- With reduced motion turned on mid-timeline, targets end visible.
- With the module forced to fail, every waypoint, row, and report line is visible and has no inline opacity.
- Lighthouse on the implementation pull request still uses pessimistic aggregation and the existing floors.

## Out of scope

Flag hoist, SVG line drawing, the hero, the terminal conversation, the commands grid (including its "Health check" card), the film, audio, and any copy change.

## Approaches considered

Play-once timelines, chosen. Scroll-synced `onScroll({ sync: true })` was rejected because the course would scrub and reverse as the visitor moves. A CSS-only stagger was rejected because the approved direction is Anime.js, and the reduced-motion and failure rules are easier to keep in one script than in delayed transitions that hide content before JavaScript runs.
