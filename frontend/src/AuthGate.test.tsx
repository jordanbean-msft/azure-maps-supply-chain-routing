import { InteractionRequiredAuthError } from "@azure/msal-browser";
import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuthGate from "./AuthGate";
import { request } from "./api";
import { GRAPH_SCOPES } from "./useAccountProfile";

const msal = vi.hoisted(() => ({
    initialize: vi.fn(),
    handleRedirectPromise: vi.fn(),
    getAllAccounts: vi.fn(),
    getActiveAccount: vi.fn(),
    setActiveAccount: vi.fn(),
    ssoSilent: vi.fn(),
    acquireTokenSilent: vi.fn(),
    loginRedirect: vi.fn(),
    logoutRedirect: vi.fn(),
    clearCache: vi.fn(),
    configuration: vi.fn(),
}));
vi.mock("@azure/msal-browser", async (importOriginal) => {
    const original =
        await importOriginal<typeof import("@azure/msal-browser")>();
    return {
        ...original,
        PublicClientApplication: class {
            constructor(config: unknown) {
                msal.configuration(config);
            }
            initialize = msal.initialize;
            handleRedirectPromise = msal.handleRedirectPromise;
            getAllAccounts = msal.getAllAccounts;
            getActiveAccount = msal.getActiveAccount;
            setActiveAccount = msal.setActiveAccount;
            ssoSilent = msal.ssoSilent;
            acquireTokenSilent = msal.acquireTokenSilent;
            loginRedirect = msal.loginRedirect;
            logoutRedirect = msal.logoutRedirect;
            clearCache = msal.clearCache;
        },
    };
});

const account = {
    homeAccountId: "user",
    name: "Demo User",
    username: "demo@example.org",
};
const config = {
    enabled: true,
    tenant_id: "11111111-1111-1111-1111-111111111111",
    client_id: "22222222-2222-2222-2222-222222222222",
    scope: "api://22222222-2222-2222-2222-222222222222/access_as_user",
};

function discovery(value: unknown = config) {
    const fetch = vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify(value)));
    vi.stubGlobal("fetch", fetch);
    return fetch;
}

beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal(
        "ResizeObserver",
        class {
            observe() {}
            unobserve() {}
            disconnect() {}
        },
    );
    msal.initialize.mockResolvedValue(undefined);
    msal.handleRedirectPromise.mockResolvedValue(null);
    msal.getAllAccounts.mockReturnValue([]);
    msal.getActiveAccount.mockReturnValue(null);
    msal.ssoSilent.mockRejectedValue(new InteractionRequiredAuthError());
    msal.acquireTokenSilent.mockImplementation(async ({ scopes }) => {
        if (scopes.includes(GRAPH_SCOPES[0]))
            throw new InteractionRequiredAuthError();
        return { accessToken: "test-access-token" };
    });
    msal.loginRedirect.mockRejectedValue(new Error("cancelled"));
    msal.logoutRedirect.mockRejectedValue(new Error("offline"));
    msal.clearCache.mockResolvedValue(undefined);
});

describe("authentication boundary", () => {
    it("restores a cached account on a return visit without another sign-in or cookie request", async () => {
        discovery();
        msal.getAllAccounts.mockReturnValue([account]);
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        expect(msal.setActiveAccount).toHaveBeenCalledWith(account);
        expect(msal.ssoSilent).not.toHaveBeenCalled();
        expect(msal.loginRedirect).not.toHaveBeenCalled();
    });

    it("silently restores the Entra cookie session when the app cache is empty", async () => {
        discovery();
        msal.ssoSilent.mockResolvedValue({ account });
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        expect(msal.ssoSilent).toHaveBeenCalledExactlyOnceWith({
            scopes: [config.scope],
        });
        expect(msal.setActiveAccount).toHaveBeenCalledWith(account);
        expect(msal.loginRedirect).not.toHaveBeenCalled();
    });

    it.each([
        new InteractionRequiredAuthError(),
        new Error("Third-party cookies blocked"),
    ])(
        "falls back to explicit sign-in without redirect loops when SSO fails: %s",
        async (error) => {
            discovery();
            msal.ssoSilent.mockRejectedValue(error);
            render(
                <AuthGate>
                    <div>Workspace</div>
                </AuthGate>,
            );
            await screen.findByRole("button", { name: "Sign in" });
            expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
            expect(msal.ssoSilent).toHaveBeenCalledTimes(1);
            expect(msal.loginRedirect).not.toHaveBeenCalled();
            await expect(request("/config")).rejects.toThrow(
                "Sign in to continue",
            );
        },
    );

    it("requires account selection when several cached users have no active account", async () => {
        discovery();
        msal.getAllAccounts.mockReturnValue([
            account,
            {
                ...account,
                homeAccountId: "another-user",
                username: "other@example.org",
            },
        ]);
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByRole("button", { name: "Sign in" });
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        expect(msal.ssoSilent).not.toHaveBeenCalled();
        expect(msal.setActiveAccount).not.toHaveBeenCalled();
    });

    it("ignores a late silent restore after unmount", async () => {
        const fetch = discovery();
        let restore: ((value: { account: typeof account }) => void) | undefined;
        msal.ssoSilent.mockImplementation(
            () =>
                new Promise((resolve) => {
                    restore = resolve;
                }),
        );
        const view = render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await waitFor(() => expect(msal.ssoSilent).toHaveBeenCalledTimes(1));
        view.unmount();
        await act(async () => restore?.({ account }));
        expect(msal.setActiveAccount).not.toHaveBeenCalled();
        await expect(request("/config")).rejects.toThrow("Sign-in is required");
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it("immediately locks this tab when another tab signs out", async () => {
        discovery();
        msal.getAllAccounts.mockReturnValue([account]);
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        act(() => {
            localStorage.setItem("routing.signed-out", "true");
            window.dispatchEvent(
                new StorageEvent("storage", {
                    key: "routing.signed-out",
                    newValue: "true",
                }),
            );
        });
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        await screen.findByRole("button", { name: "Sign in" });
        await expect(request("/config")).rejects.toThrow("Sign in to continue");
        expect(msal.ssoSilent).not.toHaveBeenCalled();
    });

    it("does not mount the workspace or access protected APIs before sign-in", async () => {
        const fetch = discovery();
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        const login = await screen.findByRole("button", {
            name: "Sign in",
        });
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        expect(fetch).toHaveBeenCalledTimes(1);
        expect(fetch.mock.calls[0][0]).toBe("/api/auth/config");
        expect(msal.configuration).toHaveBeenCalledWith(
            expect.objectContaining({
                auth: expect.objectContaining({
                    authority: `https://login.microsoftonline.com/${config.tenant_id}`,
                    redirectUri: `${location.origin}/`,
                    postLogoutRedirectUri: `${location.origin}/`,
                }),
                cache: { cacheLocation: "localStorage" },
            }),
        );
        fireEvent.click(login);
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Sign-in could not start",
        );
        expect(msal.loginRedirect).toHaveBeenCalledTimes(1);
        expect(msal.loginRedirect).toHaveBeenCalledWith({
            scopes: [config.scope],
            extraScopesToConsent: GRAPH_SCOPES,
        });
        fireEvent.click(login);
        await waitFor(() =>
            expect(msal.loginRedirect).toHaveBeenCalledTimes(2),
        );
    });

    it("fails closed on discovery errors and permits an explicit retry into disabled demo mode", async () => {
        const fetch = vi.fn().mockRejectedValue(new Error("offline"));
        vi.stubGlobal("fetch", fetch);
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Sign-in setup failed",
        );
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        fetch.mockResolvedValue(
            new Response(JSON.stringify({ enabled: false })),
        );
        fireEvent.click(
            screen.getByRole("button", { name: "Retry sign-in setup" }),
        );
        expect(await screen.findByText("Workspace")).toBeInTheDocument();
        expect(screen.getByText("Demo workspace")).toBeInTheDocument();
        expect(screen.getByText("Supply chain routing")).toBeInTheDocument();
        expect(msal.initialize).not.toHaveBeenCalled();
    });

    it.each([
        { enabled: "false" },
        { ...config, tenant_id: "common" },
        { ...config, scope: "access_as_user" },
    ])(
        "rejects malformed or non-single-tenant discovery: %j",
        async (value) => {
            discovery(value);
            render(
                <AuthGate>
                    <div>Workspace</div>
                </AuthGate>,
            );
            await screen.findByRole("alert");
            expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
            expect(msal.initialize).not.toHaveBeenCalled();
        },
    );

    it("restores redirect sign-in and obtains an API token silently for each request", async () => {
        const fetch = discovery();
        localStorage.setItem("routing.signed-out", "true");
        msal.handleRedirectPromise.mockResolvedValue({ account });
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        expect(localStorage.getItem("routing.signed-out")).toBeNull();
        fetch.mockImplementation(async () => new Response("{}"));
        await request("/config");
        await request("/maps/token");
        expect(await screen.findByText("Howdy Demo User!")).toBeInTheDocument();
        expect(msal.acquireTokenSilent).toHaveBeenCalledTimes(3);
        expect(
            msal.acquireTokenSilent.mock.calls.map(([value]) => value.scopes),
        ).toEqual([GRAPH_SCOPES, [config.scope], [config.scope]]);
        expect(msal.acquireTokenSilent).toHaveBeenCalledWith({
            account,
            scopes: [config.scope],
        });
        expect(fetch).toHaveBeenLastCalledWith(
            "/api/maps/token",
            expect.objectContaining({
                headers: expect.objectContaining({
                    authorization: "Bearer test-access-token",
                }),
            }),
        );
    });

    it("unmounts expired sessions without an automatic redirect or repeated silent-token attempts", async () => {
        const fetch = discovery();
        msal.getAllAccounts.mockReturnValue([account]);
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        msal.acquireTokenSilent.mockRejectedValue(
            new InteractionRequiredAuthError(),
        );
        await act(async () => {
            await expect(request("/config")).rejects.toThrow(
                "Unable to authorize",
            );
        });
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Sign in again",
        );
        await expect(request("/config")).rejects.toThrow("Sign in again");
        expect(msal.acquireTokenSilent).toHaveBeenCalledTimes(2);
        expect(msal.loginRedirect).not.toHaveBeenCalled();
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it("clears the active scenario and unmounts immediately even if logout fails", async () => {
        discovery();
        msal.getAllAccounts.mockReturnValue([account]);
        localStorage.setItem("routing.active", "old scenario");
        const view = render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByText("Workspace");
        fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Sign-out could not finish",
        );
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        expect(localStorage.getItem("routing.active")).toBeNull();
        expect(msal.logoutRedirect).toHaveBeenCalledWith({ account });
        expect(msal.clearCache).toHaveBeenCalledWith({ account });
        await expect(request("/config")).rejects.toThrow("Sign in to continue");
        expect(localStorage.getItem("routing.signed-out")).toBe("true");
        view.unmount();
        discovery();
        render(
            <AuthGate>
                <div>Workspace</div>
            </AuthGate>,
        );
        await screen.findByRole("button", { name: "Sign in" });
        expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
        expect(msal.ssoSilent).not.toHaveBeenCalled();
    });
});
