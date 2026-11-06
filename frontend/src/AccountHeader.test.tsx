import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AccountHeader from "./AccountHeader";
import { GRAPH_SCOPES } from "./useAccountProfile";

const account = {
    homeAccountId: "test-account",
    environment: "login.microsoftonline.com",
    tenantId: "test-tenant",
    localAccountId: "test-account",
    username: "test@example.org",
    name: "Fallback Display",
    idTokenClaims: { given_name: "Fallback", family_name: "Person" },
} as AccountInfo;
const silent = vi.fn();
const popup = vi.fn();
const session = {
    account,
    client: {
        acquireTokenSilent: silent,
        acquireTokenPopup: popup,
    } as unknown as PublicClientApplication,
};
const createObjectURL = vi.fn();
const revokeObjectURL = vi.fn();

function graph(photoStatus = 200) {
    const fetch = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/photo/"))
            return new Response(new Blob(["photo"], { type: "image/jpeg" }), {
                status: photoStatus,
                headers: { "Content-Type": "image/jpeg" },
            });
        return new Response(
            JSON.stringify({
                givenName: "First",
                surname: "Last",
                displayName: "Not the greeting",
            }),
        );
    });
    vi.stubGlobal("fetch", fetch);
    return fetch;
}

beforeEach(() => {
    vi.resetAllMocks();
    silent.mockResolvedValue({ accessToken: "graph-only-token" });
    popup.mockResolvedValue({ accessToken: "consented-graph-token" });
    createObjectURL.mockReturnValue("blob:profile-photo");
    vi.stubGlobal(
        "URL",
        class extends URL {
            static createObjectURL = createObjectURL;
            static revokeObjectURL = revokeObjectURL;
        },
    );
});

describe("account header", () => {
    it("uses both Graph names, the real photo and a separate Graph-only token", async () => {
        const fetch = graph();
        const { unmount } = render(<AccountHeader session={session} />);
        expect(
            await screen.findByText("Howdy First Last!"),
        ).toBeInTheDocument();
        await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
        expect(
            screen.getByRole("img", { name: "Profile" }).querySelector("img"),
        ).toHaveAttribute("src", "blob:profile-photo");
        expect(silent).toHaveBeenCalledWith({
            account,
            scopes: GRAPH_SCOPES,
            storeInCache: {
                accessToken: false,
                idToken: false,
                refreshToken: false,
            },
        });
        expect(fetch.mock.calls.map(([url]) => url)).toEqual([
            "https://graph.microsoft.com/v1.0/me?$select=givenName,surname,displayName",
            "https://graph.microsoft.com/v1.0/me/photo/$value",
        ]);
        for (const [, options] of fetch.mock.calls) {
            expect(options.headers.Authorization).toBe(
                "Bearer graph-only-token",
            );
            expect(options.cache).toBe("no-store");
        }
        unmount();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:profile-photo");
    });

    it("treats a photo 404 as normal and retains Fluent initials", async () => {
        graph(404);
        render(<AccountHeader session={session} />);
        await screen.findByText("Howdy First Last!");
        await waitFor(() => expect(screen.getByText("FL")).toBeInTheDocument());
        expect(createObjectURL).not.toHaveBeenCalled();
        expect(
            screen.queryByRole("button", { name: "Load profile photo" }),
        ).not.toBeInTheDocument();
        expect(popup).not.toHaveBeenCalled();
    });

    it("keeps ID-token names after denied consent and interacts only on explicit request", async () => {
        const fetch = graph();
        silent.mockRejectedValue(new Error("consent required"));
        popup.mockRejectedValueOnce(new Error("consent denied"));
        render(<AccountHeader session={session} />);
        expect(
            await screen.findByText("Howdy Fallback Person!"),
        ).toBeInTheDocument();
        const load = await screen.findByRole("button", {
            name: "Load profile photo",
        });
        expect(fetch).not.toHaveBeenCalled();
        expect(popup).not.toHaveBeenCalled();
        fireEvent.click(load);
        await waitFor(() => expect(load).not.toBeDisabled());
        expect(popup).toHaveBeenCalledWith({
            account,
            scopes: GRAPH_SCOPES,
            storeInCache: {
                accessToken: false,
                idToken: false,
                refreshToken: false,
            },
        });
        expect(screen.getByText("Howdy Fallback Person!")).toBeInTheDocument();
        fireEvent.click(load);
        await screen.findByText("Howdy First Last!");
    });

    it("keeps fallback names and offers retry on Graph network errors", async () => {
        vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
        render(<AccountHeader session={session} />);
        await screen.findByRole("button", { name: "Load profile photo" });
        expect(screen.getByText("Howdy Fallback Person!")).toBeInTheDocument();
        expect(popup).not.toHaveBeenCalled();
    });

    it("aborts pending requests and ignores a late photo after logout unmount", async () => {
        const pending: ((value: Response) => void)[] = [];
        const fetch = graph();
        fetch.mockImplementation(
            () =>
                new Promise<Response>((resolve) => {
                    pending.push(resolve);
                }),
        );
        const { rerender } = render(<AccountHeader session={session} />);
        await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
        const signal = fetch.mock.calls[0][1].signal as AbortSignal;
        rerender(<AccountHeader />);
        expect(signal.aborted).toBe(true);
        await act(async () => {
            pending[0](
                new Response(
                    JSON.stringify({ givenName: "Stale", surname: "Name" }),
                ),
            );
            pending[1](
                new Response(new Blob(["photo"], { type: "image/jpeg" })),
            );
        });
        expect(createObjectURL).not.toHaveBeenCalled();
        expect(
            screen.queryByText("Howdy Fallback Person!"),
        ).not.toBeInTheDocument();
    });

    it("does not fetch profiles or fabricate a person in demo mode", () => {
        const fetch = vi.fn();
        vi.stubGlobal("fetch", fetch);
        render(<AccountHeader demo />);
        expect(screen.getByText("Demo workspace")).toBeInTheDocument();
        expect(screen.getByText("Supply chain routing")).toBeInTheDocument();
        expect(fetch).not.toHaveBeenCalled();
        expect(silent).not.toHaveBeenCalled();
    });

    it("falls back to the ID-token name without using an email as a name", async () => {
        silent.mockRejectedValue(new Error("consent required"));
        render(
            <AccountHeader
                session={{
                    ...session,
                    account: {
                        ...account,
                        name: undefined,
                        idTokenClaims: { name: "Token Name" },
                    },
                }}
            />,
        );
        await screen.findByRole("button", { name: "Load profile photo" });
        expect(screen.getByText("Howdy Token Name!")).toBeInTheDocument();
        expect(screen.queryByText(/test@example.org/)).not.toBeInTheDocument();
    });

    it("does not fetch when token acquisition finishes after logout", async () => {
        let finish: (value: { accessToken: string }) => void = () => {};
        silent.mockImplementation(
            () =>
                new Promise((resolve) => {
                    finish = resolve;
                }),
        );
        const fetch = graph();
        const { unmount } = render(<AccountHeader session={session} />);
        unmount();
        await act(async () => finish({ accessToken: "late-token" }));
        expect(fetch).not.toHaveBeenCalled();
        expect(createObjectURL).not.toHaveBeenCalled();
    });

    it("rejects a non-image photo response without blocking the account", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
        render(<AccountHeader session={session} />);
        await screen.findByRole("button", { name: "Load profile photo" });
        expect(screen.getByText("Howdy Fallback Person!")).toBeInTheDocument();
        expect(createObjectURL).not.toHaveBeenCalled();
    });
});
