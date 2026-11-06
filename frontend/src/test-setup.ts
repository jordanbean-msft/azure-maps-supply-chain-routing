import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { setTokenProvider } from "./auth";

globalThis.ResizeObserver = class implements ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
};

afterEach(() => {
    cleanup();
    setTokenProvider(null);
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
});
