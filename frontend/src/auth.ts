export type TokenProvider = () => Promise<string>;

let tokenProvider: TokenProvider | null = null;

export function setTokenProvider(provider: TokenProvider | null): void {
    tokenProvider = provider;
}

export async function authorizationHeaders(): Promise<Record<string, string>> {
    const provider = tokenProvider;
    if (!provider) return {};
    const token = await provider();
    if (provider !== tokenProvider)
        throw new Error("The sign-in session changed. Please try again.");
    return { Authorization: `Bearer ${token}` };
}
