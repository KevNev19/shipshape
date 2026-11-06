# Setup Walkthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Play the existing four-step setup course once, then reveal the existing eight watch-bill rows and the nine-line doctor example once, using a self-hosted Anime.js 4.5.0 build.

**Architecture:** A pure gate in `site/assets/walkthrough.mjs` decides play, wait, skip, or stay. A classic IIFE at the end of `site/index.html` dynamic-imports one pinned ESM bundle only after `#how` or `#watch` is within 400px and reduced motion is off, then calls `playReveal` for three separate timelines. Default CSS stays fully visible. Inline opacity and transform are set only in the same turn as `timeline.play()`.

**Tech Stack:** Static `site/index.html` and `site/styles.css` (no bundler), animejs 4.5.0 `dist/bundles/anime.esm.min.js`, pytest, Node's built-in test runner invoked from pytest, headless Chrome for the preview.

## Global Constraints

Copied from `docs/superpowers/specs/2026-11-05-animejs-walkthrough-design.md`. Every task includes these.

- The course is four waypoints, in order: Scan, A few questions, Preview, Set up. There is no fifth step.
- Watch-bill rows stay in published order: Secret guard, CI, Secret scan, CodeQL, Dependabot, Health check, Release, Branch rule.
- The doctor reveal is `figure.scorecard` inside `#watch` (two group labels, six status lines, the Next line). The Commands card whose heading is "Health check" is out of scope.
- Course motion: opacity 0 and 8px down to opacity 1 and no offset, duration 450ms, stagger 180ms, finishes in 990ms.
- Watch rows: opacity and 8px translateY, duration 280ms, stagger 70ms, eight rows finish in 770ms.
- Doctor targets: nine items, duration 280ms, stagger 80ms, finishes in 920ms.
- Only `opacity` and `translateY`. No `translateX`, no scale that changes layout, no animating `height` or `display`.
- Each timeline plays once per page view. Scrolling away does not rewind or queue another play. No replay control.
- If `prefers-reduced-motion: reduce` matches, do not load the library and do not play.
- If reduced motion turns on while a timeline runs: stop it, leave every target fully visible, clear leftover inline opacity and transform, do not return to the hidden start, mark it played.
- If reduced motion turns off after that surface was already shown: do not play.
- If reduced motion turns off before that surface has played and it is at least 60% visible: load the module if needed, then play once.
- Default CSS shows every waypoint, row, and report line. Hide a target only in the same turn that starts its timeline.
- If the import rejects or `createTimeline` throws, remove inline opacity and transform this script set, and do not try again.
- Do not set `aria-hidden`. Do not remove targets with `display` or `visibility`. Do not add a live region per step.
- Dynamic-import only when `#how` or `#watch` is within 400px, and only when reduced motion is off.
- Lighthouse budgets stay: pessimistic aggregation, performance at least 0.90, accessibility at least 0.95, best practices at least 0.90, cumulative layout shift at most 0.10, first-load transfer at most 800 KiB. Do not edit those numbers. If a cold run is under 0.90, keep the import off the first screen. Do not lower the floor.
- Pin animejs 4.5.0. Ship `LICENSE.md` unchanged. Do not load a CDN at runtime. Do not add a bundler.
- Out of scope: flag hoist, SVG line drawing, the hero, the terminal, the commands grid, the film, audio, and any copy change.

**Dependency on pull request #37:** This plan is implemented from `main` (`a30ca87`) or a later main that already contains only this plan's commits. Do not branch it from `cursor/film-playback-budgets-ea92`. That pull request is unmerged. Its latest measured head `5225bf3` failed Lighthouse with runs 0.85, 1.00, 1.00. The cold run had total blocking time 613 ms (long tasks 321, 253, 178, 118, 94, 63 ms), LCP 757 ms, CLS 0.0002, transfer 66,665 bytes. `main`'s `lighthouserc.json` has the numeric floors above and does not set `aggregationMethod`. Task 7 adds that key without changing the numbers. A red Lighthouse run caused by the existing cold-start blocking time is not fixed by weakening a floor and is not an excuse to edit the film.

---

### Task 1: Vendor the pinned build

**Files:**
- Create: `site/assets/vendor/animejs/4.5.0/anime.esm.min.js`
- Create: `site/assets/vendor/animejs/4.5.0/LICENSE.md`
- Test: `tests/test_site.py`

**Interfaces:**
- Produces: those two files. Later tasks import `createTimeline`, `createScope`, and `stagger` from `site/assets/vendor/animejs/4.5.0/anime.esm.min.js`. Named exports were confirmed by importing that build in Node.

- [ ] **Step 1: Write the failing hash test**

Add to `tests/test_site.py`:

```python
def test_animejs_vendor_is_the_pinned_build():
    vendor = SITE / "assets" / "vendor" / "animejs" / "4.5.0"
    script = vendor / "anime.esm.min.js"
    license_file = vendor / "LICENSE.md"
    assert script.is_file()
    assert license_file.is_file()
    spec = (ROOT / "docs/superpowers/specs/2026-11-05-animejs-walkthrough-design.md").read_text(encoding="utf-8")
    script_sha = re.search(r"anime\.esm\.min\.js` \| 118678 \| 40860 \| `([0-9a-f]{64})`", spec).group(1)
    license_sha = re.search(r"LICENSE\.md` \| 1075 \| 643 \| `([0-9a-f]{64})`", spec).group(1)
    assert hashlib.sha256(script.read_bytes()).hexdigest() == script_sha
    assert hashlib.sha256(license_file.read_bytes()).hexdigest() == license_sha
    assert len(script.read_bytes()) == 118678
    assert "MIT License" in license_file.read_text(encoding="utf-8")
    assert "Copyright (c) 2025 Julian Garnier" in license_file.read_text(encoding="utf-8")
```

Add `import hashlib` at the top of the file.

- [ ] **Step 2: Run the test and confirm it fails**

Run: `python3 -m pytest tests/test_site.py::test_animejs_vendor_is_the_pinned_build -q`
Expected: FAIL because `site/assets/vendor/animejs/4.5.0/anime.esm.min.js` does not exist.

- [ ] **Step 3: Download exactly those bytes**

```bash
mkdir -p /tmp/anime-pack site/assets/vendor/animejs/4.5.0
npm pack animejs@4.5.0 --pack-destination /tmp/anime-pack
tar -xzf /tmp/anime-pack/animejs-4.5.0.tgz -C /tmp/anime-pack
cp /tmp/anime-pack/package/dist/bundles/anime.esm.min.js site/assets/vendor/animejs/4.5.0/anime.esm.min.js
cp /tmp/anime-pack/package/LICENSE.md site/assets/vendor/animejs/4.5.0/LICENSE.md
```

Confirm the npm pack shasum matches the spec's registry shasum. Do not commit the tarball or the other 33 unminified modules (measured closure 250462 bytes, larger than this 118678-byte bundle).

- [ ] **Step 4: Re-run the test**

Run: `python3 -m pytest tests/test_site.py::test_animejs_vendor_is_the_pinned_build -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py site/assets/vendor/animejs/4.5.0/anime.esm.min.js site/assets/vendor/animejs/4.5.0/LICENSE.md
git commit -m "chore: pin animejs 4.5.0 for the site"
```

### Task 2: Lock the published course, duties, and report

**Files:**
- Modify: `tests/test_site.py`
- Read only: `site/index.html` lines 195-221 (`ol.course`) and 273-307 (`table.watchbill`, `figure.scorecard`)

**Interfaces:**
- Produces: `test_walkthrough_copy_matches_the_page`, which later edits must keep passing. Selectors used by Task 3 are `#how ol.course > li.waypoint`, `#watch table.watchbill > tbody > tr`, and `#watch figure.scorecard`.

- [ ] **Step 1: Write the failing-if-copy-drifts test**

```python
def test_walkthrough_copy_matches_the_page():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    course = html.split('id="how"', 1)[1].split('id="feel"', 1)[0]
    headings = re.findall(r"<h3>(.*?)</h3>", course)
    assert headings == ["Scan", "A few questions", "Preview", "Set up"]
    watch = html.split('id="watch"', 1)[1].split('id="commands"', 1)[0]
    duties = re.findall(r"<td>([^<]*)</td><td>([^<]*)</td>", watch.replace("\n", ""))
    assert [name for _, name in duties] == [
        "Secret guard",
        "CI",
        "Secret scan",
        "CodeQL",
        "Dependabot",
        "Health check",
        "Release",
        "Branch rule",
    ]
    report = watch.split('class="scorecard"', 1)[1]
    statuses = re.findall(r'class="status (?:fail|pass)">(.*?)</b>([^<]*)', report)
    assert [label.strip() for _, label in statuses] == [
        "secret guard installed",
        "remote protection",
        "code scanning (CodeQL)",
        "dependency watch (Dependabot)",
        "automated tests (CI)",
        "managed files",
    ]
    assert report.index("Security") < report.index("secret guard installed")
    assert report.index("Setup") < report.index("automated tests (CI)")
    assert "Next: run bash .sdlc/hooks/install.sh" in report
```

The table cells in `site/index.html` are on one line each, so the duty regex matches the published "On watch" column. If a fifth `<h3>` appears inside `#how` before `#feel`, the heading assertion fails.

- [ ] **Step 2: Run it**

Run: `python3 -m pytest tests/test_site.py::test_walkthrough_copy_matches_the_page -q`
Expected: PASS on current `main`. If it fails, the page copy drifted; stop and reconcile with the spec instead of changing the four names.

- [ ] **Step 3: Commit**

```bash
git add tests/test_site.py
git commit -m "test: lock the course and watch copy"
```

### Task 3: Gate module

**Files:**
- Create: `site/assets/walkthrough.mjs`
- Create: `tests/walkthrough.test.mjs`
- Modify: `tests/test_site.py` (one subprocess test)

**Interfaces:**
- Produces:
  - `decide(state) -> "play" | "wait" | "skip" | "stay"`
  - `state` fields: `played` bool, `reduceMotion` bool, `ratio` number, `visibleSince` number or null, `now` number, `libraryReady` bool
  - `finishVisible(timeline, elements) -> true`
  - `playReveal(anime, elements, duration, staggerMs) -> timeline`
  - `COURSE_SELECTOR = "#how ol.course > li.waypoint"`
  - `WATCH_ROW_SELECTOR = "#watch table.watchbill > tbody > tr"`
  - `REPORT_SELECTOR = "#watch figure.scorecard p.group, #watch figure.scorecard li, #watch figure.scorecard p.next"`
  - `VISIBLE_RATIO = 0.6`, `LATE_MS = 300`, `NEAR_PX = 400`

- [ ] **Step 1: Write the failing Node tests**

`tests/walkthrough.test.mjs`:

```javascript
import assert from "node:assert/strict";
import test from "node:test";
import { decide, finishVisible, LATE_MS, VISIBLE_RATIO } from "../site/assets/walkthrough.mjs";

const base = { played: false, reduceMotion: false, ratio: 1, visibleSince: 0, now: 0, libraryReady: true };

test("plays once when ready and mostly visible", () => {
  assert.equal(decide(base), "play");
  assert.equal(VISIBLE_RATIO, 0.6);
  assert.equal(LATE_MS, 300);
});

test("does not play below 60 percent", () => {
  assert.equal(decide({ ...base, ratio: 0.59 }), "wait");
});

test("stays finished or reduced without hiding", () => {
  assert.equal(decide({ ...base, played: true }), "stay");
  assert.equal(decide({ ...base, reduceMotion: true }), "stay");
});

test("skips when the section was visible for 300ms before the library", () => {
  assert.equal(decide({ ...base, libraryReady: false, now: 299 }), "wait");
  assert.equal(decide({ ...base, libraryReady: false, now: 300 }), "skip");
  assert.equal(decide({ ...base, libraryReady: true, now: 300 }), "skip");
});

test("finishVisible clears inline motion and pauses", () => {
  const calls = [];
  const timeline = { pause() { calls.push("pause"); } };
  const el = { style: { opacity: "0", transform: "translateY(8px)" } };
  assert.equal(finishVisible(timeline, [el]), true);
  assert.deepEqual(calls, ["pause"]);
  assert.equal(el.style.opacity, "");
  assert.equal(el.style.transform, "");
});
```

Add to `tests/test_site.py`:

```python
def test_walkthrough_gate_node_tests():
    completed = subprocess.run(
        ["node", "--test", "tests/walkthrough.test.mjs"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
```

Add `import subprocess`.

- [ ] **Step 2: Run and confirm failure**

Run: `python3 -m pytest tests/test_site.py::test_walkthrough_gate_node_tests -q`
Expected: FAIL because `site/assets/walkthrough.mjs` cannot be imported.

- [ ] **Step 3: Implement the gate**

`site/assets/walkthrough.mjs`:

```javascript
export const VISIBLE_RATIO = 0.6;
export const LATE_MS = 300;
export const NEAR_PX = 400;
export const COURSE_SELECTOR = "#how ol.course > li.waypoint";
export const WATCH_ROW_SELECTOR = "#watch table.watchbill > tbody > tr";
export const REPORT_SELECTOR = "#watch figure.scorecard p.group, #watch figure.scorecard li, #watch figure.scorecard p.next";

export function decide(state) {
  if (state.played || state.reduceMotion) return "stay";
  if (state.ratio < VISIBLE_RATIO) return "wait";
  const waited = state.visibleSince == null ? 0 : state.now - state.visibleSince;
  if (waited >= LATE_MS) return "skip";
  if (!state.libraryReady) return "wait";
  return "play";
}

export function finishVisible(timeline, elements) {
  if (timeline && typeof timeline.pause === "function") timeline.pause();
  for (const el of elements) {
    el.style.opacity = "";
    el.style.transform = "";
  }
  return true;
}

export function playReveal(anime, elements, duration, staggerMs) {
  const timeline = anime.createTimeline({ autoplay: false });
  timeline.add(elements, {
    opacity: [0, 1],
    translateY: [8, 0],
    duration,
    delay: anime.stagger(staggerMs),
  }, 0);
  for (const el of elements) {
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
  }
  timeline.play();
  return timeline;
}
```

`pause` and `play` are documented timeline method names (`onScroll` sync modes list them). `autoplay: false` is the documented playback setting. Do not call `reset` or `reverse` here; those return toward the start and would hide text.

- [ ] **Step 4: Re-run**

Run: `python3 -m pytest tests/test_site.py::test_walkthrough_gate_node_tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/assets/walkthrough.mjs tests/walkthrough.test.mjs tests/test_site.py
git commit -m "feat: add the walkthrough play gate"
```

### Task 4: Wire the page

**Files:**
- Modify: `site/index.html` after the existing film IIFE, before `</body>` (the copy script and film script end just above line 636)
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: `decide`, `finishVisible`, `playReveal`, the three selectors, `VISIBLE_RATIO`, `LATE_MS`, `NEAR_PX` from `../assets/walkthrough.mjs` relative to `site/index.html` (URL `assets/walkthrough.mjs`)
- Consumes: `createTimeline` and `stagger` from `assets/vendor/animejs/4.5.0/anime.esm.min.js`, passed in as the `anime` argument to `playReveal`

- [ ] **Step 1: Write the source contract test**

```python
def test_walkthrough_script_is_progressive():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    script = html.split("assets/walkthrough.mjs", 1)[1]
    assert "prefers-reduced-motion" in script
    assert "onScroll" not in script
    assert "played" in script
    assert "import(" in html
    assert "anime.esm.min.js" in html
    assert "https://cdn." not in html
    assert 'aria-hidden' not in script
    commands = html.split('id="commands"', 1)[1]
    assert "<h3>Health check</h3>" in commands
    assert "COURSE_SELECTOR" not in commands
```

The new inline script must still start with `(function` so `test_site_scripts_stay_out_of_global_scope` keeps passing. `walkthrough.mjs` is a module file, not an inline script.

- [ ] **Step 2: Run it and confirm failure**

Run: `python3 -m pytest tests/test_site.py::test_walkthrough_script_is_progressive -q`
Expected: FAIL because `assets/walkthrough.mjs` is not in `index.html`.

- [ ] **Step 3: Add the loader**

Insert this script immediately before `</body>`:

```html
<script>
  (function () {
    var gateUrl = new URL("assets/walkthrough.mjs", document.baseURI).href;
    var animeUrl = new URL("assets/vendor/animejs/4.5.0/anime.esm.min.js", document.baseURI).href;
    var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var surfaces = null;
    var loading = null;
    var bootStarted = 0;

    function reduceOn() { return motion.matches; }

    function ratio(el) {
      var rect = el.getBoundingClientRect();
      var visible = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
      return rect.height ? Math.max(0, visible / rect.height) : 0;
    }

    function near(el) {
      var rect = el.getBoundingClientRect();
      return rect.top < window.innerHeight + 400 && rect.bottom > -400;
    }

    function loadGate() {
      if (loading) return loading;
      loading = Promise.all([
        import(gateUrl),
        import(animeUrl),
      ]).then(function (mods) {
        return { gate: mods[0], anime: mods[1] };
      });
      loading.catch(function () { loading = Promise.resolve(null); });
      return loading;
    }

    function ensure(mods) {
      if (surfaces) return surfaces;
      var how = document.getElementById("how");
      var watch = document.getElementById("watch");
      surfaces = {
        course: { el: how, nodes: Array.from(how.querySelectorAll(mods.gate.COURSE_SELECTOR)), duration: 450, stagger: 180, played: false, timeline: null, visibleSince: null },
        rows: { el: document.querySelector("#watch table.watchbill"), nodes: Array.from(document.querySelectorAll(mods.gate.WATCH_ROW_SELECTOR)), duration: 280, stagger: 70, played: false, timeline: null, visibleSince: null },
        report: { el: document.querySelector("#watch figure.scorecard"), nodes: Array.from(document.querySelectorAll(mods.gate.REPORT_SELECTOR)), duration: 280, stagger: 80, played: false, timeline: null, visibleSince: null },
      };
      return surfaces;
    }

    function tick(mods) {
      if (!mods) return;
      var now = performance.now();
      Object.keys(ensure(mods)).forEach(function (key) {
        var surface = surfaces[key];
        var seen = ratio(surface.el);
        if (seen >= mods.gate.VISIBLE_RATIO && surface.visibleSince == null) surface.visibleSince = now;
        var action = mods.gate.decide({
          played: surface.played,
          reduceMotion: reduceOn(),
          ratio: seen,
          visibleSince: surface.visibleSince,
          now: now,
          libraryReady: true,
        });
        if (action === "skip") {
          surface.played = true;
          return;
        }
        if (action !== "play") return;
        try {
          surface.timeline = mods.gate.playReveal(mods.anime, surface.nodes, surface.duration, surface.stagger);
          surface.played = true;
        } catch (error) {
          mods.gate.finishVisible(null, surface.nodes);
          surface.played = true;
        }
      });
    }

    function consider() {
      if (reduceOn()) return;
      var how = document.getElementById("how");
      var watch = document.getElementById("watch");
      if (!near(how) && !near(watch)) return;
      if (!bootStarted) bootStarted = performance.now();
      loadGate().then(function (mods) { tick(mods); }).catch(function () {});
    }

    function onMotion() {
      if (!reduceOn() || !surfaces) {
        consider();
        return;
      }
      Object.keys(surfaces).forEach(function (key) {
        var surface = surfaces[key];
        if (surface.timeline) {
          import(gateUrl).then(function (gate) {
            surface.played = gate.finishVisible(surface.timeline, surface.nodes);
            surface.timeline = null;
          });
        } else if (surface.played) {
          surface.played = true;
        }
      });
    }

    if ("IntersectionObserver" in window) {
      var watcher = new IntersectionObserver(consider, { rootMargin: "400px 0px", threshold: [0, 0.6] });
      watcher.observe(document.getElementById("how"));
      watcher.observe(document.getElementById("watch"));
    }
    if (motion.addEventListener) motion.addEventListener("change", onMotion);
    else if (motion.addListener) motion.addListener(onMotion);
  })();
</script>
```

`libraryReady` is true inside `tick` because `tick` runs only after the import resolves. The 300ms skip uses `visibleSince` recorded when the element first crossed 0.6, compared with `performance.now()` at resolve time. Do not set opacity to 0 anywhere except inside `playReveal`, which sets it and calls `timeline.play()` in the same turn.

Course nodes are the four `li.waypoint` elements. Watch nodes are the eight `tbody tr` elements. Report nodes are nine, in DOM order: Security label, four status lines, Setup label, two status lines, Next line. Do not query `#commands`.

- [ ] **Step 4: Run the site tests**

Run: `python3 -m pytest tests/test_site.py -q`
Expected: PASS, including the inline-script wrapper test and the local-file reference test. `assets/walkthrough.mjs` is referenced from a dynamic `import()`, not from `src=`, so add a direct assertion in `test_walkthrough_script_is_progressive` that the file exists:

```python
assert (SITE / "assets" / "walkthrough.mjs").is_file()
assert (SITE / "assets" / "vendor" / "animejs" / "4.5.0" / "anime.esm.min.js").is_file()
```

- [ ] **Step 5: Commit**

```bash
git add site/index.html tests/test_site.py
git commit -m "feat: play the course and the watch once"
```

### Task 5: Browser proof and preview

**Files:**
- Create nothing in git. Write previews to `/opt/cursor/artifacts/walkthrough/` and attach them to the implementation pull request. Do not commit png or webm files.

**Interfaces:**
- Consumes: the page from Task 4.

- [ ] **Step 1: Serve the site**

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
```

- [ ] **Step 2: Motion-allowed course plays once**

With headless Chrome at 1440x900, no reduced-motion emulation:

1. Load `http://127.0.0.1:8766/index.html` and wait 500ms. Request log must not contain `anime.esm.min.js`.
2. `scrollIntoView({ block: "center", behavior: "instant" })` on `#how`.
3. Within 200ms, waypoint 1's opacity is less than waypoint 4's, or waypoint 1 has already reached 1 while a later waypoint is still below 1.
4. After 1200ms, all four `li.waypoint` opacities are 1 and inline transforms are empty or `none`.
5. Scroll to `#install`, then back to `#how`. Opacity stays 1. No second drop to 0.

Save screenshots:

- `/opt/cursor/artifacts/walkthrough/course-desktop-mid.png` about 400ms after the scroll
- `/opt/cursor/artifacts/walkthrough/course-desktop-end.png` after 1200ms
- `/opt/cursor/artifacts/walkthrough/course-mobile-mid.png` at 390x844, about 400ms after scroll
- `/opt/cursor/artifacts/walkthrough/watch-mid.png` about 300ms after scrolling `table.watchbill` to center
- `/opt/cursor/artifacts/walkthrough/report-mid.png` about 300ms after scrolling `figure.scorecard` to center

Record one silent clip of the course reveal, about 2 seconds, to `/opt/cursor/artifacts/walkthrough/course.webm`. Capture frames with `page.screenshot` every 100ms and encode:

```bash
ffmpeg -y -framerate 10 -i /opt/cursor/artifacts/walkthrough/frame-%02d.png -c:v libvpx-vp9 -an /opt/cursor/artifacts/walkthrough/course.webm
```

Expected: the webm shows Scan appearing before Set up, and the four headings remain readable. No audio track.

- [ ] **Step 3: Reduced motion, preference change, failed load, keyboard**

1. `emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }])` before load. Scroll `#how` into view. All four waypoints stay opacity 1. `anime.esm.min.js` is not requested.
2. Load with motion allowed, scroll `#how` into view, then set the media feature to `reduce` during the 990ms window. Within 100ms, every waypoint is opacity 1 and has no inline transform. Scrolling away and back does not play.
3. Load with motion allowed, block `anime.esm.min.js` (`page.route` abort). Scroll `#how`, the watch table, and the scorecard into view. Every waypoint, row, and report line is visible and has empty inline opacity.
4. At 390px width, `document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1`.
5. `document.querySelectorAll("#how button, #watch button").length` is unchanged from before this work (no new keyboard trap). Tab order of the four `h3` elements inside `#how` is still Scan, A few questions, Preview, Set up.

- [ ] **Step 4: Attach the five png files and `course.webm` to the implementation pull request body.**

### Task 6: Lighthouse floors, unchanged

**Files:**
- Modify: `lighthouserc.json` only to insert `"aggregationMethod": "pessimistic"` inside `ci.assert` if that key is absent
- Modify: `tests/test_site.py`

**Interfaces:**
- Consumes: current floors in `lighthouserc.json` on this branch: performance 0.9, accessibility 0.95, best practices 0.9, cumulative layout shift max 0.1, total byte weight max 800000. `main` at `a30ca87` does not yet contain `aggregationMethod`. Pull request #37 does, and its cold run still missed 0.90. Do not copy film or `content-visibility` edits from that branch.

- [ ] **Step 1: Write the floor test**

```python
def test_lighthouse_floors_stay_pessimistic():
    config = (ROOT / "lighthouserc.json").read_text(encoding="utf-8")
    assert '"aggregationMethod": "pessimistic"' in config
    assert '"categories:performance": ["error", {"minScore": 0.9}]' in config
    assert '"categories:accessibility": ["error", {"minScore": 0.95}]' in config
    assert '"categories:best-practices": ["error", {"minScore": 0.9}]' in config
    assert '"cumulative-layout-shift": ["error", {"maxNumericValue": 0.1}]' in config
    assert '"total-byte-weight": ["error", {"maxNumericValue": 800000}]' in config
```

- [ ] **Step 2: Run it and confirm failure on this branch**

Run: `python3 -m pytest tests/test_site.py::test_lighthouse_floors_stay_pessimistic -q`
Expected: FAIL because `aggregationMethod` is absent. The numeric lines must already match. If a numeric assertion fails, stop. Do not edit the number to match a new value.

- [ ] **Step 3: Add only the aggregation key**

Inside `ci.assert`, before `assertions`:

```json
"aggregationMethod": "pessimistic",
```

Leave every `minScore` and `maxNumericValue` byte-for-byte as it was.

- [ ] **Step 4: Run three independent cold Lighthouse batches**

For each batch, use a new Chrome user-data directory and `lhci autorun` with the repo config (simulated throttling, three runs, pessimistic). Do not reuse a profile, discard a run, or switch to devtools throttling to raise a score.

Expected to record, per run: performance, TBT, LCP, CLS, transfer size. All three runs in all three batches must be performance >= 0.90 with the floors above still in force.

If any cold run is under 0.90, stop. Write the nine scores into the pull request. Do not change `minScore`, do not delete audits, and do not drop `aggregationMethod`. The anime module must stay off the first screen (Task 4). A failure that reproduces on a build of this branch with the dynamic import removed is the existing cold-start blocker tracked on pull request #37, not a reason to edit the film here.

- [ ] **Step 5: Commit**

```bash
git add lighthouserc.json tests/test_site.py CHANGELOG.md
git commit -m "test: keep lighthouse floors pessimistic"
```

Add one Unreleased changelog bullet: the marketing site plays the setup course and the watch report once, and leaves them still when the visitor prefers reduced motion. Do not claim a Lighthouse score in the changelog.

### Task 7: Full local check

- [ ] **Step 1: Run the suite**

Run: `python3 -m pytest tests/ -q && python3 -m ruff check . && python3 -m ruff format --check .`
Expected: pytest reports no failures. Ruff reports all checks passed.

- [ ] **Step 2: Open the implementation pull request as a draft against `main`.** Do not merge it. Do not mark it ready. Put the five screenshots and `course.webm` from Task 5 in the description, plus the nine Lighthouse scores from Task 6.
