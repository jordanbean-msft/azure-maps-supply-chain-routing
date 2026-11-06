import { describe, expect, it, vi } from "vitest";
import { setTokenProvider } from "./auth";
import { consumeEvents, type StreamEvent } from "./eventStream";

describe("authenticated fetch SSE", () => {
    it.each([1, 4096])(
        "parses UTF-8, CRLF and multiline events in chunks of %s bytes without URL credentials",
        async (chunkSize) => {
            const text =
                ": heartbeat\r\nid: 12\r\nevent: progress\r\ndata: café 🚚\r\ndata: second line\r\n\r\nevent: progress\ndata: next\n\nid: 13\rdata: last\r\rdata: incomplete";
            const bytes = new TextEncoder().encode(text);
            const cancel = vi.fn();
            const body = new ReadableStream<Uint8Array>({
                start(controller) {
                    for (
                        let offset = 0;
                        offset < bytes.length;
                        offset += chunkSize
                    )
                        controller.enqueue(
                            bytes.slice(offset, offset + chunkSize),
                        );
                    controller.close();
                },
                cancel,
            });
            const fetch = vi.fn().mockResolvedValue(
                new Response(body, {
                    headers: {
                        "Content-Type": "text/event-stream; charset=utf-8",
                    },
                }),
            );
            vi.stubGlobal("fetch", fetch);
            const token = vi.fn().mockResolvedValue("stream-token");
            setTokenProvider(token);
            const events: StreamEvent[] = [];
            await consumeEvents(
                "/runs/one/events",
                new AbortController().signal,
                (event) => events.push(event),
            );
            expect(events).toEqual([
                { type: "progress", id: "12", data: "café 🚚\nsecond line" },
                { type: "progress", id: "12", data: "next" },
                { type: "message", id: "13", data: "last" },
            ]);
            expect(token).toHaveBeenCalledTimes(1);
            expect(fetch).toHaveBeenCalledWith(
                "/api/runs/one/events",
                expect.objectContaining({
                    headers: {
                        accept: "text/event-stream",
                        authorization: "Bearer stream-token",
                    },
                }),
            );
            expect(body.locked).toBe(false);
        },
    );

    it("aborts pending reads and releases the reader on cleanup", async () => {
        const cancel = vi.fn();
        const body = new ReadableStream<Uint8Array>({ cancel });
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(body, {
                    headers: { "Content-Type": "text/event-stream" },
                }),
            ),
        );
        const controller = new AbortController();
        const pending = consumeEvents(
            "/runs/one/events",
            controller.signal,
            vi.fn(),
        );
        await vi.waitFor(() => expect(body.locked).toBe(true));
        controller.abort();
        await pending;
        expect(cancel).toHaveBeenCalledTimes(1);
        expect(body.locked).toBe(false);
    });

    it.each([401, 403, 503])(
        "rejects unavailable streams (%s) once for polling fallback",
        async (status) => {
            const fetch = vi
                .fn()
                .mockResolvedValue(new Response("", { status }));
            vi.stubGlobal("fetch", fetch);
            await expect(
                consumeEvents(
                    "/runs/one/events",
                    new AbortController().signal,
                    vi.fn(),
                ),
            ).rejects.toThrow("stream unavailable");
            expect(fetch).toHaveBeenCalledTimes(1);
        },
    );
});
