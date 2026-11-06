import {
    InteractionRequiredAuthError,
    PublicClientApplication,
    type AccountInfo,
} from "@azure/msal-browser";
import { useEffect, useState, type ReactNode } from "react";
import {
    Button,
    MessageBar,
    Spinner,
    Title3,
} from "@fluentui/react-components";
import AccountHeader from "./AccountHeader";
import { setTokenProvider } from "./auth";
import { GRAPH_SCOPES } from "./useAccountProfile";

interface AuthConfig {
    enabled: boolean;
    tenant_id: string | null;
    client_id: string | null;
    scope: string | null;
}

interface Session {
    client: PublicClientApplication;
    scope: string;
    account: AccountInfo | null;
}

const signedOutKey = "routing.signed-out";

function wasSignedOut(): boolean {
    try {
        return localStorage.getItem(signedOutKey) === "true";
    } catch {
        return false;
    }
}

function rememberSignOut(signedOut: boolean): void {
    try {
        if (signedOut) localStorage.setItem(signedOutKey, "true");
        else localStorage.removeItem(signedOutKey);
    } catch {
        // Browser storage may be unavailable.
    }
}

function validateConfig(value: unknown): AuthConfig {
    if (!value || typeof value !== "object")
        throw new Error("Invalid authentication configuration.");
    const config = value as AuthConfig;
    if (typeof config.enabled !== "boolean")
        throw new Error("Invalid authentication configuration.");
    const uuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (
        config.enabled &&
        (typeof config.tenant_id !== "string" ||
            !uuid.test(config.tenant_id) ||
            typeof config.client_id !== "string" ||
            !uuid.test(config.client_id) ||
            typeof config.scope !== "string" ||
            !/^(api|https):\/\/\S+\/access_as_user$/.test(config.scope))
    )
        throw new Error("Incomplete authentication configuration.");
    return config;
}

export default function AuthGate({ children }: { children: ReactNode }) {
    const [attempt, setAttempt] = useState(0);
    const [loading, setLoading] = useState(true);
    const [disabled, setDisabled] = useState(false);
    const [session, setSession] = useState<Session | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        const controller = new AbortController();
        let client: PublicClientApplication | null = null;
        const handleSignOut = (event: StorageEvent) => {
            if (event.key !== signedOutKey || event.newValue !== "true") return;
            setTokenProvider(async () => {
                throw new Error("Sign in to continue.");
            });
            setSession((current) =>
                current ? { ...current, account: null } : current,
            );
            setError(null);
            setBusy(false);
        };
        window.addEventListener("storage", handleSignOut);
        const initialize = async () => {
            const response = await fetch("/api/auth/config", {
                signal: AbortSignal.any([
                    controller.signal,
                    AbortSignal.timeout(30000),
                ]),
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            if (!response.ok)
                throw new Error("Authentication discovery failed.");
            const config = validateConfig(await response.json());
            if (controller.signal.aborted) return;
            if (!config.enabled) {
                setTokenProvider(null);
                setDisabled(true);
                return;
            }
            client = new PublicClientApplication({
                auth: {
                    clientId: config.client_id!,
                    authority: `https://login.microsoftonline.com/${config.tenant_id}`,
                    redirectUri: `${window.location.origin}/`,
                    postLogoutRedirectUri: `${window.location.origin}/`,
                    navigateToLoginRequestUrl: false,
                },
                cache: { cacheLocation: "localStorage" },
            });
            await client.initialize();
            if (controller.signal.aborted) return;
            const result = await client.handleRedirectPromise();
            if (controller.signal.aborted) return;
            const scope = config.scope!;
            if (result?.account) rememberSignOut(false);
            const accounts = client.getAllAccounts();
            let account =
                result?.account ??
                (wasSignedOut()
                    ? null
                    : (client.getActiveAccount() ??
                      (accounts.length === 1 ? accounts[0] : null)));
            if (!account && !wasSignedOut() && accounts.length === 0) {
                try {
                    account = (await client.ssoSilent({ scopes: [scope] }))
                        .account;
                } catch {
                    // No Entra session, blocked cookies or tenant policy require explicit sign-in.
                }
            }
            if (controller.signal.aborted) return;
            if (wasSignedOut()) account = null;
            if (account) client.setActiveAccount(account);
            const authClient = client;
            setTokenProvider(async () => {
                if (!account) throw new Error("Sign in to continue.");
                try {
                    const token = await authClient.acquireTokenSilent({
                        account,
                        scopes: [scope],
                    });
                    return token.accessToken;
                } catch (cause) {
                    if (
                        cause instanceof InteractionRequiredAuthError &&
                        !controller.signal.aborted
                    ) {
                        setTokenProvider(async () => {
                            throw new Error("Sign in again to continue.");
                        });
                        setError(
                            "Your session needs attention. Sign in again to continue.",
                        );
                        setSession({
                            client: authClient,
                            scope,
                            account: null,
                        });
                    }
                    throw new Error(
                        "Unable to authorize the request. Sign in again or retry.",
                        { cause },
                    );
                }
            });
            setSession({ client, scope, account });
        };
        void initialize()
            .catch(() => {
                if (!controller.signal.aborted)
                    setError(
                        "Sign-in setup failed. Check your connection and retry.",
                    );
            })
            .finally(() => {
                if (!controller.signal.aborted) setLoading(false);
            });
        return () => {
            controller.abort();
            window.removeEventListener("storage", handleSignOut);
            setTokenProvider(async () => {
                throw new Error("Sign-in is required.");
            });
        };
    }, [attempt]);

    const login = async () => {
        if (!session || busy) return;
        setBusy(true);
        setError(null);
        try {
            await session.client.loginRedirect({
                scopes: [session.scope],
                extraScopesToConsent: [...GRAPH_SCOPES],
            });
        } catch {
            setError("Sign-in could not start. Please retry.");
            setBusy(false);
        }
    };

    const logout = async () => {
        if (!session || busy) return;
        setBusy(true);
        setError(null);
        const account = session.account;
        rememberSignOut(true);
        setSession({ ...session, account: null });
        setTokenProvider(async () => {
            throw new Error("Sign in to continue.");
        });
        try {
            localStorage.removeItem("routing.active");
        } catch {
            // Browser storage is optional.
        }
        try {
            await session.client.clearCache({ account: account ?? undefined });
            await session.client.logoutRedirect({ account });
        } catch {
            setError(
                "Sign-out could not finish. Retry sign-out to clear your Microsoft session.",
            );
            setBusy(false);
        }
    };

    if (loading)
        return (
            <>
                <AccountHeader />
                <main className="auth-gate" aria-busy="true">
                    <Spinner label="Loading sign-in configuration…" />
                </main>
            </>
        );
    if (disabled)
        return (
            <>
                <AccountHeader demo />
                {children}
            </>
        );
    if (session?.account)
        return (
            <>
                <AccountHeader
                    session={{
                        client: session.client,
                        account: session.account,
                    }}
                    onSignOut={() => void logout()}
                    busy={busy}
                />
                {children}
            </>
        );
    return (
        <>
            <AccountHeader />
            <main className="auth-gate">
                <Title3 as="h1">Sign in</Title3>
                <p>
                    Sign in with your organization account to open the shared
                    demo workspace. This browser reuses your Microsoft session
                    on return visits. Choose Stay signed in if Microsoft asks;
                    your organization may still require MFA or another sign-in.
                    Use Sign out on shared devices.
                </p>
                {error && (
                    <MessageBar intent="error" role="alert">
                        {error}
                    </MessageBar>
                )}
                <div className="auth-gate-actions">
                    {session ? (
                        <>
                            <Button
                                appearance="primary"
                                onClick={() => void login()}
                                disabled={busy}
                            >
                                Sign in
                            </Button>
                            <Button
                                onClick={() => void logout()}
                                disabled={busy}
                            >
                                Sign out
                            </Button>
                        </>
                    ) : (
                        <Button
                            onClick={() => {
                                setLoading(true);
                                setError(null);
                                setAttempt((value) => value + 1);
                            }}
                        >
                            Retry sign-in setup
                        </Button>
                    )}
                </div>
            </main>
        </>
    );
}
