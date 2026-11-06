import { expect, test } from "@playwright/test";
import { config, run, scenario } from "../src/test-fixtures";

test("panel text, controls and warning bullets stay inside their containers", async ({
    page,
}) => {
    const longName = "HoustonDistributionAndManufacturing".repeat(3);
    const network = {
        ...scenario,
        name: longName,
        locations: scenario.locations.map((location) => ({
            ...location,
            name: `${location.name} ${longName}`,
        })),
        disruptions: [
            {
                id: "delay",
                name: longName,
                kind: "facility_delay",
                location_id: "factory-1",
                route_id: null,
                delay_minutes: 25,
                severity: 0,
                fuel_price_per_liter: null,
                enabled: true,
            },
        ],
    };
    await page.addInitScript(() =>
        localStorage.setItem(
            "routing.active",
            JSON.stringify({
                scenario_id: "scenario-1",
                run_id: "run-1",
                run_etag: '"layout"',
            }),
        ),
    );
    await page.route("**/api/**", (route) => {
        const path = new URL(route.request().url()).pathname;
        if (path === "/api/auth/config")
            return route.fulfill({ json: { enabled: false } });
        if (path === "/api/config") return route.fulfill({ json: config });
        if (path.endsWith("/events"))
            return route.fulfill({
                contentType: "text/event-stream",
                body: "",
            });
        if (path.endsWith("/runs/run-1"))
            return route.fulfill({
                json: {
                    ...run,
                    warnings: [
                        "Weather coverage is incomplete. Estimated delays may not reflect every section of this route.",
                        `Upstream reference: ${"WeatherCoverageUnavailable".repeat(6)}`,
                    ],
                },
            });
        if (path === "/api/scenarios/scenario-1")
            return route.fulfill({
                headers: { ETag: '"layout"' },
                json: network,
            });
        return route.abort();
    });
    await page.goto("/");
    await expect(page.locator(".notice li")).toHaveCount(2);
    await page.getByRole("table").getByRole("button").first().click();

    for (const width of [1440, 1024, 768, 701, 390, 320]) {
        await page.setViewportSize({ width, height: 900 });
        for (const tab of ["Network", "Disruptions"]) {
            await page.getByRole("tab", { name: tab, exact: true }).click();
            if (tab === "Disruptions") {
                await page
                    .getByLabel("Disruption kind")
                    .selectOption("weather");
            }
            const overflow = await page.evaluate(() => {
                const selectors = [
                    ".scenario-heading",
                    ".panel-heading",
                    ".section-heading",
                    ".result-summary > div",
                    ".cost-detail > div",
                    ".cost-breakdown > div",
                    ".fui-Badge",
                    ".notice",
                    ".location-card legend",
                    ".target-preview",
                    ".disruption-list li",
                    ".map-legend > span",
                    ".map-route-controls",
                    ".schematic",
                ];
                const failures: string[] = [];
                for (const element of document.querySelectorAll(
                    selectors.join(","),
                )) {
                    const box = element.getBoundingClientRect();
                    if (!box.width || !box.height) continue;
                    const walker = document.createTreeWalker(
                        element,
                        NodeFilter.SHOW_TEXT,
                    );
                    while (walker.nextNode()) {
                        const node = walker.currentNode;
                        if (!node.textContent?.trim()) continue;
                        const range = document.createRange();
                        range.selectNodeContents(node);
                        for (const rect of range.getClientRects()) {
                            if (
                                rect.width &&
                                (rect.left < box.left - 1 ||
                                    rect.right > box.right + 1 ||
                                    rect.top < box.top - 1 ||
                                    rect.bottom > box.bottom + 1)
                            )
                                failures.push(
                                    `${element.className}: ${node.textContent.trim()}`,
                                );
                        }
                    }
                }
                if (document.documentElement.scrollWidth > window.innerWidth)
                    failures.push("Page overflows horizontally");
                return failures;
            });
            expect(overflow, `${width}px, ${tab}`).toEqual([]);
        }
        const bulletGutter = await page.locator(".notice").evaluate((list) => {
            const item = list.querySelector("li")!;
            return (
                item.getBoundingClientRect().left -
                list.getBoundingClientRect().left
            );
        });
        expect(
            bulletGutter,
            `Warning bullet gutter at ${width}px`,
        ).toBeGreaterThanOrEqual(20);
        if (width === 768 || width === 320)
            await page.screenshot({
                path: test.info().outputPath(`text-containment-${width}.png`),
                fullPage: true,
            });
    }
});
