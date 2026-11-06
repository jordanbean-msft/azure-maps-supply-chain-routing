import { StrictMode } from "react";
import { FluentProvider } from "@fluentui/react-components";
import { createRoot } from "react-dom/client";
import App from "./App";
import AuthGate from "./AuthGate";
import { routingTheme } from "./theme";

// MSAL's parent window processes silent redirect responses; the iframe must not start another sign-in.
if (window.self === window.top) {
    createRoot(document.getElementById("root")!).render(
        <StrictMode>
            <FluentProvider theme={routingTheme}>
                <AuthGate>
                    <App />
                </AuthGate>
            </FluentProvider>
        </StrictMode>,
    );
}
