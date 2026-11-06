import { expect, test } from "@playwright/test";

test("seed → edit → optimize → close a route → compare persisted results", async ({
    page,
}) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/");
    await expect(page.getByText(/SIMULATION MODE/)).toBeVisible();
    await page.getByRole("button", { name: /Load seed scenario/ }).click();
    await page.getByLabel("Pause auto-refresh").check();
    const scenarioName = `Browser scenario ${Date.now()}`;
    await page.getByLabel("Scenario name", { exact: true }).fill(scenarioName);
    await page
        .getByRole("button", { name: "Save scenario", exact: true })
        .click();
    await page
        .getByRole("button", { name: "Optimize network", exact: true })
        .click();
    await expect(page.getByText(/^COMPLETED ·/)).toBeVisible();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(
        page.getByRole("img", { name: /Coordinate schematic/ }),
    ).toBeVisible();
    const route = page.getByRole("table").locator("tbody tr").first();
    const routeId = (await route.locator("small").innerText()).trim();
    await route.getByRole("button").click();
    await page.getByLabel("Target", { exact: true }).selectOption(routeId);
    await page
        .getByLabel("Disruption name", { exact: true })
        .fill("Browser road closure");
    await page.getByRole("button", { name: "Apply disruption" }).click();
    await expect(
        page.getByRole("button", {
            name: "Remove disruption Browser road closure",
        }),
    ).toBeEnabled();
    await page
        .getByRole("button", { name: "Optimize network", exact: true })
        .click();
    await expect(page.getByText(/^COMPLETED ·/)).toBeVisible();
    await expect(
        page.getByRole("table").locator("small").filter({ hasText: routeId }),
    ).toHaveCount(0);
    await expect(page.getByText(/Previous run total/)).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Scenario name", { exact: true })).toHaveValue(
        scenarioName,
    );
    await expect(page.getByRole("table")).toBeVisible();
    expect(errors).toEqual([]);
});
