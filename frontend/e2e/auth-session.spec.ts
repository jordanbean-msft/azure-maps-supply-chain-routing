import { expect, test, type BrowserContext } from "@playwright/test";

async function mockMicrosoftSession(context: BrowserContext) {
    const calls = { silent: 0 };
    const account = {
        homeAccountId: "session-demo",
        name: "Demo User",
        username: "demo@example.org",
    };
    await context.route("**/api/auth/config", (route) =>
        route.fulfill({
            json: {
                enabled: true,
                tenant_id: "11111111-1111-4111-8111-111111111111",
                client_id: "22222222-2222-4222-8222-222222222222",
                scope: "api://browser-demo/access_as_user",
            },
        }),
    );
    await context.route("**/__test/sso", (route) => {
        calls.silent += 1;
        return route
            .request()
            .headers()
            .cookie?.includes("test-entra-session=active")
            ? route.fulfill({ json: account })
            : route.fulfill({ status: 401, json: { error: "login_required" } });
    });
    await context.route("**/@azure_msal-browser.js*", (route) =>
        route.fulfill({
            contentType: "application/javascript",
            body: `
                export class InteractionRequiredAuthError extends Error {}
                export class PublicClientApplication {
                    constructor(config) {
                        this.storage = config.cache.cacheLocation === "localStorage"
                            ? localStorage : sessionStorage;
                    }
                    async initialize() {}
                    async handleRedirectPromise() {
                        if (!sessionStorage.getItem("test.redirect")) return null;
                        sessionStorage.removeItem("test.redirect");
                        return { account: this.getAllAccounts()[0] };
                    }
                    getAllAccounts() {
                        const value = this.storage.getItem("test.msal.account");
                        return value ? [JSON.parse(value)] : [];
                    }
                    getActiveAccount() { return null; }
                    setActiveAccount() {}
                    async ssoSilent() {
                        const response = await fetch("/__test/sso");
                        if (!response.ok) throw new InteractionRequiredAuthError();
                        const account = await response.json();
                        this.storage.setItem("test.msal.account", JSON.stringify(account));
                        return { account };
                    }
                    async acquireTokenSilent({scopes}) {
                        if (scopes[0].includes("graph.microsoft.com"))
                            throw new InteractionRequiredAuthError();
                        return { accessToken: "api-demo" };
                    }
                    async loginRedirect() {
                        this.storage.setItem("test.msal.account", ${JSON.stringify(JSON.stringify(account))});
                        document.cookie = "test-entra-session=active; Path=/; SameSite=Lax";
                        sessionStorage.setItem("test.redirect", "true");
                        location.assign("/");
                    }
                    async clearCache() {
                        this.storage.removeItem("test.msal.account");
                    }
                    async logoutRedirect() {
                        document.cookie = "test-entra-session=; Max-Age=0; Path=/; SameSite=Lax";
                        location.assign("/");
                    }
                }
            `,
        }),
    );
    return calls;
}

test("return visits reuse the cache or SSO cookie while explicit sign-out locks every tab", async ({
    page,
    context,
    browser,
    baseURL,
}) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const calls = await mockMicrosoftSession(context);
    await page.goto("/");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
        page.getByText("Howdy Demo User!", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
        page.getByText("Howdy Demo User!", { exact: true }),
    ).toBeVisible();
    const second = await context.newPage();
    await second.goto("/");
    await expect(
        second.getByText("Howdy Demo User!", { exact: true }),
    ).toBeVisible();
    expect(calls.silent).toBe(1);

    await page.evaluate(() => {
        const iframe = document.createElement("iframe");
        iframe.name = "silent-callback-check";
        iframe.src = "/";
        document.body.append(iframe);
    });
    await expect
        .poll(() => !!page.frame({ name: "silent-callback-check" }))
        .toBe(true);
    const callback = page.frame({ name: "silent-callback-check" })!;
    await callback.waitForLoadState("networkidle");
    await expect(callback.locator("#root")).toBeEmpty();
    expect(calls.silent).toBe(1);

    const state = await context.storageState();
    const cookieOnly = await browser.newContext({
        baseURL,
        storageState: { cookies: state.cookies, origins: [] },
    });
    try {
        const restoredCalls = await mockMicrosoftSession(cookieOnly);
        const restored = await cookieOnly.newPage();
        await restored.goto("/");
        await expect(
            restored.getByText("Howdy Demo User!", { exact: true }),
        ).toBeVisible();
        expect(restoredCalls.silent).toBe(1);
        await expect(
            restored.getByRole("button", { name: "Sign in", exact: true }),
        ).toHaveCount(0);
    } finally {
        await cookieOnly.close();
    }

    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
        page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
    await expect(
        second.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
    await expect(
        second.getByText("Howdy Demo User!", { exact: true }),
    ).toHaveCount(0);
    await page.reload();
    await expect(
        page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
    expect(calls.silent).toBe(1);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
        page.getByText("Howdy Demo User!", { exact: true }),
    ).toBeVisible();
    expect(errors).toEqual([]);
});
