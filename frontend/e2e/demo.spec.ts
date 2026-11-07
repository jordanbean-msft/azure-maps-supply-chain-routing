import { expect, test } from "@playwright/test";

test("seed → edit → optimize → close a route → compare persisted results", async ({
    page,
}) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/");
    await expect(page.getByText(/SIMULATION MODE/)).toBeVisible();
    await page.getByRole("button", { name: /Load Houston sample/ }).click();
    await page.getByText("Refresh settings", { exact: true }).click();
    await page.getByLabel("Pause auto-refresh").check();
    const scenarioName = `Browser scenario ${Date.now()}`;
    await page.getByLabel("Scenario name", { exact: true }).fill(scenarioName);
    await page
        .getByRole("button", { name: "Save scenario", exact: true })
        .click();
    await page
        .getByRole("button", { name: "Calculate shipment plan", exact: true })
        .click();
    await expect(page.getByText(/^COMPLETED ·/)).toBeVisible();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(
        page.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeVisible();
    await expect(page.locator("#shipment-plan-explanation")).toContainText(
        "without exceeding factory capacities",
    );
    const schematic = page.getByRole("group", { name: /Coordinate schematic/ });
    const recommendedRows = page
        .getByRole("table")
        .locator("tr.recommended-row");
    const recommendedCount = await recommendedRows.count();
    expect(recommendedCount).toBeGreaterThan(1);
    await expect(
        schematic.getByRole("button", { name: /^Select route / }),
    ).toHaveCount(recommendedCount);
    await expect(page.getByText(/^INSPECTED/)).toHaveCount(0);
    const alternatives = page.getByRole("checkbox", {
        name: /Show unused alternatives/,
    });
    await expect(alternatives).not.toBeChecked();
    await alternatives.check();
    await expect(
        schematic.getByRole("button", { name: /^Select route / }),
    ).toHaveCount(await page.getByRole("table").locator("tbody tr").count());
    await alternatives.uncheck();
    const unusedRoute = page
        .getByRole("table")
        .locator("tr:not(.recommended-row)")
        .last();
    await unusedRoute.getByRole("button").click();
    await expect(page.getByText(/^INSPECTED/)).toContainText(
        "Unused alternative · no shipments",
    );
    await expect(
        schematic.getByRole("button", { name: /^Select route / }),
    ).toHaveCount(recommendedCount + 1);
    const direction = page.getByRole("status", {
        name: "Selected route direction",
    });
    await expect(direction).toContainText("START · Supplier:");
    await expect(direction).toContainText("END · Factory:");
    await expect(direction).toContainText("not live vehicle tracking");
    const follower = schematic.locator(".route-motion-follower");
    await expect(follower).toHaveCount(1);
    const travel = await follower.evaluate(async (element) => {
        const animation = element.getAnimations()[0];
        animation.pause();
        const line = element.parentElement!.querySelector("polyline")!;
        const first = line.points.getItem(0);
        const last = line.points.getItem(line.points.numberOfItems - 1);
        const matrix = line.getScreenCTM()!;
        const start = new DOMPoint(first.x, first.y).matrixTransform(matrix);
        const end = new DOMPoint(last.x, last.y).matrixTransform(matrix);
        const distances: number[] = [];
        for (const [time, target] of [
            [0, start],
            [5999, end],
        ] as const) {
            animation.currentTime = time;
            await new Promise(requestAnimationFrame);
            const box = element.getBoundingClientRect();
            distances.push(
                Math.hypot(
                    box.x + box.width / 2 - target.x,
                    box.y + box.height / 2 - target.y,
                ),
            );
        }
        animation.play();
        return distances;
    });
    travel.forEach((distance) => expect(distance).toBeLessThan(12));
    const animate = page.getByRole("checkbox", {
        name: "Animate selected route",
    });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(animate).toBeDisabled();
    await expect(animate).not.toBeChecked();
    await expect(follower).not.toHaveClass(/is-moving/);
    expect(
        await follower.evaluate((element) => element.getAnimations().length),
    ).toBe(0);
    await expect(direction).toContainText(
        "Static arrow shows travel direction",
    );
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await expect(animate).toBeChecked();
    await animate.uncheck();
    await expect(follower).not.toHaveClass(/is-moving/);
    await animate.check();
    await expect(page.locator(".map-target-status")).toHaveCount(0);
    await page.screenshot({
        path: test.info().outputPath("shipment-plan-desktop.png"),
        fullPage: true,
    });
    const route = page.getByRole("table").locator("tbody tr").first();
    const routeId = await route.getAttribute("data-route-id");
    expect(routeId).toBeTruthy();
    await route.getByRole("button").click();
    await page.getByRole("tab", { name: "Disruptions" }).click();
    await page
        .getByRole("combobox", { name: "Route to close", exact: true })
        .selectOption(routeId!);
    await expect(
        page.getByRole("status", { name: "Disruption target preview" }),
    ).toContainText("This candidate is outlined on the map");
    expect(
        await page
            .getByRole("complementary", { name: "Planning controls" })
            .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
    await page.screenshot({
        path: test.info().outputPath("fluent-desktop.png"),
        fullPage: true,
    });
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
        .getByRole("button", { name: "Calculate shipment plan", exact: true })
        .click();
    await expect(page.getByText(/^COMPLETED ·/)).toBeVisible();
    await expect(
        page.getByRole("table").locator(`[data-route-id="${routeId}"]`),
    ).toHaveCount(0);
    await expect(page.getByText(/Previous run total/)).toBeVisible();
    const baytownRoute = page
        .getByRole("table")
        .locator("tbody tr")
        .filter({ hasText: "Baytown factory" })
        .first();
    const baytownId = await baytownRoute.getAttribute("data-route-id");
    const previousEta = Number.parseFloat(
        await baytownRoute.locator("td").nth(2).innerText(),
    );
    await page.getByLabel("Disruption kind").selectOption("facility_delay");
    await page
        .getByRole("button", { name: "Select facility Baytown factory" })
        .click();
    await expect(page.getByLabel("Facility to delay")).toHaveValue("baytown");
    await expect(page.locator(".map-target-status")).toContainText(
        "TARGET PREVIEW · Baytown factory",
    );
    await page
        .getByLabel("Disruption name", { exact: true })
        .fill("Loading delay");
    await page.getByLabel("Delay (minutes)", { exact: true }).fill("25");
    await page.getByRole("button", { name: "Apply disruption" }).click();
    await expect(
        page.getByRole("button", { name: "Remove disruption Loading delay" }),
    ).toBeEnabled();
    await page
        .getByRole("button", { name: "Calculate shipment plan", exact: true })
        .click();
    await expect
        .poll(async () =>
            Number.parseFloat(
                await page
                    .locator(`tr[data-route-id="${baytownId}"] td`)
                    .nth(2)
                    .innerText(),
            ),
        )
        .toBeCloseTo(previousEta + 25, 1);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(
        page.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeVisible();
    expect(
        await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
    ).toBe(true);
    await page.screenshot({
        path: test.info().outputPath("fluent-mobile.png"),
        fullPage: true,
    });
    await page.reload();
    await expect(page.getByLabel("Scenario name", { exact: true })).toHaveValue(
        scenarioName,
    );
    await expect(page.getByRole("table")).toBeVisible();
    expect(errors).toEqual([]);
});

test("profile photo and Howdy greeting align on desktop and narrow screens", async ({
    page,
}) => {
    await page.route("**/api/auth/config", (route) =>
        route.fulfill({
            json: {
                enabled: true,
                tenant_id: "11111111-1111-4111-8111-111111111111",
                client_id: "22222222-2222-4222-8222-222222222222",
                scope: "api://browser-demo/access_as_user",
            },
        }),
    );
    await page.route("**/@azure_msal-browser.js*", (route) =>
        route.fulfill({
            contentType: "application/javascript",
            body: `
                export class InteractionRequiredAuthError extends Error {}
                export class PublicClientApplication {
                    async initialize() {}
                    async handleRedirectPromise() { return null; }
                    getAllAccounts() {
                        return [{ homeAccountId: "browser-demo", name: "Fallback name" }];
                    }
                    getActiveAccount() { return null; }
                    setActiveAccount() {}
                    async acquireTokenSilent({scopes}) {
                        return { accessToken: scopes[0].includes("graph.microsoft.com") ? "graph-demo" : "api-demo" };
                    }
                }
            `,
        }),
    );
    await page.route("https://graph.microsoft.com/**", async (route) => {
        const headers = {
            "access-control-allow-origin": "*",
            "access-control-allow-headers": "Authorization",
            "access-control-allow-methods": "GET",
        };
        if (route.request().method() === "OPTIONS") {
            await route.fulfill({ status: 204, headers });
            return;
        }
        expect(route.request().headers().authorization).toBe(
            "Bearer graph-demo",
        );
        if (route.request().url().includes("/photo/"))
            await route.fulfill({
                headers,
                contentType: "image/svg+xml",
                body: '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" fill="#0f6cbd"/></svg>',
            });
        else
            await route.fulfill({
                headers,
                json: {
                    givenName: "Alex",
                    surname: "Morgan",
                    displayName: "Morgan, Alex",
                },
            });
    });
    await page.goto("/");
    const greeting = page.getByText("Howdy Alex Morgan!", { exact: true });
    await expect(greeting).toBeVisible();
    const photo = page.locator(".app-header .fui-Avatar img");
    await expect(photo).toHaveAttribute("src", /^blob:/);
    await expect(photo).toBeVisible();
    const avatarBox = await photo.boundingBox();
    const greetingBox = await greeting.boundingBox();
    expect(
        Math.abs(
            avatarBox!.y +
                avatarBox!.height / 2 -
                greetingBox!.y -
                greetingBox!.height / 2,
        ),
    ).toBeLessThan(4);
    await page.screenshot({
        path: test.info().outputPath("fluent-profile-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(greeting).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    expect(
        await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
    ).toBe(true);
    await page.screenshot({
        path: test.info().outputPath("fluent-profile-mobile.png"),
    });
});
