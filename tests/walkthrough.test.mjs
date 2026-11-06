import assert from "node:assert/strict";
import test from "node:test";
import { decide, finishVisible, LATE_MS, VISIBLE_RATIO } from "../site/assets/walkthrough.mjs";

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
