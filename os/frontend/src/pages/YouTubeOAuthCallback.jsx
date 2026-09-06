import React, { useEffect, useState } from "react";
import { apiPost } from "../api";

export default function YouTubeOAuthCallback() {
  const [status, setStatus] = useState("Connecting YouTube...");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const accountId = params.get("account_id");

    if (!code || !state) {
      setStatus("OAuth callback missing required parameters.");
      return;
    }

    const payload = {
      authorization_code: code,
      state,
    };
    // Legacy callback links may still include account_id. New flows resolve
    // the account securely from the server-side OAuth state record.
    if (accountId) payload.account_id = Number(accountId);

    apiPost("/oauth/youtube/exchange", payload)
      .then((result) => {
        if (result?.status === "connected") {
          const profile = result.scope_profile ? ` (${result.scope_profile})` : "";
          setStatus(`YouTube connected${profile}. Account ${result.account_id}.`);
          setConnected(true);
        } else {
          setStatus(result?.detail || "YouTube connection failed");
        }
      })
      .catch((error) => {
        setStatus(error.message || "YouTube connection failed");
      });
  }, []);

  const returnToOS = () => {
    window.location.assign("/");
  };

  return (
    <main>
      <h1>YouTube OAuth</h1>
      <p>{status}</p>
      <button onClick={returnToOS}>
        {connected ? "Return to Remote Pay Guide OS" : "Back to Remote Pay Guide OS"}
      </button>
    </main>
  );
}
