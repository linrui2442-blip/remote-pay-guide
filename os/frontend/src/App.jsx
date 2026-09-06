import React, { useEffect, useMemo, useState } from "react";
import {
  apiGet,
  beginYouTubeOAuth,
  collectAccountAnalytics,
  collectPublishTaskAnalytics,
  createAccount,
  createProductionTask,
  getAccounts,
  getAnalyticsCollectorStatus,
  getNetworkProxySettings,
  getProductionProviders,
  getProductionStatus,
  getProductionTasks,
  getPublishTasks,
  getYouTubeOAuthStatus,
  runProductionTask,
  saveNetworkProxySettings,
  syncAccount,
} from "./api";
import YouTubeOAuthCallback from "./pages/YouTubeOAuthCallback.jsx";
import DataCenter from "./pages/DataCenter.jsx";

const NAV_ITEMS = [
  ["overview", "总览", "⌂"],
  ["accounts", "平台账号", "◎"],
  ["production", "生产中心", "▶"],
  ["publishing", "发布中心", "↑"],
  ["analytics", "数据中心", "▥"],
  ["platforms", "平台能力", "◇"],
  ["settings", "系统设置", "⚙"],
];

const PLATFORM_LABELS = {
  youtube: "YouTube",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

const PLATFORM_CONNECTORS = { youtube: "google_oauth" };

function platformLabel(name) {
  const key = String(name || "").toLowerCase();
  if (PLATFORM_LABELS[key]) return PLATFORM_LABELS[key];
  return key ? key.charAt(0).toUpperCase() + key.slice(1) : "Unknown";
}

function platformMark(name) {
  const label = platformLabel(name);
  if (label === "YouTube") return "YT";
  if (label === "Facebook") return "FB";
  if (label === "Instagram") return "IG";
  if (label === "TikTok") return "TK";
  return label.slice(0, 2).toUpperCase();
}

function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">·</div>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

function JsonDetails({ title = "查看原始数据", data }) {
  return (
    <details className="json-details">
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function PlatformPicker({ platforms, onClose, onSelect, connectingPlatform }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className="section-kicker">ADD PLATFORM</span>
            <h2>选择平台</h2>
            <p>平台列表来自当前运行时 Registry；以后新增 Adapter 会自动出现在这里。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="platform-picker-grid">
          {platforms.map((item) => {
            const name = String(item.platform || "").toLowerCase();
            const capability = item.capabilities || {};
            const connector = PLATFORM_CONNECTORS[name];
            const connecting = connectingPlatform === name;
            return (
              <button
                key={name}
                className={`platform-choice ${connector ? "connectable" : ""}`}
                onClick={() => connector && onSelect(name)}
                disabled={!connector || connecting}
              >
                <span className="platform-choice-logo">{platformMark(name)}</span>
                <span className="platform-choice-body">
                  <strong>{platformLabel(name)}</strong>
                  <small>
                    {connector
                      ? "点击后直接进入授权"
                      : capability.publish_supported
                        ? "发布适配器已存在 · 账号授权待接入"
                        : "当前未启用连接"}
                  </small>
                </span>
                <span className="platform-choice-state">
                  {connecting ? "正在打开…" : connector ? "连接" : "待接入"}
                </span>
              </button>
            );
          })}
        </div>
        {platforms.length === 0 && (
          <EmptyState title="正在读取平台 Registry" description="稍后会显示当前可用平台。" />
        )}
      </section>
    </div>
  );
}

function App() {
  if (window.location.pathname === "/oauth/youtube/callback") {
    return <YouTubeOAuthCallback />;
  }

  const viewFromUrl = new URLSearchParams(window.location.search).get("view");
  const [activeView, setActiveView] = useState(
    NAV_ITEMS.some(([key]) => key === viewFromUrl) ? viewFromUrl : "overview"
  );
  const [system, setSystem] = useState(null);
  const [assets, setAssets] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [analyticsMessage, setAnalyticsMessage] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [accountReadiness, setAccountReadiness] = useState({});
  const [youtubeOAuthStatus, setYouTubeOAuthStatus] = useState(null);
  const [oauthMessage, setOAuthMessage] = useState("");
  const [productionStatus, setProductionStatus] = useState(null);
  const [productionTasks, setProductionTasks] = useState([]);
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState("github");
  const [showPlatformPicker, setShowPlatformPicker] = useState(false);
  const [connectingPlatform, setConnectingPlatform] = useState("");
  const [syncingAccountId, setSyncingAccountId] = useState(null);
  const [collectingAnalyticsAccountId, setCollectingAnalyticsAccountId] = useState(null);
  const [proxySettings, setProxySettings] = useState({ mode: "system", proxy_url: "" });
  const [proxyMode, setProxyMode] = useState("system");
  const [proxyUrl, setProxyUrl] = useState("");
  const [proxyMessage, setProxyMessage] = useState("");
  const [savingProxy, setSavingProxy] = useState(false);

  const refreshProduction = () => {
    getProductionStatus().then(setProductionStatus).catch(() => {});
    getProductionTasks().then(setProductionTasks).catch(() => {});
    getProductionProviders().then(setProviders).catch(() => {});
  };

  const refreshAnalytics = () => {
    apiGet("/analytics/metrics/current").then(setMetrics).catch(() => {});
  };

  const refreshPublishTasks = () => {
    getPublishTasks().then(setTasks).catch(() => {});
  };

  const refreshAccounts = () => {
    getAccounts()
      .then(async (records) => {
        setAccounts(records);
        const youtubeAccounts = records.filter(
          (account) => String(account.platform || "").toLowerCase() === "youtube"
        );
        const statuses = await Promise.all(
          youtubeAccounts.map(async (account) => {
            try {
              const status = await getAnalyticsCollectorStatus("youtube", account.id);
              return [account.id, status];
            } catch (error) {
              return [account.id, { ready: false, reason: error.message }];
            }
          })
        );
        setAccountReadiness(Object.fromEntries(statuses));
      })
      .catch((error) => setOAuthMessage(error.message));
  };

  const refreshProxy = () => {
    getNetworkProxySettings()
      .then((settings) => {
        setProxySettings(settings);
        setProxyMode(settings.mode || "system");
        setProxyUrl(settings.proxy_url || "");
      })
      .catch((error) => setProxyMessage(error.message));
  };

  useEffect(() => {
    apiGet("/").then(setSystem).catch(() => setSystem({ status: "offline" }));
    apiGet("/assets").then(setAssets).catch(() => {});
    refreshPublishTasks();
    apiGet("/publish/platforms").then(setPlatforms).catch(() => {});
    refreshAnalytics();
    getYouTubeOAuthStatus()
      .then(setYouTubeOAuthStatus)
      .catch((error) => setYouTubeOAuthStatus({ configured: false, reason: error.message }));
    refreshAccounts();
    refreshProduction();
    refreshProxy();
  }, []);

  const createTask = () => {
    createProductionTask({
      task_type: provider === "ai_gateway" ? "video_generation" : "video_render",
      provider,
      workflow: "render.yml",
      branch: "main",
    }).then(refreshProduction);
  };

  const runTask = (id) => runProductionTask(id).then(refreshProduction);

  const connectYouTube = async (accountId) => {
    if (youtubeOAuthStatus && youtubeOAuthStatus.configured === false) {
      const missing = (youtubeOAuthStatus.missing_configuration || []).join(", ");
      throw new Error(
        missing ? `YouTube OAuth 配置不完整：${missing}` : "YouTube OAuth 配置不完整。"
      );
    }
    const result = await beginYouTubeOAuth(accountId, "full");
    if (!result?.authorization_url) throw new Error("未收到 YouTube 授权地址");
    window.location.assign(result.authorization_url);
  };

  const addPlatform = async (platformName) => {
    const platform = String(platformName || "").toLowerCase();
    const connector = PLATFORM_CONNECTORS[platform];
    if (!connector) {
      setOAuthMessage(`${platformLabel(platform)} 已有平台适配器，但账号授权连接器尚未接入。`);
      setShowPlatformPicker(false);
      return;
    }

    try {
      setConnectingPlatform(platform);
      setOAuthMessage(`正在创建 ${platformLabel(platform)} 账号连接并打开授权页面…`);
      const account = await createAccount({
        platform,
        account_name: `${platformLabel(platform)} Account`,
        status: "inactive",
      });
      setShowPlatformPicker(false);
      await connectYouTube(account.id);
    } catch (error) {
      setConnectingPlatform("");
      setOAuthMessage(error.message);
      refreshAccounts();
    }
  };

  const reconnectAccount = (account) => {
    const platform = String(account.platform || "").toLowerCase();
    if (platform === "youtube") {
      setOAuthMessage("正在打开 Google 授权页面…");
      connectYouTube(account.id).catch((error) => setOAuthMessage(error.message));
    }
  };

  const syncPlatformAccount = async (account) => {
    try {
      setSyncingAccountId(account.id);
      setOAuthMessage(`正在通过 ${platformLabel(account.platform)} 官方 API 同步最新 10 条内容…`);
      const result = await syncAccount(account.id, 10);
      setOAuthMessage(
        `同步完成：发现 ${result.found ?? 0} 个视频，新导入 ${result.imported ?? 0} 个，已存在 ${result.already_present ?? 0} 个。当前主动观察窗口：最新 10 条。`
      );
      apiGet("/assets").then(setAssets).catch(() => {});
      refreshPublishTasks();
    } catch (error) {
      setOAuthMessage(error.message);
    } finally {
      setSyncingAccountId(null);
    }
  };

  const syncAccountAnalytics = async (account) => {
    const platform = String(account.platform || "").toLowerCase();
    try {
      setCollectingAnalyticsAccountId(account.id);
      setOAuthMessage(`正在通过 ${platformLabel(platform)} 官方 Analytics API 同步 ACTIVE 数据…`);
      const result = await collectAccountAnalytics(account.id, platform);
      if ((result.failed ?? 0) > 0) {
        const firstError = result.failures?.[0]?.error;
        setOAuthMessage(
          `数据同步完成：成功 ${result.collected ?? 0} 个，失败 ${result.failed ?? 0} 个${firstError ? `。首个错误：${firstError}` : ""}`
        );
      } else {
        setOAuthMessage(
          `数据同步完成：已更新 ${result.collected ?? 0} 个 ACTIVE 视频的 Analytics 数据。旧内容不会被删除。`
        );
      }
      refreshAnalytics();
    } catch (error) {
      setOAuthMessage(error.message);
    } finally {
      setCollectingAnalyticsAccountId(null);
    }
  };

  const saveProxy = async () => {
    try {
      setSavingProxy(true);
      setProxyMessage("正在应用代理配置…");
      const result = await saveNetworkProxySettings({
        mode: proxyMode,
        proxy_url: proxyMode === "manual" ? proxyUrl.trim() : null,
      });
      setProxySettings(result);
      setProxyUrl(result.proxy_url || proxyUrl);
      setProxyMessage(
        proxyMode === "manual"
          ? "代理已保存并立即应用。以后更换代理，只需要回来修改这里。"
          : proxyMode === "disabled"
            ? "已关闭 OS 后端代理。"
            : "已切换为跟随系统代理。"
      );
    } catch (error) {
      setProxyMessage(error.message);
    } finally {
      setSavingProxy(false);
    }
  };

  const collectTaskAnalytics = (task) => {
    setAnalyticsMessage(`正在采集发布任务 #${task.id} 的 YouTube 数据…`);
    collectPublishTaskAnalytics(task.id)
      .then((result) => {
        setAnalyticsMessage(`采集完成：${result.video_id || task.platform_video_id}，${result.views ?? 0} 次观看。`);
        refreshAnalytics();
      })
      .catch((error) => setAnalyticsMessage(error.message));
  };

  const canCollectTask = (task) =>
    String(task.platform || "").toLowerCase() === "youtube" &&
    String(task.status || "").toLowerCase() === "published" &&
    Boolean(task.platform_video_id) &&
    task.account_id != null;

  const publishedCount = tasks.filter(
    (task) => String(task.status || "").toLowerCase() === "published"
  ).length;
  const readyAccounts = accounts.filter((account) => accountReadiness[account.id]?.ready === true).length;
  const totalViews = useMemo(
    () => metrics.reduce((sum, item) => sum + Number(item.views || 0), 0),
    [metrics]
  );
  const totalClicks = useMemo(
    () => metrics.reduce((sum, item) => sum + Number(item.clicks || 0), 0),
    [metrics]
  );

  const renderOverview = () => (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">CONTROL CENTER</span>
          <h1>Remote Pay Guide OS</h1>
          <p>内容生产、发布、流量和转化数据统一控制台。</p>
        </div>
        <Badge tone={system?.status === "running" ? "success" : "danger"}>
          <span className="status-dot" /> {system?.status === "running" ? "系统运行中" : "系统离线"}
        </Badge>
      </div>

      <div className="stats-grid">
        <StatCard label="视频资产" value={assets.length} hint="已登记到资产层" />
        <StatCard label="发布任务" value={publishedCount} hint={`共 ${tasks.length} 个任务`} />
        <StatCard label="可用账号" value={readyAccounts} hint={`共 ${accounts.length} 个平台账号`} />
        <StatCard label="当前观看" value={totalViews.toLocaleString()} hint={`${totalClicks.toLocaleString()} 次点击`} />
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="panel-header"><div><span className="section-kicker">BUSINESS LOOP</span><h2>增长闭环</h2></div></div>
          <div className="flow-row">
            {["内容", "流量", "用户意图", "Binance 转化", "AI Intelligence", "下一轮生产"].map((item, index, array) => (
              <React.Fragment key={item}>
                <div className="flow-node">{item}</div>
                {index < array.length - 1 && <span className="flow-arrow">→</span>}
              </React.Fragment>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header"><div><span className="section-kicker">ACCOUNTS</span><h2>平台连接</h2></div><button className="text-button" onClick={() => setActiveView("accounts")}>管理账号</button></div>
          <div className="status-list">
            <div><span>平台 Registry</span><strong>{platforms.length}</strong></div>
            <div><span>YouTube OAuth</span><Badge tone={youtubeOAuthStatus?.configured ? "success" : "warning"}>{youtubeOAuthStatus?.configured ? "已配置" : "待配置"}</Badge></div>
            <div><span>可用账号</span><strong>{readyAccounts}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header"><div><span className="section-kicker">PRODUCTION</span><h2>生产运行时</h2></div><button className="text-button" onClick={() => setActiveView("production")}>打开生产中心</button></div>
          <div className="provider-pills"><Badge tone="neutral">GitHub Actions</Badge><Badge tone="info">AI Gateway · Remote</Badge></div>
          <p className="muted">现有 GitHub 生产线保持不变，AI 视频生产通过远程 Gateway 调用外部服务。</p>
        </section>
      </div>
    </>
  );

  const renderAccounts = () => (
    <>
      <div className="page-heading compact">
        <div><span className="eyebrow">ACCOUNTS</span><h1>平台账号</h1><p>选择平台并授权，然后通过官方 API 同步已发布内容和 Analytics 数据。</p></div>
        <button className="primary-button add-platform-button" onClick={() => setShowPlatformPicker(true)}>+ 添加平台账号</button>
      </div>

      {oauthMessage && <div className="notice notice-page">{oauthMessage}</div>}

      <div className="cards-list">
        {accounts.length === 0 ? (
          <EmptyState title="还没有平台账号" description="点击“添加平台账号”，从当前 Platform Registry 选择要连接的平台。" />
        ) : accounts.map((account) => {
          const platform = String(account.platform || "").toLowerCase();
          const readiness = accountReadiness[account.id];
          const connectable = Boolean(PLATFORM_CONNECTORS[platform]);
          const connected = platform === "youtube" ? readiness?.ready : account.status === "connected";
          const syncing = syncingAccountId === account.id;
          const collectingAnalytics = collectingAnalyticsAccountId === account.id;
          return (
            <section className="account-card" key={account.id}>
              <div className="account-avatar">{platformMark(platform)}</div>
              <div className="account-main">
                <div className="account-title-row">
                  <strong>{platformLabel(platform)}</strong>
                  <Badge tone={connected ? "success" : "warning"}>{connected ? "已连接" : connectable ? "需要授权" : "连接器待接入"}</Badge>
                </div>
                <span className="muted">{account.account_name} · Account #{account.id}</span>
                {readiness?.reason && !readiness.ready && <span className="small-warning">{readiness.reason}</span>}
              </div>
              <div className="account-actions">
                {platform === "youtube" && connected && (
                  <>
                    <button className="secondary-button" onClick={() => syncPlatformAccount(account)} disabled={syncing || collectingAnalytics}>
                      {syncing ? "同步中…" : "同步内容"}
                    </button>
                    <button className="secondary-button" onClick={() => syncAccountAnalytics(account)} disabled={collectingAnalytics || syncing || readiness?.ready !== true}>
                      {collectingAnalytics ? "同步数据中…" : "同步数据"}
                    </button>
                  </>
                )}
                {connectable ? (
                  <button className="primary-button" onClick={() => reconnectAccount(account)} disabled={platform === "youtube" && youtubeOAuthStatus?.configured === false}>
                    {connected ? "重新授权" : `连接 ${platformLabel(platform)}`}
                  </button>
                ) : (
                  <button className="secondary-button" disabled>授权待接入</button>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <section className="panel account-platform-summary">
        <div className="panel-header"><div><span className="section-kicker">REGISTRY</span><h2>可选平台</h2></div><span className="muted">{platforms.length} 个运行时平台</span></div>
        <div className="provider-pills">
          {platforms.map((item) => (
            <Badge key={item.platform} tone={PLATFORM_CONNECTORS[String(item.platform).toLowerCase()] ? "success" : "neutral"}>
              {platformLabel(item.platform)} · {PLATFORM_CONNECTORS[String(item.platform).toLowerCase()] ? "可连接" : "Adapter Ready"}
            </Badge>
          ))}
        </div>
      </section>
      <JsonDetails title="YouTube OAuth 技术状态" data={youtubeOAuthStatus || { status: "checking" }} />
    </>
  );

  const renderProduction = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PRODUCTION</span><h1>生产中心</h1><p>统一调度 GitHub 生产线与 AI Gateway 远程生产线。</p></div></div>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">NEW TASK</span><h2>创建生产任务</h2></div><Badge tone="success">{productionStatus?.status || "ready"}</Badge></div>
        <div className="form-row"><select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="github">GitHub Actions</option><option value="ai_gateway">AI Gateway（远程）</option></select><button className="primary-button" onClick={createTask}>创建任务</button></div>
      </section>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>生产任务</h2></div><span className="muted">{productionTasks.length} 条</span></div>
        {productionTasks.length === 0 ? <EmptyState title="暂无生产任务" description="创建任务后会显示在这里。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>Provider</th><th>状态</th><th></th></tr></thead><tbody>{productionTasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td>{task.task_type || "—"}</td><td>{task.provider || "—"}</td><td><Badge tone={task.status === "completed" ? "success" : "neutral"}>{task.status || "created"}</Badge></td><td className="table-action"><button className="secondary-button" onClick={() => runTask(task.id)}>运行</button></td></tr>)}</tbody></table></div>
        )}
      </section>
      <JsonDetails title="Provider 技术信息" data={providers} />
    </>
  );

  const renderPublishing = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PUBLISHING</span><h1>发布中心</h1><p>查看各平台发布状态，并从已发布视频直接采集数据。</p></div></div>
      {analyticsMessage && <div className="notice">{analyticsMessage}</div>}
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>发布任务</h2></div><span className="muted">{tasks.length} 条</span></div>
        {tasks.length === 0 ? <EmptyState title="暂无本地发布任务" description="现有 legacy/Postiz 发布记录尚未导入 OS Publish Center。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>平台</th><th>视频</th><th>状态</th><th></th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td>{platformLabel(task.platform)}</td><td>{task.platform_video_id || task.video_id || "—"}</td><td><Badge tone={task.status === "published" ? "success" : task.status === "failed" ? "danger" : "neutral"}>{task.status}</Badge></td><td className="table-action">{canCollectTask(task) && <button className="secondary-button" onClick={() => collectTaskAnalytics(task)} disabled={accountReadiness[task.account_id]?.ready !== true}>采集 Analytics</button>}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  );

  const renderAnalytics = () => <DataCenter />;

  const renderPlatforms = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PLATFORMS</span><h1>平台能力</h1><p>当前 Adapter 与能力状态。未来新增平台无需改核心发布逻辑。</p></div></div>
      <div className="platform-grid">
        {platforms.map((item) => {
          const capability = item.capabilities || {};
          const name = String(item.platform || "").toLowerCase();
          return <section className="platform-card" key={item.platform}>
            <div className="platform-card-header"><div className="platform-logo">{platformMark(name)}</div><div><strong>{platformLabel(name)}</strong><span>{item.adapter}</span></div><Badge tone="success">ready</Badge></div>
            <div className="capability-row"><span>发布</span><Badge tone={capability.publish_supported ? "success" : "neutral"}>{capability.publish_supported ? "支持" : "未启用"}</Badge></div>
            <div className="capability-row"><span>Analytics</span><Badge tone={capability.analytics_supported ? "success" : "neutral"}>{capability.analytics_supported ? "支持" : "未启用"}</Badge></div>
            <div className="capability-row"><span>账号连接</span><Badge tone={PLATFORM_CONNECTORS[name] ? "success" : "neutral"}>{PLATFORM_CONNECTORS[name] ? "已接入" : "待接入"}</Badge></div>
            <div className="metric-tags">{(capability.metric_types || []).map((metric) => <span key={metric}>{metric}</span>)}</div>
          </section>;
        })}
      </div>
    </>
  );

  const renderSettings = () => (
    <>
      <div className="page-heading compact">
        <div><span className="eyebrow">SETTINGS</span><h1>系统设置</h1><p>配置 Remote Pay Guide OS 后端访问外部平台时使用的网络代理。</p></div>
      </div>

      <section className="panel settings-panel">
        <div className="panel-header">
          <div><span className="section-kicker">NETWORK</span><h2>代理配置</h2></div>
          <Badge tone={proxySettings.runtime_configured ? "success" : "neutral"}>{proxySettings.runtime_configured ? "代理已启用" : "当前未使用代理"}</Badge>
        </div>

        <div className="settings-form">
          <label className="setting-field">
            <span>代理模式</span>
            <select value={proxyMode} onChange={(event) => setProxyMode(event.target.value)}>
              <option value="manual">手动配置</option>
              <option value="system">跟随系统代理</option>
              <option value="disabled">不使用代理</option>
            </select>
          </label>

          {proxyMode === "manual" && (
            <label className="setting-field">
              <span>代理地址</span>
              <input
                value={proxyUrl}
                onChange={(event) => setProxyUrl(event.target.value)}
                placeholder="例如：http://127.0.0.1:7890"
              />
              <small>以后 VPN 或代理软件更换端口，直接修改这里即可，不需要改代码。</small>
            </label>
          )}

          <div className="settings-actions">
            <button className="primary-button" onClick={saveProxy} disabled={savingProxy || (proxyMode === "manual" && !proxyUrl.trim())}>
              {savingProxy ? "保存中…" : "保存并立即应用"}
            </button>
          </div>
        </div>

        {proxyMessage && <div className="notice">{proxyMessage}</div>}

        <div className="settings-status">
          <div><span>保存模式</span><strong>{proxySettings.mode || "system"}</strong></div>
          <div><span>当前代理</span><strong>{proxySettings.proxy_url || proxySettings.effective_proxy || "未配置"}</strong></div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">NOTE</span><h2>使用方式</h2></div></div>
        <p className="muted">这里的代理只用于 OS 后端访问 Google、YouTube 以及未来接入的平台 API，不会改变你整个 Windows 的代理设置。保存后立即生效；下次启动 OS 会继续使用这里保存的配置。</p>
      </section>
    </>
  );

  const views = {
    overview: renderOverview,
    accounts: renderAccounts,
    production: renderProduction,
    publishing: renderPublishing,
    analytics: renderAnalytics,
    platforms: renderPlatforms,
    settings: renderSettings,
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block"><div className="brand-mark">R</div><div><strong>Remote Pay</strong><span>Guide OS</span></div></div>
        <nav>
          {NAV_ITEMS.map(([key, label, icon]) => (
            <button key={key} className={activeView === key ? "nav-item active" : "nav-item"} onClick={() => setActiveView(key)}><span className="nav-icon">{icon}</span>{label}</button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className={system?.status === "running" ? "health-dot online" : "health-dot"} /><div><strong>{system?.status === "running" ? "Local OS Online" : "Local OS Offline"}</strong><span>localhost:8000</span></div></div>
      </aside>
      <main className="content-area">{views[activeView]()}</main>
      {showPlatformPicker && (
        <PlatformPicker platforms={platforms} onClose={() => setShowPlatformPicker(false)} onSelect={addPlatform} connectingPlatform={connectingPlatform} />
      )}
    </div>
  );
}

export default App;
