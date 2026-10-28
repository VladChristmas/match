import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildScene,
  wrapText,
  type SceneOptions,
} from "./scene.ts";
import {
  DEMO_SCREENS,
  RESOLUTIONS,
  findResolution,
  resolveDims,
  type Orientation,
  type ScreenMode,
} from "./screen.ts";

const MODES: ScreenMode[] = ["matches", "chat", "profile", "notification"];

function optionsFor(orientation: Orientation): SceneOptions {
  return { resolution: RESOLUTIONS[0], orientation };
}

test("buildScene: все режимы дают непустой список конечных операндов", () => {
  for (const mode of MODES) {
    const scene = buildScene(DEMO_SCREENS[mode], optionsFor("portrait"));
    assert.ok(scene.commands.length > 3, `${mode}: слишком мало операндов`);
    for (const command of scene.commands) {
      assert.ok(Number.isFinite(command.x ?? 0), `${mode}: x не число`);
      assert.ok(Number.isFinite(command.y ?? 0), `${mode}: y не число`);
      if (command.op === "text") {
        assert.ok(command.text.length > 0, `${mode}: пустой текст`);
        assert.ok(command.size > 0, `${mode}: неположительный размер шрифта`);
      }
    }
  }
});

test("buildScene: альбом меняет размеры кадра", () => {
  const portrait = buildScene(DEMO_SCREENS.chat, optionsFor("portrait"));
  const landscape = buildScene(DEMO_SCREENS.chat, optionsFor("landscape"));
  assert.equal(portrait.width, 360);
  assert.equal(portrait.height, 640);
  assert.equal(landscape.width, 640);
  assert.equal(landscape.height, 360);
});

test("buildScene: размеры из пресета, fallback на первый пресет", () => {
  const big = buildScene(DEMO_SCREENS.matches, {
    resolution: findResolution("412x915"),
    orientation: "portrait",
  });
  assert.equal(big.width, 412);
  assert.equal(big.height, 915);
  assert.deepEqual(findResolution("нет-такого"), RESOLUTIONS[0]);
  assert.deepEqual(resolveDims(RESOLUTIONS[1], "landscape"), { width: 844, height: 390 });
});

test("buildScene: чат рисует сообщения собеседника и пользователя", () => {
  const scene = buildScene(DEMO_SCREENS.chat, optionsFor("portrait"));
  const texts = scene.commands.filter((c) => c.op === "text").map((c) => (c.op === "text" ? c.text : ""));
  assert.ok(texts.includes("Анна"), "имя собеседника не отрисовано");
  assert.ok(
    texts.some((t) => t.includes("Привет")),
    "текст сообщения не отрисован",
  );
  const bubbles = scene.commands.filter((c) => c.op === "roundRect" && c.w > 60 && c.w < 300);
  assert.ok(bubbles.length >= 3, "пузыри сообщений не отрисованы");
});

test("wrapText: перенос по словам, пустой ввод не ломает", () => {
  assert.deepEqual(wrapText("Привет! Как проходит вечер?", 12), ["Привет! Как", "проходит", "вечер?"]);
  assert.deepEqual(wrapText("", 12), [""]);
  assert.deepEqual(wrapText("   ", 12), [""]);
  assert.deepEqual(wrapText("длинноеслово", 4), ["длинноеслово"]);
});
