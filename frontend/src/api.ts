import type { ProblemDetails } from "./types";

export class ApiError extends Error {
    constructor(
        message: string,
        public readonly status: number,
    ) {
        super(message);
    }
}

export interface Resource<T> {
    data: T;
    etag: string | null;
}

export async function request<T>(
    path: string,
    options: RequestInit = {},
): Promise<Resource<T>> {
    const response = await fetch(`/api${path}`, {
        ...options,
        signal: options.signal
            ? AbortSignal.any([options.signal, AbortSignal.timeout(30000)])
            : AbortSignal.timeout(30000),
        headers: {
            Accept: "application/json",
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers,
        },
    });
    if (!response.ok) {
        let detail = `Request failed (${response.status}).`;
        try {
            const problem = (await response.json()) as Partial<ProblemDetails>;
            if (typeof problem.detail === "string") detail = problem.detail;
            else if (typeof problem.title === "string") detail = problem.title;
        } catch {
            // Proxies can return non-JSON errors.
        }
        if (response.status === 412)
            detail =
                "This scenario changed on the server. Your edits are preserved. Reload the server version before saving again.";
        throw new ApiError(detail, response.status);
    }
    return {
        data: (await response.json()) as T,
        etag: response.headers.get("ETag"),
    };
}

export function errorMessage(error: unknown): string {
    return error instanceof Error
        ? error.message
        : "The request could not be completed.";
}

export function scenarioPath(id: string): string {
    return `/scenarios/${encodeURIComponent(id)}`;
}
