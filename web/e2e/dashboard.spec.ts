import { test, expect } from "@playwright/test";

const expectedControls = [
  { locator: (page: any) => page.getByLabel("Dashboard base coin") },
  { locator: (page: any) => page.getByRole("button", { name: /swap coins/i }) },
  { locator: (page: any) => page.getByLabel("Dashboard quote coin") },
  { locator: (page: any) => page.getByLabel("Dashboard analytics window") },
  { locator: (page: any) => page.getByLabel("Leader symbol") },
  { locator: (page: any) => page.getByLabel("Follower symbol") },
  { locator: (page: any) => page.getByLabel("Lead/lag window") },
];

test.describe("/dashboard smoke", () => {
  test("emits performance markers and supports keyboard traversal", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.waitForSelector("main");

    await page.waitForFunction(
      () => performance.getEntriesByName("dashboard:load").length > 0,
    );

    await page.waitForFunction(
      () =>
        performance.getEntriesByName("dashboard:sentiment:render").length > 0,
    );

    for (const { locator } of expectedControls) {
      await expect(locator(page)).toBeVisible();
    }

    await page.keyboard.press("Tab");
    for (const { locator } of expectedControls) {
      await expect(locator(page)).toBeFocused({
        timeout: 2000,
      });
      await page.keyboard.press("Tab");
    }

    const swapButton = page.getByRole("button", { name: /swap coins/i });
    await swapButton.press("Enter");
    await expect(page.getByLabel("Base coin")).toHaveValue("ETH");

    const measures = await page.evaluate(() => {
      const entries = performance.getEntriesByName("dashboard:load");
      return entries.map((entry) => entry.duration);
    });
    expect(measures[0]).toBeLessThan(1200);
  });
});
