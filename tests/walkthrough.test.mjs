import assert from "node:assert/strict";
import test from "node:test";
import {
  decide,
  finishVisible,
  LATE_MS,
  playReveal,
  VISIBLE_RATIO,
  visibleRatio,
} from "../site/assets/walkthrough.mjs";

const base = {
  played: false,
  reduceMotion: false,
  ratio: 1,
  visibleSince: 0,
  now: 0,
  libraryReady: true,
};

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

test("a tall section can still count as on screen", () => {
  assert.equal(visibleRatio(100, 800, 60) >= VISIBLE_RATIO, true);
  assert.equal(visibleRatio(100, 800, 59) >= VISIBLE_RATIO, false);
  assert.equal(visibleRatio(1636, 844, 844) >= VISIBLE_RATIO, true);
  assert.equal(visibleRatio(1636, 844, 500) >= VISIBLE_RATIO, false);
  assert.equal(visibleRatio(0, 844, 0), 0);
});

test("playReveal hides only as it starts and clears when finished", () => {
  const el = { style: { opacity: "", transform: "" } };
  let finished = null;
  const timeline = {
    add(target, params, position) {
      assert.equal(target, elements);
      assert.deepEqual(params.opacity, [0, 1]);
      assert.deepEqual(params.translateY, [8, 0]);
      assert.equal(params.duration, 450);
      assert.equal(params.delay, "stagger-180");
      assert.equal(position, 0);
      return this;
    },
    play() {
      return this;
    },
    then(callback) {
      finished = callback;
      return Promise.resolve();
    },
  };
  const elements = [el];
  const anime = {
    createTimeline(options) {
      assert.deepEqual(options, { autoplay: false });
      return timeline;
    },
    stagger(ms) {
      assert.equal(ms, 180);
      return "stagger-180";
    },
  };
  assert.equal(playReveal(anime, elements, 450, 180), timeline);
  assert.equal(el.style.opacity, "0");
  assert.equal(el.style.transform, "translateY(8px)");
  finished();
  assert.equal(el.style.opacity, "");
  assert.equal(el.style.transform, "");
});

test("finishVisible clears inline motion and pauses", () => {
  const calls = [];
  const timeline = {
    pause() {
      calls.push("pause");
    },
  };
  const el = { style: { opacity: "0", transform: "translateY(8px)" } };
  assert.equal(finishVisible(timeline, [el]), true);
  assert.deepEqual(calls, ["pause"]);
  assert.equal(el.style.opacity, "");
  assert.equal(el.style.transform, "");
});
