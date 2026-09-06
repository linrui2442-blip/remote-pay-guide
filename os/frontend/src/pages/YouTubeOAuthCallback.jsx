import React, { useEffect, useState } from "react";
import { apiPost } from "../api";

export default function YouTubeOAuthCallback() {
  const [status, setStatus] = useState("Connecting YouTube...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    const accountId = params.get("account_id") || "";

    if (!code || !state || !accountId) {
      setStatus("OAuth callback missing required parameters.");
      return;
    }

    apiPost("/oauth/youtube/exchange", {
      account_id: Number(accountId),
      authorization_code: code,
      state,
    })
      .then((result) => {
        if (result?.status === "connected") {
          setStatus("YouTube connected");
        } else {
          setStatus(result?.detail || "YouTube connection failed");
        }
      })
      .catch((error) => {
        setStatus(error.message || "YouTube connection failed");
      });
  }, []);

  return (
    <main>
      <h1>YouTube OAuth</h1>
      <p>{status}</p>
    </main>
  );
}
