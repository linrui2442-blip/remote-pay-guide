import React, { useEffect, useState } from "react";
import { apiPost } from "../api";

export default function YouTubeOAuthCallback() {
  const [status, setStatus] = useState("正在连接 YouTube…");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const accountId = params.get("account_id");

    if (!code || !state) {
      setStatus("OAuth 回调缺少必要参数。");
      return;
    }

    const payload = {
      authorization_code: code,
      state,
    };
    if (accountId) payload.account_id = Number(accountId);

    apiPost("/oauth/youtube/exchange", payload)
      .then((result) => {
        if (result?.status === "connected") {
          setStatus("YouTube 已连接，发布与 Analytics 权限已经写入本地 OS。");
          setConnected(true);
        } else {
          setStatus(result?.detail || "YouTube 连接失败");
        }
      })
      .catch((error) => {
        setStatus(error.message || "YouTube 连接失败");
      });
  }, []);

  const returnToOS = () => {
    window.location.assign("/?view=accounts");
  };

  return (
    <main className="oauth-callback-shell">
      <section className="oauth-callback-card">
        <div className={`oauth-callback-icon ${connected ? "success" : ""}`}>
          {connected ? "✓" : "YT"}
        </div>
        <span className="eyebrow">YOUTUBE OAUTH</span>
        <h1>{connected ? "授权完成" : "正在完成授权"}</h1>
        <p>{status}</p>
        <button className="primary-button" onClick={returnToOS}>
          返回平台账号
        </button>
      </section>
    </main>
  );
}
