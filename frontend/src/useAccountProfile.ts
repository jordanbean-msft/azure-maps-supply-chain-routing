import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { useEffect, useRef, useState } from "react";

export const GRAPH_SCOPES = ["https://graph.microsoft.com/User.Read"];

interface Profile {
    name: string;
    photo: string | undefined;
    needsConsent: boolean;
    loading: boolean;
}

function accountName(account: AccountInfo): string {
    const claims = account.idTokenClaims;
    const names = [claims?.given_name, claims?.family_name]
        .filter((name): name is string => typeof name === "string")
        .map((name) => name.trim())
        .filter(Boolean);
    const claimName =
        typeof claims?.name === "string" ? claims.name.trim() : "";
    return names.join(" ") || claimName || account.name?.trim() || "";
}

export function useAccountProfile(
    client: PublicClientApplication,
    account: AccountInfo,
) {
    const [profile, setProfile] = useState<Profile>({
        name: accountName(account),
        photo: undefined,
        needsConsent: false,
        loading: true,
    });
    const consent = useRef<() => Promise<void>>(async () => {});

    useEffect(() => {
        const controller = new AbortController();
        let photoUrl: string | undefined;
        const load = async (interactive: boolean) => {
            setProfile((current) => ({ ...current, loading: true }));
            try {
                const request = {
                    account,
                    scopes: [...GRAPH_SCOPES],
                    storeInCache: {
                        accessToken: false,
                        idToken: false,
                        refreshToken: false,
                    },
                };
                const token = interactive
                    ? await client.acquireTokenPopup(request)
                    : await client.acquireTokenSilent(request);
                if (controller.signal.aborted) return;
                const options = {
                    signal: controller.signal,
                    headers: { Authorization: `Bearer ${token.accessToken}` },
                    cache: "no-store" as const,
                };
                const results = await Promise.allSettled([
                    (async () => {
                        const response = await fetch(
                            "https://graph.microsoft.com/v1.0/me?$select=givenName,surname,displayName",
                            options,
                        );
                        if (!response.ok)
                            throw new Error("Profile unavailable");
                        const data: unknown = await response.json();
                        if (!data || typeof data !== "object") return;
                        const fields = data as Record<string, unknown>;
                        const name = [fields.givenName, fields.surname]
                            .filter(
                                (value): value is string =>
                                    typeof value === "string",
                            )
                            .map((value) => value.trim())
                            .filter(Boolean)
                            .join(" ");
                        const fallback =
                            typeof fields.displayName === "string"
                                ? fields.displayName.trim()
                                : "";
                        if (!controller.signal.aborted)
                            setProfile((current) => ({
                                ...current,
                                name: name || fallback || current.name,
                            }));
                    })(),
                    (async () => {
                        const response = await fetch(
                            "https://graph.microsoft.com/v1.0/me/photo/$value",
                            options,
                        );
                        if (response.status === 404) return;
                        if (!response.ok) throw new Error("Photo unavailable");
                        const blob = await response.blob();
                        if (!blob.type.startsWith("image/"))
                            throw new Error("Invalid profile photo");
                        if (controller.signal.aborted) return;
                        if (photoUrl) URL.revokeObjectURL(photoUrl);
                        photoUrl = URL.createObjectURL(blob);
                        setProfile((current) => ({
                            ...current,
                            photo: photoUrl,
                        }));
                    })(),
                ]);
                if (!controller.signal.aborted)
                    setProfile((current) => ({
                        ...current,
                        needsConsent: results.some(
                            (result) => result.status === "rejected",
                        ),
                        loading: false,
                    }));
            } catch {
                if (!controller.signal.aborted)
                    setProfile((current) => ({
                        ...current,
                        loading: false,
                        needsConsent: true,
                    }));
            }
        };
        consent.current = () => load(true);
        void load(false);
        return () => {
            controller.abort();
            if (photoUrl) URL.revokeObjectURL(photoUrl);
            consent.current = async () => {};
        };
    }, [client, account]);

    return { ...profile, loadPhoto: () => consent.current() };
}
