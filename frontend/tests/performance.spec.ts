import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";

test("two-minute newly displayed swaps and capture-to-display latency", async ({
  page,
  request,
  browser,
}) => {
  await page.addInitScript(() => {
    (window as any).__aimsFrames = [];
    window.addEventListener("aims-frame", ((event: CustomEvent) => {
      (window as any).__aimsFrames.push(event.detail);
    }) as EventListener);
  });
  await page.goto(`/studio?mode=live${process.env.AIMS_WORKER === "off" ? "&worker=off" : ""}`);
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Stop camera", exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await page.locator("#live-effect").selectOption("swap");
  await page.locator("#sample-identity").selectOption("/examples/source.png");
  await expect(page.getByText("Identity applied", { exact: true })).toBeVisible(
    { timeout: 45000 },
  );
  await page.waitForTimeout(3000);
  const started = await page.evaluate(() => {
    (window as any).__aimsFrames = [];
    return performance.now();
  });
  for (let i = 0; i < 12; i++) await page.waitForTimeout(10000);
  const result = await page.evaluate((start) => {
    const frames = (window as any).__aimsFrames as {
      frame_id: number;
      swapped: boolean;
      captured_at: number;
      rendered_at: number;
      processing_ms: number;
    }[];
    const swaps = frames.filter((x) => x.swapped),
      duration = (performance.now() - start) / 1000;
    const latencies = swaps
      .map((x) => x.rendered_at - x.captured_at)
      .sort((a, b) => a - b);
    const canvas = document.querySelector(
      ".camera-output",
    ) as HTMLCanvasElement;
    const settings = (
      (document.querySelector("video") as HTMLVideoElement)
        .srcObject as MediaStream
    )
      .getVideoTracks()[0]
      .getSettings();
    const windows = Array.from({length:12},(_,i)=>swaps.filter(x=>x.rendered_at>=start+i*10000 && x.rendered_at<start+(i+1)*10000).length/10);
    return {
      ten_second_windows: windows,
      scope:
        "Chrome with a looping, replay fixture as a fake webcam; inspect the fixture manifest for its actual motion scope; includes software capture, encoding, WebSocket, new inference, decode and next animation frame",
      resolution: [canvas.width, canvas.height],
      capture_frame_rate: settings.frameRate,
      duration_seconds: duration,
      processed_frames: frames.length,
      new_displayed_swaps: swaps.length,
      displayed_swap_fps: swaps.length / duration,
      p95_capture_to_display_ms: latencies[Math.floor(latencies.length * 0.95)],
      unique_frame_ids: new Set(swaps.map((x) => x.frame_id)).size,
      first_half_swaps: swaps.filter((x) => x.rendered_at < start + 60000)
        .length,
      second_half_swaps: swaps.filter((x) => x.rendered_at >= start + 60000)
        .length,
    };
  }, started);
  const runtime = await (await request.get("/api/system")).json();
  await fs.mkdir("../outputs/benchmarks", { recursive: true });
  await fs.writeFile(
    process.env.AIMS_BENCHMARK_OUTPUT || "../outputs/benchmarks/browser-120s.json",
    JSON.stringify({ ...result, runtime, browser:browser.version(),warmup_seconds:3 }, null, 2),
  );
  await page.getByText("Live performance", { exact: true }).click();
  await page.screenshot({
    path: "../.taste-skill/qa/live-performance.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/system")).json()).active_live_sessions,
    )
    .toBe(0);
  expect(result.unique_frame_ids).toBe(result.new_displayed_swaps);
  expect(result.displayed_swap_fps).toBeGreaterThanOrEqual(15);
  for (const fps of result.ten_second_windows) expect(fps).toBeGreaterThanOrEqual(15);
  expect(result.p95_capture_to_display_ms).toBeLessThan(200);
  console.log(JSON.stringify(result));
});
