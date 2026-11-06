import { describe, expect, it, vi } from "vitest";
import { apiFetch, request } from "./api";
import { setTokenProvider } from "./auth";

describe("authorized requests", () => {
    it("preserves caller headers and concurrency tokens, but cannot override bearer auth", async () => {
        const fetch = vi
            .fn()
            .mockResolvedValue(
                new Response('{"ok":true}', { headers: { ETag: '"v2"' } }),
            );
        vi.stubGlobal("fetch", fetch);
        setTokenProvider(async () => "fresh-token");
        const response = await request("/scenarios/one", {
            method: "PUT",
            body: "{}",
            headers: new Headers({
                "If-Match": '"v1"',
                Authorization: "wrong",
            }),
        });
        const headers = new Headers(fetch.mock.calls[0][1].headers);
        expect(headers.get("Authorization")).toBe("Bearer fresh-token");
        expect(headers.get("If-Match")).toBe('"v1"');
        expect(headers.get("Content-Type")).toBe("application/json");
        expect(response.etag).toBe('"v2"');
        expect(fetch.mock.calls[0][0]).toBe("/api/scenarios/one");
    });

    it("never fetches when token acquisition fails or a pending token crosses logout", async () => {
        const fetch = vi.fn();
        vi.stubGlobal("fetch", fetch);
        setTokenProvider(async () => {
            throw new Error("expired");
        });
        await expect(request("/config")).rejects.toThrow("expired");
        let resolve!: (token: string) => void;
        setTokenProvider(
            () =>
                new Promise((done) => {
                    resolve = done;
                }),
        );
        const pending = apiFetch("/config");
        setTokenProvider(null);
        resolve("old-token");
        await expect(pending).rejects.toThrow("session changed");
        expect(fetch).not.toHaveBeenCalled();
    });

    it("supports explicitly disabled auth without an Authorization header", async () => {
        const fetch = vi.fn().mockResolvedValue(new Response("{}"));
        vi.stubGlobal("fetch", fetch);
        setTokenProvider(null);
        await request("/config");
        expect(
            new Headers(fetch.mock.calls[0][1].headers).has("Authorization"),
        ).toBe(false);
    });
});
