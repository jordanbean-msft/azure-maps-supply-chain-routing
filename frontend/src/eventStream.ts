import { apiFetch } from "./api";

export interface StreamEvent {
    type: string;
    data: string;
    id: string;
}

/** Consume one connection; the workspace polls if it closes instead of reconnecting. */
export async function consumeEvents(
    path: string,
    signal: AbortSignal,
    onEvent: (event: StreamEvent) => void,
): Promise<void> {
    const response = await apiFetch(path, {
        signal,
        headers: { Accept: "text/event-stream" },
        cache: "no-store",
    });
    if (
        !response.ok ||
        !response.headers
            .get("Content-Type")
            ?.startsWith("text/event-stream") ||
        !response.body
    )
        throw new Error("Progress stream unavailable.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let type = "";
    let data: string[] = [];
    let id = "";
    const line = (value: string) => {
        if (!value) {
            if (data.length && !signal.aborted)
                onEvent({ type: type || "message", data: data.join("\n"), id });
            type = "";
            data = [];
            return;
        }
        const colon = value.indexOf(":");
        const field = colon < 0 ? value : value.slice(0, colon);
        let content = colon < 0 ? "" : value.slice(colon + 1);
        if (content.startsWith(" ")) content = content.slice(1);
        if (field === "event") type = content;
        if (field === "data") data.push(content);
        if (field === "id" && !content.includes("\0")) id = content;
    };
    const abort = () => void reader.cancel().catch(() => {});
    signal.addEventListener("abort", abort, { once: true });
    try {
        signal.throwIfAborted();
        while (!signal.aborted) {
            const { value, done } = await reader.read();
            buffer += done
                ? decoder.decode()
                : decoder.decode(value, { stream: true });
            let start = 0;
            for (let index = 0; index < buffer.length; index++) {
                const char = buffer[index];
                if (char !== "\r" && char !== "\n") continue;
                // A trailing CR may be the first half of a split CRLF.
                if (char === "\r" && index === buffer.length - 1 && !done)
                    break;
                line(buffer.slice(start, index));
                if (char === "\r" && buffer[index + 1] === "\n") index++;
                start = index + 1;
            }
            buffer = buffer.slice(start);
            if (done) return;
        }
    } finally {
        signal.removeEventListener("abort", abort);
        await reader.cancel().catch(() => {});
        reader.releaseLock();
    }
}
