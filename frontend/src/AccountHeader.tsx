import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { Avatar, Button, Text } from "@fluentui/react-components";
import { useAccountProfile } from "./useAccountProfile";
import "./AccountHeader.css";

interface AccountHeaderProps {
    session?: { client: PublicClientApplication; account: AccountInfo };
    demo?: boolean;
    busy?: boolean;
    onSignOut?: () => void;
}

function Profile({
    session,
    busy,
    onSignOut,
}: Required<Pick<AccountHeaderProps, "session">> &
    Pick<AccountHeaderProps, "busy" | "onSignOut">) {
    const profile = useAccountProfile(session.client, session.account);
    return (
        <div className="app-header-account">
            <Avatar
                name={profile.name || undefined}
                image={profile.photo ? { src: profile.photo } : undefined}
                aria-label="Profile"
                size={32}
            />
            <Text className="app-header-greeting">
                {profile.name ? `Howdy ${profile.name}!` : "Howdy!"}
            </Text>
            {profile.needsConsent && (
                <Button
                    appearance="subtle"
                    size="small"
                    disabled={profile.loading || busy}
                    onClick={() => void profile.loadPhoto()}
                >
                    Load profile photo
                </Button>
            )}
            <Button
                appearance="subtle"
                size="small"
                disabled={busy}
                onClick={onSignOut}
            >
                Sign out
            </Button>
        </div>
    );
}

export default function AccountHeader({
    session,
    demo,
    busy,
    onSignOut,
}: AccountHeaderProps) {
    return (
        <header className="app-header" aria-label="Account">
            <Text className="app-header-title">Supply chain routing</Text>
            {session ? (
                <Profile
                    key={session.account.homeAccountId}
                    session={session}
                    busy={busy}
                    onSignOut={onSignOut}
                />
            ) : demo ? (
                <Text>Demo workspace</Text>
            ) : null}
        </header>
    );
}
