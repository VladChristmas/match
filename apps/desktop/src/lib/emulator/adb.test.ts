import assert from "node:assert/strict";
import { test } from "node:test";

import { pointToDevice } from "./adb.ts";

const RECT = { left: 100, top: 50, width: 200, height: 400 };

test("pointToDevice: центр превью → центр кадра", () => {
  const point = pointToDevice(200, 250, RECT, 1080, 2400);
  assert.equal(point.x, 540);
  assert.equal(point.y, 1200);
});

test("pointToDevice: левый верхний угол → (0,0)", () => {
  const point = pointToDevice(100, 50, RECT, 1080, 2400);
  assert.deepEqual(point, { x: 0, y: 0 });
});

test("pointToDevice: клик за пределами превью клампится в кадр", () => {
  const point = pointToDevice(-500, 10_000, RECT, 1080, 2400);
  assert.equal(point.x, 0);
  assert.equal(point.y, 2399);
});

test("pointToDevice: вырожденный прямоугольник не даёт NaN", () => {
  const point = pointToDevice(10, 10, { left: 0, top: 0, width: 0, height: 0 }, 1080, 2400);
  assert.deepEqual(point, { x: 0, y: 0 });
});

test("pointToDevice: дробные координаты дают целые пиксели устройства", () => {
  // 1/100 кадра 101 px → 1.01 → floor → 1; 1/100 кадра 401 px → 4.01 → floor → 4.
  const point = pointToDevice(1, 1, { left: 0, top: 0, width: 100, height: 100 }, 101, 401);
  assert.deepEqual(point, { x: 1, y: 4 });
});

test("pointToDevice: масштаб превью не влияет на результат", () => {
  const scaled = { left: 0, top: 0, width: 400, height: 800 };
  const point = pointToDevice(200, 400, scaled, 1080, 2400);
  assert.equal(point.x, 540);
  assert.equal(point.y, 1200);
});
