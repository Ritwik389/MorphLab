import { test, expect } from "@playwright/test";
import path from "node:path";
import {execFileSync} from 'node:child_process';
import fs from 'node:fs/promises';

test('video upload, real export, progress and playable download',async({page,request},testInfo)=>{
  test.setTimeout(180000);
  const target=testInfo.outputPath('target.mp4');
  execFileSync('ffmpeg',['-v','error','-y','-i',path.resolve('../.cache/camera.y4m'),
    '-t','1','-vf','scale=320:240','-an','-c:v','libx264','-pix_fmt','yuv420p',target]);
  await page.goto('/studio?mode=video');
  await page.locator('input[accept^="video/"]').setInputFiles(target);
  await page.getByRole('checkbox',{name:'I have permission to edit this media.'}).check();
  await page.getByRole('button',{name:'Create video',exact:true}).click();
  await expect(page.getByRole('status')).toBeVisible();
  const download=page.getByRole('link',{name:'Download result',exact:true});
  await expect(download).toBeVisible({timeout:150000});
  await expect(page.getByLabel('Edited video')).toHaveJSProperty('readyState',4);
  const response=await request.get((await download.getAttribute('href'))!);
  expect(response.ok()).toBe(true);
  const result=testInfo.outputPath('result.mp4');
  await fs.writeFile(result,await response.body());
  const metadata=JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-of','json',result],{encoding:'utf8'}));
  const video=metadata.streams.find((s:any)=>s.codec_type==='video');
  expect([video.width,video.height]).toEqual([320,240]);
  expect(Number(video.duration)).toBeGreaterThanOrEqual(.9);
  expect(Number(video.duration)).toBeLessThanOrEqual(1.1);
});

test("landing, comparison, navigation and responsive layouts", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "A new face.",
  );
  const compare = page.getByRole("slider", {
    name: "Compare original and edited image",
  });
  await compare.focus();
  await page.keyboard.press("ArrowRight");
  await expect(compare).toHaveValue("51");
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.screenshot({
      path: `../.taste-skill/qa/landing-${width}.png`,
      fullPage: true,
    });
  }
  await page.getByRole("link", { name: "How it works", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "From source to screen." }),
  ).toBeVisible();
  await page.getByText("Does MorphLab use my Mac’s GPU?").click();
  await expect(
    page.getByText("When you run MorphLab locally on Apple Silicon", {
      exact: false,
    }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("photo workflow, sample pairs, report and invalid source", async ({
  page,
}) => {
  await page.goto("/studio?mode=photo");
  await expect(page.locator("#pair option")).toHaveCount(3);
  await page.getByText("I have permission to edit this media.").click();
  await page.getByRole("button", { name: "Create photo", exact: true }).click();
  await expect(page.getByRole("link", { name: "Download result" })).toBeVisible(
    { timeout: 45000 },
  );
  await page.getByText("Experiment report", { exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Download JSON report" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "How it works", exact: true }).click();
  await page.getByRole("link", { name: "Studio", exact: true }).click();
  await page.getByRole("link", { name: "Photo", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Download result" }),
  ).toBeVisible();
  await expect(page.locator(".comparison > img").first()).toHaveAttribute(
    "src",
    /\/api\/jobs\/.*\/original/,
  );
  await page.screenshot({
    path: "../.taste-skill/qa/photo-result.png",
    fullPage: true,
  });
  await page.getByText("Test challenging images", { exact: true }).click();
  await page
    .getByRole("checkbox", { name: "I have permission to edit this media." })
    .check();
  await page
    .getByRole("button", { name: "Use as source", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "Create photo", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "No face detected in source",
    { timeout: 15000 },
  );
});

test("live detects camera faces without upload; source swap; stop and restart", async ({
  page,
  request,
}) => {
  await page.goto("/studio?mode=live");
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Stop camera", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("1 face detected", { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await page.locator("#live-effect").selectOption("swap");
  await page
    .getByRole("button", { name: "Capture camera face", exact: true })
    .click();
  await expect(page.getByText("Camera capture", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.locator("#live-effect").selectOption("swap");
  await page.locator("#sample-identity").selectOption("/examples/source.png");
  await expect(page.getByText("Identity applied", { exact: true })).toBeVisible(
    { timeout: 30000 },
  );
  await page.getByText("Live performance", { exact: true }).click();
  await expect(
    page.getByText("Displayed swaps", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.taste-skill/qa/live-swap.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
  await expect(page.getByText("Camera is off", { exact: true })).toBeVisible();
  expect(
    await page.locator("video").evaluate((v: HTMLVideoElement) => v.srcObject),
  ).toBe(null);
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/system")).json()).active_live_sessions,
    )
    .toBe(0);
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Stop camera", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "How it works", exact: true }).click();
  await expect(page.locator("video")).toHaveCount(0);
});

test("source enrollment can finish after the camera starts", async ({
  page,
}) => {
  await page.goto("/studio?mode=live");
  await page.locator("#live-effect").selectOption("swap");
  await page.route("**/api/sessions/*/source", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.continue();
  });
  await page.locator("#sample-identity").selectOption("/examples/source.png");
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Identity applied", { exact: true })).toBeVisible(
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
});

test("camera denial is actionable", async ({ browser }) => {
  const context = await browser.newContext({ permissions: [] });
  const page = await context.newPage();
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Denied", "NotAllowedError");
    };
  });
  await page.goto("/studio?mode=live");
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Camera access was denied",
  );
  await context.close();
});
