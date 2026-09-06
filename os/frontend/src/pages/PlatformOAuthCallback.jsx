import React, { useEffect, useMemo, useState } from "react";
import { exchangePlatformOAuth } from "../api";

function platformFromPath() {
  const match = window.location.pathname.match(/^\/oauth\/([^/]+)\/callback\/?$/i);
  return match ? decodeURIComponent(match[1]).toLowerCase() : "";
}

function platformLabel(platform) {
  if (!platform) return "平台";
  const known = {
    youtube: "YouTube",
    facebook: "Facebook",
    instagram: "Instagram",
    tiktok: "TikTok",
  };
  return known[platform] || platform.charAt(0).toUpperCase() + platform.slice(1);
}

export default function PlatformOAuthCallback({ platform: platformProp }) {
  const platform = useMemo(
    () => String(platformProp || platformFromPath() || "").toLowerCase(),
    [platformProp]
  );
  const label = platformLabel(platform);
  const [status, setStatus] = useState(`正在连接 ${label}…`);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!platform) {
      setStatus("OAuth 回调缺少平台标识。");
      return;
    }

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

    exchangePlatformOAuth(platform, payload)
      .then((result) => {
        if (result?.status === "connected") {
          setStatus(`${label} 已连接，授权凭证已经写入本地 OS。`);
          setConnected(true);
        } else {
          setStatus(result?.detail || `${label} 连接失败`);
        }
      })
      .catch((error) => {
        setStatus(error.message || `${label} 连接失败`);
      });
  }, [label, platform]);

  const returnToOS = () => {
    window.location.assign("/?view=accounts");
  };

  const mark = label.slice(0, 2).toUpperCase();

  return (
    <main className="oauth-callback-shell">
      <section className="oauth-callback-card">
        <div className={`oauth-callback-icon ${connected ? "success" : ""}`}>
          {connected ? "✓" : mark}
        </div>
        <span className="eyebrow">PLATFORM OAUTH</span>
        <h1>{connected ? "授权完成" : "正在完成授权"}</h1>
        <p>{status}</p>
        <button className="primary-button" onClick={returnToOS}>
          返回平台账号
        </button>
      </section>
    </main>
  );
}
