import { test, expect, type Locator, type Page } from "@playwright/test";

import {
  authenticateThroughMockProvider,
  dashboardSelectors,
  installDashboardMocks,
} from "./dashboard.helpers";

const expectedControls: Array<{ locator: (page: Page) => Locator }> = [
  { locator: (page) => page.getByLabel("Dashboard base coin") },
  { locator: (page) => page.getByRole("button", { name: /swap coins/i }) },
  { locator: (page) => page.getByLabel("Dashboard quote coin") },
  { locator: (page) => page.getByLabel("Dashboard analytics window") },
  { locator: (page) => page.getByLabel("Leader symbol") },
  { locator: (page) => page.getByLabel("Follower symbol") },
  { locator: (page) => page.getByLabel("Lead/lag window") },
];

test.describe("/dashboard smoke", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardMocks(page);
  });

  test("emits performance markers and supports keyboard traversal", async ({
    page,
  }) => {
    await authenticateThroughMockProvider(page);
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

test.describe("/dashboard explainability and graph accessibility", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardMocks(page);
  });

  test("supports hover + keyboard explainers, pulsing edges, and performant window toggles", async ({
    page,
  }) => {
    await authenticateThroughMockProvider(page);
    const selectors = dashboardSelectors(page);

    const explainChip = selectors.explainChip();
    await explainChip.hover();
    await expect(page.getByTestId("explainability-rationale")).toContainText(
      /Correlation is elevated due to synchronized flows/i,
    );
    await expect(
      page.getByRole("link", { name: /Desk note/i }),
    ).toHaveAttribute("href", "https://example.com/correlation-note");

    await explainChip.focus();
    await expect(explainChip).toBeFocused();
    await expect(page.getByTestId("explainability-rationale")).toBeVisible();

    const btcEthEdge = selectors.influenceEdge("BTC", "ETH");
    await expect(btcEthEdge).toBeVisible();
    await expect(btcEthEdge).toHaveClass(/influence-edge--pulse/);

    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(btcEthEdge).not.toHaveClass(/influence-edge--pulse/);

    const eventCard = selectors.eventCard(
      "Ethereum ETF approved with accelerated timeline",
    );
    await expect(
      eventCard.getByRole("link", { name: /Source: Ethereum ETF approved/i }),
    ).toHaveAttribute("href", "https://example.com/eth-etf");

    const priceSummary = selectors.priceSummary();
    const zscoreSummary = selectors.zscoreSummary();

    await expect(priceSummary).toContainText("$189.32");
    await expect(zscoreSummary).toContainText("-0.40");

    const windowMeasuresBefore = await page.evaluate(
      () => performance.getEntriesByName("dashboard:window-change").length,
    );
    const renderMeasuresBefore = await page.evaluate(
      () => performance.getEntriesByName("dashboard:sentiment:render").length,
    );

    await selectors.sentimentWindow("4h").click();

    await expect(priceSummary).toContainText("$209.88");
    await expect(zscoreSummary).toContainText("1.34");

    await page.waitForFunction(
      (previous) =>
        performance.getEntriesByName("dashboard:window-change").length >
        previous,
      windowMeasuresBefore,
    );
    await page.waitForFunction(
      (previous) =>
        performance.getEntriesByName("dashboard:sentiment:render").length >
        previous,
      renderMeasuresBefore,
    );

    const windowChangeDuration = await page.evaluate(() => {
      const entries = performance.getEntriesByName(
        "dashboard:window-change",
        "measure",
      );
      return entries.at(-1)?.duration ?? Number.POSITIVE_INFINITY;
    });

    const sentimentRenderDuration = await page.evaluate(() => {
      const entries = performance.getEntriesByName(
        "dashboard:sentiment:render",
        "measure",
      );
      return entries.at(-1)?.duration ?? Number.POSITIVE_INFINITY;
    });

    expect(windowChangeDuration).toBeLessThan(900);
    expect(sentimentRenderDuration).toBeLessThan(850);
  });
});
