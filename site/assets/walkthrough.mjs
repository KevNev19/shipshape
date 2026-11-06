export const VISIBLE_RATIO = 0.6;
export const LATE_MS = 300;
export const NEAR_PX = 400;
export const COURSE_SELECTOR = "#how ol.course > li.waypoint";
export const WATCH_ROW_SELECTOR = "#watch table.watchbill > tbody > tr";
export const REPORT_SELECTOR =
  "#watch figure.scorecard p.group, #watch figure.scorecard li, #watch figure.scorecard p.next";

// A section taller than the viewport can never put 60% of its own box on
// screen. Count the visible slice against whichever is smaller, the section
// or the screen, so a phone can still reach the same 60% bar.
export function visibleRatio(height, viewportHeight, visible) {
  const span = Math.min(height, viewportHeight);
  if (!span) return 0;
  return Math.max(0, visible) / span;
}

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
  timeline.add(
    elements,
    {
      opacity: [0, 1],
      translateY: [8, 0],
      duration,
      delay: anime.stagger(staggerMs),
    },
    0,
  );
  for (const el of elements) {
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
  }
  timeline.play();
  if (typeof timeline.then === "function") {
    timeline.then(() => {
      for (const el of elements) {
        el.style.opacity = "";
        el.style.transform = "";
      }
    });
  }
  return timeline;
}
