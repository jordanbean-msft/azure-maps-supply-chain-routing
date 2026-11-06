import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { setTokenProvider } from "./auth";

afterEach(() => {
    cleanup();
    setTokenProvider(null);
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
});
